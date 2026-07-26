/**
 * @module INavFailsafePanel
 * @description iNav-specific failsafe configuration via the named settings system.
 * Only shown when connected to iNav firmware.
 * @license GPL-3.0-only
 */

"use client";

import { PanelHeader } from "../shared/PanelHeader";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { ShieldAlert, Upload } from "lucide-react";
import { useSettingsParams } from "@/hooks/use-settings-params";
import type { DroneProtocol } from "@/lib/protocol/types";
import { settingNumber } from "@/lib/protocol/types";

// ── Types ─────────────────────────────────────────────────────

interface INavFailsafeState {
  fsNavMode: number;
  fsMinDistanceBehaviour: number;
  fsMinDistanceCm: number;
}

const DEFAULT: INavFailsafeState = {
  fsNavMode: 0,
  fsMinDistanceBehaviour: 0,
  fsMinDistanceCm: 0,
};

const NAV_MODE_OPTIONS = [
  { value: "0", label: "None" },
  { value: "1", label: "RTH" },
  { value: "2", label: "Land" },
  { value: "3", label: "Hover" },
];

const MIN_DIST_BEHAVIOUR_OPTIONS = [
  { value: "0", label: "Fly normally" },
  { value: "1", label: "RTH" },
  { value: "2", label: "Land" },
];

// ── Helpers ───────────────────────────────────────────────────

const settingsSupported = (p: DroneProtocol): boolean => !!p.settings;

async function readFailsafe(protocol: DroneProtocol): Promise<INavFailsafeState> {
  const settings = protocol.settings!;
  const [navMode, minDistBeh, minDist] = await Promise.all([
    settings.getSetting("failsafe_nav_mode"),
    settings.getSetting("failsafe_min_distance_behaviour"),
    settings.getSetting("failsafe_min_distance"),
  ]);
  return {
    fsNavMode: settingNumber(navMode),
    fsMinDistanceBehaviour: settingNumber(minDistBeh),
    fsMinDistanceCm: settingNumber(minDist),
  };
}

async function writeFailsafe(protocol: DroneProtocol, state: INavFailsafeState): Promise<void> {
  const settings = protocol.settings!;
  await settings.setSetting("failsafe_nav_mode", state.fsNavMode);
  await settings.setSetting("failsafe_min_distance_behaviour", state.fsMinDistanceBehaviour);
  await settings.setSetting("failsafe_min_distance", state.fsMinDistanceCm);
}

// ── Component ─────────────────────────────────────────────────

export function INavFailsafePanel() {
  const {
    values: state, setValues, loading, error, hasLoaded, dirty,
    connected, isArmed, lockMessage, read, write,
  } = useSettingsParams<INavFailsafeState>({
    panelId: "inav-failsafe",
    initial: DEFAULT,
    read: readFailsafe,
    write: writeFailsafe,
    supported: settingsSupported,
    unsupportedMessage: "Settings not available on this firmware",
  });

  function update<K extends keyof INavFailsafeState>(key: K, value: INavFailsafeState[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="iNav Failsafe"
          subtitle="Navigation-aware failsafe behaviour"
          icon={<ShieldAlert size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={read}
          connected={connected}
          error={error}
        >
          {hasLoaded && (
            <Button
              variant="primary"
              size="sm"
              icon={<Upload size={12} />}
              loading={loading}
              disabled={!connected || loading || isArmed}
              title={isArmed ? lockMessage : undefined}
              onClick={write}
            >
              Write to FC
            </Button>
          )}
        </PanelHeader>

        {dirty && (
          <p className="text-[10px] font-mono text-status-warning">
            Unsaved changes : use Write to FC to persist.
          </p>
        )}

        {hasLoaded && (
          <div className="space-y-3">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-text-tertiary font-mono">Failsafe nav mode</span>
              <Select
                label=""
                options={NAV_MODE_OPTIONS}
                value={String(state.fsNavMode)}
                onChange={(v) => update("fsNavMode", parseInt(v))}
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-text-tertiary font-mono">Min distance behaviour</span>
              <Select
                label=""
                options={MIN_DIST_BEHAVIOUR_OPTIONS}
                value={String(state.fsMinDistanceBehaviour)}
                onChange={(v) => update("fsMinDistanceBehaviour", parseInt(v))}
              />
            </div>
            <label className="flex flex-col gap-1">
              <span className="text-[10px] text-text-tertiary font-mono">Min distance (cm)</span>
              <input
                type="number"
                min={0}
                max={100000}
                value={state.fsMinDistanceCm}
                onChange={(e) => update("fsMinDistanceCm", parseInt(e.target.value) || 0)}
                onBlur={(e) => update("fsMinDistanceCm", Math.min(100000, Math.max(0, parseInt(e.target.value) || 0)))}
                className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
              />
            </label>
          </div>
        )}
      </div>
    </div>
  );
}
