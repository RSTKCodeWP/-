<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { API_BASE } from '../../lib/backend';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import Badge from '$lib/components/ui/badge/badge.svelte';
  import { X, Compass, Move3d, RotateCw, AlignHorizontalSpaceAround, Thermometer, ChevronRight } from '@lucide/svelte';
  import type { Component } from 'svelte';

  let { onclose }: { onclose: () => void } = $props();

  type CalType = 'compass' | 'accel' | 'gyro' | 'level' | 'baro';

  const calTypes: { id: CalType; labelKey: string; cmd: string; icon: Component }[] = [
    { id: 'compass', labelKey: 'cal.compass', cmd: 'cal_compass', icon: Compass },
    { id: 'accel', labelKey: 'cal.accel', cmd: 'cal_accel', icon: Move3d },
    { id: 'gyro', labelKey: 'cal.gyro', cmd: 'cal_gyro', icon: RotateCw },
    { id: 'level', labelKey: 'cal.level', cmd: 'cal_level', icon: AlignHorizontalSpaceAround },
    { id: 'baro', labelKey: 'cal.baro', cmd: 'cal_baro', icon: Thermometer },
  ];

  /* ── Accel orientation definitions ── */
  type AccelStep = 'level' | 'nose_up' | 'nose_down' | 'left' | 'right' | 'back';
  type StepStatus = 'pending' | 'active' | 'done';

  interface OrientDef {
    id: AccelStep;
    label: string;
    hint: string;
    img: string;
    keywords: string[];
  }

  // Order matches ArduPilot's actual sequence (AP_AccelCal): level, left,
  // right, nose-down, nose-up, back. A 3-column grid then lays out row-by-row
  // in the same order ArduPilot prompts the user.
  const accelOrients: OrientDef[] = [
    {
      id: 'level',
      label: 'cal.orientLevel',
      hint: 'cal.hintLevel',
      img: `${API_BASE}/images/cal/VehicleDown.png`,
      keywords: [],
    },
    {
      id: 'left',
      label: 'cal.orientLeft',
      hint: 'cal.hintLeft',
      img: `${API_BASE}/images/cal/VehicleLeft.png`,
      keywords: [],
    },
    {
      id: 'right',
      label: 'cal.orientRight',
      hint: 'cal.hintRight',
      img: `${API_BASE}/images/cal/VehicleRight.png`,
      keywords: [],
    },
    {
      id: 'nose_down',
      label: 'cal.orientNoseDown',
      hint: 'cal.hintNoseDown',
      img: `${API_BASE}/images/cal/VehicleNoseDown.png`,
      keywords: [],
    },
    {
      id: 'nose_up',
      label: 'cal.orientNoseUp',
      hint: 'cal.hintNoseUp',
      img: `${API_BASE}/images/cal/VehicleTailDown.png`,
      keywords: [],
    },
    {
      id: 'back',
      label: 'cal.orientBack',
      hint: 'cal.hintBack',
      img: `${API_BASE}/images/cal/VehicleUpsideDown.png`,
      keywords: [],
    },
  ];

  // Order matters: "upside/inverted" must match before "up" to avoid misidentification
  const orientPatterns: [RegExp, AccelStep][] = [
    [/upside|inverted|倒置|翻转/i, 'back'],
    [/\bback\b/i, 'back'],
    [/nose[\s-]*down|机头朝下/i, 'nose_down'],
    [/nose[\s-]*up|机头朝上/i, 'nose_up'],
    [/\bleft\b|左侧/i, 'left'],
    [/\bright\b|右侧/i, 'right'],
    [/\blevel\b|水平/i, 'level'],
  ];

  function detectOrientation(text: string): AccelStep | null {
    for (const [re, id] of orientPatterns) {
      if (re.test(text)) return id;
    }
    return null;
  }

  let selected = $state<CalType>('compass');
  let calibrating = $state(false);
  // HH:MM:SS marker set when calibration starts. Empty string = no active run.
  // Filtering by timestamp (instead of a length cursor) survives backend events-array trim.
  let calRunStartTime = $state('');

  const calPattern =
    /校准|calibrat|cal |gyro|compass|accel|baro|level|place|rotate|orientation|complete|success|完成|成功|失败|failed|progress/i;

  function eventInRun(ev: { time: string; text: string }): boolean {
    if (!calRunStartTime) return false;
    if (ev.time < calRunStartTime) return false;
    if (!calPattern.test(ev.text)) return false;
    if (/^指令应答:|^Command:/i.test(ev.text)) return false;
    return true;
  }

  /* Display: last 20 cal-pattern events for the message log */
  let calEvents = $derived(app.events.filter((e) => calPattern.test(e.text)).slice(-20));

  /* ── Compass: pure-derived progress/done/failed ── */
  let compassParsed = $derived.by(() => {
    let pct = 0,
      done = false,
      failed = false;
    if (selected !== 'compass') return { pct, done, failed };
    for (const ev of app.events) {
      if (!eventInRun(ev)) continue;
      const m = ev.text.match(/(\d+)%/);
      if (m) {
        pct = Math.max(pct, parseInt(m[1]));
      } else if (/complete|完成|calibrated/i.test(ev.text)) {
        done = true;
      }
      if (/failed|失败/i.test(ev.text)) failed = true;
    }
    return { pct, done, failed };
  });

  let compassProgress = $derived(compassParsed.done ? 100 : Math.min(95, compassParsed.pct));

  /* ── Accel: pure-derived per-orientation status ── */
  const EMPTY_STEPS: Record<AccelStep, StepStatus> = {
    level: 'pending',
    nose_up: 'pending',
    nose_down: 'pending',
    left: 'pending',
    right: 'pending',
    back: 'pending',
  };

  let accelParsed = $derived.by(() => {
    const steps: Record<AccelStep, StepStatus> = { ...EMPTY_STEPS };
    let active: AccelStep | null = null;
    let complete = false;
    let failed = false;
    if (selected !== 'accel') return { steps, active, complete, failed };
    for (const ev of app.events) {
      if (!eventInRun(ev)) continue;
      const txt = ev.text;
      const orient = detectOrientation(txt);
      const isPlace = /place|放置|请将/i.test(txt);
      const isDone = /完成|complete|done|success|成功|successful/i.test(txt);
      const isFailed = /failed|失败|FAILED/i.test(txt);

      if (orient && isPlace) {
        // ArduPilot moved to a new orientation — mark prev active done.
        if (active && steps[active] === 'active') steps[active] = 'done';
        steps[orient] = 'active';
        active = orient;
      } else if (orient && isDone) {
        steps[orient] = 'done';
        if (active === orient) active = null;
      } else if (!orient && isDone) {
        // Generic completion like "Calibration successful" — ArduPilot's
        // AccelCal emits this once the full 6-orientation sequence is done.
        // No orientation keyword means it's the final summary, not a per-step.
        for (const id of Object.keys(steps) as AccelStep[]) {
          if (steps[id] !== 'done') steps[id] = 'done';
        }
        active = null;
        complete = true;
      }
      if (isFailed) failed = true;
    }
    return { steps, active, complete, failed };
  });

  let accelSteps = $derived(accelParsed.steps);
  let accelActive = $derived(accelParsed.active);
  let accelDoneCount = $derived(accelOrients.filter((o) => accelSteps[o.id] === 'done').length);

  /* ── Gyro/level/baro: simple done detector. Skips the "开始" event itself. ── */
  let simpleCalDone = $derived.by(() => {
    if (selected === 'compass' || selected === 'accel') return { done: false, failed: false };
    let done = false,
      failed = false;
    for (const ev of app.events) {
      if (!eventInRun(ev)) continue;
      if (/开始|start/i.test(ev.text) && !/complete|完成|success|成功|done/i.test(ev.text)) continue;
      if (/success|成功|complete|done|完成/i.test(ev.text)) done = true;
      if (/failed|失败/i.test(ev.text)) failed = true;
    }
    return { done, failed };
  });

  /* Side effects: flip calibrating off on completion/failure; auto-accept compass. */
  $effect(() => {
    if (!calibrating) return;
    if (selected === 'compass') {
      if (compassParsed.done) {
        calibrating = false;
        dispatch('cal_compass_accept');
      } else if (compassParsed.failed) {
        calibrating = false;
      }
    } else if (selected === 'accel') {
      if (accelParsed.complete || accelParsed.failed) {
        calibrating = false;
      }
    } else if (simpleCalDone.done || simpleCalDone.failed) {
      calibrating = false;
    }
  });

  function nowHMS(): string {
    return new Date().toTimeString().slice(0, 8);
  }

  function startCal() {
    const ct = calTypes.find((c) => c.id === selected);
    if (!ct) return;
    // Mark BEFORE sending; backend's "开始..." event arrives microseconds later
    // with time >= now, captured by the >= comparison in eventInRun. No backward
    // offset — that would let events from a just-cancelled prior cal leak in.
    calRunStartTime = nowHMS();
    calibrating = true;
    dispatch(ct.cmd);
  }

  function cancelCal() {
    dispatch('cal_cancel');
    calibrating = false;
    calRunStartTime = '';
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[560px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('cal.title')}</h2>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      <!-- Tab selector -->
      <div class="flex flex-wrap gap-1.5 mb-4">
        {#each calTypes as ct (ct.id)}
          <button
            class="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md transition-all
              {selected === ct.id
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
            onclick={() => {
              if (!calibrating) selected = ct.id;
            }}
            disabled={calibrating}
          >
            <ct.icon size={13} />{t(ct.labelKey)}
          </button>
        {/each}
      </div>

      <!-- ════════════════════════════════════════════ -->
      <!-- ACCEL calibration panel                      -->
      <!-- ════════════════════════════════════════════ -->
      {#if selected === 'accel'}
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <p class="text-xs font-semibold text-foreground">{t('cal.accelTitle')}</p>
            {#if calibrating}
              <Badge variant="secondary" class="text-[10px]">{t('cal.progress')} {accelDoneCount}/6</Badge>
            {/if}
          </div>
          <p class="text-[11px] text-muted-foreground mb-3">
            {t('cal.accelDesc')}
          </p>

          <!-- 6-orientation grid -->
          <div class="grid grid-cols-3 gap-2 mb-3">
            {#each accelOrients as orient (orient.id)}
              {@const st = accelSteps[orient.id]}
              <div
                class="flex flex-col items-center p-2 rounded-lg border-2 transition-all
                {st === 'done'
                  ? 'border-green-500/60 bg-green-500/5'
                  : st === 'active'
                    ? 'border-primary/60 bg-primary/5 cal-active-border'
                    : 'border-border/50 bg-muted/20'}"
              >
                <div
                  class="w-20 h-16 flex items-center justify-center mb-1 rounded-md overflow-hidden
                  {st === 'done'
                    ? 'bg-green-900/30 ring-1 ring-green-500/40'
                    : st === 'active'
                      ? 'bg-primary/10 ring-1 ring-primary/40'
                      : 'bg-muted/20'}"
                >
                  <img
                    src={orient.img}
                    alt={t(orient.label)}
                    class="w-full h-full object-contain transition-all
                         {st === 'done' ? '' : st === 'active' ? '' : 'opacity-40 grayscale'}"
                  />
                </div>

                <!-- Label + status icon -->
                <span
                  class="text-[11px] font-medium {st === 'done'
                    ? 'text-green-400'
                    : st === 'active'
                      ? 'text-primary'
                      : 'text-muted-foreground'}"
                >
                  {t(orient.label)}
                </span>
                <span
                  class="text-[10px] mt-0.5
                  {st === 'done' ? 'text-green-500' : st === 'active' ? 'text-primary' : 'text-muted-foreground/50'}"
                >
                  {st === 'done' ? t('cal.done') : st === 'active' ? t('cal.active') : t('cal.pending')}
                </span>
              </div>
            {/each}
          </div>

          <!-- Current step hint + confirm button -->
          {#if calibrating && accelActive}
            {@const ao = accelOrients.find((o) => o.id === accelActive)}
            {#if ao}
              <div
                class="p-2.5 rounded-lg bg-primary/10 border border-primary/20 mb-3 flex items-center justify-between gap-2"
              >
                <p class="text-xs text-primary font-medium">{t(ao.hint)}，{t('cal.holdStill')}</p>
                <Button variant="default" size="sm" class="shrink-0" onclick={() => dispatch('cal_accel_next')}>
                  <ChevronRight size={14} class="mr-1" />{t('cal.accelNext')}
                </Button>
              </div>
            {/if}
          {:else if !calibrating}
            <div class="p-2.5 rounded-lg bg-muted/50 border border-border/50 mb-3">
              <p class="text-[11px] text-muted-foreground">{t('cal.accelHintBefore')}</p>
            </div>
          {/if}
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- COMPASS calibration panel                    -->
        <!-- ════════════════════════════════════════════ -->
      {:else if selected === 'compass'}
        <div class="mb-4">
          <p class="text-xs font-semibold text-foreground mb-1">{t('cal.compassTitle')}</p>
          <p class="text-[11px] text-muted-foreground mb-4">
            {t('cal.compassDesc')}
          </p>

          <!-- Circular progress indicator -->
          <div class="flex flex-col items-center mb-4">
            <div class="relative w-[120px] h-[120px]">
              <svg viewBox="0 0 120 120" class="w-full h-full">
                <!-- Background circle -->
                <circle cx="60" cy="60" r="50" fill="none" stroke="hsl(var(--border))" stroke-width="6" opacity="0.4" />
                <!-- Progress arc -->
                {#if calibrating || compassProgress > 0}
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="none"
                    stroke={compassProgress >= 100 ? '#22c55e' : 'hsl(211,100%,50%)'}
                    stroke-width="6"
                    stroke-linecap="round"
                    stroke-dasharray={Math.PI * 100}
                    stroke-dashoffset={Math.PI * 100 * (1 - compassProgress / 100)}
                    transform="rotate(-90, 60, 60)"
                    class="transition-all duration-500"
                  />
                {/if}
                <!-- Center drone icon -->
                <g transform="translate(60,60)">
                  <rect
                    x="-6"
                    y="-6"
                    width="12"
                    height="12"
                    rx="1.5"
                    fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                    opacity="0.7"
                  />
                  <line
                    x1="-6"
                    y1="-6"
                    x2="-14"
                    y2="-14"
                    stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                    stroke-width="1.5"
                    stroke-linecap="round"
                  />
                  <line
                    x1="6"
                    y1="-6"
                    x2="14"
                    y2="-14"
                    stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                    stroke-width="1.5"
                    stroke-linecap="round"
                  />
                  <line
                    x1="-6"
                    y1="6"
                    x2="-14"
                    y2="14"
                    stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                    stroke-width="1.5"
                    stroke-linecap="round"
                  />
                  <line
                    x1="6"
                    y1="6"
                    x2="14"
                    y2="14"
                    stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                    stroke-width="1.5"
                    stroke-linecap="round"
                  />
                  <circle cx="-14" cy="-14" r="3" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.5" />
                  <circle cx="14" cy="-14" r="3" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.5" />
                  <circle cx="-14" cy="14" r="3" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.5" />
                  <circle cx="14" cy="14" r="3" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.5" />
                </g>
                <!-- Rotation arrow (animated when calibrating) -->
                {#if calibrating}
                  <g class="spin-slow" style="transform-origin: 60px 60px;">
                    <path
                      d="M60,6 A54,54 0 0,1 108,40"
                      fill="none"
                      stroke="hsl(211,100%,50%)"
                      stroke-width="2"
                      stroke-linecap="round"
                      opacity="0.6"
                    />
                    <polygon points="108,40 104,32 112,34" fill="hsl(211,100%,50%)" opacity="0.6" />
                  </g>
                {/if}
              </svg>
              <!-- Percentage in center -->
              {#if calibrating || compassProgress > 0}
                <div class="absolute inset-0 flex items-center justify-center pt-8">
                  <span class="text-sm font-bold {compassProgress >= 100 ? 'text-green-400' : 'text-primary'}">
                    {compassProgress}%
                  </span>
                </div>
              {/if}
            </div>
            <p class="mt-2 text-[11px] text-muted-foreground">
              {#if !calibrating && compassProgress === 0}
                {t('cal.compassHintBefore')}
              {:else if calibrating}
                {t('cal.compassHintActive')}
              {:else if compassProgress >= 100}
                {t('cal.compassHintDone')}
              {/if}
            </p>
          </div>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- GYRO / LEVEL / BARO - simple "keep still"   -->
        <!-- ════════════════════════════════════════════ -->
      {:else}
        {@const labels = {
          gyro: { titleKey: 'cal.gyroTitle', descKey: 'cal.gyroDesc', icon: t('cal.iconGyro') },
          level: { titleKey: 'cal.levelTitle', descKey: 'cal.levelDesc', icon: t('cal.iconLevel') },
          baro: { titleKey: 'cal.baroTitle', descKey: 'cal.baroDesc', icon: t('cal.iconBaro') },
        }}
        {@const info = labels[selected]}
        <div class="mb-4">
          <p class="text-xs font-semibold text-foreground mb-1">{t(info.titleKey)}</p>
          <p class="text-[11px] text-muted-foreground mb-4">{t(info.descKey)}</p>

          <div class="flex flex-col items-center mb-4">
            <!-- Pulsing keep-still indicator -->
            <div class="relative w-[100px] h-[100px] flex items-center justify-center">
              {#if calibrating}
                <div class="absolute inset-0 rounded-full border-2 border-primary/40 gentle-pulse"></div>
                <div
                  class="absolute inset-2 rounded-full border-2 border-primary/25 gentle-pulse"
                  style="animation-delay: 0.5s;"
                ></div>
              {/if}
              <svg viewBox="0 0 60 60" class="w-[56px] h-[56px]">
                <!-- Simple flat drone -->
                <rect
                  x="22"
                  y="22"
                  width="16"
                  height="16"
                  rx="2"
                  fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                  opacity="0.8"
                />
                <line
                  x1="22"
                  y1="22"
                  x2="10"
                  y2="10"
                  stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                  stroke-width="2"
                  stroke-linecap="round"
                />
                <line
                  x1="38"
                  y1="22"
                  x2="50"
                  y2="10"
                  stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                  stroke-width="2"
                  stroke-linecap="round"
                />
                <line
                  x1="22"
                  y1="38"
                  x2="10"
                  y2="50"
                  stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                  stroke-width="2"
                  stroke-linecap="round"
                />
                <line
                  x1="38"
                  y1="38"
                  x2="50"
                  y2="50"
                  stroke={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'}
                  stroke-width="2"
                  stroke-linecap="round"
                />
                <circle cx="10" cy="10" r="5" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.6" />
                <circle cx="50" cy="10" r="5" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.6" />
                <circle cx="10" cy="50" r="5" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.6" />
                <circle cx="50" cy="50" r="5" fill={calibrating ? 'hsl(211,100%,50%)' : '#6b7280'} opacity="0.6" />
              </svg>
            </div>
            <p class="mt-3 text-[11px] {calibrating ? 'text-primary' : 'text-muted-foreground'}">
              {calibrating ? t('cal.simpleHintActive') : t('cal.simpleHintBefore')}
            </p>
          </div>
        </div>
      {/if}

      <!-- ════════════════════════════════════════════ -->
      <!-- Status messages (shared)                     -->
      <!-- ════════════════════════════════════════════ -->
      <div class="mb-4">
        <p class="text-[11px] text-muted-foreground font-semibold uppercase tracking-wider mb-1.5">
          {t('cal.messages')}
        </p>
        <div class="rounded-lg border border-border bg-muted/30 min-h-[60px] max-h-[120px] overflow-y-auto p-2">
          {#if calEvents.length > 0}
            {#each calEvents as ev (ev.time + ev.text)}
              <div class="flex items-start gap-2 py-0.5">
                <span class="text-[10px] text-muted-foreground font-mono shrink-0">{ev.time}</span>
                <span class="text-xs text-foreground">{ev.text}</span>
              </div>
            {/each}
          {:else}
            <p class="text-xs text-muted-foreground text-center py-3">{t('cal.noMessages')}</p>
          {/if}
        </div>
      </div>

      <!-- Calibrating indicator -->
      {#if calibrating}
        <div class="mb-4 flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/20">
          <div class="w-3 h-3 rounded-full bg-primary animate-pulse shrink-0"></div>
          <span class="text-xs text-primary font-medium">{t('cal.inProgress')}</span>
        </div>
      {/if}

      <!-- Action buttons -->
      <div class="flex gap-2">
        <Button variant="default" class="flex-1" onclick={startCal} disabled={calibrating || !app.drone.connected}>
          {t('cal.start')}
        </Button>
        <Button variant="secondary" class="flex-1" onclick={cancelCal} disabled={!calibrating}>
          {t('cal.cancel')}
        </Button>
      </div>

      {#if !app.drone.connected}
        <p class="mt-2 text-center text-[11px] text-muted-foreground">{t('cal.connectFirst')}</p>
      {/if}
    </div>
  </div>
</div>

<style>
  @keyframes pulse-border {
    0%,
    100% {
      border-color: hsl(211 100% 50% / 0.5);
      box-shadow: 0 0 0 0 hsl(211 100% 50% / 0.3);
    }
    50% {
      border-color: hsl(211 100% 50% / 1);
      box-shadow: 0 0 8px 2px hsl(211 100% 50% / 0.25);
    }
  }
  .cal-active-border {
    animation: pulse-border 1.5s ease-in-out infinite;
  }
  @keyframes spin-slow {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }
  .spin-slow {
    animation: spin-slow 3s linear infinite;
  }
  @keyframes gentle-pulse {
    0%,
    100% {
      opacity: 0.6;
    }
    50% {
      opacity: 1;
    }
  }
  .gentle-pulse {
    animation: gentle-pulse 2s ease-in-out infinite;
  }
</style>
