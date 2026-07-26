<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import { X, Crosshair } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  let lat = $state(app.drone.lat || 0);
  let lon = $state(app.drone.lon || 0);
  let alt = $state(app.defaultAlt);
  let roiSet = $state(false);
  let roiLat = $state(0);
  let roiLon = $state(0);
  let roiAlt = $state(0);

  function setRoi() {
    if (lat === 0 && lon === 0) {
      addToast(t('poi.hint'), 'warn');
      return;
    }
    roiLat = lat;
    roiLon = lon;
    roiAlt = alt;
    roiSet = true;
    dispatch('do_set_roi', undefined, { lat, lon, alt });
    addToast(t('poi.set') + `: ${lat.toFixed(6)}, ${lon.toFixed(6)}, ${alt}m`, 'success');
  }

  function clearRoi() {
    roiSet = false;
    roiLat = 0;
    roiLon = 0;
    roiAlt = 0;
    addToast(t('poi.clear'), 'info');
  }

  function prefillFromDrone() {
    if (app.drone.lat !== 0 || app.drone.lon !== 0) {
      lat = app.drone.lat;
      lon = app.drone.lon;
      alt = app.drone.alt_rel || app.defaultAlt;
    }
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[350px] max-h-[80vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <Crosshair size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('poi.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="overflow-y-auto px-5 py-3 space-y-4">
      {#if roiSet}
        <div class="bg-muted/30 rounded-lg p-2">
          <div class="text-[11px] font-semibold text-primary uppercase tracking-wider mb-1">ROI</div>
          <div class="text-xs text-foreground font-mono">
            {roiLat.toFixed(6)}, {roiLon.toFixed(6)}
          </div>
          <div class="text-xs text-muted-foreground">{roiAlt}m</div>
        </div>
      {:else}
        <div class="text-xs text-muted-foreground italic">{t('poi.notSet')}</div>
      {/if}

      <div class="flex flex-col gap-2">
        <div class="flex items-center gap-2">
          <label for="poi-lat" class="text-xs text-muted-foreground w-10 shrink-0">Lat</label>
          <input
            id="poi-lat"
            type="number"
            step="0.000001"
            bind:value={lat}
            class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
        </div>
        <div class="flex items-center gap-2">
          <label for="poi-lon" class="text-xs text-muted-foreground w-10 shrink-0">Lon</label>
          <input
            id="poi-lon"
            type="number"
            step="0.000001"
            bind:value={lon}
            class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
        </div>
        <div class="flex items-center gap-2">
          <label for="poi-alt" class="text-xs text-muted-foreground w-10 shrink-0">Alt</label>
          <input
            id="poi-alt"
            type="number"
            min="0"
            max="500"
            step="5"
            bind:value={alt}
            class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
          <span class="text-xs text-muted-foreground">m</span>
        </div>
      </div>

      {#if app.drone.connected}
        <Button variant="outline" size="sm" class="w-full" onclick={prefillFromDrone}>{t('poi.dronePos')}</Button>
      {/if}

      <div class="flex gap-2">
        <Button variant="default" class="flex-1" onclick={setRoi}>
          {t('poi.set')}
        </Button>
        <Button variant="outline" class="flex-1" onclick={clearRoi} disabled={!roiSet}>
          {t('poi.clear')}
        </Button>
      </div>

      <p class="text-[11px] text-muted-foreground text-center">{t('poi.hint')}</p>
    </div>
  </div>
</div>
