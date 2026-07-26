import { useEffect, useState } from "react";
import { useTelemetryStore } from "@/stores/telemetry-store";

type SignalQuality = "excellent" | "good" | "fair" | "poor" | "lost" | "unknown";

interface ConnectionQualityResult {
  /** Estimated latency in ms */
  latencyMs: number;
  /** Packet loss percentage (0-100) */
  packetLoss: number;
  /** RSSI value (0-255) */
  rssi: number;
  /** Remote RSSI */
  remoteRssi: number;
  /** TX buffer usage % */
  txBuf: number;
  /** Noise floor */
  noise: number;
  /** Overall signal quality rating */
  quality: SignalQuality;
  /** Signal strength as percentage (0-100) */
  signalStrength: number;
}

function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

function deriveQuality(strength: number, hasData: boolean): SignalQuality {
  if (!hasData) return "unknown";
  if (strength > 80) return "excellent";
  if (strength > 60) return "good";
  if (strength > 40) return "fair";
  if (strength > 20) return "poor";
  return "lost";
}

export function useConnectionQuality(): ConnectionQualityResult {
  const radio = useTelemetryStore((s) => s.radio);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  void tick;

  const latest = radio.latest();

  if (!latest) {
    return {
      latencyMs: 0,
      packetLoss: 0,
      rssi: 0,
      remoteRssi: 0,
      txBuf: 0,
      noise: 0,
      quality: "unknown",
      signalStrength: 0,
    };
  }

  const rssi = latest.rssi;
  const noise = latest.noise;
  const remoteRssi = latest.remrssi;
  const txBuf = latest.txbuf;
  const rxerrors = latest.rxerrors;

  // Signal strength: SNR-based percentage
  const snr = rssi - noise;
  const signalStrength = clamp((snr / 60) * 100, 0, 100);

  // Rough packet loss from rxerrors (normalized, capped)
  const packetLoss = clamp(rxerrors / 10, 0, 100);

  // Estimate latency from txbuf usage (higher buffer = more latency)
  const latencyMs = Math.round(clamp((100 - txBuf) * 2, 0, 500));

  const quality = deriveQuality(signalStrength, true);

  return {
    latencyMs,
    packetLoss,
    rssi,
    remoteRssi,
    txBuf,
    noise,
    quality,
    signalStrength,
  };
}
