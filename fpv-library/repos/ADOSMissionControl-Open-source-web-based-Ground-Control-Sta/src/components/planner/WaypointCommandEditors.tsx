/**
 * @module WaypointCommandEditors
 * @description Command-specific parameter editors for the WaypointListItem expanded section.
 * @license GPL-3.0-only
 */
"use client";

import { useTranslations } from "next-intl";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type { Waypoint } from "@/lib/types";
import { INAV_WP_ACTION } from "@/lib/protocol/msp/msp-decoders-inav";

/** The subset of parameter fields the command editors read directly. Both a
 * navigation `Waypoint` and an attached `MissionAction` satisfy this shape, so
 * the same per-command editors drive waypoint params and action params alike. */
export interface EditableParams {
  param1?: number;
  param2?: number;
  param3?: number;
}

/** The fields the per-command editors commit; a superset of both a waypoint's
 * and an action's editable params (holdTime only ever fires for nav commands). */
type EditableField = "param1" | "param2" | "param3" | "holdTime";

interface CmdEditorProps {
  cmd: string;
  params: EditableParams;
  localParam1: string;
  localParam2: string;
  localParam3: string;
  localHoldTime: string;
  setLocalParam1: (v: string) => void;
  setLocalParam2: (v: string) => void;
  setLocalParam3: (v: string) => void;
  setLocalHoldTime: (v: string) => void;
  commitField: (field: EditableField, value: string) => void;
  onUpdate: (update: EditableParams) => void;
}

interface INavActionEditorProps {
  action: number;
  waypoint: Waypoint;
  localParam1: string;
  localParam2: string;
  localParam3: string;
  localHoldTime: string;
  setLocalParam1: (v: string) => void;
  setLocalParam2: (v: string) => void;
  setLocalParam3: (v: string) => void;
  setLocalHoldTime: (v: string) => void;
  commitField: (field: keyof Waypoint, value: string) => void;
  onUpdate: (update: Partial<Waypoint>) => void;
}

export function CommandSpecificEditors({
  cmd, params, localParam1, localParam2, localParam3, localHoldTime,
  setLocalParam1, setLocalParam2, setLocalParam3, setLocalHoldTime,
  commitField, onUpdate,
}: CmdEditorProps) {
  const t = useTranslations("planner");
  return (
    <>
      {(cmd === "LOITER" || cmd === "LOITER_TIME" || cmd === "SPLINE_WAYPOINT") && (
        <Input label={t("holdTime")} type="number" unit="s" placeholder="0"
          value={localHoldTime} onChange={(e) => setLocalHoldTime(e.target.value)}
          onBlur={() => commitField("holdTime", localHoldTime)} />
      )}
      {cmd === "LOITER_TURNS" && (
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("turns")} type="number" placeholder="1" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Input label={t("radius")} type="number" unit="m" placeholder="0" value={localParam3}
            onChange={(e) => setLocalParam3(e.target.value)} onBlur={() => commitField("param3", localParam3)} />
        </div>
      )}
      {cmd === "CONDITION_YAW" && (
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("angle")} type="number" unit="deg" placeholder="0" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Input label={t("rate")} type="number" unit="deg/s" placeholder="0" value={localParam2}
            onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
        </div>
      )}
      {cmd === "DO_SET_CAM_TRIGG" && (
        <Input label={t("triggerDistance")} type="number" unit="m" placeholder="0" value={localParam1}
          onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
      )}
      {cmd === "DO_SET_SERVO" && (
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("servoNum")} type="number" placeholder="5" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Input label={t("pwm")} type="number" unit="us" placeholder="1500" value={localParam2}
            onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
        </div>
      )}
      {cmd === "DO_MOUNT_CONTROL" && (
        <div className="grid grid-cols-3 gap-2">
          <Input label={t("pitch")} type="number" unit="deg" placeholder="0" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Input label={t("roll")} type="number" unit="deg" placeholder="0" value={localParam2}
            onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
          <Input label={t("yaw")} type="number" unit="deg" placeholder="0" value={localParam3}
            onChange={(e) => setLocalParam3(e.target.value)} onBlur={() => commitField("param3", localParam3)} />
        </div>
      )}
      {cmd === "DO_GRIPPER" && (
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("gripperNum")} type="number" placeholder="1" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Select label={t("action")} options={[{ value: "0", label: t("release") }, { value: "1", label: t("grab") }]}
            value={String(params.param2 ?? 0)} onChange={(v) => onUpdate({ param2: parseInt(v) })} />
        </div>
      )}
      {cmd === "DO_WINCH" && (
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("winchNum")} type="number" placeholder="1" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Input label={t("length")} type="number" unit="m" placeholder="0" value={localParam3}
            onChange={(e) => setLocalParam3(e.target.value)} onBlur={() => commitField("param3", localParam3)} />
        </div>
      )}
      {cmd === "DO_FENCE_ENABLE" && (
        <Select label={t("fence")} options={[{ value: "0", label: t("disable") }, { value: "1", label: t("enable") }]}
          value={String(params.param1 ?? 1)} onChange={(v) => onUpdate({ param1: parseInt(v) })} />
      )}
      {cmd === "NAV_PAYLOAD_PLACE" && (
        <Input label={t("maxDescent")} type="number" unit="m" placeholder="10" value={localParam1}
          onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
      )}
      {cmd === "CONDITION_DISTANCE" && (
        <Input label={t("distance")} type="number" unit="m" placeholder="0" value={localParam1}
          onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
      )}
      {cmd === "DO_AUX_FUNCTION" && (
        <div className="grid grid-cols-2 gap-2">
          <Input label={t("functionNum")} type="number" placeholder="0" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <Select label={t("switch")}
            options={[{ value: "0", label: t("low") }, { value: "1", label: t("mid") }, { value: "2", label: t("high") }]}
            value={String(params.param2 ?? 0)} onChange={(v) => onUpdate({ param2: parseInt(v) })} />
        </div>
      )}
      {cmd === "DELAY" && (
        <Input label={t("delay")} type="number" unit="s" placeholder="0" value={localParam1}
          onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
      )}
      {cmd === "DO_SET_SPEED" && (
        <Input label={t("speed")} type="number" unit="m/s" placeholder="5" value={localParam2}
          onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
      )}
      {cmd === "DO_LAND_START" && (
        <p className="text-[9px] text-text-tertiary italic">
          Marks the start of a fixed-wing landing sequence. The flight controller uses this
          to begin the landing approach. Generated by the Landing Pattern tool.
        </p>
      )}
    </>
  );
}

// ── iNav action parameter hints ───────────────────────────────

export function INavActionEditors({
  action, waypoint,
  localParam1, localParam2, localParam3, localHoldTime,
  setLocalParam1, setLocalParam2, setLocalParam3, setLocalHoldTime,
  commitField, onUpdate,
}: INavActionEditorProps) {
  return (
    <>
      {action === INAV_WP_ACTION.POSHOLD_TIME && (
        <div className="flex flex-col gap-1">
          <Input label="Hold time" type="number" unit="s" placeholder="0"
            value={localHoldTime} onChange={(e) => setLocalHoldTime(e.target.value)}
            onBlur={() => commitField("holdTime", localHoldTime)} />
          <span className="text-[9px] text-text-tertiary">
            Time to loiter at this position before continuing.
          </span>
        </div>
      )}
      {action === INAV_WP_ACTION.JUMP && (
        <div className="flex flex-col gap-1.5">
          <div className="grid grid-cols-2 gap-2">
            <Input label="Target WP" type="number" placeholder="1" value={localParam1}
              onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
            <Input label="Repeat" type="number" placeholder="1" value={localParam2}
              onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
          </div>
          <span className="text-[9px] text-text-tertiary">
            Target is a 1-based waypoint number. Repeat 0 means infinite loop.
          </span>
          {localParam2 && Number(localParam2) === 0 && (
            <span className="text-[9px] text-status-warning">Repeat count 0 causes infinite loop</span>
          )}
        </div>
      )}
      {action === INAV_WP_ACTION.SET_POI && (
        <span className="text-[9px] text-text-tertiary">
          Points the gimbal at this coordinate. The aircraft continues to the next waypoint.
        </span>
      )}
      {action === INAV_WP_ACTION.SET_HEAD && (
        <div className="flex flex-col gap-1">
          <Input label="Heading" type="number" unit="deg" placeholder="0" value={localParam1}
            onChange={(e) => setLocalParam1(e.target.value)} onBlur={() => commitField("param1", localParam1)} />
          <span className="text-[9px] text-text-tertiary">
            Locks aircraft heading until the next SET_HEAD or RTH. Use -1 to cancel.
          </span>
        </div>
      )}
      {action === INAV_WP_ACTION.WAYPOINT && (
        <div className="flex flex-col gap-1">
          <Input label="Speed" type="number" unit="cm/s" placeholder="0 (default)" value={localParam2}
            onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
          <span className="text-[9px] text-text-tertiary">
            Override speed for this waypoint leg. 0 uses the mission default.
          </span>
        </div>
      )}
      {action === INAV_WP_ACTION.POSHOLD_UNLIM && (
        <span className="text-[9px] text-text-tertiary">
          Loiters at this position indefinitely. Mission does not advance automatically.
        </span>
      )}
      {action === INAV_WP_ACTION.RTH && (
        <span className="text-[9px] text-text-tertiary">
          Returns to home from this waypoint. Mission ends after landing.
        </span>
      )}
      {action === INAV_WP_ACTION.LAND && (
        <div className="flex flex-col gap-1.5">
          <div className="grid grid-cols-2 gap-2">
            <Input label="Elevation" type="number" unit="m" placeholder="0 (auto)" value={localParam2}
              onChange={(e) => setLocalParam2(e.target.value)} onBlur={() => commitField("param2", localParam2)} />
            <Select label="Altitude datum"
              options={[{ value: "0", label: "Relative (takeoff)" }, { value: "1", label: "Absolute (MSL)" }]}
              value={String((waypoint.param3 ?? 0) & 1)}
              onChange={(v) => onUpdate({ param3: ((waypoint.param3 ?? 0) & ~1) | (parseInt(v) & 1) })} />
          </div>
          <span className="text-[9px] text-text-tertiary">
            Final waypoint. Site elevation 0 uses the takeoff/home elevation. Approach direction and
            landing heading are configured in the FW Approach panel.
          </span>
        </div>
      )}
      {/* Props not used in every branch. Kept in signature for API consistency */}
      {(void localParam3, void localHoldTime, void waypoint, void setLocalParam3, void setLocalHoldTime, void onUpdate, null)}
    </>
  );
}
