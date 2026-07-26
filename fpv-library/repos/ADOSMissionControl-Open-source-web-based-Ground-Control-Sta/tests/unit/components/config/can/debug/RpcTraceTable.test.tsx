/**
 * Smoke tests for RpcTraceTable. Verifies rows render from the store,
 * filters narrow the list, and the empty state shows when there is no
 * traffic.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithIntl } from "../../../../../helpers/intl-wrapper";
import {
  useDroneCanRpcTraceStore,
  type RpcEvent,
} from "@/stores/dronecan/rpc-trace-store";
import { RingBuffer } from "@/lib/ring-buffer";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (opts: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: opts.count }, (_, i) => ({
        key: i,
        index: i,
        start: i * 24,
        size: 24,
      })),
    getTotalSize: () => opts.count * 24,
  }),
}));

import { RpcTraceTable } from "@/components/config/can/debug/RpcTraceTable";

function seedEvents(events: RpcEvent[]) {
  const ring = new RingBuffer<RpcEvent>(512);
  for (const e of events) ring.push(e);
  useDroneCanRpcTraceStore.setState({
    events: ring,
    filters: {},
    _version: 1,
  } as never);
}

describe("RpcTraceTable", () => {
  beforeEach(() => {
    seedEvents([]);
  });

  it("renders the empty state when no events have arrived", () => {
    renderWithIntl(<RpcTraceTable />);
    expect(screen.getByText("No RPC events yet")).toBeDefined();
  });

  it("renders an event row when one is seeded", () => {
    seedEvents([
      {
        t: Date.now(),
        kind: "request",
        direction: "out",
        dataTypeId: 11,
        dataTypeName: "param.GetSet",
        srcNodeId: 127,
        dstNodeId: 11,
        latencyMs: 8,
        ok: true,
      },
    ]);
    renderWithIntl(<RpcTraceTable />);
    expect(screen.getByText("param.GetSet")).toBeDefined();
  });

  it("filters by type when the type input is populated", () => {
    seedEvents([
      {
        t: 1,
        kind: "request",
        direction: "out",
        dataTypeId: 11,
        dataTypeName: "param.GetSet",
        srcNodeId: 127,
        dstNodeId: 11,
        ok: true,
      },
      {
        t: 2,
        kind: "broadcast",
        direction: "in",
        dataTypeId: 341,
        dataTypeName: "NodeStatus",
        srcNodeId: 11,
        ok: true,
      },
    ]);
    renderWithIntl(<RpcTraceTable />);
    const typeInput = screen.getByLabelText("Filter by type");
    fireEvent.change(typeInput, { target: { value: "param" } });
    expect(screen.getByText("param.GetSet")).toBeDefined();
    expect(screen.queryByText("NodeStatus")).toBeNull();
  });
});
