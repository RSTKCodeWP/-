<script lang="ts">
  import { untrack } from 'svelte';
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import { X, Radio, ChevronRight } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  const CH_COUNT = 8;
  const CH_LABELS = $derived([t('rc.roll'), t('rc.pitch'), t('rc.throttle'), t('rc.yaw'), 'CH5', 'CH6', 'CH7', 'CH8']);

  let step = $state(1);
  let trimValues = $state<number[]>(Array(CH_COUNT).fill(1500));
  let minValues = $state<number[]>(Array(CH_COUNT).fill(2200));
  let maxValues = $state<number[]>(Array(CH_COUNT).fill(800));
  let writing = $state(false);

  let connected = $derived(app.drone.connected);

  /* ── Step 2: track min/max as sticks move ── */
  $effect(() => {
    if (step !== 2) return;
    const rc = app.drone.rc;
    if (!rc || rc.length < CH_COUNT) return;
    // untrack so the read/write loop on minValues/maxValues doesn't repeatedly
    // re-trigger this effect on the same rc snapshot.
    untrack(() => {
      for (let i = 0; i < CH_COUNT; i++) {
        const v = rc[i];
        if (v < minValues[i]) minValues[i] = v;
        if (v > maxValues[i]) maxValues[i] = v;
      }
    });
  });

  let allRangeOk = $derived(minValues.every((min, i) => maxValues[i] - min > 300));

  /* ── Helpers ── */
  function barWidth(v: number): number {
    return Math.max(0, Math.min(100, (v - 800) / 14));
  }

  function recordTrim() {
    const rc = app.drone.rc;
    if (!rc || rc.length < CH_COUNT) return;
    for (let i = 0; i < CH_COUNT; i++) {
      trimValues[i] = rc[i];
    }
    step = 2;
    /* Reset min/max from current values */
    for (let i = 0; i < CH_COUNT; i++) {
      minValues[i] = rc[i];
      maxValues[i] = rc[i];
    }
  }

  let reversed = $state(Array(CH_COUNT).fill(false));

  function detectReverse() {
    for (let i = 0; i < 4; i++) {
      const expectedHighFirst = i === 0 || i === 3;
      if (minValues[i] < 2200 && maxValues[i] > 800) {
        const range = maxValues[i] - minValues[i];
        if (range > 300) {
          const centerToTrim = trimValues[i] - (minValues[i] + maxValues[i]) / 2;
          if ((expectedHighFirst && centerToTrim < -50) || (!expectedHighFirst && centerToTrim > 50)) {
            reversed[i] = true;
          }
        }
      }
    }
    reversed = [...reversed];
  }

  async function writeToFc() {
    writing = true;
    detectReverse();
    for (let i = 0; i < CH_COUNT; i++) {
      const ch = i + 1;
      const rev = reversed[i];
      dispatch('param_set', undefined, { name: `RC${ch}_MIN`, value: rev ? maxValues[i] : minValues[i] });
      dispatch('param_set', undefined, { name: `RC${ch}_MAX`, value: rev ? minValues[i] : maxValues[i] });
      dispatch('param_set', undefined, { name: `RC${ch}_TRIM`, value: trimValues[i] });
      dispatch('param_set', undefined, { name: `RC${ch}_REVERSED`, value: rev ? 1 : 0 });
    }
    writing = false;
    const revCount = reversed.filter((r) => r).length;
    const msg = t('rccal.writeDone').replace('{n}', String(CH_COUNT * 4));
    addToast(msg + (revCount > 0 ? ` (${revCount} reversed)` : ''), 'success');
  }

  function resetWizard() {
    step = 1;
    trimValues = Array(CH_COUNT).fill(1500);
    minValues = Array(CH_COUNT).fill(2200);
    maxValues = Array(CH_COUNT).fill(800);
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[600px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Radio size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('rccal.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      <!-- Step indicator -->
      <div class="flex items-center justify-center gap-2 mb-5">
        {#each [1, 2, 3] as s}
          <div class="flex items-center gap-2">
            <div
              class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all
              {step === s
                ? 'bg-primary text-primary-foreground shadow-md'
                : step > s
                  ? 'bg-green-500/80 text-white'
                  : 'bg-muted text-muted-foreground'}"
            >
              {s}
            </div>
            <span
              class="text-[11px] font-medium
              {step === s ? 'text-foreground' : 'text-muted-foreground'}"
            >
              {t(`rccal.step${s}`)}
            </span>
            {#if s < 3}
              <ChevronRight size={14} class="text-muted-foreground/40 mx-1" />
            {/if}
          </div>
        {/each}
      </div>

      <!-- Not connected warning -->
      {#if !connected}
        <div class="text-center py-8">
          <p class="text-sm text-muted-foreground">{t('cal.connectFirst')}</p>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- STEP 1 — Center Sticks                       -->
        <!-- ════════════════════════════════════════════ -->
      {:else if step === 1}
        <p class="text-[11px] text-muted-foreground mb-4">{t('rccal.center')}</p>

        <div class="space-y-1.5 mb-5">
          {#each Array(CH_COUNT) as _, i}
            {@const val = app.drone.rc?.[i] ?? 1500}
            <div class="flex items-center gap-2 text-[11px]">
              <span class="w-14 text-right text-muted-foreground text-[10px] shrink-0 font-medium">{CH_LABELS[i]}</span>
              <div class="flex-1 h-3 bg-muted rounded-full relative overflow-hidden">
                <div
                  class="h-full rounded-full bg-primary transition-all duration-100"
                  style="width:{barWidth(val)}%"
                ></div>
                <div class="absolute left-1/2 top-0 w-px h-full bg-border"></div>
              </div>
              <span class="w-10 text-right font-mono text-muted-foreground text-[10px] shrink-0">{val}</span>
            </div>
          {/each}
        </div>

        <Button
          variant="default"
          class="w-full"
          onclick={recordTrim}
          disabled={!connected || !app.drone.rc || app.drone.rc.length < CH_COUNT}
        >
          {t('rccal.recordTrim')}
        </Button>

        <!-- ════════════════════════════════════════════ -->
        <!-- STEP 2 — Full Range                          -->
        <!-- ════════════════════════════════════════════ -->
      {:else if step === 2}
        <p class="text-[11px] text-muted-foreground mb-4">{t('rccal.move')}</p>

        <div class="space-y-1.5 mb-5">
          {#each Array(CH_COUNT) as _, i}
            {@const val = app.drone.rc?.[i] ?? 1500}
            {@const range = maxValues[i] - minValues[i]}
            <div class="flex items-center gap-2 text-[11px]">
              <span class="w-14 text-right text-muted-foreground text-[10px] shrink-0 font-medium">{CH_LABELS[i]}</span>
              <div class="flex-1 h-3 bg-muted rounded-full relative overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-100
                  {range > 300 ? 'bg-green-500' : 'bg-primary'}"
                  style="width:{barWidth(val)}%"
                ></div>
                <div class="absolute left-1/2 top-0 w-px h-full bg-border"></div>
              </div>
              <span
                class="w-10 text-right font-mono text-[10px] shrink-0
                {range > 300 ? 'text-green-400' : 'text-muted-foreground'}">{val}</span
              >
              <span class="w-20 text-right font-mono text-[9px] text-muted-foreground shrink-0">
                {t('rccal.min')}:{minValues[i]}
                {t('rccal.max')}:{maxValues[i]}
              </span>
            </div>
          {/each}
        </div>

        <Button
          variant="default"
          class="w-full"
          onclick={() => {
            step = 3;
          }}
          disabled={!allRangeOk}
        >
          {t('rccal.next')}
          <ChevronRight size={14} />
        </Button>

        <!-- ════════════════════════════════════════════ -->
        <!-- STEP 3 — Review & Write                      -->
        <!-- ════════════════════════════════════════════ -->
      {:else if step === 3}
        <p class="text-[11px] text-muted-foreground mb-4">{t('rccal.done')}</p>

        <div class="rounded-lg border border-border overflow-hidden mb-5">
          <table class="w-full text-[11px]">
            <thead>
              <tr class="bg-muted/50 text-muted-foreground text-left">
                <th class="px-3 py-1.5 font-semibold">{t('rccal.ch')}</th>
                <th class="px-3 py-1.5 font-semibold text-right">{t('rccal.min')}</th>
                <th class="px-3 py-1.5 font-semibold text-right">{t('rccal.trim')}</th>
                <th class="px-3 py-1.5 font-semibold text-right">{t('rccal.max')}</th>
              </tr>
            </thead>
            <tbody>
              {#each Array(CH_COUNT) as _, i}
                <tr class="border-t border-border/50 hover:bg-muted/30 transition-colors">
                  <td class="px-3 py-1.5 font-medium text-foreground">{CH_LABELS[i]}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-muted-foreground">{minValues[i]}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-foreground">{trimValues[i]}</td>
                  <td class="px-3 py-1.5 text-right font-mono text-muted-foreground">{maxValues[i]}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>

        <div class="flex gap-2">
          <Button variant="default" class="flex-1" onclick={writeToFc} disabled={writing}>
            {t('rccal.write')}
          </Button>
          <Button variant="secondary" class="flex-1" onclick={resetWizard}>
            {t('rccal.reset')}
          </Button>
        </div>
      {/if}
    </div>
  </div>
</div>
