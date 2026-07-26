<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { getElevationProfile, interpolateRoute } from '../../lib/terrain';
  import { segDist } from '../../lib/missionIO';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Mountain } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let canvasEl: HTMLCanvasElement = $state(null!);
  let terrainElevations: number[] | null = $state(null);
  let terrainPoints: { lat: number; lon: number; wpIndex: number }[] = $state([]);
  let loading = $state(false);
  let hoverX: number | null = $state(null);
  let minClearance = $state(10);
  let frameId = 0;

  const wps = $derived(app.waypoints);

  $effect(() => {
    if (wps.length < 2) {
      terrainElevations = null;
      terrainPoints = [];
      return;
    }
    const pts = interpolateRoute(wps, Math.max(50, segDist(wps[0], wps[wps.length - 1]) / 200));
    const snapshot = JSON.stringify(wps.map((w) => `${w.lat.toFixed(5)},${w.lon.toFixed(5)}`));
    loading = true;
    getElevationProfile(pts)
      .then((elevs) => {
        const current = app.waypoints.map((w) => `${w.lat.toFixed(5)},${w.lon.toFixed(5)}`);
        if (JSON.stringify(current) !== snapshot) return;
        terrainPoints = pts;
        terrainElevations = elevs;
      })
      .catch(() => {
        terrainElevations = null;
        terrainPoints = [];
      })
      .finally(() => {
        loading = false;
      });
  });

  $effect(() => {
    if (!canvasEl || wps.length < 2) return;
    const _hover = hoverX;
    const _clearance = minClearance;
    const tElevs = terrainElevations;
    const tPts = terrainPoints;

    const ctx = canvasEl.getContext('2d')!;
    const w = (canvasEl.width = canvasEl.parentElement!.clientWidth);
    const h = canvasEl.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    const LEFT = 48,
      RIGHT = 12,
      TOP = 16,
      BOTTOM = 28;
    const cw = w - LEFT - RIGHT,
      ch = h - TOP - BOTTOM;

    const dists: number[] = [0];
    for (let i = 1; i < wps.length; i++) dists.push(dists[i - 1] + segDist(wps[i - 1], wps[i]));
    const totalD = dists[dists.length - 1] || 1;
    const alts = wps.map((wp) => wp.alt);

    let mn = Math.min(...alts),
      mx = Math.max(...alts);
    if (tElevs && tElevs.length > 0) {
      mn = Math.min(mn, ...tElevs);
      mx = Math.max(mx, ...tElevs);
    }
    if (mx === mn) {
      mx += 5;
      mn = Math.max(0, mn - 5);
    }
    const pad = (mx - mn) * 0.15;
    mn -= pad;
    mx += pad;

    const toX = (d: number) => LEFT + (d / totalD) * cw;
    const toY = (alt: number) => TOP + (1 - (alt - mn) / (mx - mn)) * ch;

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    const altStep = niceStep(mx - mn, 5);
    const altStart = Math.ceil(mn / altStep) * altStep;
    ctx.font = '10px monospace';
    for (let a = altStart; a <= mx; a += altStep) {
      const y = toY(a);
      ctx.beginPath();
      ctx.moveTo(LEFT, y);
      ctx.lineTo(w - RIGHT, y);
      ctx.stroke();
      ctx.fillStyle = '#666';
      ctx.fillText(`${a.toFixed(0)}m`, 2, y + 3);
    }
    const distStep = niceStep(totalD, 6);
    const distStart = Math.ceil(0 / distStep) * distStep;
    for (let d = distStart; d <= totalD; d += distStep) {
      const x = toX(d);
      ctx.beginPath();
      ctx.moveTo(x, TOP);
      ctx.lineTo(x, TOP + ch);
      ctx.stroke();
      ctx.fillStyle = '#666';
      const label = d >= 1000 ? `${(d / 1000).toFixed(1)}km` : `${d.toFixed(0)}m`;
      ctx.fillText(label, x - 10, h - 4);
    }

    // Terrain data
    let tDists: number[] = [];
    if (tElevs && tElevs.length > 0 && tPts.length === tElevs.length) {
      tDists = [0];
      for (let i = 1; i < tPts.length; i++) tDists.push(tDists[i - 1] + segDist(tPts[i - 1], tPts[i]));
      const tTotalD = tDists[tDists.length - 1] || totalD;

      // Brown ground fill
      ctx.fillStyle = 'rgba(141,110,68,0.35)';
      ctx.beginPath();
      ctx.moveTo(LEFT, TOP + ch);
      for (let i = 0; i < tPts.length; i++) ctx.lineTo(toX((tDists[i] / tTotalD) * totalD), toY(tElevs[i]));
      ctx.lineTo(toX(totalD), TOP + ch);
      ctx.closePath();
      ctx.fill();

      // Green clearance fill
      ctx.fillStyle = 'rgba(76,175,80,0.15)';
      ctx.beginPath();
      for (let i = 0; i < wps.length; i++) {
        const x = toX(dists[i]),
          y = toY(alts[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      for (let i = tPts.length - 1; i >= 0; i--) ctx.lineTo(toX((tDists[i] / tTotalD) * totalD), toY(tElevs[i]));
      ctx.closePath();
      ctx.fill();

      // Danger zones — red fill where clearance < minClearance
      ctx.fillStyle = 'rgba(244,67,54,0.25)';
      for (let i = 0; i < tPts.length - 1; i++) {
        const xA = (tDists[i] / tTotalD) * totalD;
        const xB = (tDists[i + 1] / tTotalD) * totalD;
        const flightAltA = interpFlightAlt(xA, dists, alts);
        const flightAltB = interpFlightAlt(xB, dists, alts);
        const clearA = flightAltA - tElevs[i];
        const clearB = flightAltB - tElevs[i + 1];
        if (clearA < _clearance || clearB < _clearance) {
          ctx.beginPath();
          ctx.moveTo(toX(xA), toY(flightAltA));
          ctx.lineTo(toX(xB), toY(flightAltB));
          ctx.lineTo(toX(xB), toY(tElevs[i + 1]));
          ctx.lineTo(toX(xA), toY(tElevs[i]));
          ctx.closePath();
          ctx.fill();
        }
      }

      // Terrain contour line
      ctx.strokeStyle = 'rgba(141,110,68,0.7)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < tPts.length; i++) {
        const x = toX((tDists[i] / tTotalD) * totalD),
          y = toY(tElevs[i]);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Flight path line
    ctx.strokeStyle = '#1565c0';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < wps.length; i++) {
      const x = toX(dists[i]),
        y = toY(alts[i]);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Waypoint dots + labels
    ctx.font = '10px monospace';
    for (let i = 0; i < wps.length; i++) {
      const x = toX(dists[i]),
        y = toY(alts[i]);
      ctx.fillStyle = wps[i].drop ? '#e65100' : '#2196f3';
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#aaa';
      ctx.fillText(`WP${i + 1}`, x + 6, y - 6);
      ctx.fillText(`${alts[i].toFixed(0)}m`, x + 6, y + 12);

      if (tElevs && tPts.length > 0) {
        const tIdx = tPts.findIndex((p) => p.wpIndex === i);
        if (tIdx >= 0) {
          const clr = alts[i] - tElevs[tIdx];
          ctx.fillStyle = clr < 0 ? '#f44336' : clr < _clearance ? '#ff9800' : '#4caf50';
          ctx.fillText(`${t('terrain.clearance')}${clr.toFixed(0)}m`, x + 6, y + 22);
        }
      }
    }

    // Hover crosshair + tooltip
    if (_hover !== null && _hover >= LEFT && _hover <= w - RIGHT && tElevs && tDists.length > 0) {
      const frac = (_hover - LEFT) / cw;
      const dist = frac * totalD;
      const tTotalD = tDists[tDists.length - 1] || totalD;
      const tFrac = dist / totalD;

      const flightAlt = interpFlightAlt(dist, dists, alts);

      let groundElev = 0;
      const tDist = tFrac * tTotalD;
      for (let i = 0; i < tDists.length - 1; i++) {
        if (tDist >= tDists[i] && tDist <= tDists[i + 1]) {
          const f = (tDist - tDists[i]) / (tDists[i + 1] - tDists[i] || 1);
          groundElev = tElevs[i] + (tElevs[i + 1] - tElevs[i]) * f;
          break;
        }
      }
      if (tDist >= tDists[tDists.length - 1]) groundElev = tElevs[tElevs.length - 1];

      const clearance = flightAlt - groundElev;

      // Vertical line
      ctx.strokeStyle = 'rgba(255,255,255,0.3)';
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(_hover, TOP);
      ctx.lineTo(_hover, TOP + ch);
      ctx.stroke();
      ctx.setLineDash([]);

      // Tooltip box
      const lines = [
        `${t('terrain.distance')}: ${dist >= 1000 ? (dist / 1000).toFixed(2) + 'km' : dist.toFixed(0) + 'm'}`,
        `${t('terrain.flightAlt')}: ${flightAlt.toFixed(0)}m`,
        `${t('terrain.groundElev')}: ${groundElev.toFixed(0)}m`,
        `${t('terrain.clearance')}: ${clearance.toFixed(0)}m`,
      ];
      const boxW = 170,
        boxH = lines.length * 16 + 8;
      let bx = _hover + 12;
      if (bx + boxW > w - 4) bx = _hover - boxW - 12;
      const by = TOP + 8;

      ctx.fillStyle = 'rgba(0,0,0,0.85)';
      ctx.beginPath();
      ctx.roundRect(bx, by, boxW, boxH, 4);
      ctx.fill();

      ctx.font = '11px monospace';
      for (let i = 0; i < lines.length; i++) {
        ctx.fillStyle = i === 3 ? (clearance < 0 ? '#f44336' : clearance < _clearance ? '#ff9800' : '#4caf50') : '#ccc';
        ctx.fillText(lines[i], bx + 8, by + 16 + i * 16);
      }
    }
  });

  function interpFlightAlt(dist: number, dists: number[], alts: number[]): number {
    for (let i = 0; i < dists.length - 1; i++) {
      if (dist >= dists[i] && dist <= dists[i + 1]) {
        const f = (dist - dists[i]) / (dists[i + 1] - dists[i] || 1);
        return alts[i] + (alts[i + 1] - alts[i]) * f;
      }
    }
    return alts[alts.length - 1];
  }

  function niceStep(range: number, maxTicks: number): number {
    const rough = range / maxTicks;
    const pow = Math.pow(10, Math.floor(Math.log10(rough)));
    const norm = rough / pow;
    if (norm <= 1) return pow;
    if (norm <= 2) return 2 * pow;
    if (norm <= 5) return 5 * pow;
    return 10 * pow;
  }

  function onMouseMove(e: MouseEvent) {
    cancelAnimationFrame(frameId);
    frameId = requestAnimationFrame(() => {
      hoverX = e.offsetX;
    });
  }

  function onMouseLeave() {
    hoverX = null;
  }

  function onClick(e: MouseEvent) {
    if (!canvasEl || wps.length < 2) return;
    const LEFT = 48,
      RIGHT = 12;
    const cw = canvasEl.width - LEFT - RIGHT;
    const frac = (e.offsetX - LEFT) / cw;
    const dists: number[] = [0];
    for (let i = 1; i < wps.length; i++) dists.push(dists[i - 1] + segDist(wps[i - 1], wps[i]));
    const totalD = dists[dists.length - 1] || 1;
    const clickDist = frac * totalD;
    let closest = 0,
      minD = Infinity;
    for (let i = 0; i < dists.length; i++) {
      const d = Math.abs(dists[i] - clickDist);
      if (d < minD) {
        minD = d;
        closest = i;
      }
    }
    app.focusWp = closest;
  }
</script>

<div
  role="dialog"
  aria-modal="true"
  class="fixed inset-0 z-[1100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-full max-w-3xl overflow-hidden">
    <!-- Header -->
    <div
      class="flex items-center justify-between px-5 py-3 border-b border-border
                bg-gradient-to-r from-amber-900/30 to-transparent"
    >
      <div class="flex items-center gap-2">
        <Mountain size={18} class="text-amber-500" />
        <h3 class="text-base font-bold text-primary">{t('terrain.profileTitle')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    {#if wps.length < 2}
      <div class="text-center py-20 text-muted-foreground text-sm">{t('terrain.noWaypoints')}</div>
    {:else}
      <!-- Clearance threshold -->
      <div class="flex items-center gap-3 px-5 py-2 border-b border-border/50 bg-muted/20">
        <label for="tp-clearance" class="text-[11px] text-muted-foreground">{t('terrain.minClearance')}:</label>
        <input
          id="tp-clearance"
          type="range"
          min="0"
          max="100"
          step="5"
          bind:value={minClearance}
          class="w-32 h-1.5 accent-amber-500"
        />
        <span class="text-xs font-mono text-foreground w-10">{minClearance}m</span>
        {#if loading}
          <span class="text-[11px] text-amber-500 ml-auto">{t('terrain.loading')}</span>
        {/if}
      </div>

      <!-- Canvas -->
      <div class="px-3 py-3">
        <div class="border border-border/50 rounded-lg overflow-hidden">
          <canvas
            bind:this={canvasEl}
            height="320"
            class="w-full cursor-crosshair"
            onmousemove={onMouseMove}
            onmouseleave={onMouseLeave}
            onclick={onClick}
          ></canvas>
        </div>
      </div>

      <!-- Legend -->
      <div class="flex items-center gap-4 px-5 pb-3 text-[10px] text-muted-foreground">
        <span class="flex items-center gap-1"
          ><span class="w-3 h-2 rounded-sm bg-[rgba(141,110,68,0.5)]"></span>{t('terrain.groundElev')}</span
        >
        <span class="flex items-center gap-1"><span class="w-3 h-0.5 bg-[#1565c0]"></span>{t('terrain.flightAlt')}</span
        >
        <span class="flex items-center gap-1"
          ><span class="w-3 h-2 rounded-sm bg-[rgba(76,175,80,0.3)]"></span>{t('terrain.clearance')}</span
        >
        <span class="flex items-center gap-1"
          ><span class="w-3 h-2 rounded-sm bg-[rgba(244,67,54,0.35)]"></span>{t('terrain.belowMin')}</span
        >
        <span class="ml-auto text-[10px]">{t('terrain.hoverTip')}</span>
      </div>
    {/if}
  </div>
</div>
