"use client";

import type { CalibrationState } from "./calibration-types";
import { LEVEL_STEPS } from "./calibration-types";
import { CalibrationWizard } from "./CalibrationWizard";
import { CalibrationRebootBanner } from "./CalibrationRebootBanner";
import { Button } from "@/components/ui/button";
import { useDroneManager } from "@/stores/drone-manager";

interface PX4CalibrationsSectionProps {
  px4QuickLevel: CalibrationState;
  px4GnssMagCal: CalibrationState;
  startPx4QuickLevel: () => void;
  startPx4GnssMagCal: () => void;
  cancelCalibration: (type: string, setter: React.Dispatch<React.SetStateAction<CalibrationState>>) => void;
  setPx4QuickLevel: React.Dispatch<React.SetStateAction<CalibrationState>>;
}

export function PX4CalibrationsSection({
  px4QuickLevel,
  px4GnssMagCal,
  startPx4QuickLevel,
  startPx4GnssMagCal,
  cancelCalibration,
  setPx4QuickLevel,
}: PX4CalibrationsSectionProps) {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);

  return (
    <>
      <div>
        <h2 className="text-sm font-display font-semibold text-text-primary mt-2 mb-1">PX4-Only Calibrations</h2>
        <p className="text-[10px] text-text-tertiary mb-4">
          Additional calibration options available on PX4 firmware
        </p>
      </div>

      {/* PX4 Quick Level */}
      <CalibrationWizard
        title="Quick Level (PX4)"
        description="Set level reference from current orientation. Place vehicle level before starting."
        steps={LEVEL_STEPS}
        currentStep={px4QuickLevel.currentStep}
        status={px4QuickLevel.status}
        progress={px4QuickLevel.progress}
        statusMessage={px4QuickLevel.message}
        onStart={startPx4QuickLevel}
        onCancel={() => cancelCalibration("level", setPx4QuickLevel)}
      />

      {/* PX4 Quick Level Reboot Banner */}
      {px4QuickLevel.needsReboot && px4QuickLevel.status === "success" && (
        <CalibrationRebootBanner label="Quick level calibration saved" onReboot={() => { const p = getSelectedProtocol(); if (p) p.reboot(); }} />
      )}

      {/* PX4 GNSS Mag Cal */}
      <CalibrationWizard
        title="GNSS Mag Calibration (PX4)"
        description="Calibrate compass yaw using GPS heading. Requires good GPS fix. No rotation needed."
        steps={[{ label: "GPS Fix", description: "Ensure the vehicle has a solid GPS fix outdoors" }]}
        currentStep={px4GnssMagCal.currentStep}
        status={px4GnssMagCal.status}
        progress={px4GnssMagCal.progress}
        statusMessage={px4GnssMagCal.message}
        preTips={[
          "Ensure vehicle is outdoors with clear sky view",
          "Wait for good GPS fix (>6 satellites) before starting",
          "Point vehicle nose in a known direction",
          "This calibration is quick and does not require rotation",
        ]}
        onStart={startPx4GnssMagCal}
      />

      {/* GNSS Mag Cal Reboot Banner */}
      {px4GnssMagCal.needsReboot && px4GnssMagCal.status === "success" && (
        <CalibrationRebootBanner label="GNSS mag calibration saved" onReboot={() => { const p = getSelectedProtocol(); if (p) p.reboot(); }} />
      )}

      {/* PX4 Thermal Calibration — deferred */}
      <div className="mt-4 p-3 rounded-md bg-bg-tertiary border border-border-default opacity-50">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-text-secondary">Thermal Calibration</div>
            <div className="text-[10px] text-text-tertiary">Requires cold-start hardware workflow. Coming in a future release.</div>
          </div>
          <Button size="sm" disabled>
            Start
          </Button>
        </div>
      </div>
    </>
  );
}
