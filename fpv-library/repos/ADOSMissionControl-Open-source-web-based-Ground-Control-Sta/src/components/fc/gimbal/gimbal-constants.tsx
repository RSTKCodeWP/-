import React from "react";

export const GIMBAL_PARAMS: string[] = [];

export const OPTIONAL_GIMBAL_PARAMS = [
  "MNT1_TYPE", "MNT1_PITCH_MIN", "MNT1_PITCH_MAX",
  "MNT1_ROLL_MIN", "MNT1_ROLL_MAX",
  "MNT1_YAW_MIN", "MNT1_YAW_MAX",
  "MNT1_RC_RATE", "MNT1_DEFLT_MODE",
  "MNT1_RC_IN_TILT", "MNT1_RC_IN_ROLL", "MNT1_RC_IN_PAN",
];

export const RC_INPUT_CHANNEL_OPTIONS = [
  { value: "0", label: "0 — Disabled" },
  { value: "5", label: "Channel 5" },
  { value: "6", label: "Channel 6" },
  { value: "7", label: "Channel 7" },
  { value: "8", label: "Channel 8" },
  { value: "9", label: "Channel 9" },
  { value: "10", label: "Channel 10" },
  { value: "11", label: "Channel 11" },
  { value: "12", label: "Channel 12" },
  { value: "13", label: "Channel 13" },
  { value: "14", label: "Channel 14" },
  { value: "15", label: "Channel 15" },
  { value: "16", label: "Channel 16" },
];

export const MNT_TYPE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — Servo" },
  { value: "6", label: "6 — SToRM32 MAVLink" },
  { value: "7", label: "7 — Alexmos" },
  { value: "8", label: "8 — SiYi" },
  { value: "9", label: "9 — Scripting" },
];

export const MNT_MODE_OPTIONS = [
  { value: "0", label: "0 — Retract" },
  { value: "1", label: "1 — Neutral" },
  { value: "2", label: "2 — MAVLink Targeting" },
  { value: "3", label: "3 — RC Targeting" },
  { value: "4", label: "4 — GPS Point" },
  { value: "5", label: "5 — SysID Target" },
  { value: "6", label: "6 — Home Location" },
];

export function GimbalCard({
  icon,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border-default bg-bg-secondary p-4 space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-accent-primary">{icon}</span>
        <div>
          <h2 className="text-sm font-medium text-text-primary">{title}</h2>
          <p className="text-[10px] text-text-tertiary">{description}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

export function LiveStat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div>
      <span className="text-[10px] text-text-tertiary block">{label}</span>
      <span className="text-sm font-mono text-text-primary">
        {value}
        <span className="text-[10px] text-text-tertiary ml-0.5">{unit}</span>
      </span>
    </div>
  );
}
