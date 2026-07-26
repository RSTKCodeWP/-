<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { parseDFLog, getTimeSeries, type DFLog } from '../../lib/dflog';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, FileText, Download, BarChart3, Table2, Activity } from '@lucide/svelte';

  let { onclose, onlog }: { onclose: () => void; onlog?: (log: DFLog) => void } = $props();

  let log = $state<DFLog | null>(null);
  let parsing = $state(false);
  let selectedTypes = $state<Set<string>>(new Set());
  let canvasEl: HTMLCanvasElement = $state(null!);
  let fileName = $state('');
  let viewMode = $state<'chart' | 'table'>('chart');
  let showStats = $state(false);

  // Multi-channel: each selected type maps to its first numeric column
  // Up to 4 channels overlaid with independent Y-axis scales
  const CHANNEL_COLORS = ['#4fc3f7', '#81c784', '#ffb74d', '#e57373', '#ba68c8', '#4dd0e1', '#aed581', '#ff8a65'];
  const MAX_OVERLAY = 4;

  // Zoom state: normalized [0,1] range into the full time domain
  let zoomStart = $state(0);
  let zoomEnd = $state(1);
  let isDragging = $state(false);
  let dragStartX = $state(0);
  let dragCurrentX = $state(0);

  // Sync marker
  let mouseX = $state(-1);
  let markerValues = $state<{ label: string; value: number; color: string }[]>([]);

  // Table virtual scroll
  let tableScrollTop = $state(0);
  const TABLE_ROW_H = 24;
  const TABLE_VISIBLE = 100;

  // Cached channel data for stats & rendering
  let channelData = $state<
    {
      label: string;
      color: string;
      series: { t: number[]; v: number[] };
      min: number;
      max: number;
      avg: number;
      std: number;
    }[]
  >([]);

  function openFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.bin,.log';
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      fileName = file.name;
      parsing = true;
      const reader = new FileReader();
      reader.onload = (ev: ProgressEvent<FileReader>) => {
        try {
          log = parseDFLog(ev.target!.result as ArrayBuffer);
          selectedTypes = new Set(['ATT', 'GPS', 'BARO', 'BAT', 'VIBE'].filter((t) => log!.types.includes(t)));
          addToast(t('logview.messages').replace('{n}', String(log.messages.length)), 'success');
          onlog?.(log);
          zoomStart = 0;
          zoomEnd = 1;
        } catch (err: unknown) {
          addToast('Parse error: ' + (err instanceof Error ? err.message : String(err)), 'error');
        }
        parsing = false;
      };
      reader.readAsArrayBuffer(file);
    };
    input.click();
  }

  function toggleType(tp: string) {
    const s = new Set(selectedTypes);
    if (s.has(tp)) {
      s.delete(tp);
    } else {
      // Enforce max overlay limit
      if (s.size >= MAX_OVERLAY) {
        const first = s.values().next().value;
        if (first !== undefined) s.delete(first);
      }
      s.add(tp);
    }
    selectedTypes = s;
  }

  // Compute channel data whenever selection or log changes
  $effect(() => {
    if (!log || selectedTypes.size === 0) {
      channelData = [];
      return;
    }
    const result: typeof channelData = [];
    let ci = 0;
    for (const tp of selectedTypes) {
      const fmt = log.formats.get(tp);
      if (!fmt) continue;
      const numCols = fmt.columns.filter((c) => c !== 'TimeUS' && c !== 'TimeMS');
      const col = numCols[0];
      if (!col) continue;
      const series = getTimeSeries(log, tp, col);
      if (series.t.length < 2) continue;
      const vals = series.v;
      let min = Infinity,
        max = -Infinity,
        sum = 0;
      for (let i = 0; i < vals.length; i++) {
        if (vals[i] < min) min = vals[i];
        if (vals[i] > max) max = vals[i];
        sum += vals[i];
      }
      const avg = sum / vals.length;
      let sqSum = 0;
      for (let i = 0; i < vals.length; i++) {
        const d = vals[i] - avg;
        sqSum += d * d;
      }
      const std = Math.sqrt(sqSum / vals.length);
      result.push({
        label: `${tp}.${col}`,
        color: CHANNEL_COLORS[ci % CHANNEL_COLORS.length],
        series,
        min,
        max,
        avg,
        std,
      });
      ci++;
    }
    channelData = result;
  });

  // Draw chart
  $effect(() => {
    if (!canvasEl || !log || channelData.length === 0 || viewMode !== 'chart') return;
    const ctx = canvasEl.getContext('2d')!;
    const w = (canvasEl.width = canvasEl.parentElement!.clientWidth);
    const h = canvasEl.height;
    ctx.clearRect(0, 0, w, h);

    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, w, h);

    // Determine global time range
    let globalMaxT = 0;
    for (const ch of channelData) {
      const lastT = ch.series.t[ch.series.t.length - 1];
      if (lastT > globalMaxT) globalMaxT = lastT;
    }
    if (globalMaxT === 0) return;

    const tStart = zoomStart * globalMaxT;
    const tEnd = zoomEnd * globalMaxT;
    const tRange = tEnd - tStart || 1;

    // Grid lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = (i / 4) * h;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Draw each channel with its own Y-axis scale
    const axisWidth = 50;
    const plotLeft = channelData.length > 1 ? axisWidth : 0;
    const plotRight = channelData.length > 2 ? w - axisWidth : w;
    const plotW = plotRight - plotLeft;

    for (let ci = 0; ci < channelData.length; ci++) {
      const ch = channelData[ci];
      const { series, min: minV, max: maxV, color } = ch;
      const range = maxV - minV || 1;

      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < series.t.length; i++) {
        if (series.t[i] < tStart || series.t[i] > tEnd) continue;
        const x = plotLeft + ((series.t[i] - tStart) / tRange) * plotW;
        const y = h - ((series.v[i] - minV) / range) * (h - 30) - 15;
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Y-axis labels for multi-channel
      if (channelData.length > 1) {
        ctx.fillStyle = color;
        ctx.font = '9px monospace';
        if (ci === 0) {
          // Left axis
          ctx.fillText(maxV.toPrecision(4), 2, 12);
          ctx.fillText(minV.toPrecision(4), 2, h - 4);
        } else if (ci === 1 && channelData.length > 2) {
          // Right axis
          ctx.fillText(maxV.toPrecision(4), w - axisWidth + 4, 12);
          ctx.fillText(minV.toPrecision(4), w - axisWidth + 4, h - 4);
        }
      }

      // Legend
      ctx.fillStyle = color;
      ctx.font = '10px monospace';
      ctx.fillText(ch.label, plotLeft + 4, 12 + ci * 14);
    }

    // Time axis labels
    ctx.fillStyle = '#666';
    ctx.font = '9px monospace';
    for (let i = 0; i <= 5; i++) {
      const sec = tStart + (i / 5) * tRange;
      const x = plotLeft + (i / 5) * plotW;
      ctx.fillText(`${sec.toFixed(1)}s`, x + 2, h - 2);
    }

    // Drag selection overlay
    if (isDragging) {
      const x1 = Math.min(dragStartX, dragCurrentX);
      const x2 = Math.max(dragStartX, dragCurrentX);
      ctx.fillStyle = 'rgba(79, 195, 247, 0.15)';
      ctx.fillRect(x1, 0, x2 - x1, h);
      ctx.strokeStyle = '#4fc3f7';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x1, 0);
      ctx.lineTo(x1, h);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(x2, 0);
      ctx.lineTo(x2, h);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Sync marker (vertical cursor line)
    if (mouseX >= 0 && !isDragging) {
      const plotLeft_ = plotLeft;
      const plotW_ = plotW;
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 0.8;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(mouseX, 0);
      ctx.lineTo(mouseX, h);
      ctx.stroke();
      ctx.setLineDash([]);

      // Compute values at cursor
      const cursorFrac = (mouseX - plotLeft_) / plotW_;
      const cursorT = tStart + cursorFrac * tRange;
      const vals: typeof markerValues = [];
      for (const ch of channelData) {
        // Binary search for nearest time
        const ts = ch.series.t;
        let lo = 0,
          hi = ts.length - 1;
        while (lo < hi) {
          const mid = (lo + hi) >> 1;
          if (ts[mid] < cursorT) lo = mid + 1;
          else hi = mid;
        }
        const idx = Math.max(0, Math.min(lo, ts.length - 1));
        vals.push({ label: ch.label, value: ch.series.v[idx], color: ch.color });
      }
      markerValues = vals;

      // Draw marker tooltip
      ctx.fillStyle = 'rgba(0,0,0,0.75)';
      const tooltipX = mouseX + 8;
      const tooltipW = 140;
      const tooltipH = 14 + vals.length * 13;
      ctx.fillRect(tooltipX, 4, tooltipW, tooltipH);
      ctx.fillStyle = '#ccc';
      ctx.font = '9px monospace';
      ctx.fillText(`t=${cursorT.toFixed(2)}s`, tooltipX + 4, 14);
      for (let i = 0; i < vals.length; i++) {
        ctx.fillStyle = vals[i].color;
        ctx.fillText(`${vals[i].label}: ${vals[i].value.toFixed(3)}`, tooltipX + 4, 27 + i * 13);
      }
    }
  });

  function onCanvasMouseDown(e: MouseEvent) {
    if (viewMode !== 'chart') return;
    const rect = canvasEl.getBoundingClientRect();
    dragStartX = e.clientX - rect.left;
    dragCurrentX = dragStartX;
    isDragging = true;
  }

  function onCanvasMouseMove(e: MouseEvent) {
    if (!canvasEl) return;
    const rect = canvasEl.getBoundingClientRect();
    const x = e.clientX - rect.left;
    mouseX = x;
    if (isDragging) {
      dragCurrentX = x;
    }
  }

  function onCanvasMouseUp(_e: MouseEvent) {
    if (!isDragging || !canvasEl || !log) {
      isDragging = false;
      return;
    }
    isDragging = false;
    const w = canvasEl.width;
    // Determine plot area
    const plotLeft = channelData.length > 1 ? 50 : 0;
    const plotRight = channelData.length > 2 ? w - 50 : w;
    const plotW = plotRight - plotLeft;
    const x1 = Math.min(dragStartX, dragCurrentX);
    const x2 = Math.max(dragStartX, dragCurrentX);
    const minDrag = 5;
    if (x2 - x1 < minDrag) return; // too small, ignore
    // Convert pixel range to zoom fraction
    const frac1 = Math.max(0, (x1 - plotLeft) / plotW);
    const frac2 = Math.min(1, (x2 - plotLeft) / plotW);
    const oldRange = zoomEnd - zoomStart;
    zoomStart = zoomStart + frac1 * oldRange;
    zoomEnd = zoomStart + (frac2 - frac1) * oldRange;
    // Clamp
    if (zoomStart < 0) zoomStart = 0;
    if (zoomEnd > 1) zoomEnd = 1;
  }

  function onCanvasDblClick() {
    zoomStart = 0;
    zoomEnd = 1;
  }

  function onCanvasMouseLeave() {
    mouseX = -1;
    if (isDragging) isDragging = false;
  }

  // Table data: filtered messages for selected types
  let tableMessages = $derived.by(() => {
    if (!log || selectedTypes.size === 0) return [];
    return log.messages.filter((m) => selectedTypes.has(m.type));
  });

  let tableVisibleStart = $derived(Math.floor(tableScrollTop / TABLE_ROW_H));
  let tableVisibleEnd = $derived(Math.min(tableVisibleStart + TABLE_VISIBLE, tableMessages.length));
  let tableVisibleRows = $derived(tableMessages.slice(tableVisibleStart, tableVisibleEnd));

  function onTableScroll(e: Event) {
    tableScrollTop = (e.target as HTMLDivElement).scrollTop;
  }

  function exportCsv() {
    if (!log) return;
    const types = [...selectedTypes];
    let csv = 'time,' + types.join(',') + '\n';
    const series = types.map((tp) => {
      const fmt = log!.formats.get(tp);
      const col = fmt?.columns.filter((c) => c !== 'TimeUS' && c !== 'TimeMS')[0] || '';
      return getTimeSeries(log!, tp, col);
    });
    const maxLen = Math.max(...series.map((s) => s.t.length));
    for (let i = 0; i < Math.min(maxLen, 10000); i++) {
      const row = [series[0]?.t[i]?.toFixed(3) || ''];
      for (const s of series) row.push(s.v[i]?.toFixed(4) || '');
      csv += row.join(',') + '\n';
    }
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = fileName.replace(/\.\w+$/, '') + '_export.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function formatFieldValues(fields: Record<string, number | string>): string {
    return Object.entries(fields)
      .filter(([k]) => k !== 'TimeUS' && k !== 'TimeMS')
      .map(([k, v]) => `${k}=${typeof v === 'number' ? v.toPrecision(5) : v}`)
      .join(' ');
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[950px] max-h-[85vh] shadow-2xl flex flex-col"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <FileText size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('logview.title')}</h3>
        {#if fileName}<span class="text-xs text-muted-foreground">{fileName}</span>{/if}
      </div>
      <div class="flex items-center gap-2">
        {#if log}
          <div class="flex border border-border rounded overflow-hidden">
            <button
              class="px-2 py-0.5 text-[10px] transition-all {viewMode === 'chart'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'}"
              onclick={() => (viewMode = 'chart')}
            >
              <BarChart3 size={12} class="inline mr-0.5" />{t('logview.chart')}
            </button>
            <button
              class="px-2 py-0.5 text-[10px] transition-all {viewMode === 'table'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'}"
              onclick={() => (viewMode = 'table')}
            >
              <Table2 size={12} class="inline mr-0.5" />{t('logview.table')}
            </button>
          </div>
          <button
            class="px-2 py-0.5 text-[10px] rounded border transition-all {showStats
              ? 'bg-primary text-primary-foreground border-primary'
              : 'text-muted-foreground border-border hover:text-foreground'}"
            onclick={() => (showStats = !showStats)}
          >
            <Activity size={12} class="inline mr-0.5" />{t('logview.stats')}
          </button>
        {/if}
        <Button variant="default" size="sm" onclick={openFile} disabled={parsing}>
          {parsing ? t('logview.parsing') : t('logview.open')}
        </Button>
        {#if log}
          <Button variant="outline" size="sm" onclick={exportCsv}
            ><Download size={13} class="mr-1" />{t('logview.export')}</Button
          >
        {/if}
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>

    <div class="flex-1 overflow-auto px-5 py-3">
      {#if !log}
        <div class="text-center py-16 text-muted-foreground text-sm">{t('logview.noFile')}</div>
      {:else}
        <div class="flex items-center gap-2 mb-3 text-xs text-muted-foreground">
          <span>{t('logview.messages').replace('{n}', String(log.messages.length))}</span>
          <span>·</span>
          <span>{t('logview.duration')}: {log.duration.toFixed(0)}s</span>
          <span>·</span>
          <span>{log.types.length} {t('logview.channels').toLowerCase()}</span>
          <span>·</span>
          <span class="text-[10px] opacity-60">{t('logview.multiChannel')}</span>
        </div>

        <div class="flex flex-wrap gap-1 mb-3">
          {#each log.types as tp}
            <button
              class="px-2 py-0.5 text-[10px] rounded border cursor-pointer transition-all
              {selectedTypes.has(tp)
                ? 'bg-primary text-primary-foreground border-primary'
                : 'text-muted-foreground border-border hover:text-foreground'}"
              onclick={() => toggleType(tp)}>{tp}</button
            >
          {/each}
        </div>

        <div class="flex gap-3">
          <!-- Main content area -->
          <div class="flex-1 min-w-0">
            {#if viewMode === 'chart'}
              <div class="border border-border rounded-lg overflow-hidden relative">
                <canvas
                  bind:this={canvasEl}
                  height="300"
                  class="w-full cursor-crosshair"
                  onmousedown={onCanvasMouseDown}
                  onmousemove={onCanvasMouseMove}
                  onmouseup={onCanvasMouseUp}
                  ondblclick={onCanvasDblClick}
                  onmouseleave={onCanvasMouseLeave}
                ></canvas>
                {#if zoomStart > 0 || zoomEnd < 1}
                  <div
                    class="absolute bottom-1 right-2 text-[9px] text-muted-foreground bg-black/50 px-1.5 py-0.5 rounded"
                  >
                    {t('logview.zoomHint')}
                  </div>
                {/if}
              </div>
            {:else}
              <!-- Table view with virtual windowing -->
              <div class="border border-border rounded-lg overflow-hidden">
                <div
                  class="bg-muted/30 px-2 py-1 flex text-[10px] font-semibold text-muted-foreground border-b border-border"
                >
                  <span class="w-20 shrink-0">{t('logview.timestamp')}</span>
                  <span class="w-14 shrink-0">{t('logview.type')}</span>
                  <span class="flex-1">{t('logview.fields')}</span>
                </div>
                <div class="h-[280px] overflow-auto" onscroll={onTableScroll}>
                  <div style="height: {tableMessages.length * TABLE_ROW_H}px; position: relative;">
                    {#each tableVisibleRows as msg, i}
                      <div
                        class="flex px-2 text-[10px] font-mono items-center border-b border-border/30 hover:bg-muted/20"
                        style="position: absolute; top: {(tableVisibleStart + i) *
                          TABLE_ROW_H}px; height: {TABLE_ROW_H}px; left: 0; right: 0;"
                      >
                        <span class="w-20 shrink-0 text-muted-foreground">{msg.timestamp.toFixed(3)}s</span>
                        <span class="w-14 shrink-0 text-primary">{msg.type}</span>
                        <span class="flex-1 truncate text-foreground/80">{formatFieldValues(msg.fields)}</span>
                      </div>
                    {/each}
                  </div>
                </div>
                <div class="bg-muted/20 px-2 py-0.5 text-[9px] text-muted-foreground">
                  {t('logview.rows').replace('{n}', String(tableMessages.length))}
                </div>
              </div>
            {/if}
          </div>

          <!-- Statistics sidebar -->
          {#if showStats && channelData.length > 0}
            <div class="w-44 shrink-0 border border-border rounded-lg p-2 space-y-2 overflow-auto max-h-[340px]">
              <div class="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                {t('logview.stats')}
              </div>
              {#each channelData as ch}
                <div class="space-y-0.5">
                  <div class="text-[10px] font-semibold truncate" style="color: {ch.color}">{ch.label}</div>
                  <div class="grid grid-cols-2 gap-x-2 text-[9px]">
                    <span class="text-muted-foreground">{t('logview.statsMin')}</span>
                    <span class="text-right font-mono">{ch.min.toPrecision(5)}</span>
                    <span class="text-muted-foreground">{t('logview.statsMax')}</span>
                    <span class="text-right font-mono">{ch.max.toPrecision(5)}</span>
                    <span class="text-muted-foreground">{t('logview.statsAvg')}</span>
                    <span class="text-right font-mono">{ch.avg.toPrecision(5)}</span>
                    <span class="text-muted-foreground">{t('logview.statsStd')}</span>
                    <span class="text-right font-mono">{ch.std.toPrecision(4)}</span>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>
