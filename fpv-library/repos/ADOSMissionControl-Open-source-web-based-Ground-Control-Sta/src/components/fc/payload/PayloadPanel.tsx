"use client";

import { Grab } from "lucide-react";
import { ParamFieldsPanel, type ParamSection } from "../shared/ParamFieldsPanel";

const SECTIONS: ParamSection[] = [
  {
    title: "Gripper",
    fields: [
      { param: "GRIP_ENABLE", label: "Gripper Enable", kind: "enum" },
      { param: "GRIP_TYPE", label: "Gripper Type", kind: "enum" },
      { param: "GRIP_GRAB", label: "Grab PWM (us)", kind: "number", min: 1000, max: 2000, step: 1 },
      { param: "GRIP_RELEASE", label: "Release PWM (us)", kind: "number", min: 1000, max: 2000, step: 1 },
      { param: "GRIP_NEUTRAL", label: "Neutral PWM (us)", kind: "number", min: 1000, max: 2000, step: 1 },
      { param: "GRIP_AUTOCLOSE", label: "Auto-close Time (s)", kind: "number", min: 0, max: 30, step: 0.5 },
    ],
  },
];

export function PayloadPanel() {
  return (
    <ParamFieldsPanel
      panelId="payload"
      title="Gripper / Payload"
      subtitle="Servo or EPM gripper release for pick-and-drop payloads"
      icon={<Grab size={16} />}
      sectionIcon={<Grab size={14} />}
      sections={SECTIONS}
      gate={{
        param: "GRIP_ENABLE",
        off: (v) => v === 0,
        message: "No gripper is configured (GRIP_ENABLE = 0).",
      }}
    />
  );
}
