export function formatBytes(bytes: number | null): string {
  if (bytes === null) return 'unknown';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`;
}

export function formatLatLon(home: { lat: number; lon: number } | null): string {
  if (!home) return 'unknown';
  const ns = home.lat >= 0 ? 'N' : 'S';
  const ew = home.lon >= 0 ? 'E' : 'W';
  return `${Math.abs(home.lat).toFixed(4)} ${ns}, ${Math.abs(home.lon).toFixed(4)} ${ew}`;
}

export function formatElevation(range: { min: number; max: number } | null): string {
  if (!range) return 'unknown';
  return `${Math.round(range.min)} to ${Math.round(range.max)} m`;
}

export function formatExtent(extent: { width: number; height: number } | null): string {
  if (!extent) return 'unknown';
  return `${(extent.width / 1000).toFixed(1)} x ${(extent.height / 1000).toFixed(1)} km`;
}

export function formatImageryDate(date: string | null): string {
  if (!date) return 'unknown';
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
