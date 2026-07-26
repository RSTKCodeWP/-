<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';

  function barWidth(v: number): number {
    return Math.max(0, Math.min(100, (v - 800) / 12));
  }
  function barColor(v: number, armed: boolean): string {
    if (!armed) return 'bg-muted-foreground/40';
    if (v < 900 || v > 2100) return 'bg-destructive';
    return 'bg-warning';
  }
</script>

<div class="bg-card border border-border rounded-xl p-4">
  <h2 class="text-sm font-semibold text-primary uppercase tracking-wider mb-3">{t('servo.title')}</h2>
  {#if !app.drone.connected}
    <div class="text-muted-foreground text-xs text-center py-4">{t('servo.empty')}</div>
  {:else if app.drone.servo.length > 0}
    <div class="grid grid-cols-2 gap-x-3 gap-y-1">
      {#each app.drone.servo as val, i}
        {#if i < 16 && val > 0}
          <div class="flex items-center gap-1.5 text-[11px]">
            <span class="w-5 text-right text-muted-foreground text-[10px] shrink-0">S{i + 1}</span>
            <div class="flex-1 h-2.5 bg-muted rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-150 {barColor(val, app.drone.armed)}"
                style="width:{barWidth(val)}%"
              ></div>
            </div>
            <span class="w-8 text-right font-mono text-muted-foreground text-[10px] shrink-0">{val}</span>
          </div>
        {/if}
      {/each}
    </div>
  {:else}
    <div class="text-muted-foreground text-xs text-center py-4">{t('servo.noData')}</div>
  {/if}
</div>
