/**
 * TrafficService — owns provider lifecycle, the merged contact cache, viewport
 * fan-out, and the push loop to the renderer.
 *
 * Enable state is per source (the two overlay toggles, 'adsb' / 'ogn'). Within a
 * source, which concrete providers run is decided by config (local / hosted API /
 * OpenSky each have their own enable flag). Electron specifics (config store,
 * secret store, window send) are injected so the service is testable in isolation.
 */

import { DEFAULT_TRAFFIC_CONFIG, type TrafficBatch, type TrafficConfig, type TrafficSource, type ViewportBbox } from '../../shared/traffic-types.js';
import { ContactCache } from './contact-cache.js';
import { withinViewport, type ProviderContext, type TrafficProvider } from './provider.js';
import { createAdsbApiProvider, createLocalAdsbProvider, createOpenSkyProvider } from './adsb-providers.js';
import { OgnAprsProvider } from './ogn-provider.js';
import { createRemoteIdProvider } from './remoteid-provider.js';

export interface TrafficServiceDeps {
  getConfig(): TrafficConfig;
  saveConfig(cfg: TrafficConfig): void;
  getSecret(service: string): string | null;
  push(batch: TrafficBatch): void;
}

const PUSH_INTERVAL_MS = 1000;

export class TrafficService {
  private deps: TrafficServiceDeps;
  private cache = new ContactCache();
  private providers: TrafficProvider[] = [];
  private activeSources = new Set<TrafficSource>();
  private viewport: ViewportBbox | null = null;
  private pushTimer: ReturnType<typeof setInterval> | null = null;

  constructor(deps: TrafficServiceDeps) {
    this.deps = deps;
  }

  /** Begin the push loop. Providers stay idle until a source is enabled. */
  start(): void {
    if (this.pushTimer) return;
    this.pushTimer = setInterval(() => this.pushSnapshot(), PUSH_INTERVAL_MS);
  }

  setEnabled(source: TrafficSource, on: boolean): void {
    if (on === this.activeSources.has(source)) return;
    if (on) this.activeSources.add(source);
    else {
      this.activeSources.delete(source);
      this.cache.dropSource(source);
    }
    this.rebuildProviders();
    if (this.activeSources.size === 0) this.deps.push({ contacts: [], generatedAt: Date.now() });
  }

  setViewport(v: ViewportBbox): void {
    this.viewport = v;
    for (const p of this.providers) p.setViewport(v);
  }

  /** Apply edited config (new URL, preset, poll rate...) by rebuilding providers. */
  setConfig(cfg: TrafficConfig): void {
    this.deps.saveConfig(cfg);
    this.rebuildProviders();
  }

  dispose(): void {
    if (this.pushTimer) clearInterval(this.pushTimer);
    this.pushTimer = null;
    for (const p of this.providers) p.stop();
    this.providers = [];
    this.cache.clear();
  }

  private ctx(): ProviderContext {
    return {
      emit: (contacts) => this.cache.upsert(contacts),
      log: (msg) => console.info(`[traffic] ${msg}`),
    };
  }

  private buildProvidersForSource(source: TrafficSource): TrafficProvider[] {
    const cfg = this.deps.getConfig();
    const out: TrafficProvider[] = [];
    if (source === 'adsb') {
      if (cfg.localAdsb.enabled) out.push(createLocalAdsbProvider(cfg.localAdsb));
      if (cfg.adsbApi.enabled) out.push(createAdsbApiProvider(cfg.adsbApi, this.deps.getSecret));
      if (cfg.openSky.enabled) out.push(createOpenSkyProvider(cfg.openSky, this.deps.getSecret));
      // Zero-config fallback: if the user enabled the Traffic layer but configured
      // no ADS-B provider, use the free no-key hosted API so it just works.
      if (out.length === 0) {
        out.push(createAdsbApiProvider({ ...DEFAULT_TRAFFIC_CONFIG.adsbApi, enabled: true, preset: 'airplanes-live' }, this.deps.getSecret));
      }
    } else if (source === 'ogn') {
      if (cfg.ogn.enabled) out.push(new OgnAprsProvider(cfg.ogn.host, cfg.ogn.port));
      // Fallback: public OGN network so the Gliders layer works out of the box.
      else out.push(new OgnAprsProvider(DEFAULT_TRAFFIC_CONFIG.ogn.host, DEFAULT_TRAFFIC_CONFIG.ogn.port));
    } else if (source === 'remoteid') {
      // No zero-config fallback: Remote ID needs a local receiver URL.
      if (cfg.remoteId.enabled && cfg.remoteId.url) out.push(createRemoteIdProvider(cfg.remoteId));
    }
    return out;
  }

  private rebuildProviders(): void {
    for (const p of this.providers) p.stop();
    this.providers = [];
    for (const source of this.activeSources) {
      for (const p of this.buildProvidersForSource(source)) {
        p.start(this.ctx());
        if (this.viewport) p.setViewport(this.viewport);
        this.providers.push(p);
      }
    }
  }

  private pushSnapshot(): void {
    if (this.activeSources.size === 0) return;
    const all = this.cache.snapshot(Date.now());
    // Only ship contacts inside the current view. A zoomed-out poll can return a
    // 250 nm radius of traffic; culling here keeps the IPC payload and the
    // renderer's marker count bounded to what's actually visible.
    const v = this.viewport;
    const contacts = v ? all.filter((c) => withinViewport(c.lat, c.lon, v)) : all;
    this.deps.push({ contacts, generatedAt: Date.now() });
  }
}
