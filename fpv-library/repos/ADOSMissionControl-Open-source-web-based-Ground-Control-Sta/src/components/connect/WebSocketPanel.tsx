"use client";

import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plug } from "lucide-react";
import { WebSocketTransport } from "@/lib/protocol/transport/websocket";
import { connectWithDetection } from "@/lib/protocol/connect-with-detection";
import { useDroneManager } from "@/stores/drone-manager";
import { useDroneMetadataStore } from "@/stores/drone-metadata-store";
import { resolveNodeId } from "@/lib/agent/node-id";
import { getPreset } from "@/lib/presets/presets";
import { BuildPresetPicker } from "./BuildPresetPicker";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import { cmdDroneStatusApi } from "@/lib/community-api-drones";

const QUICK_PRESETS = [
  { label: "mavlink-router", url: "ws://localhost:14550" },
  { label: "SITL #1", url: "ws://localhost:5760" },
  { label: "SITL #2", url: "ws://localhost:5770" },
  { label: "SITL #3", url: "ws://localhost:5780" },
  { label: "SITL #4", url: "ws://localhost:5790" },
  { label: "SITL #5", url: "ws://localhost:5800" },
];

/** Cloud-status row shape projected for the discovered-rigs section. */
type DiscoveredRig = {
  deviceId: string;
  name: string;
  mavlinkWs: string;
};

/** Detect SITL-like URLs (ws://localhost:576*). */
function isSitlUrl(url: string): boolean {
  return /^wss?:\/\/(localhost|127\.0\.0\.1):576\d/.test(url);
}

export function WebSocketPanel({
  onConnected,
  url,
  onUrlChange,
  targetDroneId,
}: {
  onConnected?: (name: string, type: "websocket", url: string) => void;
  url?: string;
  onUrlChange?: (url: string) => void;
  /** When set, connects this transport as an additional link to the existing drone (multi-link mode). */
  targetDroneId?: string | null;
}) {
  const [localUrl, setLocalUrl] = useState("ws://localhost:14550");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const addDrone = useDroneManager((s) => s.addDrone);
  const attachLinkToDrone = useDroneManager((s) => s.attachLinkToDrone);

  // Discovered rigs — the cloud heartbeat from every paired agent
  // carries a LAN-routable MAVLink WebSocket URL. Surface those as
  // one-click chips so the operator can switch from cloud relay to
  // direct LAN without copy-pasting addresses. Query is gated by the
  // skip guard so it returns undefined when Convex auth is unavailable.
  const cloudRows = useConvexSkipQuery(cmdDroneStatusApi.listMyCloudStatuses, {
    enabled: true,
  });
  const discoveredRigs: DiscoveredRig[] = useMemo(() => {
    if (!Array.isArray(cloudRows)) return [];
    const rigs: DiscoveredRig[] = [];
    for (const row of cloudRows as Array<{
      drone?: { deviceId?: string; name?: string };
      status?: {
        manualConnectionUrls?: { mavlinkWs?: string | null };
      } | null;
    }>) {
      const ws = row?.status?.manualConnectionUrls?.mavlinkWs;
      const deviceId = row?.drone?.deviceId;
      if (typeof ws === "string" && ws && typeof deviceId === "string") {
        rigs.push({
          deviceId,
          name: row?.drone?.name || deviceId,
          mavlinkWs: ws,
        });
      }
    }
    return rigs;
  }, [cloudRows]);

  const effectiveUrl = url ?? localUrl;

  const handleUrlChange = (next: string) => {
    setLocalUrl(next);
    onUrlChange?.(next);
  };

  const showPresetPicker = useMemo(() => isSitlUrl(effectiveUrl), [effectiveUrl]);

  async function handleConnect() {
    setError(null);
    const trimmed = effectiveUrl.trim();

    if (!trimmed) {
      setError("URL is required");
      return;
    }
    if (!trimmed.startsWith("ws://") && !trimmed.startsWith("wss://")) {
      setError("URL must start with ws:// or wss://");
      return;
    }

    setConnecting(true);
    let transport: WebSocketTransport | null = null;
    let handedOff = false;
    try {
      transport = new WebSocketTransport();
      await transport.connect(trimmed);

      // Multi-link mode: attach as secondary link to existing drone
      if (targetDroneId) {
        const result = await attachLinkToDrone(targetDroneId, transport);
        if (!result.ok) {
          try { await transport.disconnect(); } catch { /* ignore */ }
          setError(result.error);
          setConnecting(false);
          return;
        }
        handedOff = true;
        onConnected?.("link", "websocket", trimmed);
        setConnecting(false);
        return;
      }

      const { adapter, vehicleInfo, firmwareType } =
        await connectWithDetection(transport);
      const droneId = resolveNodeId();

      // Use preset name if available, otherwise firmware info
      // Append system ID for unique naming in multi-drone setups
      const preset = selectedPresetId ? getPreset(selectedPresetId) : null;
      const sysIdSuffix = vehicleInfo.systemId > 0 ? ` #${vehicleInfo.systemId}` : '';
      const droneName = preset
        ? `${preset.name}${sysIdSuffix}`
        : `${vehicleInfo.firmwareVersionString} (${vehicleInfo.vehicleClass})${sysIdSuffix}`;

      addDrone(droneId, droneName, adapter, transport, vehicleInfo, {
        type: "websocket",
        url: trimmed,
        presetId: selectedPresetId ?? undefined,
        firmwareType,
      });

      useDroneMetadataStore.getState().ensureProfile(droneId, {
        displayName: droneName,
        serial: `ALT-${droneId.toUpperCase()}`,
        enrolledAt: Date.now(),
      });

      handedOff = true;
      onConnected?.(droneName, "websocket", trimmed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
      // Tear down the opened socket on a failed connect so it doesn't leak.
      if (transport && !handedOff) {
        try {
          await transport.disconnect();
        } catch {
          /* ignore */
        }
      }
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Input
        label="WebSocket URL"
        value={effectiveUrl}
        onChange={(e) => {
          handleUrlChange(e.target.value);
          setError(null);
        }}
        placeholder="ws://localhost:14550"
      />

      {discoveredRigs.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-text-tertiary mb-1.5">
            Discovered rigs
          </div>
          <div className="flex flex-wrap gap-1.5">
            {discoveredRigs.map((rig) => (
              <button
                key={rig.deviceId}
                onClick={() => handleUrlChange(rig.mavlinkWs)}
                className={`px-2 py-1 text-[10px] font-mono border transition-colors cursor-pointer ${
                  effectiveUrl === rig.mavlinkWs
                    ? "border-accent-primary text-accent-primary bg-accent-primary/10"
                    : "border-border-default text-text-tertiary hover:text-text-secondary hover:border-border-strong"
                }`}
                title={rig.mavlinkWs}
              >
                {rig.name} — {rig.mavlinkWs.replace(/^wss?:\/\//, "")}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Quick-connect presets */}
      <div className="flex flex-wrap gap-1.5">
        {QUICK_PRESETS.map((preset) => (
          <button
            key={preset.url}
            onClick={() => handleUrlChange(preset.url)}
            className={`px-2 py-1 text-[10px] font-mono border transition-colors cursor-pointer ${
              effectiveUrl === preset.url
                ? "border-accent-primary text-accent-primary bg-accent-primary/10"
                : "border-border-default text-text-tertiary hover:text-text-secondary hover:border-border-strong"
            }`}
          >
            {preset.label} — {preset.url.replace("ws://", "")}
          </button>
        ))}
      </div>

      {/* Build preset picker — shown when SITL URL detected */}
      {showPresetPicker && (
        <BuildPresetPicker
          selectedPresetId={selectedPresetId}
          onSelect={setSelectedPresetId}
        />
      )}

      <Button
        onClick={handleConnect}
        loading={connecting}
        icon={<Plug size={14} />}
      >
        {connecting ? "Connecting..." : "Connect"}
      </Button>

      <p className="text-[10px] text-text-tertiary">
        For a raw UDP or TCP MAVLink endpoint, use the UDP or TCP method instead.
      </p>

      {error && <p className="text-xs text-status-error">{error}</p>}
    </div>
  );
}
