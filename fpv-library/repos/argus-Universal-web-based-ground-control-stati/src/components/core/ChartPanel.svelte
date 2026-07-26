<script lang="ts">
  import { untrack } from 'svelte';
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';

  const MAX = 120;
  let altData: number[] = [];
  let spdData: number[] = [];
  let batData: number[] = [];
  let curData: number[] = [];
  let vzData: number[] = [];
  let vibeData: number[] = [];

  $effect(() => {
    if (!app.drone.connected) return;
    const alt = app.drone.alt_rel;
    const spd = app.drone.gs;
    const bat = app.drone.voltage;
    const cur = app.drone.current;
    const vz = app.drone.vz;
    const vb = Math.max(app.drone.vibe[0], app.drone.vibe[1], app.drone.vibe[2]);
    untrack(() => {
      altData.push(alt);
      spdData.push(spd);
      batData.push(bat);
      curData.push(cur);
      vzData.push(vz);
      vibeData.push(vb);
      if (altData.length > MAX) altData.shift();
      if (spdData.length > MAX) spdData.shift();
      if (batData.length > MAX) batData.shift();
      if (curData.length > MAX) curData.shift();
      if (vzData.length > MAX) vzData.shift();
      if (vibeData.length > MAX) vibeData.shift();
    });
    untrack(() => {
      draw(cAlt, altData, '#4fc3f7');
      draw(cSpd, spdData, '#69f0ae');
      draw(cBat, batData, '#ffa726');
      draw(cCur, curData, '#ff5252');
      draw(cVz, vzData, '#ce93d8');
      draw(cVibe, vibeData, '#ffab91');
    });
  });

  function draw(canvas: HTMLCanvasElement | null, data: number[], color: string) {
    if (!canvas || data.length < 2) return;
    const ctx = canvas.getContext('2d')!;
    const w = (canvas.width = canvas.parentElement!.clientWidth);
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    let mn = Math.min(...data),
      mx = Math.max(...data);
    if (mx === mn) {
      mx += 1;
      mn -= 1;
    }
    const rng = mx - mn;
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    for (let i = 0; i < 4; i++) {
      const y = (h * i) / 3;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    ctx.fillStyle = '#666';
    ctx.font = '9px monospace';
    ctx.fillText(mx.toFixed(1), 2, 10);
    ctx.fillText(mn.toFixed(1), 2, h - 3);
    const pts: [number, number][] = [];
    for (let i = 0; i < data.length; i++) {
      pts.push([(i / (data.length - 1)) * w, (1 - (data[i] - mn) / rng) * (h - 4) + 2]);
    }
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, color + '30');
    grad.addColorStop(1, color + '05');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], h);
    for (const [x, y] of pts) ctx.lineTo(x, y);
    ctx.lineTo(pts[pts.length - 1][0], h);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]);
      else ctx.lineTo(pts[i][0], pts[i][1]);
    }
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.font = 'bold 11px monospace';
    ctx.fillText(data[data.length - 1].toFixed(1), w - 45, 12);
  }

  let cAlt: HTMLCanvasElement = $state(null!);
  let cSpd: HTMLCanvasElement = $state(null!);
  let cBat: HTMLCanvasElement = $state(null!);
  let cCur: HTMLCanvasElement = $state(null!);
  let cVz: HTMLCanvasElement = $state(null!);
  let cVibe: HTMLCanvasElement = $state(null!);
</script>

<div class="bg-card border border-border rounded-xl p-4">
  <h2 class="text-sm font-semibold text-primary uppercase tracking-wider mb-2">{t('chart.title')}</h2>
  {#if !app.drone.connected}
    <div class="text-muted-foreground text-xs text-center py-8">{t('chart.empty')}</div>
  {:else}
    <div class="grid grid-cols-3 gap-2 max-md:grid-cols-2">
      <div>
        <div class="text-[11px] text-muted-foreground mb-0.5">{t('chart.alt')}</div>
        <canvas bind:this={cAlt} height="72" class="w-full bg-background rounded-lg"></canvas>
      </div>
      <div>
        <div class="text-[11px] text-muted-foreground mb-0.5">{t('chart.speed')}</div>
        <canvas bind:this={cSpd} height="72" class="w-full bg-background rounded-lg"></canvas>
      </div>
      <div>
        <div class="text-[11px] text-muted-foreground mb-0.5">{t('chart.vs')}</div>
        <canvas bind:this={cVz} height="72" class="w-full bg-background rounded-lg"></canvas>
      </div>
      <div>
        <div class="text-[11px] text-muted-foreground mb-0.5">{t('chart.voltage')}</div>
        <canvas bind:this={cBat} height="72" class="w-full bg-background rounded-lg"></canvas>
      </div>
      <div>
        <div class="text-[11px] text-muted-foreground mb-0.5">{t('chart.current')}</div>
        <canvas bind:this={cCur} height="72" class="w-full bg-background rounded-lg"></canvas>
      </div>
      <div>
        <div class="text-[11px] text-muted-foreground mb-0.5">{t('chart.vibe')}</div>
        <canvas bind:this={cVibe} height="72" class="w-full bg-background rounded-lg"></canvas>
      </div>
    </div>
  {/if}
</div>
