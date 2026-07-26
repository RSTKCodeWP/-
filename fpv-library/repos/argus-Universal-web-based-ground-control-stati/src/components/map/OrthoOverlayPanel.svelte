<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Image, Upload } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  const STORAGE_KEY = 'argus_ortho_overlays';

  interface OrthoOverlay {
    id: number;
    dataUrl: string;
    nwLat: number;
    nwLon: number;
    seLat: number;
    seLon: number;
    opacity: number;
  }

  let overlays: OrthoOverlay[] = $state(loadOverlays());
  let nwLat = $state(0);
  let nwLon = $state(0);
  let seLat = $state(0);
  let seLon = $state(0);
  let opacity = $state(80);
  let pendingDataUrl = $state('');
  let pendingFileName = $state('');

  function loadOverlays(): OrthoOverlay[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch {}
    return [];
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(overlays));
    } catch {}
  }

  function handleUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      addToast(t('ortho.invalidFile'), 'warn');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      pendingDataUrl = reader.result as string;
      pendingFileName = file.name;
      addToast(t('ortho.imageLoaded'), 'success');
    };
    reader.readAsDataURL(file);
    input.value = '';
  }

  function applyOverlay() {
    if (!pendingDataUrl) {
      addToast(t('ortho.noImage'), 'warn');
      return;
    }
    if (nwLat === 0 && nwLon === 0 && seLat === 0 && seLon === 0) {
      addToast(t('ortho.noCoords'), 'warn');
      return;
    }
    overlays.push({
      id: Date.now(),
      dataUrl: pendingDataUrl,
      nwLat,
      nwLon,
      seLat,
      seLon,
      opacity: opacity / 100,
    });
    persist();
    pendingDataUrl = '';
    pendingFileName = '';
    nwLat = 0;
    nwLon = 0;
    seLat = 0;
    seLon = 0;
    opacity = 80;
    addToast(t('ortho.applied'), 'success');
  }

  function removeOverlay(id: number) {
    const idx = overlays.findIndex((o) => o.id === id);
    if (idx >= 0) {
      overlays.splice(idx, 1);
      persist();
    }
  }
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
  onclick={(e) => {
    if (e.target === e.currentTarget) onclose();
  }}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[500px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Image size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('ortho.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
      <!-- Upload button -->
      <label
        class="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-lg border border-dashed border-border
                     bg-muted/20 hover:bg-muted/40 cursor-pointer transition-colors text-xs text-muted-foreground"
      >
        <Upload size={14} />
        {pendingFileName || t('ortho.upload')}
        <input type="file" accept=".jpg,.jpeg,.png" class="hidden" onchange={handleUpload} />
      </label>

      <!-- Corner coordinate inputs -->
      <div class="space-y-2">
        <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('ortho.nwCorner')}</div>
        <div class="grid grid-cols-2 gap-2">
          <div class="flex items-center gap-1">
            <label for="nw-lat" class="text-[11px] text-muted-foreground w-8 shrink-0">{t('label.lat')}</label>
            <input
              id="nw-lat"
              type="number"
              step="0.000001"
              bind:value={nwLat}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-1">
            <label for="nw-lon" class="text-[11px] text-muted-foreground w-8 shrink-0">{t('label.lon')}</label>
            <input
              id="nw-lon"
              type="number"
              step="0.000001"
              bind:value={nwLon}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
        </div>

        <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('ortho.seCorner')}</div>
        <div class="grid grid-cols-2 gap-2">
          <div class="flex items-center gap-1">
            <label for="se-lat" class="text-[11px] text-muted-foreground w-8 shrink-0">{t('label.lat')}</label>
            <input
              id="se-lat"
              type="number"
              step="0.000001"
              bind:value={seLat}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-1">
            <label for="se-lon" class="text-[11px] text-muted-foreground w-8 shrink-0">{t('label.lon')}</label>
            <input
              id="se-lon"
              type="number"
              step="0.000001"
              bind:value={seLon}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
        </div>
      </div>

      <!-- Opacity slider -->
      <div class="flex items-center gap-3">
        <span class="text-xs text-muted-foreground w-16 shrink-0">{t('ortho.opacity')}</span>
        <input
          type="range"
          min="0"
          max="100"
          bind:value={opacity}
          class="flex-1 h-1 appearance-none bg-border rounded-full [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
        />
        <span class="text-xs font-mono text-foreground w-8 text-right">{opacity}%</span>
      </div>

      <!-- Apply button -->
      <Button variant="default" class="w-full" onclick={applyOverlay}>
        {t('ortho.apply')}
      </Button>

      <!-- Active overlays list -->
      {#if overlays.length > 0}
        <div class="space-y-1">
          <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {t('ortho.active')} ({overlays.length})
          </div>
          {#each overlays as ov (ov.id)}
            <div class="flex items-center gap-2 bg-muted/20 rounded-lg p-2 group">
              <Image size={14} class="text-primary shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="text-[11px] font-mono text-foreground truncate">
                  {t('label.nw')}: {ov.nwLat.toFixed(4)}, {ov.nwLon.toFixed(4)}
                </div>
                <div class="text-[11px] font-mono text-muted-foreground truncate">
                  {t('label.se')}: {ov.seLat.toFixed(4)}, {ov.seLon.toFixed(4)} | {Math.round(ov.opacity * 100)}%
                </div>
              </div>
              <button
                class="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-destructive hover:bg-destructive/10 rounded"
                onclick={() => removeOverlay(ov.id)}
              >
                <X size={13} />
              </button>
            </div>
          {/each}
        </div>
      {/if}

      <!-- Hint -->
      <div class="p-3 rounded-lg bg-primary/5 border border-primary/20">
        <p class="text-xs text-muted-foreground leading-relaxed">
          {t('ortho.hint')}
        </p>
      </div>
    </div>
  </div>
</div>
