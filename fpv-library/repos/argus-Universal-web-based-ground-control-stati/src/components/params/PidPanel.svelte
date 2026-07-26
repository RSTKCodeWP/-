<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import { paramState, getParam } from '../../lib/paramStore.svelte';
  import { X, Sliders } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Helpers ── */

  let paramsAvailable = $derived(paramState.list.length > 0);

  /* ── Axis definitions ── */

  type Axis = 'roll' | 'pitch' | 'yaw';

  const axes: { id: Axis; labelKey: string }[] = [
    { id: 'roll',  labelKey: 'pid.roll' },
    { id: 'pitch', labelKey: 'pid.pitch' },
    { id: 'yaw',   labelKey: 'pid.yaw' },
  ];

  const paramPrefix: Record<Axis, string> = {
    roll:  'ATC_RAT_RLL',
    pitch: 'ATC_RAT_PIT',
    yaw:   'ATC_RAT_YAW',
  };

  interface PidSliderDef {
    suffix: string;
    labelKey: string;
    min: number;
    max: number;
    step: number;
  }

  // AC_AttitudeControl rate PID terms — P/I/D/FF per axis
  const pidSliders: PidSliderDef[] = [
    { suffix: '_P',  labelKey: 'pid.rateP',  min: 0, max: 0.5,  step: 0.001 },
    { suffix: '_I',  labelKey: 'pid.rateI',  min: 0, max: 0.5,  step: 0.001 },
    { suffix: '_D',  labelKey: 'pid.rateD',  min: 0, max: 0.05, step: 0.0001 },
    { suffix: '_FF', labelKey: 'pid.rateFF', min: 0, max: 0.5,  step: 0.001 },
  ];

  /* ── State ── */

  let activeTab = $state<Axis>('roll');

  /* PID values keyed by full param name */
  let values = $state<Record<string, number>>({});

  /* ── Load from paramState on mount ── */

  // Audit F-17: load once, don't clobber operator edits mid-stream.
  let _loaded = $state(false);
  $effect(() => {
    if (!paramsAvailable) { _loaded = false; return; }
    if (_loaded) return;
    _loaded = true;
    const v: Record<string, number> = {};
    for (const axis of axes) {
      for (const s of pidSliders) {
        const name = paramPrefix[axis.id] + s.suffix;
        v[name] = getParam(name, 0);
      }
    }
    values = v;
  });

  /* ── Slider change handler — sends param_set immediately ── */

  function onSliderChange(paramName: string, newVal: number) {
    values[paramName] = newVal;
    dispatch('param_set', undefined, { name: paramName, value: newVal });
  }

  /* ── Input field change handler (typed value) ── */

  function onInputChange(paramName: string, raw: string, slider: PidSliderDef) {
    const val = parseFloat(raw);
    if (isNaN(val)) return;
    const clamped = Math.max(slider.min, Math.min(slider.max, val));
    onSliderChange(paramName, clamped);
  }

  /* ── Response curve tracking ── */

  const HISTORY_LEN = 200;
  let responseHistory = $state<{ t: number; actual: number; target: number }[]>([]);
  let responseCanvas: HTMLCanvasElement = $state(null!);
  let showResponse = $state(false);

  $effect(() => {
    if (!showResponse || !app.drone.connected) return;
    const d = app.drone;
    const actual = activeTab === 'roll' ? d.roll : activeTab === 'pitch' ? d.pitch : d.yaw;
    const target = 0;
    responseHistory.push({ t: Date.now(), actual, target });
    if (responseHistory.length > HISTORY_LEN) responseHistory.splice(0, responseHistory.length - HISTORY_LEN);
  });

  $effect(() => {
    if (!responseCanvas || !showResponse || responseHistory.length < 2) return;
    const ctx = responseCanvas.getContext('2d')!;
    const w = responseCanvas.width = responseCanvas.parentElement!.clientWidth;
    const h = responseCanvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);
    const data = responseHistory;
    const vals = data.map(d => d.actual);
    const minV = Math.min(...vals, -10);
    const maxV = Math.max(...vals, 10);
    const range = maxV - minV || 1;
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    const zeroY = h - ((-minV) / range) * (h - 20) - 10;
    ctx.beginPath(); ctx.moveTo(0, zeroY); ctx.lineTo(w, zeroY); ctx.stroke();
    ctx.strokeStyle = '#4fc3f7';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = (i / (HISTORY_LEN - 1)) * w;
      const y = h - ((data[i].actual - minV) / range) * (h - 20) - 10;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = (i / (HISTORY_LEN - 1)) * w;
      const y = h - ((data[i].target - minV) / range) * (h - 20) - 10;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#4fc3f7';
    ctx.font = '9px monospace';
    ctx.fillText(t('pid.actual'), 4, 12);
    ctx.fillStyle = '#555';
    ctx.fillText(t('pid.target'), 4, 24);
    ctx.fillStyle = '#666';
    ctx.fillText(`${vals[vals.length - 1]?.toFixed(1)}°`, w - 40, 12);
  });

  /* ── Save to flash ── */

  function saveToFlash() {
    dispatch('param_save_to_flash');
    addToast(t('pid.saved'), 'success');
  }
</script>

<div role="dialog" aria-modal="true" tabindex="-1" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
     onclick={(e) => { if (e.target === e.currentTarget) onclose(); }} onkeydown={(e) => { if (e.key === "Escape") onclose(); }}>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[500px] max-h-[85vh] flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Sliders size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('pid.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">

      {#if !paramsAvailable}
        <!-- Hint: params not loaded -->
        <div class="p-4 rounded-lg bg-muted/50 border border-border/50 text-center">
          <p class="text-xs text-muted-foreground">{t('pid.hint')}</p>
        </div>
      {:else}

        <!-- Tab selector: Roll / Pitch / Yaw -->
        <div class="flex gap-1.5 mb-4">
          {#each axes as axis (axis.id)}
            <button
              class="flex-1 px-3 py-1.5 text-xs font-semibold rounded-md transition-all
                {activeTab === axis.id
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
              onclick={() => { activeTab = axis.id; }}
            >
              {t(axis.labelKey)}
            </button>
          {/each}
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- PID Sliders for active axis                   -->
        <!-- ════════════════════════════════════════════ -->
        <div class="space-y-4">
          {#each pidSliders as slider (slider.suffix)}
            {@const paramName = paramPrefix[activeTab] + slider.suffix}
            {@const val = values[paramName] ?? 0}
            <div class="rounded-lg border border-border bg-muted/20 p-3">
              <!-- Label row -->
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-semibold text-foreground">{t(slider.labelKey)}</span>
                  <span class="text-[10px] text-muted-foreground font-mono">{paramName}</span>
                </div>
                <input
                  type="number"
                  value={val}
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  class="w-20 h-6 px-1.5 text-right font-mono text-xs bg-input border border-border rounded-md text-foreground
                         focus:outline-none focus:ring-1 focus:ring-ring/50"
                  onchange={(e) => onInputChange(paramName, (e.target as HTMLInputElement).value, slider)}
                />
              </div>
              <!-- Range slider -->
              <div class="flex items-center gap-2">
                <span class="text-[9px] text-muted-foreground font-mono w-8 text-right shrink-0">{slider.min}</span>
                <input
                  type="range"
                  value={val}
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  class="flex-1 h-2 accent-primary cursor-pointer"
                  oninput={(e) => onSliderChange(paramName, parseFloat((e.target as HTMLInputElement).value))}
                />
                <span class="text-[9px] text-muted-foreground font-mono w-8 shrink-0">{slider.max}</span>
              </div>
            </div>
          {/each}
        </div>

        <!-- Response curve -->
        <div class="mt-4">
          <button class="text-[10px] text-muted-foreground hover:text-primary transition-colors cursor-pointer border-none bg-transparent"
                  onclick={() => { showResponse = !showResponse; responseHistory = []; }}>
            {showResponse ? '▼' : '▶'} {t('pid.responseCurve')}
          </button>
          {#if showResponse}
            <div class="mt-2 border border-border rounded-lg overflow-hidden">
              <canvas bind:this={responseCanvas} height="120" class="w-full"></canvas>
            </div>
          {/if}
        </div>

        <!-- Save to Flash button -->
        <div class="flex justify-end pt-4">
          <Button variant="default" size="sm" class="h-8 text-xs px-6" onclick={saveToFlash}
                  disabled={!app.drone.connected}>
            {t('pid.save')}
          </Button>
        </div>

      {/if}
    </div>
  </div>
</div>
