/**
 * @license GPL-3.0-only
 *
 * A2 regression: the MqttBridge connect effect consumes the broker URL + viewer
 * credentials (resolved from clientConfig, `undefined` on the first render and
 * populated a tick later). Those props must be in the effect deps so that when
 * the creds arrive the client tears down + reconnects to the correct broker
 * with credentials — instead of connecting once, credential-less, to the
 * default broker and never re-running.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";

interface FakeClient {
  on: ReturnType<typeof vi.fn>;
  subscribe: ReturnType<typeof vi.fn>;
  end: ReturnType<typeof vi.fn>;
}

const h = vi.hoisted(() => ({
  connect:
    vi.fn<(url: string, opts: Record<string, unknown>) => FakeClient>(),
}));

// The bridge dynamically imports "mqtt"; intercept both the connect fn and the
// returned client so we can observe the URL + options each connect used.
vi.mock("mqtt", () => ({
  connect: (url: string, opts: Record<string, unknown>) => h.connect(url, opts),
}));

// useToast needs a provider in the tree; stub it to a no-op toaster.
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

import { MqttBridge } from "../MqttBridge";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { OFFICIAL_MQTT_WS_URL } from "@/lib/config/endpoints";

const BROKER = "wss://broker.example/mqtt";

const clients: FakeClient[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
  clients.length = 0;
  h.connect.mockImplementation(() => {
    const c: FakeClient = { on: vi.fn(), subscribe: vi.fn(), end: vi.fn() };
    clients.push(c);
    return c;
  });
  // The effect early-returns without a cloud device id.
  useAgentConnectionStore.setState({ cloudDeviceId: "cloud-1" });
});

describe("MqttBridge — credentials-arrive-late (A2)", () => {
  it("reconnects to the correct broker with creds when they arrive after mount", async () => {
    const { rerender } = render(
      <MqttBridge
        mqttBrokerUrl={undefined}
        mqttViewerUsername={undefined}
        mqttViewerPassword={undefined}
      />,
    );

    // First connect fires before clientConfig resolves: the default broker,
    // no username (the credential-less path).
    await waitFor(() => expect(h.connect).toHaveBeenCalledTimes(1));
    const [firstUrl, firstOpts] = h.connect.mock.calls[0];
    expect(firstUrl).toBe(OFFICIAL_MQTT_WS_URL);
    expect(firstOpts.username).toBeUndefined();
    expect(firstOpts.password).toBeUndefined();

    // clientConfig resolves → the real broker + viewer creds arrive on props.
    rerender(
      <MqttBridge
        mqttBrokerUrl={BROKER}
        mqttViewerUsername="viewer"
        mqttViewerPassword="pw"
      />,
    );

    // The effect re-runs: the stale client is torn down and a fresh one dials
    // the configured broker WITH credentials.
    await waitFor(() => expect(h.connect).toHaveBeenCalledTimes(2));
    const [secondUrl, secondOpts] = h.connect.mock.calls[1];
    expect(secondUrl).toBe(BROKER);
    expect(secondOpts.username).toBe("viewer");
    expect(secondOpts.password).toBe("pw");
    // The first (credential-less) client was ended on reconnect.
    expect(clients[0].end).toHaveBeenCalled();
  });
});
