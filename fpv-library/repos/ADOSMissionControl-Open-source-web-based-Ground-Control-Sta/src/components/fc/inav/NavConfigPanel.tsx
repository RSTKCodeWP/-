/**
 * @module NavConfigPanel
 * @description iNav navigation configuration via the named settings system.
 * Reads and writes nav_* settings through the DroneProtocol settings surface.
 * @license GPL-3.0-only
 */

"use client";

import { PanelHeader } from "../shared/PanelHeader";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Navigation, Upload } from "lucide-react";
import { useSettingsParams } from "@/hooks/use-settings-params";
import type { DroneProtocol } from "@/lib/protocol/types";
import { settingNumber } from "@/lib/protocol/types";

// ── Types ─────────────────────────────────────────────────────

interface NavState {
  navMinRadError: number;
  navAutoSpeed: number;
  navManualSpeed: number;
  navMaxBankAngle: number;
  navUserControlMode: number;
  navPositionTimeout: number;
}

const DEFAULT: NavState = {
  navMinRadError: 100,
  navAutoSpeed: 300,
  navManualSpeed: 500,
  navMaxBankAngle: 40,
  navUserControlMode: 0,
  navPositionTimeout: 5,
};

const USER_CONTROL_OPTIONS = [
  { value: "0", label: "Position hold" },
  { value: "1", label: "Cruise" },
];

// ── Helpers ───────────────────────────────────────────────────

const settingsSupported = (p: DroneProtocol): boolean => !!p.settings;

async function readNavConfig(protocol: DroneProtocol): Promise<NavState> {
  const settings = protocol.settings!;
  const [minRad, autoSpd, manSpd, bankAngle, ctrlMode, posTimeout] = await Promise.all([
    settings.getSetting("nav_min_circle_dist"),
    settings.getSetting("nav_auto_speed"),
    settings.getSetting("nav_manual_speed"),
    settings.getSetting("nav_max_bank_angle"),
    settings.getSetting("nav_user_control_mode"),
    settings.getSetting("nav_position_timeout"),
  ]);
  return {
    navMinRadError: settingNumber(minRad),
    navAutoSpeed: settingNumber(autoSpd),
    navManualSpeed: settingNumber(manSpd),
    navMaxBankAngle: settingNumber(bankAngle),
    navUserControlMode: settingNumber(ctrlMode),
    navPositionTimeout: settingNumber(posTimeout),
  };
}

async function writeNavConfig(protocol: DroneProtocol, state: NavState): Promise<void> {
  const settings = protocol.settings!;
  await settings.setSetting("nav_min_circle_dist", state.navMinRadError);
  await settings.setSetting("nav_auto_speed", state.navAutoSpeed);
  await settings.setSetting("nav_manual_speed", state.navManualSpeed);
  await settings.setSetting("nav_max_bank_angle", state.navMaxBankAngle);
  await settings.setSetting("nav_user_control_mode", state.navUserControlMode);
  await settings.setSetting("nav_position_timeout", state.navPositionTimeout);
}

// ── Component ─────────────────────────────────────────────────

export function NavConfigPanel() {
  const {
    values: state, setValues, loading, error, hasLoaded, dirty,
    connected, isArmed, lockMessage, read, write,
  } = useSettingsParams<NavState>({
    panelId: "inav-nav-config",
    initial: DEFAULT,
    read: readNavConfig,
    write: writeNavConfig,
    supported: settingsSupported,
    unsupportedMessage: "Settings not available on this firmware",
  });

  function update<K extends keyof NavState>(key: K, value: NavState[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="Navigation Config"
          subtitle="iNav position hold and navigation speed settings"
          icon={<Navigation size={16} />}
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
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary font-mono">Min circle dist (cm)</span>
                <input
                  type="number"
                  min={100}
                  max={50000}
                  value={state.navMinRadError}
                  onChange={(e) => update("navMinRadError", parseInt(e.target.value) || 0)}
                  onBlur={(e) => update("navMinRadError", Math.min(50000, Math.max(100, parseInt(e.target.value) || 100)))}
                  className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary font-mono">Auto speed (cm/s)</span>
                <input
                  type="number"
                  min={100}
                  max={2500}
                  value={state.navAutoSpeed}
                  onChange={(e) => update("navAutoSpeed", parseInt(e.target.value) || 0)}
                  onBlur={(e) => update("navAutoSpeed", Math.min(2500, Math.max(100, parseInt(e.target.value) || 100)))}
                  className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary font-mono">Manual speed (cm/s)</span>
                <input
                  type="number"
                  min={100}
                  max={2500}
                  value={state.navManualSpeed}
                  onChange={(e) => update("navManualSpeed", parseInt(e.target.value) || 0)}
                  onBlur={(e) => update("navManualSpeed", Math.min(2500, Math.max(100, parseInt(e.target.value) || 100)))}
                  className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary font-mono">Max bank angle (deg)</span>
                <input
                  type="number"
                  min={5}
                  max={80}
                  value={state.navMaxBankAngle}
                  onChange={(e) => update("navMaxBankAngle", parseInt(e.target.value) || 0)}
                  onBlur={(e) => update("navMaxBankAngle", Math.min(80, Math.max(5, parseInt(e.target.value) || 5)))}
                  className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary font-mono">Position timeout (s)</span>
                <input
                  type="number"
                  min={0}
                  max={60}
                  value={state.navPositionTimeout}
                  onChange={(e) => update("navPositionTimeout", parseInt(e.target.value) || 0)}
                  onBlur={(e) => update("navPositionTimeout", Math.min(60, Math.max(0, parseInt(e.target.value) || 0)))}
                  className="bg-bg-tertiary border border-border-default rounded px-2 py-1 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-primary"
                />
              </label>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] text-text-tertiary font-mono">User control mode</span>
                <Select
                  label=""
                  options={USER_CONTROL_OPTIONS}
                  value={String(state.navUserControlMode)}
                  onChange={(v) => update("navUserControlMode", parseInt(v))}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
