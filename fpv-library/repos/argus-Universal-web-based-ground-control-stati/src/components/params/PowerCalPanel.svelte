<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { getParam } from '../../lib/paramStore.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Battery, Zap } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  function writeParam(name: string, value: number) {
    dispatch('param_set', undefined, { name, value });
    addToast(t('power.saved'), 'success');
  }

  /* ── State ── */
  let measuredVoltage = $state('');
  let calculatedMult = $state<number | null>(null);
  let manualAmpPerVlt = $state('');
  let selectedCells = $state(0);

  /* ── Derived values ── */
  let voltMult = $derived(getParam('BATT_VOLT_MULT', 0));
  let ampPerVlt = $derived(getParam('BATT_AMP_PERVLT', 0));
  let nCells = $derived(getParam('BATT_N_CELLS', 0));
  let connected = $derived(app.drone.connected);

  /* ── Actions ── */
  function autoCalcVolt() {
    const measured = parseFloat(measuredVoltage);
    if (!measured || measured <= 0 || app.drone.voltage <= 0) return;
    calculatedMult = voltMult * (measured / app.drone.voltage);
  }

  function writeVoltMult() {
    if (calculatedMult !== null && calculatedMult > 0) {
      writeParam('BATT_VOLT_MULT', calculatedMult);
      calculatedMult = null;
      measuredVoltage = '';
    }
  }

  function writeAmpPerVlt() {
    const val = parseFloat(manualAmpPerVlt);
    if (!val || val <= 0) return;
    writeParam('BATT_AMP_PERVLT', val);
    manualAmpPerVlt = '';
  }

  function writeCells() {
    if (selectedCells >= 1 && selectedCells <= 14) {
      writeParam('BATT_N_CELLS', selectedCells);
    }
  }
</script>

<div role="dialog" aria-modal="true" tabindex="-1" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
     onclick={(e) => { if (e.target === e.currentTarget) onclose(); }} onkeydown={(e) => { if (e.key === "Escape") onclose(); }}>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[450px] max-h-[85vh] flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Battery size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('power.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">

      <!-- ════════════════════════════════════════════ -->
      <!-- Current Readings                             -->
      <!-- ════════════════════════════════════════════ -->
      <div class="rounded-lg border border-border/50 bg-muted/20 p-3">
        <p class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">{t('power.hint')}</p>
        <div class="grid grid-cols-3 gap-3">
          <div class="text-center">
            <Zap size={14} class="mx-auto mb-1 text-yellow-500" />
            <p class="text-lg font-mono font-bold text-foreground">{app.drone.voltage.toFixed(2)}</p>
            <p class="text-[10px] text-muted-foreground">V</p>
          </div>
          <div class="text-center">
            <Zap size={14} class="mx-auto mb-1 text-orange-400" />
            <p class="text-lg font-mono font-bold text-foreground">{app.drone.current.toFixed(1)}</p>
            <p class="text-[10px] text-muted-foreground">A</p>
          </div>
          <div class="text-center">
            <Battery size={14} class="mx-auto mb-1 {app.drone.remaining > 20 ? 'text-green-400' : 'text-red-400'}" />
            <p class="text-lg font-mono font-bold text-foreground">{app.drone.remaining >= 0 ? app.drone.remaining : '--'}</p>
            <p class="text-[10px] text-muted-foreground">%</p>
          </div>
        </div>
      </div>

      <!-- ════════════════════════════════════════════ -->
      <!-- Voltage Calibration                          -->
      <!-- ════════════════════════════════════════════ -->
      <div class="rounded-lg border border-green-500/30 bg-green-500/5 p-3">
        <p class="text-xs font-semibold text-foreground mb-2">{t('power.voltMult')}</p>

        <!-- Current multiplier -->
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] text-muted-foreground">BATT_VOLT_MULT</span>
          <span class="text-xs font-mono font-bold text-green-400">{voltMult.toFixed(4)}</span>
        </div>

        <!-- Measured voltage input + auto calc -->
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <label for="power-measured-volt" class="text-[11px] text-muted-foreground w-24 shrink-0">{t('power.measured')}</label>
            <input
              id="power-measured-volt"
              type="number"
              step="0.01"
              min="0"
              bind:value={measuredVoltage}
              placeholder="0.00"
              class="flex-1 h-7 px-2 text-xs font-mono rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <Button variant="secondary" size="xs" onclick={autoCalcVolt}
                    disabled={!measuredVoltage || app.drone.voltage <= 0}>
              {t('power.calculate')}
            </Button>
          </div>

          {#if calculatedMult !== null}
            <div class="flex items-center justify-between p-2 rounded-md bg-green-500/10 border border-green-500/20">
              <span class="text-[11px] text-muted-foreground">New BATT_VOLT_MULT</span>
              <span class="text-xs font-mono font-bold text-green-400">{calculatedMult.toFixed(4)}</span>
            </div>
            <Button variant="default" size="xs" class="w-full" onclick={writeVoltMult}>
              {t('power.voltMult')} &rarr; {t('power.write')}
            </Button>
          {/if}
        </div>
      </div>

      <!-- ════════════════════════════════════════════ -->
      <!-- Current Calibration                          -->
      <!-- ════════════════════════════════════════════ -->
      <div class="rounded-lg border border-border/50 bg-muted/20 p-3">
        <p class="text-xs font-semibold text-foreground mb-2">{t('power.ampPerVolt')}</p>

        <!-- Current value -->
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] text-muted-foreground">BATT_AMP_PERVLT</span>
          <span class="text-xs font-mono font-bold text-foreground">{ampPerVlt.toFixed(2)}</span>
        </div>

        <!-- Manual input -->
        <div class="flex items-center gap-2">
          <label for="power-amp-pervlt" class="text-[11px] text-muted-foreground w-24 shrink-0">{t('power.ampPerVolt')}</label>
          <input
            id="power-amp-pervlt"
            type="number"
            step="0.1"
            min="0"
            bind:value={manualAmpPerVlt}
            placeholder={ampPerVlt.toFixed(2)}
            class="flex-1 h-7 px-2 text-xs font-mono rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <Button variant="secondary" size="xs" onclick={writeAmpPerVlt}
                  disabled={!manualAmpPerVlt}>
            {t('power.write')}
          </Button>
        </div>
      </div>

      <!-- ════════════════════════════════════════════ -->
      <!-- Cell Count                                   -->
      <!-- ════════════════════════════════════════════ -->
      <div class="rounded-lg border border-border/50 bg-muted/20 p-3">
        <p class="text-xs font-semibold text-foreground mb-2">{t('power.cells')}</p>

        <!-- Current value -->
        <div class="flex items-center justify-between mb-2">
          <span class="text-[11px] text-muted-foreground">BATT_N_CELLS</span>
          <span class="text-xs font-mono font-bold text-foreground">{nCells}</span>
        </div>

        <!-- Dropdown -->
        <div class="flex items-center gap-2">
          <select
            bind:value={selectedCells}
            class="flex-1 h-7 px-2 text-xs font-mono rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value={0} disabled>--</option>
            {#each Array(14) as _, i}
              <option value={i + 1}>{i + 1}S</option>
            {/each}
          </select>
          <Button variant="secondary" size="xs" onclick={writeCells}
                  disabled={selectedCells < 1}>
            {t('power.write')}
          </Button>
        </div>
      </div>

      {#if !connected}
        <p class="text-center text-[11px] text-muted-foreground">{t('cal.connectFirst')}</p>
      {/if}
    </div>
  </div>
</div>
