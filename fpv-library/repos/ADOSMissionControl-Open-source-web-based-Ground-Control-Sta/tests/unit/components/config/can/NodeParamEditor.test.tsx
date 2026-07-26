/**
 * Smoke tests for NodeParamEditor. Verifies the slide-over renders rows
 * from a mock client, tracks dirty edits, and invokes saveAllDirty when
 * the Send all dirty button is clicked.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithIntl } from "../../../../helpers/intl-wrapper";
import { ValueTag } from "@/lib/dronecan/dsdl/param-getset";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { NodeParamEditor } from "@/components/config/can/NodeParamEditor";

interface MockResponse {
  name: string;
  value:
    | { tag: 0 }
    | { tag: 1; value: bigint }
    | { tag: 2; value: number }
    | { tag: 3; value: boolean }
    | { tag: 4; value: string };
  default_value: { tag: 0 };
  max_value: { tag: 0 };
  min_value: { tag: 0 };
}

function mkParam(name: string, intVal: number): MockResponse {
  return {
    name,
    value: { tag: ValueTag.Integer, value: BigInt(intVal) },
    default_value: { tag: ValueTag.Empty },
    max_value: { tag: ValueTag.Empty },
    min_value: { tag: ValueTag.Empty },
  };
}

const EMPTY = {
  name: "",
  value: { tag: ValueTag.Empty } as const,
  default_value: { tag: ValueTag.Empty } as const,
  max_value: { tag: ValueTag.Empty } as const,
  min_value: { tag: ValueTag.Empty } as const,
};

function buildClient() {
  const calls: { paramSet: unknown[] } = { paramSet: [] };
  const params = [mkParam("GPS_TYPE", 9), mkParam("MAG_ENABLE", 1)];
  return {
    calls,
    client: {
      paramGet: vi.fn(async (_: number, idx: number) =>
        params[idx] ?? EMPTY,
      ),
      paramSet: vi.fn(async (_: number, name: string, value: unknown) => {
        calls.paramSet.push({ name, value });
        const found = params.find((p) => p.name === name);
        return found
          ? { ...found, value: value as MockResponse["value"] }
          : EMPTY;
      }),
      paramExecuteOpcode: vi.fn(async () => ({ argument: BigInt(0), ok: true })),
      restart: vi.fn(async () => ({ ok: true })),
    },
  };
}

describe("NodeParamEditor", () => {
  beforeEach(() => {
    useDroneCanNodeStore.setState({ nodes: new Map(), _version: 0 } as never);
  });

  it("renders rows from the mock client", async () => {
    const { client } = buildClient();
    renderWithIntl(<NodeParamEditor nodeId={11} client={client} onClose={() => undefined} />);
    await waitFor(() => {
      expect(screen.getByText("GPS_TYPE")).toBeDefined();
      expect(screen.getByText("MAG_ENABLE")).toBeDefined();
    });
  });

  it("marks rows dirty on edit and increments the dirty count", async () => {
    const { client } = buildClient();
    renderWithIntl(<NodeParamEditor nodeId={11} client={client} onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("GPS_TYPE")).toBeDefined());

    const input = screen.getByLabelText("GPS_TYPE value");
    fireEvent.change(input, { target: { value: "12" } });

    await waitFor(() => {
      expect(screen.getByTestId("node-param-editor-dirty-count").textContent).toContain("1");
    });
  });

  it("invokes saveAllDirty when Send all dirty is clicked", async () => {
    const { client } = buildClient();
    renderWithIntl(<NodeParamEditor nodeId={11} client={client} onClose={() => undefined} />);
    await waitFor(() => expect(screen.getByText("GPS_TYPE")).toBeDefined());

    const input = screen.getByLabelText("GPS_TYPE value");
    fireEvent.change(input, { target: { value: "12" } });

    await waitFor(() => {
      expect(screen.getByTestId("node-param-editor-dirty-count").textContent).toContain("1");
    });

    const sendBtn = screen.getByTestId("node-param-editor-send-all");
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(client.paramSet).toHaveBeenCalled();
    });
  });

  it("renders a no-client hint when client is null", () => {
    renderWithIntl(<NodeParamEditor nodeId={11} client={null} onClose={() => undefined} />);
    // The empty-state placeholder is "—"; just confirm the dialog renders.
    expect(screen.getByTestId("node-param-editor")).toBeDefined();
  });
});
