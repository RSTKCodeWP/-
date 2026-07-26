/**
 * Source configuration popover. Add a feed for the current vehicle from a
 * preset (SIYI / Herelink / RunCam / RubyFPV / RTSP / UVC / …), edit its url /
 * label / FOV, pick which configured source is live, and remove sources.
 */

import { useEffect, useState } from 'react';
import { useCameraStore, sourcesForVehicle } from '../../stores/camera-store';
import { CAMERA_PRESETS, presetById } from './camera-presets';
import { WfbngSetupGuide } from './WfbngSetupGuide';
import type { CameraSourceConfig, GimbalControlMode } from '../../../shared/camera-types';
import { DEFAULT_GIMBAL_CONFIG } from '../../../shared/camera-types';

interface CameraSourceMenuProps {
  vehicleKey: string | null;
  onClose: () => void;
}

export function CameraSourceMenu({ vehicleKey, onClose }: CameraSourceMenuProps) {
  const store = useCameraStore();
  const sources = vehicleKey ? sourcesForVehicle(store, vehicleKey) : [];
  const selectedId = vehicleKey ? store.selectedByVehicle[vehicleKey] : undefined;
  const [presetId, setPresetId] = useState(CAMERA_PRESETS[0]?.id ?? 'mavlink');
  const [uvcDevices, setUvcDevices] = useState<MediaDeviceInfo[]>([]);

  const preset = presetById(presetId);

  useEffect(() => {
    if (preset?.kind !== 'uvc') return;
    void navigator.mediaDevices.enumerateDevices().then((d) =>
      setUvcDevices(d.filter((x) => x.kind === 'videoinput')),
    );
  }, [preset?.kind]);

  if (!vehicleKey) {
    return (
      <Shell onClose={onClose}>
        <p className="text-xs text-content-secondary">Select a vehicle to configure its camera feeds.</p>
      </Shell>
    );
  }

  const addFromPreset = (deviceId?: string) => {
    if (!preset) return;
    const source: CameraSourceConfig = {
      id: crypto.randomUUID(),
      vehicleKey,
      kind: preset.kind,
      label: preset.label,
      preset: preset.id,
      ...(preset.url ? { url: preset.url } : {}),
      ...(preset.hfovDeg ? { hfovDeg: preset.hfovDeg } : {}),
      ...(deviceId ? { deviceId } : {}),
      lowLatency: true,
    };
    store.addSource(source);
  };

  return (
    <Shell onClose={onClose}>
      {/* Add new */}
      <div className="mb-3">
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-content-secondary">Add a feed</div>
        <div className="flex gap-1.5">
          <select
            value={presetId}
            onChange={(e) => setPresetId(e.target.value)}
            className="min-w-0 flex-1 rounded border border-default bg-surface-input px-2 py-1 text-xs text-content"
          >
            {CAMERA_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          {preset?.kind !== 'uvc' && (
            <button onClick={() => addFromPreset()} className="rounded bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-500">Add</button>
          )}
        </div>
        {preset?.note && <p className="mt-1 text-[10px] leading-tight text-content-tertiary">{preset.note}</p>}
        {preset?.kind === 'wfbng' && <WfbngSetupGuide port={5600} />}
        {preset?.kind === 'uvc' && (
          <div className="mt-1.5 flex flex-col gap-1">
            {uvcDevices.length === 0 && <span className="text-[10px] text-content-tertiary">No capture devices detected.</span>}
            {uvcDevices.map((d) => (
              <button
                key={d.deviceId}
                onClick={() => addFromPreset(d.deviceId)}
                className="rounded bg-surface-raised px-2 py-1 text-left text-[11px] text-content hover:bg-surface-raised"
              >{d.label || `Camera ${d.deviceId.slice(0, 6)}`}</button>
            ))}
          </div>
        )}
      </div>

      {/* Configured sources */}
      <div className="text-[10px] font-medium uppercase tracking-wider text-content-secondary">Feeds for this vehicle</div>
      {sources.length === 0 && <p className="mt-1 text-xs text-content-tertiary">None yet.</p>}
      <div className="mt-1 flex flex-col gap-2">
        {sources.map((s) => (
          <SourceRow
            key={s.id}
            source={s}
            selected={s.id === selectedId}
            onSelect={() => store.setSelectedSource(vehicleKey, s.id)}
            onChange={(patch) => store.updateSource(s.id, patch)}
            onRemove={() => store.removeSource(s.id)}
          />
        ))}
      </div>

      <GimbalSection vehicleKey={vehicleKey} />
    </Shell>
  );
}

function GimbalSection({ vehicleKey }: { vehicleKey: string }) {
  const store = useCameraStore();
  const cfg = store.gimbalByVehicle[vehicleKey] ?? DEFAULT_GIMBAL_CONFIG;
  const info = store.gimbalInfo[vehicleKey];

  return (
    <div className="mt-3 border-t border-subtle pt-2">
      <div className="text-[10px] font-medium uppercase tracking-wider text-content-secondary">Gimbal</div>
      <div className="mt-1 flex items-center gap-2 text-[11px] text-content">
        <label className="flex flex-1 items-center gap-1" title="How the GCS commands the mount. Auto/Manager use the MAVLink gimbal manager (ArduPilot 4.1+). Mount control uses DO_MOUNT_CONTROL for legacy mounts. RC-driven = flown from the transmitter (display only). Off hides the controls.">
          Control
          <select
            value={cfg.mode}
            onChange={(e) => store.setGimbalConfig(vehicleKey, { mode: e.target.value as GimbalControlMode })}
            className="min-w-0 flex-1 rounded bg-surface-input px-1 py-0.5 text-content"
          >
            <option value="auto">Auto (MAVLink)</option>
            <option value="manager">MAVLink manager</option>
            <option value="mount">Mount control (legacy)</option>
            <option value="rc">RC-driven (display only)</option>
            <option value="off">Off / no gimbal</option>
          </select>
        </label>
        <label className="flex items-center gap-1" title="Which mount instance to command (0 = all gimbals, 1 = MNT1, 2 = MNT2).">
          Mount
          <select
            value={cfg.deviceId}
            onChange={(e) => store.setGimbalConfig(vehicleKey, { deviceId: Number(e.target.value) })}
            className="rounded bg-surface-input px-1 py-0.5 text-content"
          >
            <option value={0}>All</option>
            <option value={1}>1</option>
            <option value={2}>2</option>
          </select>
        </label>
      </div>
      {info && (
        <p className="mt-1 text-[10px] text-content-tertiary">
          Detected manager · pitch {info.pitchMinDeg.toFixed(0)}…{info.pitchMaxDeg.toFixed(0)}°, yaw {info.yawMinDeg.toFixed(0)}…{info.yawMaxDeg.toFixed(0)}°
        </p>
      )}
    </div>
  );
}

function SourceRow({ source, selected, onSelect, onChange, onRemove }: {
  source: CameraSourceConfig;
  selected: boolean;
  onSelect: () => void;
  onChange: (patch: Partial<CameraSourceConfig>) => void;
  onRemove: () => void;
}) {
  return (
    <div className={`rounded-lg border p-2 ${selected ? 'border-blue-500/60 bg-blue-500/5' : 'border-subtle bg-surface'}`}>
      <div className="flex items-center gap-2">
        <input
          type="radio"
          checked={selected}
          onChange={onSelect}
          className="accent-blue-500"
          title="Make this the live feed"
        />
        <input
          value={source.label}
          onChange={(e) => onChange({ label: e.target.value })}
          className="min-w-0 flex-1 rounded bg-surface-input px-1.5 py-0.5 text-xs text-content"
        />
        <button onClick={onRemove} className="text-content-tertiary hover:text-red-400" title="Remove feed">✕</button>
      </div>
      {source.kind !== 'uvc' && source.kind !== 'mavlink' && (
        <input
          value={source.url ?? ''}
          onChange={(e) => onChange({ url: e.target.value })}
          placeholder="rtsp://…"
          className="mt-1 w-full rounded bg-surface-input px-1.5 py-0.5 font-mono text-[11px] text-content"
        />
      )}
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-content-secondary">
        <span className="uppercase">{source.kind}</span>
        <label className="flex items-center gap-1">
          HFOV
          <input
            type="number"
            value={source.hfovDeg ?? ''}
            onChange={(e) => onChange({ hfovDeg: e.target.value ? Number(e.target.value) : undefined })}
            placeholder="°"
            className="w-12 rounded bg-surface-input px-1 py-0.5 text-content"
            title="Horizontal field of view — needed for click-to-point accuracy"
          />
        </label>
        {source.kind === 'wfbng' && (
          <>
            <label className="flex items-center gap-1" title="Dongle: ArduDeck receives directly with the plugged-in dongle. Network: a separate ground station forwards video to the udp url.">
              Via
              <select
                value={source.wfbMode ?? 'dongle'}
                onChange={(e) => onChange({ wfbMode: e.target.value as 'dongle' | 'network' })}
                className="rounded bg-surface-input px-1 py-0.5 text-content"
              >
                <option value="dongle">Dongle</option>
                <option value="network">Network</option>
              </select>
            </label>
            <label className="flex items-center gap-1" title="Codec the camera sends. WiFiLink 2 defaults to H.265.">
              Codec
              <select
                value={source.wfbCodec ?? 'h265'}
                onChange={(e) => onChange({ wfbCodec: e.target.value as 'h265' | 'h264' })}
                className="rounded bg-surface-input px-1 py-0.5 text-content"
              >
                <option value="h265">H.265</option>
                <option value="h264">H.264</option>
              </select>
            </label>
            <label className="flex items-center gap-1" title="Convert to H.264 so the stream can render (required for H.265; costs some CPU)">
              <input
                type="checkbox"
                checked={source.wfbTranscode ?? (source.wfbCodec ?? 'h265') === 'h265'}
                onChange={(e) => onChange({ wfbTranscode: e.target.checked })}
                className="accent-blue-500"
              />
              Convert
            </label>
          </>
        )}
        {(source.kind === 'rtsp' || source.kind === 'mavlink') && (
          <label className="flex items-center gap-1" title="RTSP transport: Auto negotiates UDP then falls back to TCP. UDP = lowest latency on a clean LAN; TCP = reliable through firewalls / lossy links.">
            RTSP
            <select
              value={source.rtspTransport ?? 'automatic'}
              onChange={(e) => onChange({ rtspTransport: e.target.value as 'automatic' | 'tcp' | 'udp' })}
              className="rounded bg-surface-input px-1 py-0.5 text-content"
            >
              <option value="automatic">Auto</option>
              <option value="udp">UDP</option>
              <option value="tcp">TCP</option>
            </select>
          </label>
        )}
        <label className="ml-auto flex items-center gap-1" title="Low-latency: small jitter buffer, drop late frames">
          <input type="checkbox" checked={source.lowLatency ?? false} onChange={(e) => onChange({ lowLatency: e.target.checked })} className="accent-blue-500" />
          Low latency
        </label>
      </div>
    </div>
  );
}

function Shell({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-30" onClick={onClose} />
      <div className="absolute right-2 top-9 z-40 w-96 max-w-[calc(100vw-1rem)] max-h-[calc(100vh-6rem)] overflow-y-auto overflow-x-hidden rounded-xl border border-default bg-surface-solid p-3 shadow-xl">
        {children}
      </div>
    </>
  );
}
