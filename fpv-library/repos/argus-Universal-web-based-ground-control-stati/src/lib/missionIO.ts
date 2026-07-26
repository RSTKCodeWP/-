import type { Waypoint } from './types';

export function parseQgcWaypoints(text: string): Waypoint[] {
  const wps: Waypoint[] = [];
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('QGC') || trimmed.startsWith('#')) continue;
    const cols = trimmed.split('\t');
    if (cols.length < 12) continue;
    const cmd = parseInt(cols[3]);
    if (cmd !== 16 && cmd !== 18 && cmd !== 19 && cmd !== 82) continue;
    const lat = parseFloat(cols[8]),
      lon = parseFloat(cols[9]),
      alt = parseFloat(cols[10]);
    if (Math.abs(lat) < 0.001) continue;
    const type: Waypoint['type'] =
      cmd === 18 ? 'loiter_turns' : cmd === 19 ? 'loiter_time' : cmd === 82 ? 'spline' : 'wp';
    wps.push({
      lat,
      lon,
      alt,
      drop: false,
      delay: cmd === 16 || cmd === 82 ? parseFloat(cols[4]) || 0 : 0,
      speed: 0,
      type,
      loiter_param: cmd === 18 || cmd === 19 ? parseFloat(cols[4]) || 0 : 0,
    });
  }
  return wps;
}

export function parseQgcPlan(text: string): Waypoint[] {
  const plan = JSON.parse(text);
  const items = plan?.mission?.items || [];
  const wps: Waypoint[] = [];
  for (const item of items) {
    const cmd = item.command;
    if (cmd !== 16 && cmd !== 18 && cmd !== 19 && cmd !== 82) continue;
    const params = item.params || [];
    const lat = params[4] ?? 0,
      lon = params[5] ?? 0,
      alt = params[6] ?? 30;
    if (Math.abs(lat) < 0.001) continue;
    const type: Waypoint['type'] =
      cmd === 18 ? 'loiter_turns' : cmd === 19 ? 'loiter_time' : cmd === 82 ? 'spline' : 'wp';
    wps.push({
      lat,
      lon,
      alt,
      drop: false,
      delay: cmd === 16 || cmd === 82 ? params[0] || 0 : 0,
      speed: 0,
      type,
      loiter_param: cmd === 18 || cmd === 19 ? params[0] || 0 : 0,
    });
  }
  return wps;
}

export function exportKml(waypoints: Waypoint[]): string {
  const coords = waypoints.map((w) => `${w.lon},${w.lat},${w.alt}`).join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Argus Mission</name>
<Placemark><name>Route</name><LineString><coordinates>${coords}</coordinates></LineString></Placemark>
</Document></kml>`;
}

export function parseKmlCoords(text: string, defaultAlt: number): Waypoint[] {
  const doc = new DOMParser().parseFromString(text, 'text/xml');
  const coords: Waypoint[] = [];
  const els = doc.getElementsByTagName('coordinates');
  for (let i = 0; i < els.length; i++) {
    els[i]
      .textContent!.trim()
      .split(/\s+/)
      .forEach((c: string) => {
        const p = c.split(',');
        if (p.length >= 2) {
          const lon = parseFloat(p[0]),
            lat = parseFloat(p[1]);
          const alt = parseFloat(p[2]) || defaultAlt;
          if (Math.abs(lat) > 0.001 && Math.abs(lon) > 0.001)
            coords.push({ lat, lon, alt, drop: false, delay: 0, speed: 0, type: 'wp', loiter_param: 0 });
        }
      });
  }
  if (coords.length > 1 && Math.abs(coords[0].lat - coords[coords.length - 1].lat) < 0.00001) coords.pop();
  return coords;
}

export function segDist(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const dlat = (b.lat - a.lat) * 111320;
  const dlon = (b.lon - a.lon) * 111320 * Math.cos((a.lat * Math.PI) / 180);
  return Math.sqrt(dlat * dlat + dlon * dlon);
}

export function totalDist(waypoints: Waypoint[]): string {
  let d = 0;
  for (let i = 1; i < waypoints.length; i++) {
    d += segDist(waypoints[i - 1], waypoints[i]);
  }
  return d < 1000 ? d.toFixed(0) + 'm' : (d / 1000).toFixed(1) + 'km';
}

export function pointInPoly(lat: number, lon: number, poly: { lat: number; lon: number }[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    if (
      poly[i].lon > lon !== poly[j].lon > lon &&
      lat < ((poly[j].lat - poly[i].lat) * (lon - poly[i].lon)) / (poly[j].lon - poly[i].lon) + poly[i].lat
    ) {
      inside = !inside;
    }
  }
  return inside;
}
