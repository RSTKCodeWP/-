<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Camera } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Camera presets ── */
  interface CameraPreset {
    name: string;
    focal: number;
    sw: number;
    sh: number;
    iw: number;
    ih: number;
  }

  const presets: CameraPreset[] = [
    { name: 'DJI Phantom 4 Pro', focal: 8.8, sw: 13.2, sh: 8.8, iw: 5472, ih: 3648 },
    { name: 'DJI Mavic 3', focal: 12.29, sw: 17.3, sh: 13.0, iw: 5280, ih: 3956 },
    { name: 'Sony A7R', focal: 35, sw: 35.9, sh: 24.0, iw: 7952, ih: 5304 },
    { name: 'Custom', focal: 0, sw: 0, sh: 0, iw: 0, ih: 0 },
  ];

  let selectedPreset = $state(0);
  let focalLength = $state(8.8);
  let sensorWidth = $state(13.2);
  let sensorHeight = $state(8.8);
  let imageWidth = $state(5472);
  let imageHeight = $state(3648);
  let altitude = $state(100);
  let frontOverlap = $state(75);
  let sideOverlap = $state(65);

  function applyPreset(idx: number) {
    selectedPreset = idx;
    const p = presets[idx];
    if (p.name === 'Custom') return;
    focalLength = p.focal;
    sensorWidth = p.sw;
    sensorHeight = p.sh;
    imageWidth = p.iw;
    imageHeight = p.ih;
  }

  /* ── Derived calculations ── */
  let gsd = $derived(
    focalLength > 0 && imageWidth > 0 ? ((sensorWidth * altitude) / (focalLength * imageWidth)) * 100 : 0,
  );

  let footprintW = $derived(focalLength > 0 ? (sensorWidth * altitude) / focalLength : 0);

  let footprintH = $derived(focalLength > 0 ? (sensorHeight * altitude) / focalLength : 0);

  let triggerDist = $derived(footprintH * (1 - frontOverlap / 100));

  let lineSpacing = $derived(footprintW * (1 - sideOverlap / 100));

  let hasResult = $derived(gsd > 0 && triggerDist > 0 && lineSpacing > 0);

  function applyToSurvey() {
    if (!hasResult) return;
    app.surveySpacing = Math.round(lineSpacing);
    addToast(
      t('overlap.result')
        .replace('{s}', lineSpacing.toFixed(1))
        .replace('{f}', triggerDist.toFixed(1))
        .replace('{g}', gsd.toFixed(2)),
      'success',
    );
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[450px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Camera size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('overlap.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      <!-- Camera preset selector -->
      <div class="mb-4">
        <label for="oc-preset" class="text-xs text-muted-foreground block mb-1">Camera</label>
        <select
          id="oc-preset"
          value={selectedPreset}
          onchange={(e) => applyPreset(Number((e.target as HTMLSelectElement).value))}
          class="w-full h-8 px-2 bg-input border border-border rounded-md text-xs text-foreground
                       focus:outline-none focus:ring-1 focus:ring-ring/50"
        >
          {#each presets as p, i}
            <option value={i}>{p.name}</option>
          {/each}
        </select>
      </div>

      <!-- Camera parameters -->
      <div class="grid grid-cols-2 gap-x-3 gap-y-2.5 mb-4">
        <div class="flex flex-col gap-0.5">
          <label for="oc-focal" class="text-[11px] text-muted-foreground">{t('overlap.focalLength')}</label>
          <input
            id="oc-focal"
            type="number"
            min="1"
            max="500"
            step="0.1"
            bind:value={focalLength}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
        <div class="flex flex-col gap-0.5">
          <label for="oc-alt" class="text-[11px] text-muted-foreground">{t('overlap.altitude')}</label>
          <input
            id="oc-alt"
            type="number"
            min="5"
            max="1000"
            step="5"
            bind:value={altitude}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
        <div class="flex flex-col gap-0.5">
          <label for="oc-sw" class="text-[11px] text-muted-foreground">{t('overlap.sensorWidth')}</label>
          <input
            id="oc-sw"
            type="number"
            min="0.1"
            max="100"
            step="0.1"
            bind:value={sensorWidth}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
        <div class="flex flex-col gap-0.5">
          <label for="oc-sh" class="text-[11px] text-muted-foreground">{t('overlap.sensorHeight')}</label>
          <input
            id="oc-sh"
            type="number"
            min="0.1"
            max="100"
            step="0.1"
            bind:value={sensorHeight}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
        <div class="flex flex-col gap-0.5">
          <label for="oc-iw" class="text-[11px] text-muted-foreground">{t('overlap.imageWidth')}</label>
          <input
            id="oc-iw"
            type="number"
            min="100"
            max="20000"
            step="1"
            bind:value={imageWidth}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
        <div class="flex flex-col gap-0.5">
          <label for="oc-ih" class="text-[11px] text-muted-foreground">{t('overlap.imageHeight')}</label>
          <input
            id="oc-ih"
            type="number"
            min="100"
            max="20000"
            step="1"
            bind:value={imageHeight}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
      </div>

      <!-- Overlap sliders -->
      <div class="flex flex-col gap-2.5 mb-4">
        <div class="flex items-center gap-2">
          <label for="oc-front" class="text-xs text-muted-foreground w-24 shrink-0">{t('overlap.frontOverlap')}</label>
          <input
            id="oc-front"
            type="range"
            min="10"
            max="95"
            step="5"
            bind:value={frontOverlap}
            class="flex-1 accent-primary"
          />
          <span class="text-xs text-muted-foreground min-w-[36px] text-right">{frontOverlap}%</span>
        </div>
        <div class="flex items-center gap-2">
          <label for="oc-side" class="text-xs text-muted-foreground w-24 shrink-0">{t('overlap.sideOverlap')}</label>
          <input
            id="oc-side"
            type="range"
            min="10"
            max="95"
            step="5"
            bind:value={sideOverlap}
            class="flex-1 accent-primary"
          />
          <span class="text-xs text-muted-foreground min-w-[36px] text-right">{sideOverlap}%</span>
        </div>
      </div>

      <!-- Results -->
      {#if hasResult}
        <div class="rounded-lg border border-primary/30 bg-primary/5 p-3 mb-4">
          <div class="grid grid-cols-3 gap-3 text-center">
            <div>
              <div class="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{t('overlap.gsd')}</div>
              <div class="text-sm font-bold text-primary">{gsd.toFixed(2)}</div>
              <div class="text-[10px] text-muted-foreground">cm/px</div>
            </div>
            <div>
              <div class="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{t('survey.spacing')}</div>
              <div class="text-sm font-bold text-primary">{lineSpacing.toFixed(1)}</div>
              <div class="text-[10px] text-muted-foreground">m</div>
            </div>
            <div>
              <div class="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{t('overlap.trigger')}</div>
              <div class="text-sm font-bold text-primary">{triggerDist.toFixed(1)}</div>
              <div class="text-[10px] text-muted-foreground">m</div>
            </div>
          </div>
          <div class="mt-2 pt-2 border-t border-primary/20 grid grid-cols-2 gap-2 text-[11px] text-muted-foreground">
            <span>{t('overlap.footprint')}: {footprintW.toFixed(1)} x {footprintH.toFixed(1)} m</span>
            <span class="text-right">{t('overlap.coverage')}: {((footprintW * footprintH) / 10000).toFixed(2)} ha</span>
          </div>
        </div>
      {:else}
        <div class="rounded-lg border border-border bg-muted/30 p-3 mb-4 text-center">
          <p class="text-xs text-muted-foreground">{t('overlap.spacing')}</p>
        </div>
      {/if}

      <!-- Apply button -->
      <Button variant="default" class="w-full" onclick={applyToSurvey} disabled={!hasResult}>
        {t('overlap.apply')}
      </Button>
    </div>
  </div>
</div>
