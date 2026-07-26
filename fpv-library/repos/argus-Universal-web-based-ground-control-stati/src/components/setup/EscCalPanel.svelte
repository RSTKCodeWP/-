<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, AlertTriangle, ChevronRight } from '@lucide/svelte';

  let { onclose: _onclose }: { onclose: () => void } = $props();

  let step = $state(0);
  const connected = $derived(app.drone.connected);

  function safeClose() {
    if (step > 0 && step < 5) {
      const channels = Array(8).fill(0);
      dispatch('rc_override', undefined, { channels });
    }
    step = 0;
    _onclose();
  }
  const onclose = safeClose;

  function setMax() {
    const channels = Array(8).fill(2000);
    dispatch('rc_override', undefined, { channels });
    step = 2;
  }

  function setMin() {
    const channels = Array(8).fill(1000);
    dispatch('rc_override', undefined, { channels });
    step = 4;
  }

  function release() {
    const channels = Array(8).fill(0);
    dispatch('rc_override', undefined, { channels });
    addToast(t('esccal.title') + ' OK', 'success');
    step = 5;
  }

  const STEPS = $derived([
    t('esccal.step1'),
    t('esccal.step2'),
    t('esccal.step3'),
    t('esccal.step4'),
    t('esccal.step5'),
  ]);
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[420px] shadow-2xl"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-warning/20 to-warning/5 px-5 py-3 flex items-center justify-between">
      <h3 class="text-base font-bold text-warning">{t('esccal.title')}</h3>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="px-5 py-4 space-y-4">
      <div class="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30">
        <AlertTriangle size={18} class="text-destructive shrink-0" />
        <span class="text-xs font-bold text-destructive">{t('esccal.warn')}</span>
      </div>

      {#if !connected}
        <div class="text-center py-8 text-sm text-muted-foreground">{t('console.notConnected')}</div>
      {:else}
        <div class="space-y-2">
          {#each STEPS as label, i}
            <div
              class="flex items-center gap-3 py-2 px-3 rounded-lg transition-colors
              {step === i
                ? 'bg-primary/10 border border-primary/30'
                : step > i
                  ? 'bg-muted/50 text-muted-foreground'
                  : 'text-muted-foreground/60'}"
            >
              <span
                class="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0
                {step === i
                  ? 'bg-primary text-primary-foreground'
                  : step > i
                    ? 'bg-muted-foreground/30 text-muted-foreground'
                    : 'bg-muted text-muted-foreground/50'}"
              >
                {i + 1}
              </span>
              <span class="text-sm flex-1">{label}</span>
              {#if step === i}
                <ChevronRight size={14} class="text-primary" />
              {/if}
            </div>
          {/each}
        </div>

        <div class="flex gap-2 pt-2">
          {#if step === 0}
            <Button variant="default" class="flex-1" onclick={() => (step = 1)}>{t('rccal.next')}</Button>
          {:else if step === 1}
            <Button variant="destructive" class="flex-1" onclick={setMax}>{t('esccal.maxThrottle')}</Button>
          {:else if step === 2 || step === 3}
            <Button variant="secondary" class="flex-1 bg-amber-600 hover:bg-amber-700 text-white" onclick={setMin}
              >{t('esccal.minThrottle')}</Button
            >
          {:else if step === 4}
            <Button variant="default" class="flex-1" onclick={release}>{t('rccal.done')}</Button>
          {:else}
            <Button variant="secondary" class="flex-1" onclick={onclose}>{t('summary.confirm')}</Button>
          {/if}
          <Button
            variant="outline"
            onclick={() => {
              step = 0;
              const ch = Array(8).fill(0);
              dispatch('rc_override', undefined, { channels: ch });
            }}
          >
            {t('rccal.reset')}
          </Button>
        </div>
      {/if}
    </div>
  </div>
</div>
