<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Box } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let canvasEl: HTMLCanvasElement = $state(null!);
  let rotX = $state(-0.6);
  let rotY = $state(0.4);
  let zoom = $state(1);
  let dragging = $state(false);
  let lastMouse = $state({ x: 0, y: 0 });

  const wps = $derived(app.waypoints);

  $effect(() => {
    if (!canvasEl || wps.length < 2) return;
    const ctx = canvasEl.getContext('2d')!;
    const w = (canvasEl.width = canvasEl.parentElement!.clientWidth);
    const h = canvasEl.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    const cx = w / 2,
      cy = h / 2;
    const cosX = Math.cos(rotX),
      sinX = Math.sin(rotX);
    const cosY = Math.cos(rotY),
      sinY = Math.sin(rotY);

    const cLat = wps.reduce((s, p) => s + p.lat, 0) / wps.length;
    const cLon = wps.reduce((s, p) => s + p.lon, 0) / wps.length;
    const cAlt = wps.reduce((s, p) => s + p.alt, 0) / wps.length;
    const maxRange = Math.max(
      ...wps.map((p) =>
        Math.max(
          Math.abs((p.lat - cLat) * 111320),
          Math.abs((p.lon - cLon) * 111320 * Math.cos((cLat * Math.PI) / 180)),
          Math.abs(p.alt - cAlt),
        ),
      ),
      50,
    );
    const scale = ((Math.min(w, h) / 3) * zoom) / maxRange;

    function project(lat: number, lon: number, alt: number): [number, number] {
      const x = (lon - cLon) * 111320 * Math.cos((cLat * Math.PI) / 180);
      const y = alt - cAlt;
      const z = (lat - cLat) * 111320;
      const y1 = y * cosX - z * sinX;
      const z1 = y * sinX + z * cosX;
      const x1 = x * cosY + z1 * sinY;
      return [cx + x1 * scale, cy - y1 * scale];
    }

    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    const gridN = 5;
    for (let i = -gridN; i <= gridN; i++) {
      const gLat = cLat + ((i / gridN) * maxRange) / 111320;
      const gLon0 = cLon - maxRange / (111320 * Math.cos((cLat * Math.PI) / 180));
      const gLon1 = cLon + maxRange / (111320 * Math.cos((cLat * Math.PI) / 180));
      const [x0, y0] = project(gLat, gLon0, 0);
      const [x1, y1] = project(gLat, gLon1, 0);
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      const gLon = cLon + ((i / gridN) * maxRange) / (111320 * Math.cos((cLat * Math.PI) / 180));
      const gLat0 = cLat - maxRange / 111320;
      const gLat1 = cLat + maxRange / 111320;
      const [xa, ya] = project(gLat0, gLon, 0);
      const [xb, yb] = project(gLat1, gLon, 0);
      ctx.beginPath();
      ctx.moveTo(xa, ya);
      ctx.lineTo(xb, yb);
      ctx.stroke();
    }

    for (const wp of wps) {
      const [px, py] = project(wp.lat, wp.lon, wp.alt);
      const [gx, gy] = project(wp.lat, wp.lon, 0);
      ctx.strokeStyle = '#555';
      ctx.lineWidth = 0.5;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(gx, gy);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.strokeStyle = '#4fc3f7';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < wps.length; i++) {
      const [px, py] = project(wps[i].lat, wps[i].lon, wps[i].alt);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();

    for (let i = 0; i < wps.length; i++) {
      const [px, py] = project(wps[i].lat, wps[i].lon, wps[i].alt);
      ctx.fillStyle = wps[i].drop ? '#e65100' : '#4fc3f7';
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#aaa';
      ctx.font = '9px monospace';
      ctx.fillText(`${i + 1}`, px + 6, py - 4);
      ctx.fillText(`${wps[i].alt.toFixed(0)}m`, px + 6, py + 8);
    }

    ctx.fillStyle = '#666';
    ctx.font = '10px monospace';
    ctx.fillText('N', ...(project(cLat + maxRange / 111320, cLon, 0) as [number, number]));
  });

  function onMouseDown(e: MouseEvent) {
    dragging = true;
    lastMouse = { x: e.clientX, y: e.clientY };
  }
  function onMouseMove(e: MouseEvent) {
    if (!dragging) return;
    rotY += (e.clientX - lastMouse.x) * 0.01;
    rotX += (e.clientY - lastMouse.y) * 0.01;
    lastMouse = { x: e.clientX, y: e.clientY };
  }
  function onMouseUp() {
    dragging = false;
  }
  function onWheel(e: WheelEvent) {
    e.preventDefault();
    zoom = Math.max(0.2, Math.min(5, zoom * (e.deltaY > 0 ? 0.9 : 1.1)));
  }
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center"
  onclick={onclose}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div
    class="bg-card border border-border rounded-2xl overflow-hidden w-[700px] shadow-2xl"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Box size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('panel.mission3d')}</h3>
        <span class="text-xs text-muted-foreground">{wps.length} WP</span>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>
    <div class="px-2 py-2">
      {#if wps.length < 2}
        <div class="text-center py-16 text-muted-foreground text-sm">{t('wp.clickToAdd')}</div>
      {:else}
        <div class="border border-border rounded-lg overflow-hidden">
          <canvas
            bind:this={canvasEl}
            height="400"
            class="w-full cursor-grab"
            onmousedown={onMouseDown}
            onmousemove={onMouseMove}
            onmouseup={onMouseUp}
            onmouseleave={onMouseUp}
            onwheel={onWheel}
          ></canvas>
        </div>
        <div class="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground px-2">
          <span>{t('panel.mission3d.hint')}</span>
          <span>Zoom: {zoom.toFixed(1)}x</span>
        </div>
      {/if}
    </div>
  </div>
</div>
