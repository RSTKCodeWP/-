"use client";

/**
 * @module BusSetupSection
 * @description CAN port + protocol + SLCAN passthrough parameter editor.
 *
 * Three cards: CAN1 (CAN_P1_*, CAN_D1_*), CAN2 (CAN_P2_*, CAN_D2_*),
 * and SLCAN passthrough (CAN_SLCAN_*). Each parameter row carries a
 * description tooltip and either a Select for enumerated values or
 * a numeric Input for ranges.
 *
 * The Save and Write-to-Flash buttons at the bottom call into
 * `useParamPanelActions`, matching the established Power panel pattern.
 *
 * The "Enter SLCAN mode" button at the foot of the SLCAN card hands off
 * to the SLCAN flash arbiter (`enterSlcanMode`). The arbiter writes the
 * four `CAN_SLCAN_*` params, decides between reboot-and-poll (F4) or
 * MAV_CMD_CAN_FORWARD hot-switch (F7/H7/G4), opens the SLCAN session, and
 * returns an `exitFn` for the page to invoke when the operator clicks
 * "Resume MAVLink" (driven from the top-of-shell banner).
 *
 * @license GPL-3.0-only
 */

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { HardDrive, Power, Save, Network, ShieldAlert, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useFcPanelState } from "@/hooks/use-fc-panel-state";
import { useParamPanelActions } from "@/hooks/use-param-panel-actions";
import { enterSlcanMode } from "@/lib/protocol/transport/slcan-flash-arbiter";
import { useDroneManager } from "@/stores/drone-manager";
import { useSlcanModeStore } from "@/stores/slcan-mode-store";

const BUS_SETUP_PARAMS = [
  "CAN_P1_DRIVER",
  "CAN_P1_BITRATE",
  "CAN_P1_FDBITRATE",
  "CAN_P1_OPTIONS",
  "CAN_D1_PROTOCOL",
  "CAN_D1_UC_NODE",
  "CAN_D1_UC_OPTION",
  "CAN_P2_DRIVER",
  "CAN_P2_BITRATE",
  "CAN_P2_FDBITRATE",
  "CAN_D2_PROTOCOL",
  "CAN_D2_UC_NODE",
  "CAN_D2_UC_OPTION",
  "CAN_SLCAN_CPORT",
  "CAN_SLCAN_SERNUM",
  "CAN_SLCAN_TIMOUT",
  "CAN_SLCAN_OVRIDE",
] as const;

// Every parameter is treated as optional — non-CAN-capable firmware
// builds may not expose all 17 names and we don't want a missing
// FDBITRATE to throw the whole panel into an error state.
const OPTIONAL_BUS_SETUP_PARAMS = [...BUS_SETUP_PARAMS] as string[];

const DRIVER_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "1", label: "1 — First driver" },
  { value: "2", label: "2 — Second driver" },
  { value: "3", label: "3 — Third driver" },
];

const FD_BITRATE_OPTIONS = [
  { value: "1", label: "1 — 1 Mbit/s" },
  { value: "2", label: "2 — 2 Mbit/s" },
  { value: "4", label: "4 — 4 Mbit/s" },
  { value: "5", label: "5 — 5 Mbit/s" },
  { value: "8", label: "8 — 8 Mbit/s" },
];

const PROTOCOL_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "1", label: "1 — DroneCAN" },
  { value: "4", label: "4 — PiccoloCAN" },
  { value: "5", label: "5 — CAN Tester" },
  { value: "6", label: "6 — EFI NWPMU" },
  { value: "7", label: "7 — USD1" },
  { value: "8", label: "8 — KDECAN" },
  { value: "10", label: "10 — Scripting" },
  { value: "11", label: "11 — Benewake" },
  { value: "12", label: "12 — Scripting 2" },
];

const SLCAN_CPORT_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "1", label: "1 — CAN1" },
  { value: "2", label: "2 — CAN2" },
];

const SLCAN_SERIAL_OPTIONS = [
  { value: "-1", label: "-1 — Disabled" },
  { value: "0", label: "0 — Serial0 (USB)" },
  { value: "1", label: "1 — Serial1" },
  { value: "2", label: "2 — Serial2" },
  { value: "3", label: "3 — Serial3" },
  { value: "4", label: "4 — Serial4" },
  { value: "5", label: "5 — Serial5" },
  { value: "6", label: "6 — Serial6" },
];

const BITRATE_QUICK_PICKS = [1_000_000, 500_000, 250_000, 125_000];

interface ParamCellProps {
  label: string;
  description?: string;
  missing: boolean;
  children: React.ReactNode;
}

function ParamCell({ label, description, missing, children }: ParamCellProps) {
  return (
    <div className={missing ? "opacity-40" : ""}>
      <label className="text-[11px] text-text-secondary mb-1 block">
        {label}
        {missing && <span className="ml-1 text-text-tertiary">(not present)</span>}
      </label>
      {children}
      {description && (
        <p className="text-[10px] text-text-tertiary mt-1">{description}</p>
      )}
    </div>
  );
}

export function BusSetupSection() {
  const t = useTranslations("canConfig.busSetup");
  const tParam = useTranslations("canConfig.busSetup.param");

  const paramNames = useMemo(() => [...BUS_SETUP_PARAMS], []);
  const optionalParams = useMemo(() => OPTIONAL_BUS_SETUP_PARAMS, []);

  const panelState = useFcPanelState({
    paramNames,
    optionalParams,
    panelId: "can-bus-setup",
    autoLoad: true,
  });
  const {
    params,
    loading,
    error,
    dirtyParams,
    hasRamWrites,
    hasLoaded,
    getProtocol,
    missingOptional,
    refresh,
    setLocalValue,
  } = panelState;
  const { saving, save: handleSave, flash: handleFlash } = useParamPanelActions(panelState);

  const connected = !!getProtocol();
  const hasDirty = dirtyParams.size > 0;
  const slcanReboot = dirtyParams.has("CAN_SLCAN_CPORT");

  const [slcanConfirmOpen, setSlcanConfirmOpen] = useState(false);
  const [rebootPending, setRebootPending] = useState(false);
  const [rebootStatus, setRebootStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  const get = (name: string, fallback = "0") => String(params.get(name) ?? fallback);
  const setNum = (name: string, v: string) => setLocalValue(name, Number(v) || 0);
  const isMissing = (name: string) => missingOptional.has(name);

  // Subscribe only to stable primitives. `getSelectedDrone()` returned a
  // fresh object in tests with mocked store state, which made the snapshot
  // selector unstable and triggered an infinite render loop via
  // useSyncExternalStore. The drone itself is read imperatively inside
  // event handlers where reactivity is not needed.
  const selectedDroneId = useDroneManager((s) => s.selectedDroneId);
  const drones = useDroneManager((s) => s.drones);
  const selectedDrone = selectedDroneId
    ? drones.get(selectedDroneId) ?? null
    : null;
  const slcanState = useSlcanModeStore((s) => s.state);

  const enterSlcan = async () => {
    setSlcanConfirmOpen(false);
    const protocol = getProtocol();
    const drone = useDroneManager.getState().getSelectedDrone();
    if (!protocol || !drone) return;
    if (drone.transport?.type !== "webserial") {
      setRebootStatus("error");
      return;
    }
    // Mirror the desired params locally for UI continuity. The arbiter
    // writes the same four params on the FC before flipping the mode.
    setLocalValue("CAN_SLCAN_CPORT", 1);
    setLocalValue("CAN_SLCAN_SERNUM", 0);
    setLocalValue("CAN_SLCAN_TIMOUT", 300);
    setLocalValue("CAN_SLCAN_OVRIDE", 1);
    try {
      await enterSlcanMode({
        protocol,
        droneId: drone.id,
        bus: 1,
        bitrate: 1_000_000,
        timeoutSec: 300,
      });
      setRebootPending(false);
    } catch {
      // Arbiter has already pushed an error message into the store; the
      // banner surfaces it. Leave the panel in a passive state.
    }
  };

  const rebootFc = async () => {
    const protocol = getProtocol();
    if (!protocol) return;
    setRebootStatus("sending");
    try {
      await protocol.reboot();
      setRebootStatus("sent");
      setRebootPending(false);
    } catch {
      setRebootStatus("error");
    }
  };

  const labelFor = (param: string) => {
    const labelKey = `${param}.label` as const;
    return `${param} — ${tParam(labelKey)}`;
  };

  const descFor = (param: string) => tParam(`${param}.description`);

  return (
    <div className="space-y-4">
      {error && (
        <p className="text-xs text-status-error">{error}</p>
      )}

      {!connected && (
        <p className="text-xs text-text-tertiary">
          {t("notConnected")}
        </p>
      )}

      {loading && !hasLoaded && (
        <p className="text-xs text-text-tertiary">{t("loading")}</p>
      )}

      {/* CAN1 */}
      <Card>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Network size={14} className="text-accent-primary" />
            <h3 className="text-sm font-medium text-text-primary">{t("can1Title")}</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <ParamCell label={labelFor("CAN_P1_DRIVER")} description={descFor("CAN_P1_DRIVER")} missing={isMissing("CAN_P1_DRIVER")}>
              <Select options={DRIVER_OPTIONS} value={get("CAN_P1_DRIVER")} onChange={(v) => setNum("CAN_P1_DRIVER", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_P1_BITRATE")} description={descFor("CAN_P1_BITRATE")} missing={isMissing("CAN_P1_BITRATE")}>
              <div className="space-y-1">
                <Input
                  type="number"
                  step={1000}
                  min={10000}
                  max={1000000}
                  value={get("CAN_P1_BITRATE", "1000000")}
                  onChange={(e) => setNum("CAN_P1_BITRATE", e.target.value)}
                />
                <div className="flex flex-wrap gap-1">
                  {BITRATE_QUICK_PICKS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      className="px-2 py-0.5 text-[10px] border border-border-default rounded hover:border-accent-primary text-text-secondary hover:text-accent-primary transition-colors"
                      onClick={() => setLocalValue("CAN_P1_BITRATE", preset)}
                    >
                      {(preset / 1000).toLocaleString()}k
                    </button>
                  ))}
                </div>
              </div>
            </ParamCell>

            <ParamCell label={labelFor("CAN_P1_FDBITRATE")} description={descFor("CAN_P1_FDBITRATE")} missing={isMissing("CAN_P1_FDBITRATE")}>
              <Select options={FD_BITRATE_OPTIONS} value={get("CAN_P1_FDBITRATE", "1")} onChange={(v) => setNum("CAN_P1_FDBITRATE", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_P1_OPTIONS")} description={descFor("CAN_P1_OPTIONS")} missing={isMissing("CAN_P1_OPTIONS")}>
              <Input type="number" step={1} min={0} value={get("CAN_P1_OPTIONS")} onChange={(e) => setNum("CAN_P1_OPTIONS", e.target.value)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_D1_PROTOCOL")} description={descFor("CAN_D1_PROTOCOL")} missing={isMissing("CAN_D1_PROTOCOL")}>
              <Select options={PROTOCOL_OPTIONS} value={get("CAN_D1_PROTOCOL")} onChange={(v) => setNum("CAN_D1_PROTOCOL", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_D1_UC_NODE")} description={descFor("CAN_D1_UC_NODE")} missing={isMissing("CAN_D1_UC_NODE")}>
              <Input type="number" step={1} min={1} max={125} value={get("CAN_D1_UC_NODE", "10")} onChange={(e) => setNum("CAN_D1_UC_NODE", e.target.value)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_D1_UC_OPTION")} description={descFor("CAN_D1_UC_OPTION")} missing={isMissing("CAN_D1_UC_OPTION")}>
              <Input type="number" step={1} min={0} value={get("CAN_D1_UC_OPTION")} onChange={(e) => setNum("CAN_D1_UC_OPTION", e.target.value)} />
            </ParamCell>
          </div>
        </div>
      </Card>

      {/* CAN2 */}
      <Card>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Network size={14} className="text-accent-primary" />
            <h3 className="text-sm font-medium text-text-primary">{t("can2Title")}</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <ParamCell label={labelFor("CAN_P2_DRIVER")} description={descFor("CAN_P2_DRIVER")} missing={isMissing("CAN_P2_DRIVER")}>
              <Select options={DRIVER_OPTIONS} value={get("CAN_P2_DRIVER")} onChange={(v) => setNum("CAN_P2_DRIVER", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_P2_BITRATE")} description={descFor("CAN_P2_BITRATE")} missing={isMissing("CAN_P2_BITRATE")}>
              <div className="space-y-1">
                <Input
                  type="number"
                  step={1000}
                  min={10000}
                  max={1000000}
                  value={get("CAN_P2_BITRATE", "1000000")}
                  onChange={(e) => setNum("CAN_P2_BITRATE", e.target.value)}
                />
                <div className="flex flex-wrap gap-1">
                  {BITRATE_QUICK_PICKS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      className="px-2 py-0.5 text-[10px] border border-border-default rounded hover:border-accent-primary text-text-secondary hover:text-accent-primary transition-colors"
                      onClick={() => setLocalValue("CAN_P2_BITRATE", preset)}
                    >
                      {(preset / 1000).toLocaleString()}k
                    </button>
                  ))}
                </div>
              </div>
            </ParamCell>

            <ParamCell label={labelFor("CAN_P2_FDBITRATE")} description={descFor("CAN_P2_FDBITRATE")} missing={isMissing("CAN_P2_FDBITRATE")}>
              <Select options={FD_BITRATE_OPTIONS} value={get("CAN_P2_FDBITRATE", "1")} onChange={(v) => setNum("CAN_P2_FDBITRATE", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_D2_PROTOCOL")} description={descFor("CAN_D2_PROTOCOL")} missing={isMissing("CAN_D2_PROTOCOL")}>
              <Select options={PROTOCOL_OPTIONS} value={get("CAN_D2_PROTOCOL")} onChange={(v) => setNum("CAN_D2_PROTOCOL", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_D2_UC_NODE")} description={descFor("CAN_D2_UC_NODE")} missing={isMissing("CAN_D2_UC_NODE")}>
              <Input type="number" step={1} min={1} max={125} value={get("CAN_D2_UC_NODE", "10")} onChange={(e) => setNum("CAN_D2_UC_NODE", e.target.value)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_D2_UC_OPTION")} description={descFor("CAN_D2_UC_OPTION")} missing={isMissing("CAN_D2_UC_OPTION")}>
              <Input type="number" step={1} min={0} value={get("CAN_D2_UC_OPTION")} onChange={(e) => setNum("CAN_D2_UC_OPTION", e.target.value)} />
            </ParamCell>
          </div>
        </div>
      </Card>

      {/* SLCAN passthrough */}
      <Card>
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Terminal size={14} className="text-accent-primary" />
            <h3 className="text-sm font-medium text-text-primary">{t("slcanTitle")}</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <ParamCell label={labelFor("CAN_SLCAN_CPORT")} description={descFor("CAN_SLCAN_CPORT")} missing={isMissing("CAN_SLCAN_CPORT")}>
              <Select options={SLCAN_CPORT_OPTIONS} value={get("CAN_SLCAN_CPORT")} onChange={(v) => setNum("CAN_SLCAN_CPORT", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_SLCAN_SERNUM")} description={descFor("CAN_SLCAN_SERNUM")} missing={isMissing("CAN_SLCAN_SERNUM")}>
              <Select options={SLCAN_SERIAL_OPTIONS} value={get("CAN_SLCAN_SERNUM", "-1")} onChange={(v) => setNum("CAN_SLCAN_SERNUM", v)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_SLCAN_TIMOUT")} description={descFor("CAN_SLCAN_TIMOUT")} missing={isMissing("CAN_SLCAN_TIMOUT")}>
              <Input type="number" step={1} min={0} max={127} unit="s" value={get("CAN_SLCAN_TIMOUT")} onChange={(e) => setNum("CAN_SLCAN_TIMOUT", e.target.value)} />
            </ParamCell>

            <ParamCell label={labelFor("CAN_SLCAN_OVRIDE")} description={descFor("CAN_SLCAN_OVRIDE")} missing={isMissing("CAN_SLCAN_OVRIDE")}>
              <Select
                options={[
                  { value: "0", label: "0 — Off" },
                  { value: "1", label: "1 — Override on" },
                ]}
                value={get("CAN_SLCAN_OVRIDE")}
                onChange={(v) => setNum("CAN_SLCAN_OVRIDE", v)}
              />
            </ParamCell>
          </div>

          <div className="pt-1">
            <Button
              variant="secondary"
              size="sm"
              icon={<ShieldAlert size={12} />}
              onClick={() => setSlcanConfirmOpen(true)}
              disabled={
                !connected ||
                slcanState !== "IDLE" ||
                selectedDrone?.transport?.type !== "webserial"
              }
            >
              {t("enterSlcan")}
            </Button>
          </div>
        </div>
      </Card>

      {/* Save / Flash row */}
      <div className="flex flex-wrap items-center gap-3 pt-2">
        <Button
          variant="primary"
          size="lg"
          icon={<Save size={14} />}
          disabled={!hasDirty || !connected}
          loading={saving}
          onClick={handleSave}
        >
          {t("saveToRam")}
        </Button>
        {hasRamWrites && (
          <Button variant="secondary" size="lg" icon={<HardDrive size={14} />} onClick={handleFlash}>
            {t("commitToFlash")}
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={refresh} disabled={!connected || loading}>
          {t("reloadFromFc")}
        </Button>
        {hasDirty && <span className="text-[10px] text-status-warning">{t("dirty")}</span>}
        {(slcanReboot || rebootPending) && (
          <>
            <span className="text-[10px] text-status-warning">{t("rebootRequired")}</span>
            <Button
              variant="secondary"
              size="sm"
              icon={<Power size={12} />}
              onClick={rebootFc}
              disabled={!connected || rebootStatus === "sending"}
              loading={rebootStatus === "sending"}
            >
              {t("rebootFc")}
            </Button>
          </>
        )}
        {rebootStatus === "sent" && (
          <span className="text-[10px] text-status-success">{t("rebootSent")}</span>
        )}
        {rebootStatus === "error" && (
          <span className="text-[10px] text-status-error">{t("rebootFailed")}</span>
        )}
      </div>

      <ConfirmDialog
        open={slcanConfirmOpen}
        onConfirm={enterSlcan}
        onCancel={() => setSlcanConfirmOpen(false)}
        title={t("enterSlcan")}
        message={t("enterSlcanConfirm")}
        variant="danger"
      />
    </div>
  );
}
