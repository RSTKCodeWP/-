/**
 * Sensor calibration quick-launch row inside the System tab Hardware
 * section. Each tile deep-links the operator to the corresponding
 * calibration wizard inside the Configure tab.
 *
 * @license GPL-3.0-only
 */

"use client";

import { Activity, Compass, RotateCw, Radio, ExternalLink } from "lucide-react";

const CALIBRATION_TILES: { label: string; icon: typeof Activity; href: string }[] = [
  { label: "Accelerometer", icon: Activity, href: "/config?panel=calibration&type=accel" },
  { label: "Compass", icon: Compass, href: "/config?panel=calibration&type=compass" },
  { label: "Gyroscope", icon: RotateCw, href: "/config?panel=calibration&type=gyro" },
  { label: "Level Horizon", icon: Activity, href: "/config?panel=calibration&type=level" },
  { label: "RC Input", icon: Radio, href: "/config?panel=calibration&type=rc" },
];

export function CalibrationLauncher() {
  return (
    <div className="border border-border-default rounded-lg p-4 bg-bg-secondary">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-3">
        Sensor Calibration
      </h4>
      <div className="flex flex-wrap gap-2">
        {CALIBRATION_TILES.map(({ label, icon: Icon, href }) => (
          <a
            key={label}
            href={href}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-border-default rounded-lg hover:border-accent-primary hover:text-accent-primary text-text-secondary transition-colors"
          >
            <Icon size={12} />
            {label}
            <ExternalLink size={10} className="text-text-tertiary" />
          </a>
        ))}
      </div>
      <p className="text-[10px] text-text-tertiary mt-2">
        Opens calibration wizard in the Configure tab
      </p>
    </div>
  );
}
