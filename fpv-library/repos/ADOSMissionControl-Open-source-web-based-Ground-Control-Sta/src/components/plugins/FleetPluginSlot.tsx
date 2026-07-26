/**
 * @module plugins/FleetPluginSlot
 * @description The fleet-scoped (no-drone) analogue of the per-drone slot
 * hosts. Mounts a single fleet `<PluginHostProvider deviceId={null}>` wrapping
 * a `<PluginSlot>` fed by `useFleetPluginContributions(slot)`, so a plugin
 * installed at the GCS level (no specific drone) renders into a fleet UI slot:
 * settings.section, fc.tab, hardware.tab, mission.template, map.overlay, or
 * notification.channel.
 *
 * Each fleet slot brings its own provider (mirrors `VideoOverlayHost`), so the
 * six scattered surfaces (settings nav, FC configure nav, system hardware,
 * planner gallery, planner map, notification system) each host their slot
 * independently without forcing a single root provider. The provider's
 * `deviceId={null}` collapses to the stable `"fleet"` subtree key, so the host
 * is a single long-lived host (no per-drone teardown).
 *
 * Inert until a plugin contributes: the slot renders nothing (or the supplied
 * `emptyState`) when the fleet producer yields no contribution for the slot.
 * The `<PluginSlot>` capability-gate (`ui.slot.<id>`) still applies, so a
 * contribution missing its slot cap is dropped with a one-shot toast.
 *
 * The per-drone path (`usePluginContributions(deviceId, slot)` + the keyed
 * per-drone `<PluginHostProvider>`) is untouched.
 *
 * @license GPL-3.0-only
 */

"use client";

import type { ReactNode } from "react";

import { PluginSlot } from "@/components/plugins/PluginSlot";
import { PluginHostProvider } from "@/components/plugins/PluginHostProvider";
import { useFleetPluginContributions } from "@/hooks/use-fleet-plugin-contributions";
import type { PluginSlotName } from "@/lib/plugins/types";

interface FleetPluginSlotProps {
  /** Which fleet slot to host. */
  name: PluginSlotName;
  /** Rendered when no plugin contributes to this fleet slot. */
  emptyState?: ReactNode;
  /** Class on the slot wrapper. */
  className?: string;
  /** Class on each mounted iframe. Slot owners control sizing. */
  iframeClassName?: string;
}

/**
 * Host one fleet slot. Resolves the fleet contributions for `name`, mounts a
 * fleet-scoped provider, and renders a `<PluginSlot>` over them. Renders the
 * `emptyState` (or nothing) when no plugin contributes.
 */
export function FleetPluginSlot({
  name,
  emptyState,
  className,
  iframeClassName,
}: FleetPluginSlotProps) {
  const contributions = useFleetPluginContributions(name);

  // No fleet contribution for this slot — stay mute (or show the host's empty
  // copy). Mounting the provider with an empty list is harmless, but skipping
  // it keeps a non-contributing surface free of an idle host.
  if (contributions.length === 0) return <>{emptyState}</>;

  return (
    <PluginHostProvider deviceId={null} contributions={contributions}>
      <PluginSlot
        name={name}
        contributions={contributions}
        className={className}
        iframeClassName={iframeClassName}
      />
    </PluginHostProvider>
  );
}
