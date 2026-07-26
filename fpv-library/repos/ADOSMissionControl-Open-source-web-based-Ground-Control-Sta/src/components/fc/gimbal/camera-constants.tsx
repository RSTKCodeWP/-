import React from "react";

export const CAMERA_PARAMS: string[] = [];

export const OPTIONAL_CAMERA_PARAMS = [
  "CAM1_TYPE", "CAM1_DURATION", "CAM1_SERVO_OFF", "CAM1_SERVO_ON", "CAM1_TRIGG_DIST",
];

export const CAM_TYPE_OPTIONS = [
  { value: "0", label: "0 — None" },
  { value: "1", label: "1 — Servo" },
  { value: "2", label: "2 — Relay" },
  { value: "3", label: "3 — GoPro" },
  { value: "4", label: "4 — Mount (SIYI)" },
  { value: "5", label: "5 — MAVLink" },
  { value: "6", label: "6 — Scripting" },
];

export function CameraCard({
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
