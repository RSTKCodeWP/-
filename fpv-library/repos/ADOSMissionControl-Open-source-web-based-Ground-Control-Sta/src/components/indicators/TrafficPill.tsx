/**
 * @module TrafficPill
 * @description Compact pill showing ADS-B traffic count from iNav.
 * Opens a popover with per-vehicle details on click.
 * Fires a warning toast when a vehicle is within 500 m.
 * @license GPL-3.0-only
 */
"use client";

import { useState, useEffect, useRef } from "react";
import { useTelemetryStore } from "@/stores/telemetry-store";
import { useDroneManager } from "@/stores/drone-manager";
import { useTelemetryFreshness } from "@/hooks/use-telemetry-freshness";
import { useToast } from "@/components/ui/toast";
import type { INavAdsbVehicle } from "@/lib/protocol/msp/msp-decoders-inav";

// ── Proximity constants ──────────────────────────────────────

const PROXIMITY_ALERT_RANGE_M = 500;
const TOAST_COOLDOWN_MS = 30_000;

// ── Distance helper ──────────────────────────────────────────

function haversineMeters(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6_371_000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ── Vehicle row ──────────────────────────────────────────────

function VehicleRow({ vehicle, ownLat, ownLon }: { vehicle: INavAdsbVehicle; ownLat: number | null; ownLon: number | null }) {
  const distM =
    ownLat !== null && ownLon !== null
      ? haversineMeters(ownLat, ownLon, vehicle.lat, vehicle.lon)
      : null;
  const distLabel = distM !== null ? `${(distM / 1000).toFixed(2)} km` : "--";
  const altLabel = `${vehicle.alt} cm`;

  return (
    <div className="flex items-start justify-between gap-3 py-1 border-b border-border-default last:border-0">
      <span className="text-[10px] font-mono text-text-primary">{vehicle.callsign || "(no callsign)"}</span>
      <div className="text-right shrink-0">
        <div className="text-[9px] text-text-secondary">{distLabel}</div>
        <div className="text-[9px] text-text-tertiary">{altLabel}</div>
        <div className="text-[9px] text-text-tertiary">TTL {vehicle.ttlSec}s</div>
      </div>
    </div>
  );
}

// ── Component ────────────────────────────────────────────────

export function TrafficPill() {
  const getProtocol = useDroneManager((s) => s.getSelectedProtocol);
  const protocol = getProtocol();
  const firmwareType = protocol?.getVehicleInfo()?.firmwareType;

  const vehicles = useTelemetryStore((s) => s.adsbVehicles);
  const { toast } = useToast();
  const { getFreshness } = useTelemetryFreshness();

  const [open, setOpen] = useState(false);
  const pillRef = useRef<HTMLButtonElement>(null);

  // Track which ICAO codes have recently fired a proximity toast
  const alertedRef = useRef<Map<number, number>>(new Map());

  // Get own drone position for distance calculations
  const positionFresh = getFreshness("position") !== "none";
  const latestPosition = useTelemetryStore((s) => s.position.latest() ?? null);

  const ownLat = positionFresh && latestPosition ? latestPosition.lat : null;
  const ownLon = positionFresh && latestPosition ? latestPosition.lon : null;

  // Proximity alert check
  useEffect(() => {
    if (firmwareType !== "inav" || ownLat === null || ownLon === null) return;

    const now = Date.now();

    for (const v of vehicles) {
      const distM = haversineMeters(ownLat, ownLon, v.lat, v.lon);
      if (distM <= PROXIMITY_ALERT_RANGE_M) {
        const lastAlert = alertedRef.current.get(v.icao) ?? 0;
        if (now - lastAlert > TOAST_COOLDOWN_MS) {
          alertedRef.current.set(v.icao, now);
          const label = v.callsign || `ICAO ${v.icao}`;
          toast(`Traffic nearby: ${label} at ${Math.round(distM)} m`, "warning");
        }
      }
    }
  }, [vehicles, ownLat, ownLon, firmwareType, toast]);

  // Close popover on outside click
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (pillRef.current && !pillRef.current.closest("[data-traffic-pill]")?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  if (firmwareType !== "inav" || vehicles.length === 0) return null;

  return (
    <div className="relative" data-traffic-pill="">
      <button
        ref={pillRef}
        onClick={() => setOpen((v) => !v)}
        aria-label={`ADS-B traffic nearby: ${vehicles.length} aircraft`}
        aria-expanded={open}
        aria-haspopup="listbox"
        className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono border bg-status-warning/10 border-status-warning/30 text-status-warning cursor-pointer hover:bg-status-warning/20 transition-colors"
      >
        Traffic: {vehicles.length}
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 w-56 bg-bg-secondary border border-border-default shadow-lg p-2">
          <p className="text-[9px] text-text-tertiary mb-1 uppercase tracking-wider">Nearby traffic</p>
          {vehicles.map((v) => (
            <VehicleRow key={v.icao} vehicle={v} ownLat={ownLat} ownLon={ownLon} />
          ))}
        </div>
      )}
    </div>
  );
}
