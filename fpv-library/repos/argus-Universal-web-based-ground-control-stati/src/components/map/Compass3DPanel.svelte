<script lang="ts">
  import { untrack } from 'svelte';
  import { app } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { isSerialConnected, serialCalCompass } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Compass } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let canvasEl: HTMLCanvasElement = $state(null!);
  let samples: { x: number; y: number; z: number }[] = $state([]);
  let rotX = $state(-0.5);
  let rotY = $state(0.5);
  let dragging = $state(false);
  let lastMouse = $state({ x: 0, y: 0 });

  let wasConnected = false;
  $effect(() => {
    const d = app.drone;
    if (!d.connected) {
      wasConnected = false;
      return;
    }
    if (!wasConnected) {
      // Fresh session (connect or reconnect) — a mixed old/new sphere from a
      // different vehicle or mounting would mislead the calibration read.
      wasConnected = true;
      untrack(() => samples.splice(0, samples.length));
    }
    // Raw magnetometer field in milligauss (backend RAW_IMU push) — during a
    // cal rotation these trace the sphere the calibrator is fitting.
    const raw = d.mag;
    if (!raw || (raw[0] === 0 && raw[1] === 0 && raw[2] === 0)) return;
    // untrack the sample mutation so the effect isn't dirtied by its own write
    untrack(() => {
      const last = samples[samples.length - 1];
      if (last && last.x === raw[0] && last.y === raw[1] && last.z === raw[2]) return;
      samples.push({ x: raw[0], y: raw[1], z: raw[2] });
      if (samples.length > 2000) samples.splice(0, samples.length - 1500);
    });
  });

  $effect(() => {
    if (!canvasEl || samples.length < 2) return;
    const ctx = canvasEl.getContext('2d')!;
    const w = (canvasEl.width = canvasEl.parentElement!.clientWidth);
    const h = canvasEl.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);
    const cx = w / 2,
      cy = h / 2;
    const scale = Math.min(w, h) / 3;
    const cosX = Math.cos(rotX),
      sinX = Math.sin(rotX);
    const cosY = Math.cos(rotY),
      sinY = Math.sin(rotY);

    function project(x: number, y: number, z: number): [number, number] {
      const y1 = y * cosX - z * sinX;
      const z1 = y * sinX + z * cosX;
      const x1 = x * cosY + z1 * sinY;
      return [cx + x1 * scale, cy - y1 * scale];
    }

    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 12) {
      const pts: [number, number][] = [];
      for (let b = 0; b <= Math.PI * 2; b += Math.PI / 24) {
        pts.push(project(Math.cos(a) * Math.cos(b), Math.sin(a) * Math.cos(b), Math.sin(b)));
      }
      ctx.beginPath();
      pts.forEach(([px, py], i) => (i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)));
      ctx.stroke();
    }

    const maxVal = Math.max(...samples.map((s) => Math.max(Math.abs(s.x), Math.abs(s.y), Math.abs(s.z))), 1);
    for (const s of samples) {
      const nx = s.x / maxVal,
        ny = s.y / maxVal,
        nz = s.z / maxVal;
      const [px, py] = project(nx, ny, nz);
      const dist = Math.sqrt(nx * nx + ny * ny + nz * nz);
      ctx.fillStyle = dist > 0.7 ? '#4fc3f7' : '#ff9800';
      ctx.fillRect(px - 1, py - 1, 2, 2);
    }

    ctx.fillStyle = '#fff';
    ctx.font = '10px monospace';
    ctx.fillText(`${t('compass3d.samples')}: ${samples.length}`, 8, 14);
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

  function startCal() {
    if (isSerialConnected()) serialCalCompass();
    else dispatch('cal_compass');
  }
  function clearSamples() {
    samples = [];
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[500px] shadow-2xl"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Compass size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('compass3d.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>
    <div class="px-5 py-3">
      <p class="text-xs text-muted-foreground mb-3">{t('compass3d.hint')}</p>
      <div class="border border-border rounded-lg overflow-hidden">
        <canvas
          bind:this={canvasEl}
          height="300"
          class="w-full cursor-grab"
          onmousedown={onMouseDown}
          onmousemove={onMouseMove}
          onmouseup={onMouseUp}
          onmouseleave={onMouseUp}
        ></canvas>
      </div>
      <div class="flex gap-2 mt-3">
        <Button variant="default" size="sm" onclick={startCal} disabled={!app.drone.connected}>{t('cal.start')}</Button>
        <Button variant="outline" size="sm" onclick={clearSamples}>{t('inspector.clear')}</Button>
      </div>
    </div>
  </div>
</div>
