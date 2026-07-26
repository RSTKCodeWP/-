/**
 * Tests for `useDroneCanNodeParams`. Covers:
 *   - index-walk on refresh, terminates on empty-name response
 *   - setLocal marks an entry dirty
 *   - saveAllDirty flushes dirty entries through paramSet and clears the flag
 *   - eraseToDefaults and restartNode forward to the client
 */

import { describe, it, expect, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

import {
  PARAM_OPCODE_ERASE,
  useDroneCanNodeParams,
  type DroneCanClient,
  type ParamValue,
} from "@/hooks/use-dronecan-node-params";
import { ValueTag } from "@/lib/dronecan/dsdl/param-getset";

type RawEntry = {
  name: string;
  value: ParamValue;
  default_value: ParamValue;
  min_value: ParamValue;
  max_value: ParamValue;
};

const EMPTY: ParamValue = { tag: ValueTag.Empty };

function makeClient(): {
  client: DroneCanClient;
  paramGet: ReturnType<typeof vi.fn>;
  paramSet: ReturnType<typeof vi.fn>;
  paramExecuteOpcode: ReturnType<typeof vi.fn>;
  restart: ReturnType<typeof vi.fn>;
} {
  // Index 0 → "P_ONE", 1 → "P_TWO", 2 → "P_THREE", 3 → empty (end of walk).
  const entries: RawEntry[] = [
    {
      name: "P_ONE",
      value: { tag: ValueTag.Real, value: 1.0 },
      default_value: EMPTY,
      min_value: EMPTY,
      max_value: EMPTY,
    },
    {
      name: "P_TWO",
      value: { tag: ValueTag.Integer, value: BigInt(42) },
      default_value: EMPTY,
      min_value: EMPTY,
      max_value: EMPTY,
    },
    {
      name: "P_THREE",
      value: { tag: ValueTag.Boolean, value: true },
      default_value: EMPTY,
      min_value: EMPTY,
      max_value: EMPTY,
    },
  ];
  const paramGet = vi.fn(async (_nodeId: number, index: number) => {
    if (index < entries.length) return entries[index];
    return {
      name: "",
      value: EMPTY,
      default_value: EMPTY,
      min_value: EMPTY,
      max_value: EMPTY,
    };
  });
  // A successful paramSet on the real client echoes the name + new value
  // back. Use that shape so the hook's success-detection logic exercises
  // the real contract.
  const paramSet = vi.fn(
    async (_nodeId: number, name: string, value: ParamValue) => ({
      name,
      value,
      default_value: EMPTY,
      min_value: EMPTY,
      max_value: EMPTY,
    }),
  );
  const paramExecuteOpcode = vi.fn(async () => ({ argument: BigInt(0), ok: true }));
  const restart = vi.fn(async () => ({ ok: true }));
  const client: DroneCanClient = {
    paramGet,
    paramSet,
    paramExecuteOpcode,
    restart,
  };
  return { client, paramGet, paramSet, paramExecuteOpcode, restart };
}

describe("useDroneCanNodeParams", () => {
  it("walks the param index and stops on empty name", async () => {
    const { client, paramGet } = makeClient();
    const { result } = renderHook(() => useDroneCanNodeParams(client, 10));

    await act(async () => {
      await result.current.refresh();
    });

    await waitFor(() => expect(result.current.params.size).toBe(3));
    expect(paramGet).toHaveBeenCalledTimes(4); // 0, 1, 2, then 3 returns empty
    expect(result.current.params.get("P_ONE")?.value).toEqual({
      tag: ValueTag.Real,
      value: 1.0,
    });
    expect(result.current.params.get("P_TWO")?.value).toEqual({
      tag: ValueTag.Integer,
      value: BigInt(42),
    });
    expect(result.current.error).toBeNull();
    expect(result.current.dirty.size).toBe(0);
  });

  it("setLocal marks an entry dirty; saveAllDirty flushes via paramSet", async () => {
    const { client, paramSet } = makeClient();
    const { result } = renderHook(() => useDroneCanNodeParams(client, 10));

    await act(async () => {
      await result.current.refresh();
    });

    act(() => {
      result.current.setLocal("P_ONE", { tag: ValueTag.Real, value: 2.5 });
    });

    expect(result.current.dirty.has("P_ONE")).toBe(true);
    expect(result.current.params.get("P_ONE")?.dirty).toBe(true);
    expect(result.current.params.get("P_ONE")?.value).toEqual({
      tag: ValueTag.Real,
      value: 2.5,
    });

    let saveResult: { saved: number; failed: number } = {
      saved: 0,
      failed: 0,
    };
    await act(async () => {
      saveResult = await result.current.saveAllDirty();
    });

    expect(saveResult).toEqual({ saved: 1, failed: 0 });
    expect(paramSet).toHaveBeenCalledTimes(1);
    expect(paramSet).toHaveBeenCalledWith(10, "P_ONE", {
      tag: ValueTag.Real,
      value: 2.5,
    });
    await waitFor(() => expect(result.current.dirty.size).toBe(0));
    expect(result.current.params.get("P_ONE")?.dirty).toBe(false);
  });

  it("saveAllDirty counts failures when paramSet echoes Empty (rejected write)", async () => {
    const { client, paramSet } = makeClient();
    // Rejected write — node echoes Empty-tagged value with empty name.
    paramSet.mockResolvedValueOnce({
      name: "",
      value: EMPTY,
      default_value: EMPTY,
      min_value: EMPTY,
      max_value: EMPTY,
    });
    const { result } = renderHook(() => useDroneCanNodeParams(client, 10));

    await act(async () => {
      await result.current.refresh();
    });
    act(() => {
      result.current.setLocal("P_TWO", {
        tag: ValueTag.Integer,
        value: BigInt(99),
      });
    });
    let saveResult: { saved: number; failed: number } = {
      saved: 0,
      failed: 0,
    };
    await act(async () => {
      saveResult = await result.current.saveAllDirty();
    });
    expect(saveResult).toEqual({ saved: 0, failed: 1 });
    expect(result.current.params.get("P_TWO")?.dirty).toBe(true);
  });

  it("eraseToDefaults sends ERASE opcode", async () => {
    const { client, paramExecuteOpcode } = makeClient();
    const { result } = renderHook(() => useDroneCanNodeParams(client, 10));
    await act(async () => {
      await result.current.eraseToDefaults();
    });
    expect(paramExecuteOpcode).toHaveBeenCalledWith(10, PARAM_OPCODE_ERASE);
  });

  it("restartNode forwards to client.restart", async () => {
    const { client, restart } = makeClient();
    const { result } = renderHook(() => useDroneCanNodeParams(client, 10));
    await act(async () => {
      await result.current.restartNode();
    });
    expect(restart).toHaveBeenCalledWith(10);
  });

  it("returns early when client is null", async () => {
    const { result } = renderHook(() => useDroneCanNodeParams(null, 10));
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.params.size).toBe(0);
    expect(result.current.loading).toBe(false);
  });

  it("surfaces an error message when paramGet throws", async () => {
    const { client, paramGet } = makeClient();
    paramGet.mockRejectedValueOnce(new Error("transport down"));
    const { result } = renderHook(() => useDroneCanNodeParams(client, 10));
    await act(async () => {
      await result.current.refresh();
    });
    await waitFor(() => expect(result.current.error).toBe("transport down"));
    expect(result.current.loading).toBe(false);
  });
});
