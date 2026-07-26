"use client";

/**
 * @module command/PluginsTab
 * @description Per-drone plugin management surface on the Command page.
 *
 * The Command page's Plugins sub-tab. Renders the install affordance
 * and the list of installed plugins for the currently-connected drone.
 *
 * Why this is its own component rather than a thin re-export of the
 * dashboard's DronePluginsTab: the dashboard version looks up the
 * target drone in `useFleetStore`, which is only populated by demo
 * mode. The Command page connects via cloud relay or LAN-direct and
 * keeps the active drone in `agent-connection-store` +
 * `pairing-store`. This adapter resolves the active drone from those
 * stores and renders the same list + install affordance the dashboard
 * version uses.
 *
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import { useTranslations } from "next-intl";

import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useLocalNodesStore } from "@/stores/local-nodes-store";
import { usePairingStore } from "@/stores/pairing-store";
import { useSurfaceGate } from "@/hooks/use-surface-gate";
import { deviceIdFromNodeId } from "@/lib/agent/node-id";
import { agentGateFallback } from "./shared/agent-gate-fallback";
import { DronePluginsList } from "@/components/dashboard/drone-plugins/DronePluginsList";
import { InstallPluginButton } from "@/components/dashboard/drone-plugins/InstallPluginButton";
import { RegistryPluginGrid } from "@/components/dashboard/drone-plugins/RegistryPluginGrid";
import type { FleetDrone } from "@/lib/types";

export function PluginsTab() {
  const t = useTranslations("dronePlugins");
  const cloudMode = useAgentConnectionStore((s) => s.cloudMode);
  const agentGate = useSurfaceGate("agent-online");
  const selectedPairedId = usePairingStore((s) => s.selectedPairedId);
  const pairedDrones = usePairingStore((s) => s.pairedDrones);
  const localNodes = useLocalNodesStore((s) => s.nodes);

  // Resolve the active drone from the canonical `node:<deviceId>` selection id.
  // A LAN-paired node resolves to its local credentials; otherwise a
  // cloud-paired drone (matched by device id). Build a FleetDrone-shaped object
  // large enough for InstallPluginButton (reads id / name / cloudDeviceId) and
  // DronePluginsList (reads agentId, passed in via id).
  const activeDrone = useMemo<FleetDrone | null>(() => {
    const deviceId = deviceIdFromNodeId(selectedPairedId);
    if (!deviceId) return null;
    const node = localNodes.find((n) => n.deviceId === deviceId);
    if (node) {
      return {
        id: node.deviceId,
        name: node.name ?? node.deviceId,
        // LocalNode has no cloudDeviceId; the install dialog falls
        // back to targetDevice.id when cloudDeviceId is absent.
      } as FleetDrone;
    }
    const paired = pairedDrones.find((d) => d.deviceId === deviceId);
    if (!paired) return null;
    return {
      id: paired.deviceId,
      name: paired.name ?? paired.deviceId,
      cloudDeviceId: paired.deviceId,
    } as FleetDrone;
  }, [selectedPairedId, pairedDrones, localNodes]);

  const blocked = agentGateFallback(agentGate);
  if (blocked) return blocked;

  if (activeDrone === null) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
        <p className="text-sm text-text-secondary">
          {t("notConnectedTitle")}
        </p>
        <p className="mt-1 text-xs text-text-tertiary">
          {cloudMode ? t("notConnectedCloud") : t("notConnectedLocal")}
        </p>
      </div>
    );
  }

  const droneName = activeDrone.name ?? activeDrone.id;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border-default bg-bg-secondary px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold text-text-primary">
            {t("titleForDrone", { drone: droneName })}
          </h2>
          <p className="truncate text-xs text-text-tertiary">
            {t("subtitle")}
          </p>
        </div>
        <InstallPluginButton
          targetDevice={activeDrone}
          variant="secondary"
          label={t("installFromFile")}
        />
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-6">
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-text-secondary">
              {t("installedSectionTitle")}
            </h3>
            <DronePluginsList
              agentId={activeDrone.id}
              emptyState={<InstalledEmptyState drone={activeDrone} />}
            />
          </section>
          <RegistryPluginGrid
            target={{
              _id: activeDrone.cloudDeviceId ?? activeDrone.id,
              deviceId: activeDrone.cloudDeviceId ?? activeDrone.id,
              name: activeDrone.name ?? activeDrone.id,
            }}
          />
        </div>
      </div>
    </div>
  );
}

function InstalledEmptyState({ drone }: { drone: FleetDrone }) {
  const t = useTranslations("dronePlugins");
  return (
    <div className="rounded-md border border-dashed border-border-default p-6 text-center">
      <p className="text-sm text-text-primary">{t("emptyStateTitle")}</p>
      <p className="mx-auto mt-1 max-w-md text-xs text-text-tertiary">
        {t("emptyInstalledHint")}
      </p>
      <div className="mt-3 flex items-center justify-center gap-2">
        <InstallPluginButton
          targetDevice={drone}
          variant="secondary"
          label={t("installFromFile")}
        />
      </div>
    </div>
  );
}
