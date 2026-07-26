<script lang="ts">
  import { t } from '../../lib/i18n.svelte';
  import {
    X,
    ChevronRight,
    ChevronLeft,
    Check,
    Layers,
    Radio,
    Zap,
    Compass,
    ShieldAlert,
    Plane,
    PartyPopper,
  } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  import { panels } from '../../lib/panels.svelte';

  let {
    onclose,
  }: {
    onclose: () => void;
  } = $props();

  /* ── Steps ── */

  interface Step {
    key: string;
    icon: typeof Layers;
    color: string;
    callback: () => void;
  }

  const steps: Step[] = [
    { key: 'setup.frame', icon: Layers, color: 'text-blue-500', callback: () => panels.open('frameSelect') },
    { key: 'setup.rc', icon: Radio, color: 'text-orange-500', callback: () => panels.open('rcCal') },
    { key: 'setup.motor', icon: Zap, color: 'text-yellow-500', callback: () => panels.open('motorTest') },
    { key: 'setup.cal', icon: Compass, color: 'text-green-500', callback: () => panels.open('calibration') },
    { key: 'setup.failsafe', icon: ShieldAlert, color: 'text-red-500', callback: () => panels.open('failsafe') },
    { key: 'setup.modes', icon: Plane, color: 'text-purple-500', callback: () => panels.open('flightModes') },
  ];

  let currentStep = $state(0);
  let completed = $state<boolean[]>(Array(steps.length).fill(false));

  let isLastStep = $derived(currentStep >= steps.length);
  let step = $derived(currentStep < steps.length ? steps[currentStep] : null);

  /* ── Navigation ── */

  function next() {
    if (currentStep < steps.length) {
      currentStep++;
    }
  }

  function prev() {
    if (currentStep > 0) {
      currentStep--;
    }
  }

  function skip() {
    next();
  }

  function openTool() {
    if (!step) return;
    completed[currentStep] = true;
    step.callback();
  }

  function goToStep(i: number) {
    if (i >= 0 && i <= steps.length) {
      currentStep = i;
    }
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[550px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Compass size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('setup.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      <!-- Step indicator -->
      <div class="flex items-center justify-center gap-1 mb-6 flex-wrap">
        {#each steps as s, i}
          <div class="flex items-center gap-1">
            <div role="presentation" class="flex items-center gap-1 cursor-pointer" onclick={() => goToStep(i)}>
              <div
                class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all
                {currentStep === i
                  ? 'bg-primary text-primary-foreground shadow-md'
                  : completed[i]
                    ? 'bg-green-500/80 text-white'
                    : 'bg-muted text-muted-foreground'}"
              >
                {#if completed[i] && currentStep !== i}
                  <Check size={12} />
                {:else}
                  {i + 1}
                {/if}
              </div>
              <span
                class="text-[10px] font-medium hidden sm:inline
                {currentStep === i ? 'text-foreground' : 'text-muted-foreground'}"
              >
                {t(s.key)}
              </span>
            </div>
            {#if i < steps.length - 1}
              <ChevronRight size={12} class="text-muted-foreground/40 mx-0.5" />
            {/if}
          </div>
        {/each}
      </div>

      <!-- Step content -->
      {#if isLastStep}
        <!-- Completion -->
        <div class="text-center py-10">
          <div
            class="w-16 h-16 rounded-full bg-green-500/10 border-2 border-green-500/30 flex items-center justify-center mx-auto mb-4"
          >
            <PartyPopper size={28} class="text-green-500" />
          </div>
          <h3 class="text-lg font-bold text-foreground mb-2">{t('setup.done')}</h3>
          <p class="text-xs text-muted-foreground mb-6">
            {completed.filter(Boolean).length}/{steps.length}
            {t('setup.step')}
          </p>
          <div class="flex gap-2 justify-center">
            <Button variant="default" onclick={onclose}>
              {t('setup.done')}
            </Button>
          </div>
        </div>
      {:else if step}
        <!-- Active step -->
        <div class="rounded-lg border border-border bg-card overflow-hidden">
          <!-- Step header -->
          <div class="px-5 py-4 bg-muted/30 border-b border-border/50">
            <div class="flex items-center gap-3">
              {#each [step] as s}
                {@const Icon = s.icon}
                <div class="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                  <Icon size={20} class={s.color} />
                </div>
              {/each}
              <div>
                <h3 class="text-sm font-semibold text-foreground">
                  {t('setup.step')}
                  {currentStep + 1}: {t(step.key)}
                </h3>
                <p class="text-[11px] text-muted-foreground mt-0.5">
                  {t(step.key + '.desc')}
                </p>
              </div>
              {#if completed[currentStep]}
                <div class="ml-auto">
                  <div class="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center">
                    <Check size={14} class="text-green-500" />
                  </div>
                </div>
              {/if}
            </div>
          </div>

          <!-- Step action -->
          <div class="px-5 py-4">
            <Button variant="default" class="w-full" onclick={openTool}>
              {t(step.key)}
            </Button>
          </div>
        </div>

        <!-- Navigation buttons -->
        <div class="flex items-center justify-between mt-4 pt-3 border-t border-border/50">
          <Button variant="ghost" size="sm" class="text-xs" onclick={prev} disabled={currentStep === 0}>
            <ChevronLeft size={14} />
            {t('setup.prev')}
          </Button>

          <div class="flex gap-2">
            <Button variant="ghost" size="sm" class="text-xs text-muted-foreground" onclick={skip}>
              {t('setup.skip')}
            </Button>
            <Button variant="default" size="sm" class="text-xs" onclick={next}>
              {t('setup.next')}
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>
