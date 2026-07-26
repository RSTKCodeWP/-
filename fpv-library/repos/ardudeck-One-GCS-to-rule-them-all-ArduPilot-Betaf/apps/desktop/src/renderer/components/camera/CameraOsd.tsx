/**
 * On-video OSD overlay. Each layer is independently toggleable (see the OSD
 * menu in CameraPanel). Layers are absolutely positioned over the video and
 * never intercept pointer events — clicks fall through to the video for
 * gimbal point-at-target.
 *
 * Telemetry comes from the per-vehicle fleet view-model so it works for any
 * vehicle (active or grid tile). The conformal artificial horizon needs
 * roll/pitch, which only the active vehicle exposes, so it renders only there.
 */

import type { OsdLayers } from '../../../shared/camera-types';
import type { FleetVehicle } from '../../hooks/useFleet';
import { formatCoord } from './geolocation';

interface CameraOsdProps {
  layers: OsdLayers;
  vehicle: FleetVehicle | null;
  /** Roll/pitch in degrees for the artificial horizon (active vehicle only). */
  attitude?: { roll: number; pitch: number } | null;
  /** Frame-center ground coordinate, when projectable. */
  frameCenter?: { lat: number; lon: number } | null;
}

export function CameraOsd({ layers, vehicle, attitude, frameCenter }: CameraOsdProps) {
  return (
    <div className="pointer-events-none absolute inset-0 select-none font-mono text-[11px] text-white/90"
      style={{ textShadow: '0 1px 2px rgba(0,0,0,0.9)' }}>
      {layers.artificialHorizon && attitude && <ArtificialHorizon roll={attitude.roll} pitch={attitude.pitch} />}

      {layers.crosshair && <Crosshair />}

      {layers.cornerTelemetry && vehicle && (
        <>
          {/* Top-left: identity + mode */}
          <div className="absolute top-2 left-2 leading-tight">
            <div className="text-sm font-semibold">{vehicle.label}</div>
            <div className={vehicle.armed ? 'text-red-400' : 'text-white/70'}>
              {vehicle.armed ? 'ARMED' : 'DISARMED'} · {vehicle.mode}
            </div>
          </div>
          {/* Top-right: battery */}
          <div className="absolute top-2 right-2 text-right leading-tight">
            <div>{vehicle.batteryPct != null ? `${vehicle.batteryPct.toFixed(0)}%` : '--'}</div>
          </div>
          {/* Bottom-left: alt + speed */}
          <div className="absolute bottom-2 left-2 leading-tight">
            <div>ALT {vehicle.altitudeAgl.toFixed(1)} m</div>
            <div>SPD {vehicle.groundspeed.toFixed(1)} m/s</div>
          </div>
        </>
      )}

      {layers.northIndicator && vehicle && <NorthIndicator headingDeg={vehicle.heading} />}

      {layers.frameCenterCoords && frameCenter && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 mt-5 whitespace-nowrap text-[10px]">
          {formatCoord(frameCenter.lat, frameCenter.lon)}
        </div>
      )}
    </div>
  );
}

function Crosshair() {
  return (
    <svg className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" width="48" height="48" viewBox="0 0 48 48">
      <g stroke="white" strokeWidth="1.5" opacity="0.85" style={{ filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.9))' }}>
        <line x1="24" y1="6" x2="24" y2="18" />
        <line x1="24" y1="30" x2="24" y2="42" />
        <line x1="6" y1="24" x2="18" y2="24" />
        <line x1="30" y1="24" x2="42" y2="24" />
        <circle cx="24" cy="24" r="2" fill="white" stroke="none" />
      </g>
    </svg>
  );
}

/** Compass rose lower-left showing the camera/vehicle facing. */
function NorthIndicator({ headingDeg }: { headingDeg: number }) {
  return (
    <div className="absolute bottom-2 right-2">
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle cx="22" cy="22" r="20" fill="rgba(0,0,0,0.35)" stroke="white" strokeOpacity="0.5" strokeWidth="1" />
        <g transform={`rotate(${-headingDeg} 22 22)`}>
          <polygon points="22,4 26,22 22,18 18,22" fill="#ef4444" />
          <text x="22" y="14" textAnchor="middle" fontSize="8" fill="white">N</text>
        </g>
      </svg>
    </div>
  );
}

/** Conformal horizon line + roll for forward-looking cameras. */
function ArtificialHorizon({ roll, pitch }: { roll: number; pitch: number }) {
  // Pitch shifts the line vertically (~1.5% of frame per degree); roll rotates it.
  const pitchOffset = Math.max(-40, Math.min(40, pitch * 1.5));
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div
        className="absolute left-1/2 top-1/2 w-[200%] -translate-x-1/2 -translate-y-1/2"
        style={{ transform: `translate(-50%, calc(-50% + ${pitchOffset}%)) rotate(${-roll}deg)` }}
      >
        <div className="h-px w-full bg-cyan-300/70" />
      </div>
    </div>
  );
}
