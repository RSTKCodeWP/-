<script lang="ts">
  import type { FlightSummary } from '../../lib/types';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Clock, ArrowUp, Gauge, Route, BatteryLow } from '@lucide/svelte';
  import { t } from '../../lib/i18n.svelte';
  import { fmtDist } from '../../lib/units';

  let { summary, onclose }: { summary: FlightSummary; onclose: () => void } = $props();

  function fmtTime(s: number): string {
    const m = Math.floor(s / 60),
      sec = s % 60;
    return `${m}:${sec < 10 ? '0' : ''}${sec}`;
  }

  let avgSpeed = $derived(summary.duration > 0 ? (summary.total_dist / summary.duration).toFixed(1) : '---');

  function exportReport() {
    const lines = [
      `Argus ${t('summary.title')}`,
      `Date: ${new Date().toLocaleString()}`,
      ``,
      `${t('summary.duration')}: ${fmtTime(summary.duration)}`,
      `${t('summary.maxAlt')}: ${summary.max_alt} m`,
      `${t('summary.maxSpd')}: ${summary.max_speed} m/s`,
      `${t('summary.dist')}: ${fmtDist(summary.total_dist)}`,
      `${t('summary.avgSpd')}: ${avgSpeed} m/s`,
      summary.bat_used >= 0 ? `${t('summary.batUsed')}: ${summary.bat_used}%` : '',
    ]
      .filter(Boolean)
      .join('\n');
    const blob = new Blob([lines], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `flight_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  class="fixed inset-0 bg-black/70 backdrop-blur-sm z-[9999] flex items-center justify-center"
  onclick={onclose}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div
    role="presentation"
    class="bg-card border border-border rounded-2xl overflow-hidden min-w-[340px] shadow-2xl"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between">
      <div>
        <h3 class="text-base font-bold text-primary">{t('summary.title')}</h3>
        <p class="text-[11px] text-muted-foreground mt-0.5">{t('summary.subtitle')}</p>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>
    <div class="px-5 py-3 grid grid-cols-2 gap-3">
      <div class="flex items-center gap-2.5 py-1.5">
        <div class="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center shrink-0">
          <Clock size={16} class="text-blue-400" />
        </div>
        <div>
          <div class="text-[10px] text-muted-foreground">{t('summary.duration')}</div>
          <div class="text-sm font-bold tabular-nums">{fmtTime(summary.duration)}</div>
        </div>
      </div>
      <div class="flex items-center gap-2.5 py-1.5">
        <div class="w-8 h-8 rounded-lg bg-sky-500/15 flex items-center justify-center shrink-0">
          <ArrowUp size={16} class="text-sky-400" />
        </div>
        <div>
          <div class="text-[10px] text-muted-foreground">{t('summary.maxAlt')}</div>
          <div class="text-sm font-bold tabular-nums">{summary.max_alt} m</div>
        </div>
      </div>
      <div class="flex items-center gap-2.5 py-1.5">
        <div class="w-8 h-8 rounded-lg bg-green-500/15 flex items-center justify-center shrink-0">
          <Gauge size={16} class="text-green-400" />
        </div>
        <div>
          <div class="text-[10px] text-muted-foreground">{t('summary.maxSpd')}</div>
          <div class="text-sm font-bold tabular-nums">{summary.max_speed} m/s</div>
        </div>
      </div>
      <div class="flex items-center gap-2.5 py-1.5">
        <div class="w-8 h-8 rounded-lg bg-teal-500/15 flex items-center justify-center shrink-0">
          <Route size={16} class="text-teal-400" />
        </div>
        <div>
          <div class="text-[10px] text-muted-foreground">{t('summary.dist')}</div>
          <div class="text-sm font-bold tabular-nums">{fmtDist(summary.total_dist)}</div>
        </div>
      </div>
      {#if summary.bat_used >= 0}
        <div class="flex items-center gap-2.5 py-1.5">
          <div class="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0">
            <BatteryLow size={16} class="text-amber-400" />
          </div>
          <div>
            <div class="text-[10px] text-muted-foreground">{t('summary.batUsed')}</div>
            <div class="text-sm font-bold tabular-nums">{summary.bat_used}%</div>
          </div>
        </div>
      {/if}
      <div class="flex items-center gap-2.5 py-1.5">
        <div class="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center shrink-0">
          <Gauge size={16} class="text-purple-400" />
        </div>
        <div>
          <div class="text-[10px] text-muted-foreground">{t('summary.avgSpd')}</div>
          <div class="text-sm font-bold tabular-nums">{avgSpeed} m/s</div>
        </div>
      </div>
    </div>
    <div class="px-5 pb-4 flex gap-2">
      <Button variant="outline" class="flex-1" onclick={exportReport}>{t('wp.export')}</Button>
      <Button class="flex-1" onclick={onclose}>{t('summary.confirm')}</Button>
    </div>
  </div>
</div>
