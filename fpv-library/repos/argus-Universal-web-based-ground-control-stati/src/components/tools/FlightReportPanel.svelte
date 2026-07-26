<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, FileText, Download } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Editable fields ── */
  let pilotName = $state(localStorage.getItem('argus_pilot_name') ?? '');
  let reportDate = $state(new Date().toISOString().slice(0, 10));
  let weather = $state('');
  let notes = $state('');

  /* ── Auto-populated vehicle info ── */
  let vehicleInfo = $derived(
    [app.drone.vtype, app.drone.fw_version, app.drone.board_id ? `Board ${app.drone.board_id}` : '']
      .filter(Boolean)
      .join(' / ') || '---',
  );

  /* ── Flight summary ── */
  let summary = $derived(app.drone.flight_summary);

  /* ── Recent events (last 50) ── */
  let recentEvents = $derived(app.events.slice(-50));

  /* ── Formatting helpers ── */
  function fmtDuration(s: number): string {
    const m = Math.floor(s / 60),
      sec = s % 60;
    return `${m}m ${sec}s`;
  }

  function fmtTime(timeStr: string): string {
    return timeStr;
  }

  /* ── Persist pilot name ── */
  function savePilot() {
    try {
      localStorage.setItem('argus_pilot_name', pilotName);
    } catch {}
  }

  /* ── Export report ── */
  let exportTimer: ReturnType<typeof setTimeout> | null = null;
  let exporting = $state(false);

  function exportReport() {
    exporting = true;
    savePilot();

    const lines: string[] = [];
    lines.push('=== Argus Flight Report ===');
    lines.push(`Date: ${reportDate}`);
    lines.push(`Pilot: ${pilotName || '---'}`);
    lines.push(`Vehicle: ${vehicleInfo}`);
    lines.push(`Weather: ${weather || '---'}`);
    lines.push('');

    /* Flight summary */
    lines.push('--- Flight Summary ---');
    if (summary) {
      lines.push(`Duration: ${fmtDuration(summary.duration)}`);
      lines.push(`Max Altitude: ${summary.max_alt.toFixed(1)} m`);
      lines.push(`Max Speed: ${summary.max_speed.toFixed(1)} m/s`);
      lines.push(`Distance: ${summary.total_dist} m`);
      if (summary.bat_used >= 0) {
        lines.push(`Battery Used: ${summary.bat_used}%`);
      }
    } else {
      lines.push('(No flight data available)');
    }
    lines.push('');

    /* Event log */
    lines.push('--- Event Log ---');
    if (recentEvents.length > 0) {
      for (const ev of recentEvents) {
        lines.push(`${fmtTime(ev.time)}  ${ev.text}`);
      }
    } else {
      lines.push('(No events)');
    }
    lines.push('');

    /* Notes */
    lines.push('--- Notes ---');
    lines.push(notes || '(none)');

    const text = lines.join('\n');
    const blob = new Blob([text], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `flight_report_${reportDate}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);

    if (exportTimer) clearTimeout(exportTimer);
    exportTimer = setTimeout(() => {
      exporting = false;
      exportTimer = null;
    }, 1000);
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
  <div
    class="bg-card border border-border rounded-xl shadow-2xl w-[500px] max-h-[85vh] flex flex-col overflow-hidden"
    role="dialog"
    aria-modal="true"
    aria-label={t('report.title')}
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <FileText size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('report.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
      <!-- Editable form fields -->
      <div class="space-y-3">
        <!-- Pilot name -->
        <div class="space-y-1">
          <span class="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t('report.pilot')}</span
          >
          <input
            bind:value={pilotName}
            onblur={savePilot}
            placeholder={t('report.pilot')}
            class="w-full h-8 px-3 bg-input border border-border rounded-md text-xs text-foreground
                   placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
        </div>

        <!-- Date -->
        <div class="space-y-1">
          <span class="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t('report.date')}</span>
          <input
            type="date"
            bind:value={reportDate}
            class="w-full h-8 px-3 bg-input border border-border rounded-md text-xs text-foreground
                   focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
        </div>

        <!-- Vehicle (read-only) -->
        <div class="space-y-1">
          <span class="text-[11px] font-medium text-muted-foreground uppercase tracking-wider"
            >{t('report.vehicle')}</span
          >
          <div
            class="w-full h-8 px-3 flex items-center bg-muted/50 border border-border rounded-md text-xs text-foreground"
          >
            {vehicleInfo}
          </div>
        </div>

        <!-- Weather -->
        <div class="space-y-1">
          <span class="text-[11px] font-medium text-muted-foreground uppercase tracking-wider"
            >{t('report.weather')}</span
          >
          <input
            bind:value={weather}
            placeholder={t('report.weather')}
            class="w-full h-8 px-3 bg-input border border-border rounded-md text-xs text-foreground
                   placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
          />
        </div>

        <!-- Notes -->
        <div class="space-y-1">
          <span class="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">{t('report.notes')}</span
          >
          <textarea
            bind:value={notes}
            placeholder={t('report.notes')}
            rows="3"
            class="w-full px-3 py-2 bg-input border border-border rounded-md text-xs text-foreground
                   placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-ring/50"
          ></textarea>
        </div>
      </div>

      <!-- Auto-populated: Flight summary -->
      <div class="space-y-2">
        <h3
          class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border pb-1"
        >
          Flight Summary
        </h3>
        {#if summary}
          <div class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            <div class="flex justify-between">
              <span class="text-muted-foreground">Duration</span>
              <span class="font-mono font-medium text-foreground">{fmtDuration(summary.duration)}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Max Alt</span>
              <span class="font-mono font-medium text-foreground">{summary.max_alt.toFixed(1)} m</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Max Speed</span>
              <span class="font-mono font-medium text-foreground">{summary.max_speed.toFixed(1)} m/s</span>
            </div>
            <div class="flex justify-between">
              <span class="text-muted-foreground">Distance</span>
              <span class="font-mono font-medium text-foreground">{summary.total_dist} m</span>
            </div>
            {#if summary.bat_used >= 0}
              <div class="flex justify-between">
                <span class="text-muted-foreground">Battery Used</span>
                <span class="font-mono font-medium text-foreground">{summary.bat_used}%</span>
              </div>
            {/if}
          </div>
        {:else}
          <p class="text-xs text-muted-foreground italic">No flight data available</p>
        {/if}
      </div>

      <!-- Auto-populated: Event log -->
      <div class="space-y-2">
        <h3
          class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border pb-1"
        >
          Event Log ({recentEvents.length})
        </h3>
        {#if recentEvents.length > 0}
          <div class="bg-background rounded-lg p-2 max-h-40 overflow-y-auto text-[11px] font-mono space-y-0.5">
            {#each recentEvents as ev}
              <div class="flex gap-2 py-0.5 px-1 border-b border-border/30">
                <span class="text-muted-foreground shrink-0">{ev.time}</span>
                <span class="text-foreground min-w-0">{ev.text}</span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-muted-foreground italic">No events recorded</p>
        {/if}
      </div>
    </div>

    <!-- Footer: Export button -->
    <div class="px-4 py-3 border-t border-border flex justify-end">
      <Button variant="default" size="sm" class="h-8 text-xs px-6 gap-2" onclick={exportReport} disabled={exporting}>
        <Download size={14} />
        {exporting ? t('report.generating') : t('report.export')}
      </Button>
    </div>
  </div>
</div>
