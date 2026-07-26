/**
 * adsb-providers — factories building PollProvider instances for the three ADS-B
 * sources (local receiver, hosted API preset, OpenSky). Secrets are pulled lazily
 * via getSecret so a key entered after start takes effect on the next tick.
 */

import {
  ADSB_API_PRESETS,
  TRAFFIC_SECRET_SERVICES,
  type TrafficConfig,
} from '../../shared/traffic-types.js';
import { PollProvider } from './poll-provider.js';
import { KM_TO_NM, viewportToBbox } from './provider.js';
import { parseAdsbxV2, parseOpenSkyStates } from './parse.js';

export type SecretGetter = (service: string) => string | null;

const MAX_RADIUS_NM = 250;

export function createLocalAdsbProvider(cfg: TrafficConfig['localAdsb']): PollProvider {
  return new PollProvider({
    id: 'adsb-local',
    source: 'adsb',
    pollMs: cfg.pollMs,
    // A local receiver serves the whole field; viewport is irrelevant.
    buildRequest: () => (cfg.url ? { url: cfg.url } : null),
    parse: parseAdsbxV2,
  });
}

export function createAdsbApiProvider(cfg: TrafficConfig['adsbApi'], getSecret: SecretGetter): PollProvider {
  const preset = ADSB_API_PRESETS[cfg.preset];
  return new PollProvider({
    id: `adsb-${cfg.preset}`,
    source: 'adsb',
    pollMs: cfg.pollMs,
    buildRequest: (v) => {
      const template = cfg.preset === 'custom' ? cfg.customUrl : preset.urlTemplate;
      if (!template) return null;
      const radiusNm = Math.min(MAX_RADIUS_NM, Math.max(1, Math.round(v.radiusKm * KM_TO_NM)));
      const url = template
        .replace('{lat}', v.lat.toFixed(5))
        .replace('{lon}', v.lon.toFixed(5))
        .replace('{radiusNm}', String(radiusNm));
      const headers: Record<string, string> = { ...(preset.extraHeaders ?? {}) };
      if (cfg.preset === 'adsbexchange') {
        const key = getSecret(TRAFFIC_SECRET_SERVICES.adsbexchange);
        if (!key) return null; // no key -> don't hammer a 401
        headers[preset.keyHeader!] = key;
      } else if (cfg.preset === 'custom') {
        const key = getSecret(TRAFFIC_SECRET_SERVICES.custom);
        if (key && cfg.customKeyHeader) headers[cfg.customKeyHeader] = key;
      }
      return { url, headers };
    },
    parse: parseAdsbxV2,
  });
}

export function createOpenSkyProvider(cfg: TrafficConfig['openSky'], getSecret: SecretGetter): PollProvider {
  return new PollProvider({
    id: 'adsb-opensky',
    source: 'adsb',
    pollMs: cfg.pollMs,
    buildRequest: (v) => {
      const b = viewportToBbox(v);
      const url = `https://opensky-network.org/api/states/all?lamin=${b.lamin.toFixed(4)}&lomin=${b.lomin.toFixed(4)}&lamax=${b.lamax.toFixed(4)}&lomax=${b.lomax.toFixed(4)}`;
      const headers: Record<string, string> = {};
      if (cfg.useAuth) {
        const creds = getSecret(TRAFFIC_SECRET_SERVICES.openSky);
        if (creds) headers['Authorization'] = `Basic ${Buffer.from(creds).toString('base64')}`;
      }
      return { url, headers };
    },
    parse: (json) => parseOpenSkyStates(json),
  });
}
