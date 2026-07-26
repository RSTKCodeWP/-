<script lang="ts">
  import { onMount } from 'svelte';
  import { app, addToast } from '../../lib/stores.svelte';
  import { apiUrl } from '../../lib/backend';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Download, HardDrive } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let latMin = $state(34.2);
  let latMax = $state(34.3);
  let lonMin = $state(108.9);
  let lonMax = $state(109.0);
  let zMin = $state(10);
  let zMax = $state(16);
  let style = $state('6');
  let downloading = $state(false);
  let result = $state<{ total: number; downloaded: number; skipped: number } | null>(null);
  let cacheInfo = $state<{ size: number; count: number } | null>(null);

  // Snapshot drone position once on mount instead of via $effect, so the user's
  // manually-edited bounding box isn't clobbered by every telemetry frame.
  onMount(() => {
    fetch(apiUrl('/api/tile_cache'))
      .then((r) => r.json())
      .then((d) => (cacheInfo = d))
      .catch(() => {});
    if (app.drone.lat !== 0) {
      latMin = app.drone.lat - 0.05;
      latMax = app.drone.lat + 0.05;
      lonMin = app.drone.lon - 0.05;
      lonMax = app.drone.lon + 0.05;
    }
  });

  let estimatedTiles = $derived.by(() => {
    let total = 0;
    for (let z = zMin; z <= zMax; z++) {
      const n = 2 ** z;
      const xRange = Math.ceil(((lonMax - lonMin) / 360) * n) + 1;
      const yRange = Math.ceil(((latMax - latMin) / 180) * n) + 1;
      total += xRange * yRange;
    }
    return Math.min(total, 5000);
  });

  async function startDownload() {
    downloading = true;
    result = null;
    try {
      const r = await fetch(apiUrl('/api/tile_bulk_download'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat_min: latMin,
          lat_max: latMax,
          lon_min: lonMin,
          lon_max: lonMax,
          z_min: zMin,
          z_max: zMax,
          style,
        }),
      });
      result = await r.json();
      addToast(t('offmap.done'), 'success');
      fetch(apiUrl('/api/tile_cache'))
        .then((r) => r.json())
        .then((d) => (cacheInfo = d))
        .catch(() => {});
    } catch (err: unknown) {
      addToast(err instanceof Error ? err.message : String(err), 'error');
    }
    downloading = false;
  }

  function fmtSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[450px] shadow-2xl"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <HardDrive size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('offmap.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>
    <div class="px-5 py-4 space-y-3">
      {#if cacheInfo}
        <div class="flex justify-between text-xs text-muted-foreground p-2 bg-muted rounded-lg">
          <span>{t('label.cache')}: {cacheInfo.count} tiles</span>
          <span>{fmtSize(cacheInfo.size)}</span>
        </div>
      {/if}
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span class="text-muted-foreground">{t('label.latMin')}</span>
          <input
            type="number"
            step="0.01"
            bind:value={latMin}
            class="w-full h-7 px-2 bg-input border border-border rounded text-xs font-mono"
          />
        </div>
        <div>
          <span class="text-muted-foreground">{t('label.latMax')}</span>
          <input
            type="number"
            step="0.01"
            bind:value={latMax}
            class="w-full h-7 px-2 bg-input border border-border rounded text-xs font-mono"
          />
        </div>
        <div>
          <span class="text-muted-foreground">{t('label.lonMin')}</span>
          <input
            type="number"
            step="0.01"
            bind:value={lonMin}
            class="w-full h-7 px-2 bg-input border border-border rounded text-xs font-mono"
          />
        </div>
        <div>
          <span class="text-muted-foreground">{t('label.lonMax')}</span>
          <input
            type="number"
            step="0.01"
            bind:value={lonMax}
            class="w-full h-7 px-2 bg-input border border-border rounded text-xs font-mono"
          />
        </div>
      </div>
      <div class="flex gap-3 items-center text-xs">
        <span class="text-muted-foreground">{t('offmap.zoomRange')}:</span>
        <input
          type="number"
          min="1"
          max="18"
          bind:value={zMin}
          class="w-12 h-7 px-1 bg-input border border-border rounded text-xs text-center"
        />
        <span>—</span>
        <input
          type="number"
          min="1"
          max="18"
          bind:value={zMax}
          class="w-12 h-7 px-1 bg-input border border-border rounded text-xs text-center"
        />
        <select bind:value={style} class="h-7 px-1 bg-input border border-border rounded text-xs">
          <option value="6">{t('label.satellite')}</option>
          <option value="7">{t('label.vector')}</option>
          <option value="osm">OSM</option>
        </select>
      </div>
      <div class="text-xs text-muted-foreground">
        {t('offmap.estimateTiles').replace('{n}', String(estimatedTiles))}
      </div>
      {#if result}
        <div class="text-xs p-2 bg-muted rounded-lg">
          Total: {result.total} · Downloaded: {result.downloaded} · Cached: {result.skipped}
        </div>
      {/if}
      <Button variant="default" class="w-full" onclick={startDownload} disabled={downloading}>
        <Download size={14} class="mr-1" />
        {downloading
          ? t('offmap.downloading').replace('{done}', '...').replace('{total}', String(estimatedTiles))
          : t('offmap.download')}
      </Button>
    </div>
  </div>
</div>
