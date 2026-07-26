/**
 * @module NavPidPanel
 * @description iNav navigation PID gains via the named settings system.
 * Reads and writes nav_*_pid_* settings for six navigation controllers.
 * @license GPL-3.0-only
 */

"use client";

import { PanelHeader } from "../shared/PanelHeader";
import { Button } from "@/components/ui/button";
import { Settings2, Upload } from "lucide-react";
import { useSettingsParams } from "@/hooks/use-settings-params";
import type { DroneProtocol } from "@/lib/protocol/types";
import { settingNumber } from "@/lib/protocol/types";

// ── Types ─────────────────────────────────────────────────────

interface PidGroup {
  p: number;
  i: number;
  d: number;
}

interface NavPidState {
  posXy: PidGroup;
  posZ: PidGroup;
  heading: PidGroup;
  surface: PidGroup;
  velXy: PidGroup;
  velZ: PidGroup;
}

const DEFAULT_GROUP: PidGroup = { p: 0, i: 0, d: 0 };

const DEFAULT: NavPidState = {
  posXy: { ...DEFAULT_GROUP },
  posZ: { ...DEFAULT_GROUP },
  heading: { ...DEFAULT_GROUP },
  surface: { ...DEFAULT_GROUP },
  velXy: { ...DEFAULT_GROUP },
  velZ: { ...DEFAULT_GROUP },
};

/** Maps each PID group to its iNav setting name prefix. */
const GROUPS: { key: keyof NavPidState; label: string; base: string }[] = [
  { key: "posXy",   label: "Position XY", base: "nav_mc_pos_xy" },
  { key: "posZ",    label: "Position Z",  base: "nav_mc_pos_z" },
  { key: "heading", label: "Heading",     base: "nav_mc_heading" },
  { key: "surface", label: "Surface",     base: "nav_mc_surface" },
  { key: "velXy",   label: "Velocity XY", base: "nav_mc_vel_xy" },
  { key: "velZ",    label: "Velocity Z",  base: "nav_mc_vel_z" },
];

// ── Helpers ───────────────────────────────────────────────────

function clampU8(v: number): number {
  return Math.min(255, Math.max(0, Math.round(v)));
}

const settingsSupported = (p: DroneProtocol): boolean => !!p.settings;

async function readNavPid(protocol: DroneProtocol): Promise<NavPidState> {
  const settings = protocol.settings!;
  const next = structuredClone(DEFAULT);
  for (const { key, base } of GROUPS) {
    const [p, i, d] = await Promise.all([
      settings.getSetting(`${base}_p`),
      settings.getSetting(`${base}_i`),
      settings.getSetting(`${base}_d`),
    ]);
    next[key] = { p: settingNumber(p), i: settingNumber(i), d: settingNumber(d) };
  }
  return next;
}

async function writeNavPid(protocol: DroneProtocol, state: NavPidState): Promise<void> {
  const settings = protocol.settings!;
  for (const { key, base } of GROUPS) {
    const g = state[key];
    await settings.setSetting(`${base}_p`, clampU8(g.p));
    await settings.setSetting(`${base}_i`, clampU8(g.i));
    await settings.setSetting(`${base}_d`, clampU8(g.d));
  }
}

// ── Component ─────────────────────────────────────────────────

export function NavPidPanel() {
  const {
    values: state, setValues, loading, error, hasLoaded, dirty,
    connected, isArmed, lockMessage, read, write,
  } = useSettingsParams<NavPidState>({
    panelId: "inav-nav-pid",
    initial: DEFAULT,
    read: readNavPid,
    write: writeNavPid,
    supported: settingsSupported,
    unsupportedMessage: "Settings not available on this firmware",
  });

  function updateGroup(group: keyof NavPidState, key: keyof PidGroup, value: number) {
    setValues((prev) => ({ ...prev, [group]: { ...prev[group], [key]: value } }));
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="Nav PID"
          subtitle="iNav navigation controller PID gains"
          icon={<Settings2 size={16} />}
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
          <div className="space-y-5">
            {GROUPS.map(({ key, label }) => (
              <fieldset key={key} className="rounded border border-border-default p-3">
                <legend className="px-1 text-[10px] font-mono text-text-tertiary uppercase tracking-wider">
                  {label}
                </legend>
                <div className="grid grid-cols-3 gap-3 mt-1">
                  {(["p", "i", "d"] as const).map((term) => (
                    <label key={term} className="flex flex-col gap-1">
                      <span className="text-[10px] text-text-tertiary font-mono uppercase">{term}</span>
                      <input
                        type="number"
                        min={0}
                        max={255}
                        step={1}
                        value={state[key][term]}
                        onChange={(e) => updateGroup(key, term, parseInt(e.target.value) || 0)}
                        onBlur={(e) => updateGroup(key, term, clampU8(parseInt(e.target.value) || 0))}
                        className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                      />
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
