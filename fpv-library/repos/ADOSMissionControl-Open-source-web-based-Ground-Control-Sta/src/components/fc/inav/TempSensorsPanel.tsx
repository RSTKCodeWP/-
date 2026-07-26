/**
 * @module TempSensorsPanel
 * @description iNav temperature sensor configuration viewer.
 * Reads sensor type and address from the FC and shows live readings
 * when available. Read-only display panel.
 * @license GPL-3.0-only
 */

"use client";

import { useCallback, useState } from "react";
import { useDroneManager } from "@/stores/drone-manager";
import { PanelHeader } from "../shared/PanelHeader";
import { Thermometer } from "lucide-react";
import type { INavTempSensorConfigEntry } from "@/lib/protocol/msp/msp-decoders-inav";

// ── Constants ─────────────────────────────────────────────────

const SENSOR_TYPE_LABELS: Record<number, string> = {
  0: "None",
  1: "LM75",
  2: "DS18B20",
};

function sensorTypeLabel(type: number): string {
  return SENSOR_TYPE_LABELS[type] ?? `Type ${type}`;
}

function addrHex(addr: number[]): string {
  return addr.map((b) => b.toString(16).padStart(2, "0").toUpperCase()).join(":");
}

// ── Component ─────────────────────────────────────────────────

export function TempSensorsPanel() {
  const getSelectedProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const connected = !!getSelectedProtocol();

  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sensors, setSensors] = useState<INavTempSensorConfigEntry[]>([]);

  const handleRead = useCallback(async () => {
    const protocol = getSelectedProtocol();
    if (!protocol?.getTempSensorConfigs) { setError("Temperature sensor config not supported"); return; }
    setLoading(true); setError(null);
    try {
      const data = await protocol.getTempSensorConfigs();
      setSensors(data); setHasLoaded(true);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [getSelectedProtocol]);

  const activeSensors = sensors.filter((s) => s.type !== 0);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl space-y-4">
        <PanelHeader
          title="Temperature Sensors"
          subtitle="1-Wire and I2C temperature sensor configuration"
          icon={<Thermometer size={16} />}
          loading={loading}
          loadProgress={null}
          hasLoaded={hasLoaded}
          onRead={handleRead}
          connected={connected}
          error={error}
        />

        {hasLoaded && (
          <div className="space-y-2">
            {activeSensors.length === 0 && (
              <p className="text-xs text-text-tertiary font-mono">
                No temperature sensors configured on this FC.
              </p>
            )}
            {sensors.map((sensor, idx) => (
              sensor.type === 0 ? null : (
                <div
                  key={idx}
                  className="border border-border-default rounded p-3 space-y-1 bg-surface-primary"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-text-primary">
                      Sensor {idx + 1}
                    </span>
                    <span className="text-[10px] font-mono text-accent-primary">
                      {sensorTypeLabel(sensor.type)}
                    </span>
                  </div>
                  <p className="text-[10px] font-mono text-text-tertiary">
                    Address: {addrHex(sensor.address)}
                  </p>
                  <p className="text-[10px] font-mono text-text-tertiary">
                    Alarm: {(sensor.alarmMin / 10).toFixed(1)}°C : {(sensor.alarmMax / 10).toFixed(1)}°C
                  </p>
                  {sensor.label && (
                    <p className="text-[10px] font-mono text-text-tertiary">
                      Label: {sensor.label}
                    </p>
                  )}
                </div>
              )
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
