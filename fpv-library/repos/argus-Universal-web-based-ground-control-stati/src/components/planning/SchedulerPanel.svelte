<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import {
    schedulerState,
    addSchedule,
    advanceSchedule,
    deleteSchedule,
    fireSchedule,
    persistSchedules,
    type Frequency,
    type Schedule,
    type ScheduleStatus,
  } from '../../lib/scheduler.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Clock, Calendar, Play, Trash2 } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  let showForm = $state(false);

  let formName = $state('');
  let formFrequency: Frequency = $state('once');
  let formCustomHours = $state(24);
  let formStartTime = $state('');
  let formAutoArm = $state(false);

  function submit() {
    if (!formName.trim()) {
      addToast(t('sched.nameRequired'), 'warn');
      return;
    }
    if (!formStartTime) {
      addToast(t('sched.timeRequired'), 'warn');
      return;
    }
    addSchedule({
      name: formName.trim(),
      frequency: formFrequency,
      customHours: formCustomHours,
      startTime: formStartTime,
      autoArm: formAutoArm,
    });
    formName = '';
    formFrequency = 'once';
    formCustomHours = 24;
    formStartTime = '';
    formAutoArm = false;
    showForm = false;
    addToast(t('sched.created'), 'success');
  }

  async function runNow(s: Schedule) {
    const result = await fireSchedule(s);
    if (result !== 'fired') return; // declined or stolen — leave the schedule as-is
    if (s.frequency === 'once') {
      s.status = 'completed';
    } else {
      // Advance past now like the tick's post-fire path: a past-due repeating
      // schedule left pending would be re-detected as due and pop a second
      // confirm within one tick (TICK_MS).
      advanceSchedule(s, Date.now());
    }
    persistSchedules();
  }

  function fmtFreq(s: Schedule): string {
    switch (s.frequency) {
      case 'once':
        return t('sched.once');
      case 'daily':
        return t('sched.daily');
      case 'weekly':
        return t('sched.weekly');
      case 'custom':
        return `${s.customHours}h`;
    }
  }

  function statusColor(s: ScheduleStatus): string {
    return s === 'completed' ? 'text-muted-foreground' : 'text-yellow-400';
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[500px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Calendar size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('sched.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
      <!-- New schedule toggle -->
      {#if !showForm}
        <Button variant="outline" class="w-full" onclick={() => (showForm = true)}>
          + {t('sched.new')}
        </Button>
      {:else}
        <div class="bg-muted/30 rounded-lg p-3 space-y-2">
          <!-- Name -->
          <div class="flex items-center gap-2">
            <label for="sched-name" class="text-xs text-muted-foreground w-16 shrink-0">{t('sched.name')}</label>
            <input
              id="sched-name"
              type="text"
              bind:value={formName}
              placeholder="..."
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>

          <!-- Frequency -->
          <div class="flex items-center gap-2">
            <label for="sched-freq" class="text-xs text-muted-foreground w-16 shrink-0">{t('sched.frequency')}</label>
            <select
              id="sched-freq"
              bind:value={formFrequency}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            >
              <option value="once">{t('sched.once')}</option>
              <option value="daily">{t('sched.daily')}</option>
              <option value="weekly">{t('sched.weekly')}</option>
              <option value="custom">{t('sched.custom')}</option>
            </select>
          </div>

          {#if formFrequency === 'custom'}
            <div class="flex items-center gap-2">
              <label for="sched-hours" class="text-xs text-muted-foreground w-16 shrink-0">{t('sched.interval')}</label>
              <input
                id="sched-hours"
                type="number"
                min="1"
                max="720"
                bind:value={formCustomHours}
                class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
              />
              <span class="text-xs text-muted-foreground">h</span>
            </div>
          {/if}

          <!-- Start time -->
          <div class="flex items-center gap-2">
            <label for="sched-time" class="text-xs text-muted-foreground w-16 shrink-0">{t('sched.startTime')}</label>
            <input
              id="sched-time"
              type="datetime-local"
              bind:value={formStartTime}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>

          <!-- Auto-arm -->
          <div class="flex items-center gap-2">
            <label for="sched-arm" class="text-xs text-muted-foreground w-16 shrink-0">{t('sched.autoArm')}</label>
            <input
              id="sched-arm"
              type="checkbox"
              bind:checked={formAutoArm}
              class="w-4 h-4 rounded border-border text-primary focus:ring-primary"
            />
          </div>

          <!-- Form actions -->
          <div class="flex gap-2">
            <Button variant="default" size="sm" class="flex-1" onclick={submit}>
              {t('sched.create')}
            </Button>
            <Button variant="ghost" size="sm" onclick={() => (showForm = false)}>
              {t('map.cancel')}
            </Button>
          </div>
        </div>
      {/if}

      <!-- Schedule list -->
      {#if schedulerState.schedules.length > 0}
        <div class="space-y-1">
          {#each schedulerState.schedules as sched (sched.id)}
            <div class="flex items-start gap-2 bg-muted/20 rounded-lg p-2 group">
              <Clock size={14} class="text-primary mt-0.5 shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-medium text-foreground truncate">{sched.name}</span>
                  <span class="text-[10px] font-medium {statusColor(sched.status)} bg-muted/50 px-1.5 py-0.5 rounded">
                    {t(`sched.status.${sched.status}`)}
                  </span>
                </div>
                <div class="text-[11px] text-muted-foreground">
                  {fmtFreq(sched)}
                  &middot; {sched.startTime.replace('T', ' ')}
                  {#if sched.autoArm}&middot; {t('sched.autoArm')}{/if}
                </div>
              </div>
              <div class="flex items-center gap-1 shrink-0">
                <button
                  class="p-1 text-primary hover:bg-primary/10 rounded"
                  onclick={() => void runNow(sched)}
                  title={t('sched.runNow')}
                >
                  <Play size={13} />
                </button>
                <button
                  class="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-destructive hover:bg-destructive/10 rounded"
                  onclick={() => deleteSchedule(sched.id)}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div class="text-xs text-muted-foreground text-center py-4 italic">
          {t('sched.empty')}
        </div>
      {/if}

      <!-- Hint -->
      <div class="p-3 rounded-lg bg-primary/5 border border-primary/20">
        <p class="text-xs text-muted-foreground leading-relaxed">
          {t('sched.hint')}
        </p>
      </div>
    </div>
  </div>
</div>
