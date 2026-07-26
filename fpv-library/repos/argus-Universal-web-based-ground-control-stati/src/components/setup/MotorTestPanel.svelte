<script lang="ts">
  import { onDestroy } from 'svelte';
  import { app, isPlane } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, AlertTriangle, Zap, Square } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  const MOTOR_COUNT = 8;

  let throttle = $state(5);
  let duration = $state(2);
  let spinning: Record<number, number> = $state({});
  let timers: Record<number, ReturnType<typeof setInterval>> = {};

  let connected = $derived(app.drone.connected);
  let isCopter = $derived(!isPlane());

  function spinMotor(index: number) {
    if (!connected) return;
    dispatch('motor_test', undefined, {
      motor: index,
      throttle: throttle,
      duration: duration,
    });
    /* Start countdown for this motor */
    stopTimer(index);
    spinning[index] = duration;
    timers[index] = setInterval(() => {
      spinning[index] = Math.max(0, (spinning[index] ?? 0) - 0.1);
      if (spinning[index] <= 0) {
        stopTimer(index);
        delete spinning[index];
        /* Trigger reactivity by reassigning */
        spinning = { ...spinning };
      }
    }, 100);
  }

  function stopTimer(index: number) {
    if (timers[index]) {
      clearInterval(timers[index]);
      delete timers[index];
    }
  }

  function stopAll() {
    dispatch('motor_test_stop');
    for (let i = 0; i < MOTOR_COUNT; i++) {
      stopTimer(i);
    }
    spinning = {};
  }

  function isSpinning(index: number): boolean {
    return (spinning[index] ?? 0) > 0;
  }

  function remainStr(index: number): string {
    const r = spinning[index] ?? 0;
    return r > 0 ? r.toFixed(1) + 's' : '';
  }

  /* Quad X motor position labels */
  const quadLabels: Record<number, string> = {
    0: t('motor.fl'),
    1: t('motor.fr'),
    2: t('motor.bl'),
    3: t('motor.br'),
  };

  // Stop motors and clear intervals if the panel unmounts mid-spin so the
  // backend doesn't keep a motor running and we don't leak setInterval timers.
  onDestroy(stopAll);
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[560px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('motor.title')}</h2>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      <!-- Warning banner -->
      <div class="flex items-center gap-2 p-3 mb-3 rounded-lg bg-destructive/10 border border-destructive/30">
        <AlertTriangle size={18} class="text-destructive shrink-0" />
        <span class="text-xs font-semibold text-destructive">{t('motor.warn')}</span>
      </div>

      <!-- Hint text -->
      <p class="text-[11px] text-muted-foreground mb-4">{t('motor.hint')}</p>

      <!-- Motor grid (4x2) -->
      <div class="grid grid-cols-4 gap-2 mb-4">
        {#each Array(MOTOR_COUNT) as _, i}
          {@const active = isSpinning(i)}
          <div
            class="flex flex-col items-center gap-1.5 p-2 rounded-lg border transition-all
            {active ? 'border-primary/60 bg-primary/5' : 'border-border/50 bg-muted/20'}"
          >
            <!-- Spinning indicator circle -->
            <div class="relative w-8 h-8 flex items-center justify-center">
              <div
                class="w-8 h-8 rounded-full border-2 transition-all
                {active ? 'border-primary bg-primary/20 motor-active' : 'border-muted-foreground/30 bg-muted/30'}"
              ></div>
              <span
                class="absolute text-[10px] font-bold
                {active ? 'text-primary' : 'text-muted-foreground'}"
              >
                {i + 1}
              </span>
            </div>

            <!-- Motor label -->
            <span class="text-[10px] font-medium text-muted-foreground">
              {t('motor.motorNum')}{i + 1}
            </span>

            <!-- Spin button / countdown -->
            <Button
              variant={active ? 'secondary' : 'default'}
              size="xs"
              class="w-full text-[10px]"
              disabled={!connected}
              onclick={() => spinMotor(i)}
            >
              {#if active}
                <Zap size={10} />
                {remainStr(i)}
              {:else}
                {t('motor.spin')}
              {/if}
            </Button>
          </div>
        {/each}
      </div>

      <!-- Copter motor layout hint (Quad X) -->
      {#if isCopter}
        <div class="mb-4 p-2.5 rounded-lg bg-muted/50 border border-border/50">
          <p class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
            {t('label.quadX')}
          </p>
          <div class="grid grid-cols-2 gap-1 max-w-[160px] mx-auto">
            {#each [0, 1, 2, 3] as m}
              <div class="text-center text-[10px] font-mono text-muted-foreground py-0.5 rounded bg-muted/40">
                {quadLabels[m]}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Controls row -->
      <div class="space-y-3 mb-4">
        <!-- Throttle slider -->
        <div class="flex items-center gap-3">
          <label for="motor-throttle" class="text-[11px] font-medium text-foreground w-16 shrink-0"
            >{t('motor.throttle')}</label
          >
          <input
            id="motor-throttle"
            type="range"
            min="0"
            max="100"
            step="1"
            bind:value={throttle}
            class="flex-1 h-1.5 accent-primary"
          />
          <span class="text-xs font-mono text-muted-foreground w-10 text-right">{throttle}%</span>
        </div>

        <!-- Duration slider -->
        <div class="flex items-center gap-3">
          <label for="motor-duration" class="text-[11px] font-medium text-foreground w-16 shrink-0"
            >{t('motor.duration')}</label
          >
          <input
            id="motor-duration"
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            bind:value={duration}
            class="flex-1 h-1.5 accent-primary"
          />
          <span class="text-xs font-mono text-muted-foreground w-10 text-right">{duration}s</span>
        </div>
      </div>

      <!-- Stop All button -->
      <Button variant="destructive" class="w-full" onclick={stopAll} disabled={!connected}>
        <Square size={14} />
        {t('motor.stop')}
      </Button>

      {#if !connected}
        <p class="mt-2 text-center text-[11px] text-muted-foreground">{t('cal.connectFirst')}</p>
      {/if}
    </div>
  </div>
</div>

<style>
  @keyframes motor-pulse {
    0%,
    100% {
      box-shadow: 0 0 0 0 hsl(211 100% 50% / 0.4);
    }
    50% {
      box-shadow: 0 0 12px 4px hsl(211 100% 50% / 0.25);
    }
  }
  .motor-active {
    animation: motor-pulse 0.8s ease-in-out infinite;
  }
</style>
