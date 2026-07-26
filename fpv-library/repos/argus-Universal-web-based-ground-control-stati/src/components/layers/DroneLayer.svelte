<script lang="ts">
  import { onDestroy } from 'svelte';
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';

  type CoordFn = (lat: number, lon: number) => [number, number];
  let { map, follow, trail, coord }: { map: L.Map; follow: boolean; trail: [number, number][]; coord: CoordFn } =
    $props();

  function escHtml(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  let droneMarker: L.Marker | null = null;
  let homeMarker: L.Marker | null = null;
  let trailLine: L.Polyline | null = null;
  let velocityLine: L.Polyline | null = null;
  let homeLine: L.Polyline | null = null;
  let rangeRing: L.Circle | null = null;
  let prevLat = 0;
  let prevLon = 0;

  $effect(() => {
    if (!app.drone.connected) return;
    const lat = app.drone.lat,
      lon = app.drone.lon;
    if (Math.abs(lat) < 0.001) return;
    const [glat, glon] = coord(lat, lon);

    if (!droneMarker) {
      const icon = L.divIcon({
        className: 'drone-icon',
        html: `<div class="drone-arrow" style="transform:rotate(${app.drone.yaw}deg)"><svg viewBox="-12 -12 24 24" width="28" height="28"><polygon points="0,-10 -7,8 0,4 7,8" fill="#4fc3f7" stroke="white" stroke-width="1"/></svg></div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });
      droneMarker = L.marker([glat, glon], { icon, zIndexOffset: 1000 }).addTo(map);
      droneMarker.on('click', () => {
        const d = app.drone;
        const coordStr = `${d.lat.toFixed(6)}, ${d.lon.toFixed(6)}`;
        const content = `<div style="font-size:12px;min-width:160px">
          <b>${d.mode}</b> ${d.armed ? `<span style="color:#f44336">${t('label.armed')}</span>` : t('label.disarmed')}<br>
          <span style="color:#888;cursor:pointer;text-decoration:underline dotted" onclick="navigator.clipboard.writeText('${coordStr}')">${coordStr}</span><br>
          ${t('label.alt')}: <b>${d.alt_rel.toFixed(1)}m</b> (${t('label.msl')} ${d.alt_msl.toFixed(0)}m)<br>
          ${t('label.spd')}: <b>${d.gs.toFixed(1)} m/s</b> ${t('label.hdg')} ${d.hdg.toFixed(0)}°<br>
          ${t('label.home')}: <b>${d.dist_home.toFixed(0)}m</b>
        </div>`;
        L.popup({ closeButton: true }).setLatLng([glat, glon]).setContent(content).openOn(map);
      });
    } else {
      droneMarker.setLatLng([glat, glon]);
      const el = droneMarker.getElement();
      if (el) {
        const a = el.querySelector('.drone-arrow');
        if (a) (a as HTMLElement).style.transform = `rotate(${app.drone.yaw}deg)`;
      }
    }

    if (velocityLine) {
      map.removeLayer(velocityLine);
      velocityLine = null;
    }
    if (app.drone.gs > 0.5) {
      const hdgRad = (app.drone.hdg * Math.PI) / 180;
      const scale = Math.min(app.drone.gs * 8, 200);
      const endLat = glat + (Math.cos(hdgRad) * scale) / 111320;
      const endLon = glon + (Math.sin(hdgRad) * scale) / (111320 * Math.cos((glat * Math.PI) / 180));
      velocityLine = L.polyline(
        [
          [glat, glon],
          [endLat, endLon],
        ],
        {
          color: '#69f0ae',
          weight: 2,
          opacity: 0.6,
          dashArray: '4,6',
        },
      ).addTo(map);
    }

    if (homeLine) {
      map.removeLayer(homeLine);
      homeLine = null;
    }
    if (app.drone.home_lat !== 0 && app.drone.dist_home > 5) {
      const [hlat, hlon] = coord(app.drone.home_lat, app.drone.home_lon);
      homeLine = L.polyline(
        [
          [glat, glon],
          [hlat, hlon],
        ],
        {
          color: '#ffa726',
          weight: 1.5,
          opacity: 0.5,
          dashArray: '6,8',
        },
      ).addTo(map);
    }

    if (app.drone.home_lat !== 0 && !homeMarker) {
      const [hlat, hlon] = coord(app.drone.home_lat, app.drone.home_lon);
      const homeIcon = L.divIcon({
        className: '',
        html: '<div style="width:26px;height:26px;border-radius:50%;background:#4caf50;color:white;text-align:center;line-height:26px;font-size:14px;font-weight:bold;border:2px solid white;box-shadow:0 0 6px rgba(0,0,0,0.5)">H</div>',
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });
      homeMarker = L.marker([hlat, hlon], { icon: homeIcon, zIndexOffset: 500 }).addTo(map);
    }

    if (Math.abs(lat - prevLat) > 0.000001 || Math.abs(lon - prevLon) > 0.000001) {
      trail.push([glat, glon]);
      if (trail.length > 2000) trail.splice(0, trail.length - 1500);
      if (trailLine) map.removeLayer(trailLine);
      trailLine = L.polyline(trail, { color: '#4fc3f7', weight: 2, opacity: 0.7 }).addTo(map);
      prevLat = lat;
      prevLon = lon;
    }
    if (follow) map.setView([glat, glon], map.getZoom());
  });

  $effect(() => {
    if (rangeRing) {
      map.removeLayer(rangeRing);
      rangeRing = null;
    }
    const d = app.drone;
    if (!d.connected || !d.armed || d.home_lat === 0 || d.bat_time <= 0) return;
    const speed = Math.max(d.gs, 3);
    const safeSeconds = Math.max(0, d.bat_time - 60);
    const radius = safeSeconds * speed * 0.5;
    if (radius < 10) return;
    const [hlat, hlon] = coord(d.home_lat, d.home_lon);
    const ratio = d.dist_home / Math.max(radius, 1);
    const color = ratio > 0.9 ? '#ef4444' : ratio > 0.7 ? '#eab308' : '#22c55e';
    rangeRing = L.circle([hlat, hlon], {
      radius,
      color,
      fill: true,
      fillColor: color,
      fillOpacity: 0.06,
      dashArray: '8,6',
      weight: 1.5,
    }).addTo(map);
  });

  let otherMarkers: Map<number, L.Marker> = new Map();

  $effect(() => {
    const vehicles = app.drone.vehicles || [];
    const activeSids = new Set(vehicles.map((v) => v.sysid));
    for (const [sid, m] of otherMarkers) {
      if (!activeSids.has(sid)) {
        map.removeLayer(m);
        otherMarkers.delete(sid);
      }
    }
    for (const v of vehicles) {
      if (Math.abs(v.lat) < 0.001) continue;
      const [glat, glon] = coord(v.lat, v.lon);
      const existing = otherMarkers.get(v.sysid);
      if (existing) {
        existing.setLatLng([glat, glon]);
        const el = existing.getElement();
        if (el) {
          const a = el.querySelector('.drone-arrow');
          if (a) (a as HTMLElement).style.transform = `rotate(${v.hdg}deg)`;
        }
      } else {
        const color = v.armed ? '#ef4444' : '#888';
        const icon = L.divIcon({
          className: 'drone-icon',
          html: `<div class="drone-arrow" style="transform:rotate(${v.hdg}deg)"><svg viewBox="-12 -12 24 24" width="22" height="22"><polygon points="0,-8 -5,6 0,3 5,6" fill="${color}" stroke="white" stroke-width="0.8"/></svg><div style="position:absolute;top:-10px;left:50%;transform:translateX(-50%);font-size:9px;color:${color};font-weight:bold;white-space:nowrap">V${v.sysid}</div></div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        });
        const m = L.marker([glat, glon], { icon, zIndexOffset: 800 }).addTo(map);
        otherMarkers.set(v.sysid, m);
      }
    }
  });

  let adsbMarkers = new Map<number, L.Marker>();

  $effect(() => {
    const adsb = app.drone.adsb || [];
    const seen = new Set<number>();
    for (const a of adsb) {
      seen.add(a.icao);
      const [glat, glon] = coord(a.lat, a.lon);
      const existing = adsbMarkers.get(a.icao);
      if (existing) {
        existing.setLatLng([glat, glon]);
      } else {
        const icon = L.divIcon({
          className: '',
          html: `<div style="transform:rotate(${a.hdg}deg)"><svg viewBox="-10 -10 20 20" width="20" height="20"><polygon points="0,-8 -5,6 0,3 5,6" fill="#ffc107" stroke="#333" stroke-width="0.5"/></svg></div>
            <div style="position:absolute;top:-14px;left:50%;transform:translateX(-50%);font-size:8px;color:#ffc107;font-weight:bold;white-space:nowrap">${a.callsign ? escHtml(a.callsign) : a.icao.toString(16)}</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        });
        const m = L.marker([glat, glon], { icon, zIndexOffset: 600 }).addTo(map);
        m.bindTooltip(
          `${a.callsign ? escHtml(a.callsign) : 'ADSB'} | ${a.alt.toFixed(0)}m | ${a.speed.toFixed(0)}m/s`,
          { permanent: false },
        );
        adsbMarkers.set(a.icao, m);
      }
    }
    for (const [icao, m] of adsbMarkers) {
      if (!seen.has(icao)) {
        map.removeLayer(m);
        adsbMarkers.delete(icao);
      }
    }
  });

  onDestroy(() => {
    [droneMarker, homeMarker, trailLine, velocityLine, homeLine, rangeRing]
      .filter(Boolean)
      .forEach((l) => map.removeLayer(l!));
    otherMarkers.forEach((m) => map.removeLayer(m));
    adsbMarkers.forEach((m) => map.removeLayer(m));
  });
</script>
