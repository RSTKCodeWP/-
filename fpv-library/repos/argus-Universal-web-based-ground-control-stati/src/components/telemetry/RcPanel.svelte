<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import Badge from '$lib/components/ui/badge/badge.svelte';
  import { t } from '../../lib/i18n.svelte';

  const LABELS = $derived([
    t('rc.roll'),
    t('rc.pitch'),
    t('rc.throttle'),
    t('rc.yaw'),
    'CH5',
    'CH6',
    'CH7',
    'CH8',
    'CH9',
    'CH10',
    'CH11',
    'CH12',
    'CH13',
    'CH14',
    'CH15',
    'CH16',
  ]);

  function barWidth(v: number): number {
    return Math.max(0, Math.min(100, (v - 800) / 12));
  }
  function barColor(v: number): string {
    if (v < 900 || v > 2100) return 'bg-destructive';
    if (v < 1000 || v > 2000) return 'bg-warning';
    return 'bg-primary';
  }
</script>

<div class="bg-card border border-border rounded-xl p-4">
  <div class="flex items-center justify-between mb-3">
    <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('rc.title')}</h2>
    <Badge variant="outline" class="text-[10px] font-mono">RSSI: {app.drone.rc_rssi}</Badge>
  </div>
  {#if !app.drone.connected}
    <div class="text-muted-foreground text-xs text-center py-4">{t('rc.empty')}</div>
  {:else if app.drone.rc.length > 0}
    <div class="grid grid-cols-2 gap-x-3 gap-y-1">
      {#each app.drone.rc as val, i}
        {#if i < 16}
          <div class="flex items-center gap-1.5 text-[11px]">
            <span class="w-7 text-right text-muted-foreground text-[10px] shrink-0">{LABELS[i]}</span>
            <div class="flex-1 h-2.5 bg-muted rounded-full relative overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-150 {barColor(val)}"
                style="width:{barWidth(val)}%"
              ></div>
              <div class="absolute left-1/2 top-0 w-px h-full bg-border"></div>
            </div>
            <span class="w-8 text-right font-mono text-muted-foreground text-[10px] shrink-0">{val}</span>
          </div>
        {/if}
      {/each}
    </div>
  {:else}
    <div class="text-muted-foreground text-xs text-center py-4">{t('rc.noData')}</div>
  {/if}
</div>
