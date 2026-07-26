<script lang="ts">
  import { app, addToast, isPlane } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { paramState, getParam } from '../../lib/paramStore.svelte';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Zap, AlertTriangle } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  const connected = $derived(app.drone.connected);
  const armed = $derived(app.drone.armed);
  const AUTOTUNE_MODE_COPTER = 15;
  const AUTOTUNE_MODE_PLANE = 8;
  let axes = $state(0);

  const AXES_OPTIONS = $derived([
    { value: 0, label: t('autotune.all') },
    { value: 1, label: t('autotune.rollOnly') },
    { value: 2, label: t('autotune.pitchOnly') },
    { value: 4, label: t('autotune.yawOnly') },
  ]);

  let isAutotuning = $derived(
    app.drone.mode_id === (isPlane() ? AUTOTUNE_MODE_PLANE : AUTOTUNE_MODE_COPTER)
  );

  function start() {
    if (axes !== 0) {
      dispatch('param_set', undefined, { name: 'AUTOTUNE_AXES', value: axes });
    }
    dispatch('mode', isPlane() ? AUTOTUNE_MODE_PLANE : AUTOTUNE_MODE_COPTER);
    addToast(t('autotune.start'), 'info');
  }

  function stop() {
    // Plane: 19=QLoiter, Copter: 5=Loiter — safe hover modes to exit AutoTune
    dispatch('mode', isPlane() ? 19 : 5);
    addToast(t('autotune.stop'), 'info');
  }

  let currentAxes = $derived(getParam('AUTOTUNE_AXES', 0));
  let aggr = $derived(getParam('AUTOTUNE_AGGR', 0.1));
</script>

<div role="dialog" aria-modal="true" tabindex="-1" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center" onclick={onclose} onkeydown={(e) => { if (e.key === "Escape") onclose(); }}>
  <div class="bg-card border border-border rounded-2xl overflow-hidden w-[420px] shadow-2xl" role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Zap size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('autotune.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="px-5 py-4 space-y-4">
      {#if !connected}
        <div class="text-center py-8 text-sm text-muted-foreground">{t('console.notConnected')}</div>
      {:else}
        <div class="flex items-start gap-2 p-3 rounded-lg bg-warning/10 border border-warning/30">
          <AlertTriangle size={16} class="text-warning shrink-0 mt-0.5" />
          <p class="text-xs text-warning">{t('autotune.hint')}</p>
        </div>

        <div>
          <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('autotune.axes')}</span>
          <div class="flex gap-1.5 mt-1.5">
            {#each AXES_OPTIONS as opt}
              <button class="px-3 py-1.5 text-xs rounded-md border transition-all cursor-pointer
                {axes === opt.value
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card text-muted-foreground border-border hover:text-foreground hover:bg-muted'}"
                onclick={() => axes = opt.value}>{opt.label}</button>
            {/each}
          </div>
        </div>

        {#if paramState.list.length > 0}
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="flex justify-between p-2 bg-muted rounded-lg">
              <span class="text-muted-foreground">AUTOTUNE_AXES</span>
              <span class="font-mono">{currentAxes}</span>
            </div>
            <div class="flex justify-between p-2 bg-muted rounded-lg">
              <span class="text-muted-foreground">AUTOTUNE_AGGR</span>
              <span class="font-mono">{aggr.toFixed(2)}</span>
            </div>
          </div>
        {/if}

        {#if isAutotuning}
          <div class="text-center py-3">
            <div class="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 rounded-full">
              <span class="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
              <span class="text-sm font-bold text-primary">AutoTune {t('cal.active')}</span>
            </div>
          </div>
          <Button variant="destructive" class="w-full" onclick={stop}>{t('autotune.stop')}</Button>
        {:else}
          <Button variant="default" class="w-full" onclick={start} disabled={!armed}>
            <Zap size={14} class="mr-1" />{t('autotune.start')}
          </Button>
          {#if !armed}
            <p class="text-[10px] text-muted-foreground text-center">{t('check.notArmed')}</p>
          {/if}
        {/if}
      {/if}
    </div>
  </div>
</div>
