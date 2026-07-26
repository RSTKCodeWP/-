<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { isSerialConnected, serialUploadFence } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import Badge from '$lib/components/ui/badge/badge.svelte';

  let drawingFence = $state(false);

  function startDraw() {
    app.fencePolygon = [];
    app.fenceUploaded = false;
    drawingFence = true;
    app.drawingFence = true;
  }
  function finishDraw() {
    drawingFence = false;
    app.drawingFence = false;
  }
  function clearFence() {
    app.fencePolygon = [];
    app.fenceUploaded = false;
    app.drawingFence = false;
    drawingFence = false;
  }

  function fmtArea(): string {
    if (app.fencePolygon.length < 3) return '---';
    const pts = app.fencePolygon;
    const origin = pts[0];
    let area = 0;
    for (let i = 0; i < pts.length; i++) {
      const j = (i + 1) % pts.length;
      const x1 = (pts[i].lon - origin.lon) * 111320 * Math.cos((origin.lat * Math.PI) / 180);
      const y1 = (pts[i].lat - origin.lat) * 111320;
      const x2 = (pts[j].lon - origin.lon) * 111320 * Math.cos((origin.lat * Math.PI) / 180);
      const y2 = (pts[j].lat - origin.lat) * 111320;
      area += x1 * y2 - x2 * y1;
    }
    const m2 = Math.abs(area) / 2;
    return m2 < 10000 ? m2.toFixed(0) + ' m²' : (m2 / 10000).toFixed(2) + ' ' + t('fence.hectare');
  }

  function saveFence() {
    const data = JSON.stringify(app.fencePolygon, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'fence_' + new Date().toISOString().slice(0, 10) + '.json';
    a.click();
    URL.revokeObjectURL(a.href);
    addToast(t('fence.exported'), 'success');
  }

  function loadFence() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev: ProgressEvent<FileReader>) => {
        try {
          const pts = JSON.parse(ev.target!.result as string);
          if (!Array.isArray(pts) || pts.length < 3) throw new Error('min 3');
          for (const p of pts) {
            const lat = Number(p?.lat),
              lon = Number(p?.lon);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) throw new Error('bad coord');
            if (lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new Error('bad coord');
          }
          app.fencePolygon = pts;
          app.fenceUploaded = false;
          addToast(t('fence.loaded').replace('{n}', String(pts.length)), 'success');
        } catch {
          addToast(t('fence.loadFail'), 'error');
        }
      };
      reader.readAsText(file);
    };
    input.click();
  }

  function uploadFence() {
    if (app.fencePolygon.length < 3) {
      addToast(t('fence.min3'), 'error');
      return;
    }
    addToast(t('fence.uploading'), 'info');
    if (isSerialConnected()) {
      // WebSerial direct: run the MISSION protocol with mission_type=1 in
      // transport.ts. The WS path goes through backend which emits
      // fence_ack_ok/fail events that ws.ts handles to set fenceUploaded.
      serialUploadFence(app.fencePolygon).then((res) => {
        if (res.ok) {
          app.fenceUploaded = true;
          addToast(t('fence.uploaded') ?? 'Fence uploaded', 'success');
        } else {
          addToast(`${t('fence.uploading')}: ${res.error}`, 'error', 5000);
        }
      });
      return;
    }
    dispatch('fence_upload', undefined, { polygon: app.fencePolygon });
  }

  function exportKml() {
    if (app.fencePolygon.length < 3) return;
    const coords = [...app.fencePolygon, app.fencePolygon[0]].map((p) => `${p.lon},${p.lat},0`).join('\n');
    const kml = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>${t('fence.kmlName')}</name>
<Style id="fence"><LineStyle><color>ff4444ff</color><width>2</width></LineStyle>
<PolyStyle><color>224444ff</color></PolyStyle></Style>
<Placemark><name>${t('fence.kmlArea')}</name><styleUrl>#fence</styleUrl>
<Polygon><outerBoundaryIs><LinearRing><coordinates>${coords}</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document></kml>`;
    const blob = new Blob([kml], { type: 'application/vnd.google-earth.kml+xml' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'fence_' + new Date().toISOString().slice(0, 10) + '.kml';
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<div class="bg-card border border-border rounded-xl p-3 mx-2 mb-2">
  <div class="flex items-center gap-2 mb-2">
    <h2 class="text-sm font-semibold text-destructive uppercase tracking-wider">{t('fence.title')}</h2>
    {#if app.fencePolygon.length >= 3}
      {#if app.fenceUploaded}
        <Badge variant="default" class="text-[10px]">{t('fence.uploaded')}</Badge>
      {:else}
        <Badge variant="outline" class="text-[10px]">{t('fence.notUploaded')}</Badge>
      {/if}
    {/if}
  </div>
  {#if app.fencePolygon.length < 3 && !drawingFence}
    <div class="flex gap-2">
      <button
        class="flex-1 py-2.5 bg-transparent border-2 border-dashed border-destructive/50 rounded-lg cursor-pointer
                      text-sm font-bold text-destructive hover:bg-destructive/5 transition-colors"
        onclick={startDraw}>{t('fence.draw')}</button
      >
      <Button variant="outline" size="sm" onclick={loadFence}>{t('fence.load')}</Button>
    </div>
    <div class="text-[11px] text-muted-foreground mt-1 text-center">{t('fence.drawHint')}</div>
  {:else if drawingFence}
    <div class="flex items-center gap-2 text-sm">
      <span>{t('fence.vertexCount').replace('{n}', String(app.fencePolygon.length))}</span>
      {#if app.fencePolygon.length >= 3}
        <Button variant="default" size="xs" onclick={finishDraw}>{t('fence.finish')}</Button>
      {/if}
      <Button variant="ghost" size="xs" onclick={clearFence}>{t('map.cancel')}</Button>
    </div>
  {:else}
    <div class="text-xs text-muted-foreground mb-2">
      {t('fence.vertexSummary').replace('{n}', String(app.fencePolygon.length))} | {fmtArea()}
    </div>
    <div class="flex flex-wrap gap-1">
      <Button variant="default" size="xs" onclick={uploadFence}>{t('fence.upload')}</Button>
      <Button variant="outline" size="xs" onclick={startDraw}>{t('fence.redraw')}</Button>
      <Button variant="outline" size="xs" onclick={saveFence}>{t('fence.save')}</Button>
      <Button variant="outline" size="xs" onclick={loadFence}>{t('fence.load')}</Button>
      <Button variant="outline" size="xs" onclick={exportKml}>KML</Button>
      <Button variant="ghost" size="xs" onclick={clearFence}>{t('fence.clear')}</Button>
    </div>
  {/if}
</div>
