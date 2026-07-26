<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import { app, saveWaypoints } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';

  type CoordFn = (lat: number, lon: number) => [number, number];
  let { map, coord, coordInv }: { map: L.Map; coord: CoordFn; coordInv: CoordFn } = $props();

  let wpMarkers: L.Marker[] = [];
  let wpLine: L.Polyline | null = null;
  let geoCircle: L.Circle | null = null;
  let activeWpMarker: L.CircleMarker | null = null;
  let wpDistLabels: L.Marker[] = [];
  let wpPopup: L.Popup | null = null;
  let focusRing: L.CircleMarker | null = null;

  $effect(() => {
    if (activeWpMarker) {
      map.removeLayer(activeWpMarker);
      activeWpMarker = null;
    }
    const wpIdx = app.drone.wp_idx;
    if (wpIdx >= 0 && app.waypoints.length > 0) {
      if (wpIdx < app.waypoints.length) {
        const wp = app.waypoints[wpIdx];
        const [glat, glon] = coord(wp.lat, wp.lon);
        activeWpMarker = L.circleMarker([glat, glon], {
          radius: 16,
          color: '#ffa726',
          fillColor: 'transparent',
          weight: 3,
          dashArray: '4,4',
        }).addTo(map);
      }
    }
  });

  $effect(() => {
    wpMarkers.forEach((m) => map.removeLayer(m));
    wpMarkers = [];
    if (wpLine) {
      map.removeLayer(wpLine);
      wpLine = null;
    }
    const pts: [number, number][] = [];
    app.waypoints.forEach((wp, i) => {
      const [glat, glon] = coord(wp.lat, wp.lon);
      pts.push([glat, glon]);
      const isLoiter = wp.type === 'loiter_turns' || wp.type === 'loiter_time';
      const color = wp.drop ? '#e65100' : isLoiter ? '#7e57c2' : '#1565c0';
      const border = isLoiter ? 'border:2px dashed rgba(255,255,255,0.8)' : 'border:2px solid white';
      const badge = wp.drop
        ? '<div style="position:absolute;top:-5px;right:-5px;width:8px;height:8px;border-radius:50%;background:#ff5722;border:1px solid white"></div>'
        : '';
      const sub = isLoiter
        ? `<div style="position:absolute;bottom:-10px;left:50%;transform:translateX(-50%);font-size:8px;color:${color};white-space:nowrap;font-weight:600">${wp.type === 'loiter_turns' ? t('label.turns').replace('{n}', String(wp.loiter_param)) : wp.loiter_param + 's'}</div>`
        : wp.delay
          ? `<div style="position:absolute;bottom:-10px;left:50%;transform:translateX(-50%);font-size:8px;color:#888;white-space:nowrap">+${wp.delay}s</div>`
          : '';
      const icon = L.divIcon({
        className: '',
        html: `<div style="position:relative;width:22px;height:22px;border-radius:50%;background:${color};color:white;text-align:center;line-height:22px;font-size:11px;font-weight:bold;${border};box-shadow:0 0 4px rgba(0,0,0,0.5)">${i + 1}${badge}${sub}</div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });
      const m = L.marker([glat, glon], { icon, draggable: true }).addTo(map);
      m.on('dragend', () => {
        const ll = m.getLatLng();
        const [wlat, wlon] = coordInv(ll.lat, ll.lng);
        app.waypoints[i].lat = wlat;
        app.waypoints[i].lon = wlon;
        saveWaypoints();
      });
      m.on('click', (e: L.LeafletMouseEvent) => {
        e.originalEvent?.stopPropagation();
        let segInfo = '';
        if (i > 0) {
          const prev = app.waypoints[i - 1];
          const dlat2 = (wp.lat - prev.lat) * 111320,
            dlon2 = (wp.lon - prev.lon) * 111320 * Math.cos((wp.lat * Math.PI) / 180);
          const seg = Math.sqrt(dlat2 * dlat2 + dlon2 * dlon2);
          const segFmt = seg < 1000 ? seg.toFixed(0) + 'm' : (seg / 1000).toFixed(1) + 'km';
          segInfo = `<br>${t('label.seg')}: <b>${segFmt}</b>`;
        }
        const content = `<div style="font-size:12px;min-width:140px">
          <b>${t('label.wp')} ${i + 1}</b> ${wp.drop ? `<span style="color:#e65100">${t('label.drop')}</span>` : ''}<br>
          <span style="color:#888">${wp.lat.toFixed(6)}, ${wp.lon.toFixed(6)}</span><br>
          ${t('label.alt')}: <b>${wp.alt}m</b>${wp.speed ? ` · ${t('label.spd')}: ${wp.speed}m/s` : ''}
          ${wp.delay ? `<br>${t('label.delay')}: ${wp.delay}s` : ''}${segInfo}
        </div>`;
        if (wpPopup) map.closePopup(wpPopup);
        wpPopup = L.popup({ closeButton: true, className: 'wp-popup' })
          .setLatLng([glat, glon])
          .setContent(content)
          .openOn(map);
      });
      wpMarkers.push(m);
    });
    if (pts.length > 1) wpLine = L.polyline(pts, { color: '#1565c0', weight: 2, dashArray: '6,4' }).addTo(map);

    wpDistLabels.forEach((l) => map.removeLayer(l));
    wpDistLabels = [];
    for (let i = 1; i < pts.length; i++) {
      const [lat1, lon1] = pts[i - 1],
        [lat2, lon2] = pts[i];
      const mid = L.latLng((lat1 + lat2) / 2, (lon1 + lon2) / 2);
      const dist = map.distance(L.latLng(lat1, lon1), L.latLng(lat2, lon2));
      const txt = dist < 1000 ? `${dist.toFixed(0)}m` : `${(dist / 1000).toFixed(1)}km`;
      const lbl = L.marker(mid, {
        icon: L.divIcon({
          className: '',
          html: `<div style="background:rgba(21,101,192,0.85);color:white;padding:1px 5px;border-radius:3px;font-size:10px;font-weight:600;white-space:nowrap">${txt}</div>`,
          iconAnchor: [0, 0],
        }),
        interactive: false,
      }).addTo(map);
      wpDistLabels.push(lbl);
    }

    if (geoCircle) {
      map.removeLayer(geoCircle);
      geoCircle = null;
    }
    if (app.drone.home_lat !== 0 && app.geoRadius > 0) {
      const [hlat, hlon] = coord(app.drone.home_lat, app.drone.home_lon);
      geoCircle = L.circle([hlat, hlon], {
        radius: app.geoRadius,
        color: '#f44336',
        fill: false,
        dashArray: '8,4',
        weight: 1,
      }).addTo(map);
    }
  });

  $effect(() => {
    if (app.focusWp < 0 || app.focusWp >= app.waypoints.length) return;
    const wp = app.waypoints[app.focusWp];
    const [glat, glon] = coord(wp.lat, wp.lon);
    map.setView([glat, glon], Math.max(map.getZoom(), 16));
    if (focusRing) map.removeLayer(focusRing);
    focusRing = L.circleMarker([glat, glon], {
      radius: 20,
      color: '#ffa726',
      fillColor: 'transparent',
      weight: 3,
      dashArray: '4,4',
    }).addTo(map);
    const focusTimer = setTimeout(() => {
      if (focusRing) {
        map.removeLayer(focusRing);
        focusRing = null;
      }
    }, 2000);
    // Reset focusWp via untrack so this write doesn't dirty the effect and
    // trigger an immediate cleanup that would clear the just-created timer.
    untrack(() => {
      app.focusWp = -1;
    });
    return () => clearTimeout(focusTimer);
  });

  $effect(() => {
    if (app.fitRouteFlag <= 0 || app.waypoints.length < 2) return;
    const pts = app.waypoints.map((w) => coord(w.lat, w.lon));
    map.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
  });

  onDestroy(() => {
    wpMarkers.forEach((m) => map.removeLayer(m));
    wpDistLabels.forEach((l) => map.removeLayer(l));
    [wpLine, geoCircle, activeWpMarker, focusRing].filter(Boolean).forEach((l) => map.removeLayer(l!));
    if (wpPopup) map.closePopup(wpPopup);
  });
</script>
