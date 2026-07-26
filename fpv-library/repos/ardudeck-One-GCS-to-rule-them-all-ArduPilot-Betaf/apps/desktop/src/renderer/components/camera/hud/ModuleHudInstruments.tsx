/**
 * Renders module-contributed HUD instruments (host.hud.registerInstrument) into
 * the HUD's own SVG, so a cargo's symbology (e.g. the Release Point CCRP/CCIP
 * reticle) draws alongside the built-in instruments - in the live camera
 * overlay AND the OSD Tool designer preview, with the same demo/live values.
 *
 * Mounted inside FighterHud's <svg>, so each instrument's returned <g> shares
 * the 1600x900 viewBox and lines up with the pitch ladder. Only the instruments
 * toggled on in config.moduleInstruments draw; a module that isn't loaded
 * contributes nothing.
 */

import { useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import type { HudInstrumentContext, HudMissionWaypoint, HudCommandTarget } from '@ardudeck/module-sdk';
import { listModuleHudInstruments, subscribeModuleHudInstruments } from '../../../modules/module-hud-registry';
import { useMissionStore } from '../../../stores/mission-store';
import { useSelfActiveTarget } from '../../../stores/command-target-store';
import { buildHudProjection } from './hud-projection';
import type { HudConfig } from './hud-config';
import type { FighterHudValues } from './FighterHud';

interface Props {
  v: FighterHudValues;
  config: HudConfig;
}

export function ModuleHudInstruments({ v, config }: Props) {
  // Re-read when a module registers/unregisters an instrument (snapshot on count).
  useSyncExternalStore(subscribeModuleHudInstruments, () => listModuleHudInstruments().length);
  const missionItems = useMissionStore((s) => s.missionItems);
  const commandTarget = useSelfActiveTarget();

  const instruments = listModuleHudInstruments();
  if (instruments.length === 0) return null;

  const enabled = instruments.filter((i) => i.render && config.moduleInstruments[i.id]);
  if (enabled.length === 0) return null;

  const ctx: HudInstrumentContext = {
    projection: buildHudProjection(config),
    values: {
      roll: v.roll,
      pitch: v.pitch,
      heading: v.heading,
      airspeed: v.airspeed,
      groundspeed: v.groundspeed,
      altitude: v.altitude,
      vario: v.vario,
      throttle: v.throttle,
      vx: v.vx,
      vy: v.vy,
      vz: v.vz,
      lat: v.lat,
      lon: v.lon,
    },
    mission: missionItems as unknown as HudMissionWaypoint[],
    commandTarget: (commandTarget as unknown as HudCommandTarget | null) ?? null,
  };

  return (
    <>
      {enabled.map((inst) => {
        let node: ReactNode = null;
        try {
          node = inst.render!(ctx) as ReactNode;
        } catch {
          node = null; // a misbehaving module must not break the HUD
        }
        return <g key={inst.id}>{node}</g>;
      })}
    </>
  );
}
