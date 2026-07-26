/**
 * TrafficSettingsCard — provider configuration for the ADS-B + glider overlays.
 *
 * Non-secret config (enable flags, URLs, hosts, preset, proximity thresholds) is
 * persisted via setTrafficConfig; API keys / OpenSky credentials go through the
 * existing encrypted secret store (getApiKey/setApiKey). Enabling a source here
 * only configures it — the map overlay toggles ('Traffic' / 'Gliders') start and
 * stop the live feed.
 */

import { useEffect, useState } from 'react';
import {
  ADSB_API_PRESETS,
  DEFAULT_TRAFFIC_CONFIG,
  TRAFFIC_SECRET_SERVICES,
  type AdsbApiPreset,
  type AlertZone,
  type RemoteIdShape,
  type TrafficConfig,
} from '../../../shared/traffic-types';
import { useTrafficStore } from '../../stores/traffic-store';

const inputCls =
  'px-3 py-1.5 bg-surface-input border border-border rounded-lg text-sm text-content placeholder-content-tertiary focus:outline-none focus:border-blue-500';

function Toggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={`w-9 h-5 rounded-full transition-colors relative flex-shrink-0 ${on ? 'bg-blue-600' : 'bg-surface-raised'}`}
    >
      <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all ${on ? 'left-[18px]' : 'left-0.5'}`} />
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs text-content-secondary mb-1">{label}</span>
      {children}
    </label>
  );
}

export function TrafficSettingsCard() {
  const [cfg, setCfg] = useState<TrafficConfig>(DEFAULT_TRAFFIC_CONFIG);
  const [adsbxKey, setAdsbxKey] = useState('');
  const [customKey, setCustomKey] = useState('');
  const [openSkyCreds, setOpenSkyCreds] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    void window.electronAPI?.getTrafficConfig().then((c) => c && setCfg(c));
    void window.electronAPI?.getApiKey(TRAFFIC_SECRET_SERVICES.adsbexchange).then((r) => r?.hasKey && setAdsbxKey(r.key));
    void window.electronAPI?.getApiKey(TRAFFIC_SECRET_SERVICES.custom).then((r) => r?.hasKey && setCustomKey(r.key));
    void window.electronAPI?.getApiKey(TRAFFIC_SECRET_SERVICES.openSky).then((r) => r?.hasKey && setOpenSkyCreds(r.key));
  }, []);

  const patch = (p: Partial<TrafficConfig>): void => setCfg((c) => ({ ...c, ...p }));

  const save = async (): Promise<void> => {
    await window.electronAPI?.setTrafficConfig(cfg);
    await window.electronAPI?.setApiKey(TRAFFIC_SECRET_SERVICES.adsbexchange, adsbxKey.trim());
    await window.electronAPI?.setApiKey(TRAFFIC_SECRET_SERVICES.custom, customKey.trim());
    await window.electronAPI?.setApiKey(TRAFFIC_SECRET_SERVICES.openSky, openSkyCreds.trim());
    // Apply view-affecting settings to the live map immediately.
    useTrafficStore.getState().setProximity(cfg.proximity);
    useTrafficStore.getState().setAltitudeBand(cfg.altitudeFilter);
    useTrafficStore.getState().setIconScale(cfg.iconScale);
    useTrafficStore.getState().setAlertZones(cfg.alertZones);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const preset = ADSB_API_PRESETS[cfg.adsbApi.preset];

  return (
    <div className="bg-surface rounded-xl border border-subtle p-5 mt-4">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center">
          <svg className="w-4 h-4 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V9m0 0l8 5V7.5a.75.75 0 00-1.1-.66L12 9zm0 0L5.1 6.84A.75.75 0 004 7.5V14l8-5z" />
          </svg>
        </div>
        <div>
          <h3 className="text-sm font-medium text-content">Traffic & Gliders</h3>
          <p className="text-xs text-content-secondary">ADS-B and OGN sources — toggle a layer on the map to go live</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Local ADS-B receiver */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm text-content font-medium">Local ADS-B receiver</div>
            <Toggle on={cfg.localAdsb.enabled} onChange={(v) => patch({ localAdsb: { ...cfg.localAdsb, enabled: v } })} />
          </div>
          <Field label="aircraft.json URL (dump1090 / readsb / tar1090)">
            <input
              className={`${inputCls} w-full`}
              value={cfg.localAdsb.url}
              onChange={(e) => patch({ localAdsb: { ...cfg.localAdsb, url: e.target.value } })}
              placeholder="http://localhost:8080/data/aircraft.json"
            />
          </Field>
        </div>

        {/* Hosted ADS-B API */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm text-content font-medium">Hosted ADS-B API</div>
            <Toggle on={cfg.adsbApi.enabled} onChange={(v) => patch({ adsbApi: { ...cfg.adsbApi, enabled: v } })} />
          </div>
          <Field label="Provider">
            <select
              className={`${inputCls} w-full`}
              value={cfg.adsbApi.preset}
              onChange={(e) => patch({ adsbApi: { ...cfg.adsbApi, preset: e.target.value as AdsbApiPreset } })}
            >
              {Object.values(ADSB_API_PRESETS).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </Field>
          {cfg.adsbApi.preset === 'custom' && (
            <>
              <Field label="Endpoint URL ({lat} {lon} {radiusNm} substituted)">
                <input
                  className={`${inputCls} w-full`}
                  value={cfg.adsbApi.customUrl}
                  onChange={(e) => patch({ adsbApi: { ...cfg.adsbApi, customUrl: e.target.value } })}
                  placeholder="https://example.com/api/lat/{lat}/lon/{lon}/dist/{radiusNm}"
                />
              </Field>
              <Field label="API key header name (optional)">
                <input
                  className={`${inputCls} w-full`}
                  value={cfg.adsbApi.customKeyHeader}
                  onChange={(e) => patch({ adsbApi: { ...cfg.adsbApi, customKeyHeader: e.target.value } })}
                  placeholder="X-API-Key"
                />
              </Field>
              <Field label="API key (optional)">
                <input type="password" className={`${inputCls} w-full`} value={customKey} onChange={(e) => setCustomKey(e.target.value)} placeholder="Paste key" />
              </Field>
            </>
          )}
          {cfg.adsbApi.preset === 'adsbexchange' && (
            <Field label="RapidAPI key">
              <input type="password" className={`${inputCls} w-full`} value={adsbxKey} onChange={(e) => setAdsbxKey(e.target.value)} placeholder="Paste RapidAPI key" />
            </Field>
          )}
          {!preset.needsKey && cfg.adsbApi.preset !== 'custom' && (
            <p className="text-xs text-content-tertiary">No key required.</p>
          )}
        </div>

        {/* OpenSky */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm text-content font-medium">OpenSky Network</div>
            <Toggle on={cfg.openSky.enabled} onChange={(v) => patch({ openSky: { ...cfg.openSky, enabled: v } })} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-content-secondary">Use account (higher rate limit)</span>
            <Toggle on={cfg.openSky.useAuth} onChange={(v) => patch({ openSky: { ...cfg.openSky, useAuth: v } })} />
          </div>
          {cfg.openSky.useAuth && (
            <Field label="Credentials (username:password)">
              <input type="password" className={`${inputCls} w-full`} value={openSkyCreds} onChange={(e) => setOpenSkyCreds(e.target.value)} placeholder="user:pass" />
            </Field>
          )}
        </div>

        {/* OGN gliders */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm text-content font-medium">Gliders (OGN / APRS-IS)</div>
            <Toggle on={cfg.ogn.enabled} onChange={(v) => patch({ ogn: { ...cfg.ogn, enabled: v } })} />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="col-span-2">
              <Field label="APRS-IS host (public or local receiver)">
                <input className={`${inputCls} w-full`} value={cfg.ogn.host} onChange={(e) => patch({ ogn: { ...cfg.ogn, host: e.target.value } })} placeholder="aprs.glidernet.org" />
              </Field>
            </div>
            <Field label="Port">
              <input
                type="number"
                className={`${inputCls} w-full`}
                value={cfg.ogn.port}
                onChange={(e) => patch({ ogn: { ...cfg.ogn, port: Number(e.target.value) || 14580 } })}
              />
            </Field>
          </div>
        </div>

        {/* Remote ID receiver */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-sm text-content font-medium">Remote ID receiver</div>
            <Toggle on={cfg.remoteId.enabled} onChange={(v) => patch({ remoteId: { ...cfg.remoteId, enabled: v } })} />
          </div>
          <p className="text-xs text-content-secondary">
            Ingest broadcast drone Remote ID (FAA RID / ASTM F3411 / EU Direct Remote ID) from a
            local receiver or gateway exposing decoded messages as JSON over HTTP.
          </p>
          <Field label="Receiver JSON URL">
            <input
              className={`${inputCls} w-full`}
              value={cfg.remoteId.url}
              onChange={(e) => patch({ remoteId: { ...cfg.remoteId, url: e.target.value } })}
              placeholder="http://localhost:9090/api/remoteid"
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="JSON format">
              <select
                className={`${inputCls} w-full`}
                value={cfg.remoteId.shape}
                onChange={(e) => patch({ remoteId: { ...cfg.remoteId, shape: e.target.value as RemoteIdShape } })}
              >
                <option value="ardudeck">Normalised (ArduDeck)</option>
                <option value="opendroneid">OpenDroneID receiver</option>
              </select>
            </Field>
            <Field label="Poll (ms)">
              <input
                type="number"
                className={`${inputCls} w-full`}
                value={cfg.remoteId.pollMs}
                onChange={(e) => patch({ remoteId: { ...cfg.remoteId, pollMs: Math.max(250, Number(e.target.value) || 1000) } })}
              />
            </Field>
          </div>
        </div>

        {/* Perimeter alert zones */}
        <AlertZonesSection
          zones={cfg.alertZones}
          onChange={(alertZones) => patch({ alertZones })}
        />

        {/* Altitude relevance band */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="text-sm text-content font-medium">Altitude filter</div>
          <p className="text-xs text-content-secondary">
            Your operating band (MSL), used as the default on the map. Below the floor is hidden; above the ceiling fades out (or is hidden, below). These are defaults — the on-map control governs the live view.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Floor (m)">
              <input
                type="number"
                className={`${inputCls} w-full`}
                value={cfg.altitudeFilter.floorMeters}
                onChange={(e) => patch({ altitudeFilter: { ...cfg.altitudeFilter, floorMeters: Number(e.target.value) || 0 } })}
              />
            </Field>
            <Field label="Ceiling (m)">
              <input
                type="number"
                className={`${inputCls} w-full`}
                value={cfg.altitudeFilter.ceilingMeters}
                onChange={(e) => patch({ altitudeFilter: { ...cfg.altitudeFilter, ceilingMeters: Number(e.target.value) || 0 } })}
              />
            </Field>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-content-secondary">Hide traffic above ceiling (instead of fading)</span>
            <Toggle on={cfg.altitudeFilter.hardCeiling} onChange={(v) => patch({ altitudeFilter: { ...cfg.altitudeFilter, hardCeiling: v } })} />
          </div>
          <div className="pt-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-content-secondary">Icon size</span>
              <span className="text-xs text-content tabular-nums">{Math.round(cfg.iconScale * 100)}%</span>
            </div>
            <input
              type="range"
              min={0.6}
              max={2}
              step={0.1}
              value={cfg.iconScale}
              onChange={(e) => patch({ iconScale: Number(e.target.value) })}
              className="w-full accent-sky-500"
            />
          </div>
        </div>

        {/* Proximity thresholds */}
        <div className="bg-surface-input rounded-lg p-3 space-y-2">
          <div className="text-sm text-content font-medium">Proximity warning</div>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Range (m)">
              <input
                type="number"
                className={`${inputCls} w-full`}
                value={cfg.proximity.rangeMeters}
                onChange={(e) => patch({ proximity: { ...cfg.proximity, rangeMeters: Math.max(0, Number(e.target.value) || 0) } })}
              />
            </Field>
            <Field label="Vertical separation (m)">
              <input
                type="number"
                className={`${inputCls} w-full`}
                value={cfg.proximity.verticalMeters}
                onChange={(e) => patch({ proximity: { ...cfg.proximity, verticalMeters: Math.max(0, Number(e.target.value) || 0) } })}
              />
            </Field>
          </div>
        </div>

        <button onClick={() => void save()} className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors">
          {saved ? 'Saved' : 'Save traffic settings'}
        </button>
      </div>
    </div>
  );
}

/**
 * Perimeter alert zones: circular zones seeded from the current map centre, with
 * an optional altitude band. A cooperative contact entering an enabled zone
 * raises an alert (detect + alert only). Zones persist in the traffic config and
 * push to the live store on Save.
 */
function AlertZonesSection({ zones, onChange }: { zones: AlertZone[]; onChange: (z: AlertZone[]) => void }) {
  const viewportCenter = useTrafficStore((s) => s.viewportCenter);

  const addZone = (): void => {
    const center = viewportCenter ?? { lat: 0, lon: 0 };
    const zone: AlertZone = {
      id: (globalThis.crypto?.randomUUID?.() ?? `zone-${Date.now()}`),
      name: `Zone ${zones.length + 1}`,
      enabled: true,
      shape: 'circle',
      center: { lat: Number(center.lat.toFixed(6)), lon: Number(center.lon.toFixed(6)) },
      radiusMeters: 1000,
    };
    onChange([...zones, zone]);
  };

  const update = (id: string, patch: Partial<AlertZone>): void =>
    onChange(zones.map((z) => (z.id === id ? { ...z, ...patch } : z)));
  const remove = (id: string): void => onChange(zones.filter((z) => z.id !== id));

  return (
    <div className="bg-surface-input rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm text-content font-medium">Perimeter alert zones</div>
        <button
          onClick={addZone}
          className="px-2 py-1 text-[11px] bg-amber-600 hover:bg-amber-500 text-white rounded-md transition-colors"
        >
          Add zone here
        </button>
      </div>
      <p className="text-xs text-content-secondary">
        Alert when any contact (ADS-B, glider, or Remote ID) enters a zone. Detect and alert only -
        ArduDeck never mitigates. New zones centre on the current map view.
      </p>
      {zones.length === 0 ? (
        <p className="text-[11px] text-content-tertiary">No zones. Pan the map to a site and click "Add zone here".</p>
      ) : (
        <div className="space-y-2">
          {zones.map((z) => (
            <div key={z.id} className="rounded-md border border-subtle p-2 space-y-2">
              <div className="flex items-center gap-2">
                <Toggle on={z.enabled} onChange={(v) => update(z.id, { enabled: v })} />
                <input
                  className={`${inputCls} flex-1 !py-1`}
                  value={z.name}
                  onChange={(e) => update(z.id, { name: e.target.value })}
                />
                <button onClick={() => remove(z.id)} className="text-content-tertiary hover:text-red-400 text-xs px-1" title="Delete zone">
                  Remove
                </button>
              </div>
              {z.shape === 'circle' && (
                <div className="grid grid-cols-3 gap-2">
                  <Field label="Lat">
                    <input
                      type="number"
                      className={`${inputCls} w-full !py-1`}
                      value={z.center?.lat ?? 0}
                      onChange={(e) => update(z.id, { center: { lat: Number(e.target.value) || 0, lon: z.center?.lon ?? 0 } })}
                    />
                  </Field>
                  <Field label="Lon">
                    <input
                      type="number"
                      className={`${inputCls} w-full !py-1`}
                      value={z.center?.lon ?? 0}
                      onChange={(e) => update(z.id, { center: { lat: z.center?.lat ?? 0, lon: Number(e.target.value) || 0 } })}
                    />
                  </Field>
                  <Field label="Radius (m)">
                    <input
                      type="number"
                      className={`${inputCls} w-full !py-1`}
                      value={z.radiusMeters ?? 1000}
                      onChange={(e) => update(z.id, { radiusMeters: Math.max(10, Number(e.target.value) || 1000) })}
                    />
                  </Field>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2">
                <Field label="Min alt (m, optional)">
                  <input
                    type="number"
                    className={`${inputCls} w-full !py-1`}
                    value={z.minAltMeters ?? ''}
                    onChange={(e) => update(z.id, { minAltMeters: e.target.value === '' ? undefined : Number(e.target.value) })}
                  />
                </Field>
                <Field label="Max alt (m, optional)">
                  <input
                    type="number"
                    className={`${inputCls} w-full !py-1`}
                    value={z.maxAltMeters ?? ''}
                    onChange={(e) => update(z.id, { maxAltMeters: e.target.value === '' ? undefined : Number(e.target.value) })}
                  />
                </Field>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
