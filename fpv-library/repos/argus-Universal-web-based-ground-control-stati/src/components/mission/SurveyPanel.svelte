<script lang="ts">
  import { app, pushUndo, saveWaypoints, addToast } from '../../lib/stores.svelte';
  import { generateSurveyGrid, polygonArea } from '../../lib/survey';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let angle = $state(0);
  let overshoot = $state(10);

  let polyPts = $derived(app.surveyPolygon);
  let area = $derived(polygonArea(polyPts));
  let previewCount = $derived.by(() => {
    if (polyPts.length < 3) return 0;
    return generateSurveyGrid(polyPts, { angle, spacing: app.surveySpacing, alt: app.defaultAlt, overshoot }).length;
  });

  function generate() {
    if (polyPts.length < 3) return;
    const wps = generateSurveyGrid(polyPts, { angle, spacing: app.surveySpacing, alt: app.defaultAlt, overshoot });
    if (wps.length === 0) {
      addToast(t('survey.genFail'), 'warn');
      return;
    }
    pushUndo();
    app.waypoints = [...app.waypoints, ...wps];
    saveWaypoints();
    addToast(t('survey.genDone').replace('{n}', String(wps.length)), 'success');
  }

  function clearPoly() {
    app.surveyPolygon = [];
    app.drawingPolygon = false;
  }

  function fmtArea(m2: number): string {
    if (m2 < 10000) return m2.toFixed(0) + ' m²';
    return (m2 / 10000).toFixed(2) + ' ' + t('survey.hectare');
  }
</script>

<div class="bg-card border border-border rounded-xl p-3 mx-2 mb-2">
  <h2 class="text-sm font-semibold text-primary uppercase tracking-wider mb-2">{t('survey.title')}</h2>

  {#if !app.drawingPolygon && polyPts.length < 3}
    <button
      class="w-full py-3 bg-transparent border-2 border-dashed border-border rounded-lg cursor-pointer
                    text-sm font-bold text-primary hover:border-primary transition-colors"
      onclick={() => {
        app.surveyPolygon = [];
        app.drawingPolygon = true;
      }}
    >
      {t('survey.drawArea')}
    </button>
    <div class="text-[11px] text-muted-foreground mt-1 text-center">{t('survey.drawHint')}</div>
  {:else if app.drawingPolygon}
    <div class="flex items-center gap-2 text-sm">
      <span>{t('survey.vertexCount').replace('{n}', String(polyPts.length))}</span>
      {#if polyPts.length >= 3}
        <Button variant="default" size="xs" onclick={() => (app.drawingPolygon = false)}
          >{t('survey.finishDraw')}</Button
        >
      {/if}
      <Button variant="ghost" size="xs" onclick={clearPoly}>{t('map.cancel')}</Button>
    </div>
  {:else}
    <div class="flex items-center gap-2 text-xs text-muted-foreground mb-2">
      <span>{t('survey.area')}: {fmtArea(area)} | {polyPts.length} {t('survey.vertex')}</span>
      <Button variant="outline" size="xs" onclick={() => (app.drawingPolygon = true)}>{t('survey.edit')}</Button>
      <Button variant="ghost" size="xs" onclick={clearPoly}>{t('survey.clear')}</Button>
    </div>
    <div class="flex flex-col gap-2">
      <div class="flex items-center gap-2">
        <label for="sv-angle" class="text-xs text-muted-foreground w-16 shrink-0">{t('survey.angle')}</label>
        <input id="sv-angle" type="range" min="0" max="180" step="5" bind:value={angle} class="flex-1 accent-primary" />
        <span class="text-xs text-muted-foreground min-w-[30px]">{angle}°</span>
      </div>
      <div class="flex items-center gap-2">
        <label for="sv-spacing" class="text-xs text-muted-foreground w-16 shrink-0">{t('survey.spacing')}</label>
        <input
          id="sv-spacing"
          type="number"
          min="5"
          max="200"
          step="5"
          bind:value={app.surveySpacing}
          class="w-16 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
        />
        <span class="text-xs text-muted-foreground">m</span>
      </div>
      <div class="flex items-center gap-2">
        <label for="sv-over" class="text-xs text-muted-foreground w-16 shrink-0">{t('survey.overshoot')}</label>
        <input
          id="sv-over"
          type="number"
          min="0"
          max="100"
          step="5"
          bind:value={overshoot}
          class="w-16 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
        />
        <span class="text-xs text-muted-foreground">m</span>
      </div>
      <div class="text-xs text-muted-foreground mt-1">
        {t('survey.previewCount')} <b class="text-foreground">{previewCount}</b>
        {t('survey.waypointUnit')} | {t('survey.altitude')}
        {app.defaultAlt}m
      </div>
      <Button variant="default" class="w-full mt-1" onclick={generate} disabled={previewCount === 0}>
        {t('survey.generate')}
      </Button>
    </div>
  {/if}
</div>
