/**
 * OgnAprsProvider — live gliders via OGN's APRS-IS feed.
 *
 * Unlike the ADS-B sources this is a persistent TCP stream, not polling: connect,
 * log in with a server-side area filter (r/lat/lon/radius), then parse each line
 * into a contact. The host is configurable so the same provider serves both the
 * public network (aprs.glidernet.org) and a local OGN/FLARM receiver. On viewport
 * change beyond a threshold we re-issue the filter; on socket drop we reconnect
 * with backoff.
 */

import net from 'node:net';
import type { ViewportBbox } from '../../shared/traffic-types.js';
import type { ProviderContext, TrafficProvider } from './provider.js';
import { parseOgnAprs } from './parse.js';

const RECONNECT_BASE_MS = 3000;
const RECONNECT_MAX_MS = 60_000;
/** Re-issue the area filter when the viewport centre moves more than this. */
const REFILTER_KM = 20;

export class OgnAprsProvider implements TrafficProvider {
  readonly source = 'ogn' as const;
  readonly id = 'ogn';
  private host: string;
  private port: number;
  private ctx: ProviderContext | null = null;
  private socket: net.Socket | null = null;
  private viewport: ViewportBbox | null = null;
  private filterAt: ViewportBbox | null = null;
  private buffer = '';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = RECONNECT_BASE_MS;
  private stopped = false;

  constructor(host: string, port: number) {
    this.host = host;
    this.port = port;
  }

  start(ctx: ProviderContext): void {
    this.ctx = ctx;
    this.stopped = false;
    this.connect();
  }

  setViewport(v: ViewportBbox): void {
    this.viewport = v;
    if (!this.filterAt || haversineKm(v.lat, v.lon, this.filterAt.lat, this.filterAt.lon) > REFILTER_KM) {
      this.sendFilter();
    }
  }

  stop(): void {
    this.stopped = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.socket?.destroy();
    this.socket = null;
    this.ctx = null;
  }

  private connect(): void {
    if (this.stopped) return;
    const sock = net.createConnection({ host: this.host, port: this.port });
    this.socket = sock;
    sock.setEncoding('utf8');

    sock.on('connect', () => {
      this.reconnectDelay = RECONNECT_BASE_MS;
      // APRS-IS login. user/pass -1 = receive-only; filter applied once we know the view.
      sock.write('user ARDUDECK pass -1 vers ArduDeck 1.0\r\n');
      this.filterAt = null;
      this.sendFilter();
    });

    sock.on('data', (chunk: string) => this.onData(chunk));
    sock.on('error', (err) => this.ctx?.log(`ogn socket error: ${err.message}`));
    sock.on('close', () => {
      if (this.socket === sock) this.socket = null;
      this.scheduleReconnect();
    });
  }

  private sendFilter(): void {
    const sock = this.socket;
    const v = this.viewport;
    if (!sock || !sock.writable || !v) return;
    const radius = Math.max(1, Math.round(v.radiusKm));
    sock.write(`#filter r/${v.lat.toFixed(4)}/${v.lon.toFixed(4)}/${radius}\r\n`);
    this.filterAt = v;
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf('\n')) >= 0) {
      const line = this.buffer.slice(0, nl).replace(/\r$/, '');
      this.buffer = this.buffer.slice(nl + 1);
      const contact = parseOgnAprs(line, Date.now());
      if (contact) this.ctx?.emit([contact]);
    }
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(RECONNECT_MAX_MS, this.reconnectDelay * 2);
  }
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
