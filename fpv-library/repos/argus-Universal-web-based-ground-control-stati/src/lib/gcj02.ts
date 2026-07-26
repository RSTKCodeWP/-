const A = 6378245;
const EE = 0.00669342162296594323;

function _tLat(x: number, y: number): number {
  let r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  r += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3;
  r += ((20 * Math.sin(y * Math.PI) + 40 * Math.sin((y / 3) * Math.PI)) * 2) / 3;
  r += ((160 * Math.sin((y / 12) * Math.PI) + 320 * Math.sin((y * Math.PI) / 30)) * 2) / 3;
  return r;
}

function _tLon(x: number, y: number): number {
  let r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  r += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3;
  r += ((20 * Math.sin(x * Math.PI) + 40 * Math.sin((x / 3) * Math.PI)) * 2) / 3;
  r += ((150 * Math.sin((x / 12) * Math.PI) + 300 * Math.sin((x / 30) * Math.PI)) * 2) / 3;
  return r;
}

export function toGcj(wlat: number, wlon: number): [number, number] {
  const dx = wlon - 105,
    dy = wlat - 35;
  let dLat = _tLat(dx, dy),
    dLon = _tLon(dx, dy);
  const r = (wlat / 180) * Math.PI;
  let m = Math.sin(r);
  m = 1 - EE * m * m;
  const s = Math.sqrt(m);
  dLat = (dLat * 180) / (((A * (1 - EE)) / (m * s)) * Math.PI);
  dLon = (dLon * 180) / ((A / s) * Math.cos(r) * Math.PI);
  return [wlat + dLat, wlon + dLon];
}

export function toWgs(glat: number, glon: number): [number, number] {
  const g = toGcj(glat, glon);
  return [glat * 2 - g[0], glon * 2 - g[1]];
}
