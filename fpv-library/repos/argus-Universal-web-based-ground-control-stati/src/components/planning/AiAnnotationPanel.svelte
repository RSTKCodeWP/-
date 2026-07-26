<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, ScanLine, Square, Tag } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  interface Annotation {
    id: number;
    type: 'crack' | 'corrosion' | 'damage' | 'other';
    severity: 'low' | 'medium' | 'high';
    bbox: { x: number; y: number; w: number; h: number };
    notes: string;
  }

  const SEVERITY_COLORS: Record<string, string> = {
    high: 'rgba(239,68,68,0.35)',
    medium: 'rgba(249,115,22,0.35)',
    low: 'rgba(234,179,8,0.35)',
  };

  const SEVERITY_BORDER: Record<string, string> = {
    high: '#ef4444',
    medium: '#f97316',
    low: '#eab308',
  };

  let canvasEl: HTMLCanvasElement | undefined = $state(undefined);
  let imageLoaded = $state(false);
  let imgFileName = $state('');
  let imgElement: HTMLImageElement | null = null;
  let annotations: Annotation[] = $state(loadAnnotations());

  let isDrawing = $state(false);
  let drawStart = $state({ x: 0, y: 0 });
  let drawEnd = $state({ x: 0, y: 0 });

  let editType: Annotation['type'] = $state('crack');
  let editSeverity: Annotation['severity'] = $state('medium');
  let editNotes = $state('');

  function storageKey(): string {
    return `argus_ai_annotations_${imgFileName}`;
  }

  function loadAnnotations(): Annotation[] {
    if (!imgFileName) return [];
    try {
      const raw = localStorage.getItem(`argus_ai_annotations_${imgFileName}`);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch {}
    return [];
  }

  function persist() {
    if (!imgFileName) return;
    try {
      localStorage.setItem(storageKey(), JSON.stringify(annotations));
    } catch {}
  }

  function handleLoadImage(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      addToast(t('aiAnnot.invalidFile'), 'warn');
      return;
    }
    imgFileName = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      const img = new window.Image();
      img.onload = () => {
        imgElement = img;
        imageLoaded = true;
        annotations = loadAnnotations();
        redrawCanvas();
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
    input.value = '';
  }

  function redrawCanvas() {
    if (!canvasEl || !imgElement) return;
    const ctx = canvasEl.getContext('2d');
    if (!ctx) return;
    canvasEl.width = imgElement.naturalWidth;
    canvasEl.height = imgElement.naturalHeight;
    ctx.drawImage(imgElement, 0, 0);

    for (const ann of annotations) {
      const color = SEVERITY_COLORS[ann.severity] || SEVERITY_COLORS.low;
      const border = SEVERITY_BORDER[ann.severity] || SEVERITY_BORDER.low;
      ctx.fillStyle = color;
      ctx.fillRect(ann.bbox.x, ann.bbox.y, ann.bbox.w, ann.bbox.h);
      ctx.strokeStyle = border;
      ctx.lineWidth = 2;
      ctx.strokeRect(ann.bbox.x, ann.bbox.y, ann.bbox.w, ann.bbox.h);
    }

    if (isDrawing) {
      const rx = Math.min(drawStart.x, drawEnd.x);
      const ry = Math.min(drawStart.y, drawEnd.y);
      const rw = Math.abs(drawEnd.x - drawStart.x);
      const rh = Math.abs(drawEnd.y - drawStart.y);
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.setLineDash([]);
    }
  }

  function canvasCoords(e: MouseEvent): { x: number; y: number } {
    if (!canvasEl) return { x: 0, y: 0 };
    const rect = canvasEl.getBoundingClientRect();
    const scaleX = canvasEl.width / rect.width;
    const scaleY = canvasEl.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  }

  function handleMouseDown(e: MouseEvent) {
    if (!imageLoaded) return;
    const c = canvasCoords(e);
    drawStart = c;
    drawEnd = c;
    isDrawing = true;
  }

  function handleMouseMove(e: MouseEvent) {
    if (!isDrawing) return;
    drawEnd = canvasCoords(e);
    redrawCanvas();
  }

  function handleMouseUp() {
    if (!isDrawing) return;
    isDrawing = false;
    const rx = Math.min(drawStart.x, drawEnd.x);
    const ry = Math.min(drawStart.y, drawEnd.y);
    const rw = Math.abs(drawEnd.x - drawStart.x);
    const rh = Math.abs(drawEnd.y - drawStart.y);
    if (rw < 5 || rh < 5) {
      redrawCanvas();
      return;
    }
    annotations.push({
      id: Date.now(),
      type: editType,
      severity: editSeverity,
      bbox: { x: Math.round(rx), y: Math.round(ry), w: Math.round(rw), h: Math.round(rh) },
      notes: editNotes,
    });
    persist();
    editNotes = '';
    redrawCanvas();
  }

  function deleteAnnotation(id: number) {
    const idx = annotations.findIndex((a) => a.id === id);
    if (idx >= 0) {
      annotations.splice(idx, 1);
      persist();
      redrawCanvas();
    }
  }

  function exportAnnotations() {
    if (annotations.length === 0) {
      addToast(t('aiAnnot.noAnnotations'), 'warn');
      return;
    }
    const data = {
      filename: imgFileName,
      annotations: annotations.map((a) => ({
        type: a.type,
        severity: a.severity,
        bbox: a.bbox,
        notes: a.notes,
      })),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${imgFileName.replace(/\.\w+$/, '')}_annotations.json`;
    a.click();
    URL.revokeObjectURL(url);
    addToast(t('aiAnnot.exported'), 'success');
  }

  function aiDetect() {
    addToast(t('aiAnnot.connectAi'), 'info');
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[600px] max-h-[90vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <ScanLine size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('aiAnnot.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
      <!-- Load image button -->
      <label
        class="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-lg border border-dashed border-border
                     bg-muted/20 hover:bg-muted/40 cursor-pointer transition-colors text-xs text-muted-foreground"
      >
        <Square size={14} />
        {imgFileName || t('aiAnnot.loadImage')}
        <input type="file" accept=".jpg,.jpeg,.png" class="hidden" onchange={handleLoadImage} />
      </label>

      <!-- Canvas -->
      {#if imageLoaded}
        <div class="border border-border rounded-lg overflow-hidden bg-black/20">
          <canvas
            bind:this={canvasEl}
            class="w-full h-auto cursor-crosshair"
            onmousedown={handleMouseDown}
            onmousemove={handleMouseMove}
            onmouseup={handleMouseUp}
            onmouseleave={handleMouseUp}
          ></canvas>
        </div>
      {/if}

      <!-- Drawing tools -->
      <div class="grid grid-cols-3 gap-2">
        <div class="flex flex-col gap-1">
          <label for="ann-type" class="text-[11px] text-muted-foreground">{t('aiAnnot.type')}</label>
          <select
            id="ann-type"
            bind:value={editType}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          >
            <option value="crack">{t('aiAnnot.crack')}</option>
            <option value="corrosion">{t('aiAnnot.corrosion')}</option>
            <option value="damage">{t('aiAnnot.damage')}</option>
            <option value="other">{t('aiAnnot.other')}</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label for="ann-sev" class="text-[11px] text-muted-foreground">{t('aiAnnot.severity')}</label>
          <select
            id="ann-sev"
            bind:value={editSeverity}
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          >
            <option value="low">{t('aiAnnot.low')}</option>
            <option value="medium">{t('aiAnnot.medium')}</option>
            <option value="high">{t('aiAnnot.high')}</option>
          </select>
        </div>
        <div class="flex flex-col gap-1">
          <label for="ann-notes" class="text-[11px] text-muted-foreground">{t('aiAnnot.notes')}</label>
          <input
            id="ann-notes"
            type="text"
            bind:value={editNotes}
            placeholder="..."
            class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
        </div>
      </div>

      <!-- Action buttons -->
      <div class="flex gap-2">
        <Button variant="outline" class="flex-1" onclick={exportAnnotations}>
          <Tag size={14} class="mr-1" />{t('aiAnnot.export')}
        </Button>
        <Button variant="outline" class="flex-1" onclick={aiDetect}>
          <ScanLine size={14} class="mr-1" />{t('aiAnnot.aiDetect')}
        </Button>
      </div>

      <!-- Annotation list -->
      {#if annotations.length > 0}
        <div class="space-y-1">
          <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {t('aiAnnot.annotations')} ({annotations.length})
          </div>
          {#each annotations as ann (ann.id)}
            <div class="flex items-center gap-2 bg-muted/20 rounded-lg p-2 group">
              <div
                class="w-3 h-3 rounded-full shrink-0"
                style="background:{SEVERITY_BORDER[ann.severity] || '#eab308'}"
              ></div>
              <div class="flex-1 min-w-0">
                <div class="text-xs font-medium text-foreground">
                  {t(`aiAnnot.${ann.type}`)} <span class="text-muted-foreground">({t(`aiAnnot.${ann.severity}`)})</span>
                </div>
                <div class="text-[10px] font-mono text-muted-foreground">
                  {ann.bbox.x},{ann.bbox.y}
                  {ann.bbox.w}x{ann.bbox.h}
                  {#if ann.notes}&middot; {ann.notes}{/if}
                </div>
              </div>
              <button
                class="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-destructive hover:bg-destructive/10 rounded"
                onclick={() => deleteAnnotation(ann.id)}
              >
                <X size={13} />
              </button>
            </div>
          {/each}
        </div>
      {/if}

      <!-- Hint -->
      {#if !imageLoaded}
        <div class="p-3 rounded-lg bg-primary/5 border border-primary/20">
          <p class="text-xs text-muted-foreground leading-relaxed">
            {t('aiAnnot.hint')}
          </p>
        </div>
      {/if}
    </div>
  </div>
</div>
