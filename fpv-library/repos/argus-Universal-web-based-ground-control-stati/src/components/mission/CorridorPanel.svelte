<script lang="ts">
  import { app, pushUndo, saveWaypoints, addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Route } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import type { Waypoint } from '../../lib/types';

  let { onclose }: { onclose: () => void } = $props();

  let width = $state(100);
  let spacing = $state(30);
  let altitude = $state(app.defaultAlt);

  let centerLine = $derived(app.waypoints);
  let canGenerate = $derived(centerLine.length >= 2 && width > 0 && spacing > 0);

  const M_PER_DEG_LAT = 111320;
  function mPerDegLon(lat: number): number {
    return 111320 * Math.cos((lat * Math.PI) / 180);
  }

  function generateCorridor() {
    if (centerLine.length < 2) {
      addToast(t('corridor.hint'), 'warn');
      return;
    }

    const halfWidth = width / 2;
    const numLines = Math.max(1, Math.floor(width / spacing) + 1);
    const offsets: number[] = [];
    if (numLines === 1) {
      offsets.push(0);
    } else {
      for (let i = 0; i < numLines; i++) {
        offsets.push(-halfWidth + i * (width / (numLines - 1)));
      }
    }

    const allLines: { lat: number; lon: number }[][] = [];

    for (const offset of offsets) {
      const line: { lat: number; lon: number }[] = [];
      for (let i = 0; i < centerLine.length; i++) {
        const p = centerLine[i];
        let dx: number, dy: number;

        if (i === 0) {
          const next = centerLine[i + 1];
          dx = (next.lon - p.lon) * mPerDegLon(p.lat);
          dy = (next.lat - p.lat) * M_PER_DEG_LAT;
        } else if (i === centerLine.length - 1) {
          const prev = centerLine[i - 1];
          dx = (p.lon - prev.lon) * mPerDegLon(p.lat);
          dy = (p.lat - prev.lat) * M_PER_DEG_LAT;
        } else {
          const prev = centerLine[i - 1];
          const next = centerLine[i + 1];
          dx = (next.lon - prev.lon) * mPerDegLon(p.lat);
          dy = (next.lat - prev.lat) * M_PER_DEG_LAT;
        }

        const len = Math.sqrt(dx * dx + dy * dy);
        if (len < 1e-9) {
          line.push({ lat: p.lat, lon: p.lon });
          continue;
        }

        // Perpendicular: rotate direction 90 degrees to the right
        const perpLat = ((dx / len) * offset) / M_PER_DEG_LAT;
        const perpLon = ((-dy / len) * offset) / mPerDegLon(p.lat);

        line.push({ lat: p.lat + perpLat, lon: p.lon + perpLon });
      }
      allLines.push(line);
    }

    // Build serpentine waypoints from parallel lines
    const waypoints: Waypoint[] = [];
    for (let i = 0; i < allLines.length; i++) {
      const line = i % 2 === 0 ? allLines[i] : [...allLines[i]].reverse();
      for (const pt of line) {
        waypoints.push({
          lat: pt.lat,
          lon: pt.lon,
          alt: altitude,
          drop: false,
          delay: 0,
          speed: 0,
          type: 'wp' as const,
          loiter_param: 0,
        });
      }
    }

    if (waypoints.length === 0) {
      addToast(t('corridor.hint'), 'warn');
      return;
    }

    pushUndo();
    app.waypoints = [...app.waypoints, ...waypoints];
    saveWaypoints();
    addToast(t('corridor.generate') + ': ' + waypoints.length + ' wp', 'success');
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
    role="presentation"
    class="bg-card border border-border rounded-2xl overflow-hidden w-[450px] max-h-[80vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <Route size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('corridor.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="overflow-y-auto px-5 py-3 space-y-4">
      <p class="text-xs text-muted-foreground">{t('corridor.drawCenter')}</p>

      <div class="text-xs text-muted-foreground">
        {t('corridor.hint')} &mdash; {centerLine.length} pts
      </div>

      {#if centerLine.length >= 2}
        <div class="bg-muted/30 rounded-lg p-2 max-h-24 overflow-y-auto">
          {#each centerLine as pt, i}
            <div class="text-[11px] text-foreground font-mono">
              {i + 1}. {pt.lat.toFixed(6)}, {pt.lon.toFixed(6)}
            </div>
          {/each}
        </div>
      {/if}

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2">
          <label for="cor-width" class="text-xs text-muted-foreground w-20 shrink-0">{t('corridor.width')}</label>
          <input
            id="cor-width"
            type="number"
            min="10"
            max="1000"
            step="10"
            bind:value={width}
            class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
          <span class="text-xs text-muted-foreground">m</span>
        </div>
        <div class="flex items-center gap-2">
          <label for="cor-spacing" class="text-xs text-muted-foreground w-20 shrink-0">{t('corridor.spacing')}</label>
          <input
            id="cor-spacing"
            type="number"
            min="5"
            max="200"
            step="5"
            bind:value={spacing}
            class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
          <span class="text-xs text-muted-foreground">m</span>
        </div>
        <div class="flex items-center gap-2">
          <label for="cor-alt" class="text-xs text-muted-foreground w-20 shrink-0">{t('survey.altitude')}</label>
          <input
            id="cor-alt"
            type="number"
            min="5"
            max="500"
            step="5"
            bind:value={altitude}
            class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
          <span class="text-xs text-muted-foreground">m</span>
        </div>
      </div>

      <Button variant="default" class="w-full" onclick={generateCorridor} disabled={!canGenerate}>
        {t('corridor.generate')}
      </Button>
    </div>
  </div>
</div>
