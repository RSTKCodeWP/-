/**
 * Render smoke test for FleetNetworkPanel.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, vi } from "vitest";
import { renderWithIntl } from "../../../helpers/intl-wrapper";

vi.mock("@/stores/agent-connection-store", () => ({
  useAgentConnectionStore: (sel: (s: unknown) => unknown) =>
    sel({ connected: false, mqttConnected: false }),
}));

vi.mock("@/stores/fleet-network-store", () => ({
  useFleetNetworkStore: (sel: (s: unknown) => unknown) =>
    sel({
      peers: [],
      fetchPeers: vi.fn(),
    }),
}));

vi.mock("@/hooks/use-mqtt-config", () => ({
  useMqttConfig: () => ({
    config: {
      mode: "self-hosted",
      brokerUrl: "mqtt://localhost:1883",
      username: "",
      password: "",
      tls: false,
    },
    setMode: vi.fn(),
    setBrokerUrl: vi.fn(),
    setUsername: vi.fn(),
    setPassword: vi.fn(),
    setTls: vi.fn(),
    testConnection: vi.fn(),
    isTesting: false,
    lastResult: null,
  }),
}));

vi.mock("@/components/command/shared/MeshNetEnrollmentCard", () => ({
  MeshNetEnrollmentCard: () => <div data-testid="meshnet-enrollment" />,
}));

vi.mock("@/components/command/system/shared", () => ({
  CollapsibleSection: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <section data-testid="collapsible" data-title={title}>
      {children}
    </section>
  ),
}));

import { FleetNetworkPanel } from "@/components/command/system/FleetNetworkPanel";

describe("FleetNetworkPanel", () => {
  it("renders without crashing", () => {
    const { container } = renderWithIntl(<FleetNetworkPanel />);
    expect(container.firstChild).toBeTruthy();
  });
});
