<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { paramState, getParam } from '../../lib/paramStore.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, ShieldAlert, Battery, Radio, Wifi, Navigation } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Helpers ── */

  function saveParams(pairs: [string, number][]) {
    for (const [name, value] of pairs) {
      dispatch('param_set', undefined, { name, value });
    }
    addToast(t('failsafe.saved').replace('{n}', String(pairs.length)), 'success');
  }

  let paramsAvailable = $derived(paramState.list.length > 0);

  /* ── Battery failsafe ── */
  let battEnable  = $state(0);
  let battAction  = $state(0);
  let battVoltage = $state(10.5);
  let battMah     = $state(0);

  /* ── RC Loss ── */
  let rcEnable    = $state(0);
  let rcAction    = $state(0);
  let rcPwm       = $state(975);

  /* ── GCS Loss ── */
  let gcsEnable   = $state(0);
  let gcsAction   = $state(0);

  /* ── EKF/GPS ── */
  let ekfAction   = $state(0);
  let ekfThresh   = $state(0.8);

  /* ── Load from params on mount ── */
  // Audit F-17: a bare $effect over paramsAvailable + getParam re-fired on
  // every PARAM_VALUE arriving during streaming, clobbering any edit the
  // operator had already made. Only seed values once on first load.
  let _loaded = $state(false);
  $effect(() => {
    if (!paramsAvailable) { _loaded = false; return; }
    if (_loaded) return;
    _loaded = true;
    // AP_BattMonitor_Params.cpp: BATT_FS_LOW_ACT is the action (0=warn/disabled).
    // BATT_LOW_VOLT / BATT_LOW_MAH are the trigger thresholds.
    battAction  = getParam('BATT_FS_LOW_ACT', 0);
    battEnable  = battAction > 0 ? 1 : 0;
    battVoltage = getParam('BATT_LOW_VOLT', 10.5);
    battMah     = getParam('BATT_LOW_MAH', 0);

    rcEnable    = getParam('FS_THR_ENABLE', 0);
    // FS_THR_ENABLE is itself the action enum (0=disabled, 1=Always RTL,
    // 2=Continue with Mission, 3=Always Land, 4=SmartRTL or RTL, ...).
    // Use the same value for the action selector; the UI then maps it to
    // a label via rcActions.
    rcAction    = getParam('FS_THR_ENABLE', 0);
    rcPwm       = getParam('FS_THR_VALUE', 975);

    gcsEnable   = getParam('FS_GCS_ENABLE', 0);
    // FS_GCS_ENABLE is the action enum same as FS_THR_ENABLE.
    gcsAction   = getParam('FS_GCS_ENABLE', 0);

    ekfAction   = getParam('FS_EKF_ACTION', 0);
    ekfThresh   = getParam('FS_EKF_THRESH', 0.8);
  });

  /* ── Action option maps ── */
  // AP_BattMonitor_Params.cpp: BATT_FS_LOW_ACT values for Copter:
  // 0=Warn only, 1=Land, 2=RTL, 3=SmartRTL or RTL, 4=SmartRTL or Land, 5=Terminate
  const battActions: [number, string][] = [
    [0, 'failsafe.actionNone'],
    [1, 'failsafe.actionLand'],
    [2, 'failsafe.actionRtl'],
    [3, 'failsafe.actionSmartRtl'],
    [4, 'failsafe.actionSmartRtlLand'],
    [5, 'failsafe.actionTerminate'],
  ];

  // ArduCopter/Parameters.cpp: FS_THR_ENABLE values:
  // 0=Disabled, 1=Always RTL, 2=Continue Mission in Auto, 3=Always Land,
  // 4=SmartRTL or RTL, 5=SmartRTL or Land
  const rcActions: [number, string][] = [
    [0, 'failsafe.actionNone'],
    [1, 'failsafe.actionRtl'],
    [2, 'failsafe.actionContinue'],
    [3, 'failsafe.actionLand'],
    [4, 'failsafe.actionSmartRtl'],
    [5, 'failsafe.actionSmartRtlLand'],
  ];

  // ArduCopter/Parameters.cpp: FS_GCS_ENABLE values:
  // 0=Disabled, 1=Always RTL, 2=Continue Mission in Auto,
  // 3=SmartRTL or RTL, 4=SmartRTL or Land, 5=Always Land
  const gcsActions: [number, string][] = [
    [0, 'failsafe.actionNone'],
    [1, 'failsafe.actionRtl'],
    [2, 'failsafe.actionContinue'],
    [3, 'failsafe.actionSmartRtl'],
    [4, 'failsafe.actionSmartRtlLand'],
    [5, 'failsafe.actionLand'],
  ];

  const ekfActions: [number, string][] = [
    [0, 'failsafe.actionNone'],
    [1, 'failsafe.actionLand'],
    // ArduPilot FS_EKF_ACTION value 2 = AltHold mode
    [2, 'failsafe.actionAltHold'],
  ];

  /* ── Section save handlers ── */
  function saveBattery() {
    // AP_BattMonitor_Params.cpp: BATT_FS_LOW_ACT controls action (0=warn/off).
    // FS_BATT_VOLTAGE and FS_BATT_MAH set the trigger thresholds.
    saveParams([
      ['BATT_FS_LOW_ACT', battEnable ? battAction || 1 : 0],
      ['BATT_LOW_VOLT', battVoltage],
      ['BATT_LOW_MAH', battMah],
    ]);
  }

  function saveRc() {
    saveParams([
      ['FS_THR_ENABLE', rcEnable ? rcAction || 1 : 0],
      ['FS_THR_VALUE', rcPwm],
    ]);
  }

  function saveGcs() {
    saveParams([
      ['FS_GCS_ENABLE', gcsEnable ? gcsAction || 1 : 0],
    ]);
  }

  function saveEkf() {
    saveParams([
      ['FS_EKF_ACTION', ekfAction],
      ['FS_EKF_THRESH', ekfThresh],
    ]);
  }
</script>

<div role="dialog" aria-modal="true" tabindex="-1" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
     onclick={(e) => { if (e.target === e.currentTarget) onclose(); }} onkeydown={(e) => { if (e.key === "Escape") onclose(); }}>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[550px] max-h-[85vh] flex flex-col overflow-hidden">

    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <ShieldAlert size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('failsafe.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">

      {#if !paramsAvailable}
        <!-- Hint: params not loaded -->
        <div class="p-4 rounded-lg bg-muted/50 border border-border/50 text-center">
          <p class="text-xs text-muted-foreground">{t('failsafe.hint')}</p>
        </div>
      {:else}

        <!-- ════════════════════════════════════════════ -->
        <!-- 1. Battery Failsafe                          -->
        <!-- ════════════════════════════════════════════ -->
        <div class="rounded-lg border border-border bg-card overflow-hidden border-l-[3px] border-l-red-500">
          <div class="px-4 py-2.5 flex items-center justify-between bg-muted/30">
            <div class="flex items-center gap-2">
              <Battery size={14} class="text-red-500" />
              <span class="text-xs font-semibold text-foreground uppercase tracking-wider">{t('failsafe.battery')}</span>
            </div>
            <button type="button" role="switch" aria-checked={battEnable > 0}
                    class="relative inline-flex items-center cursor-pointer"
                    onclick={() => { battEnable = battEnable > 0 ? 0 : 1; }}>
              <div class="w-9 h-5 rounded-full transition-colors
                          after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                          after:bg-white after:rounded-full after:h-4 after:w-4
                          after:transition-all {battEnable > 0 ? 'bg-red-500 after:translate-x-full' : 'bg-muted-foreground/30'}"></div>
              <span class="ml-2 text-[11px] text-muted-foreground">
                {battEnable > 0 ? t('failsafe.enable') : t('failsafe.disable')}
              </span>
            </button>
          </div>
          <div class="px-4 py-3 space-y-2.5">
            <div class="flex justify-between items-center">
              <label for="fs-batt-action" class="text-xs text-muted-foreground">{t('failsafe.action')}</label>
              <select id="fs-batt-action" bind:value={battAction}
                      class="w-36 h-7 px-2 bg-input border border-border rounded-md text-xs text-foreground
                             focus:outline-none focus:ring-1 focus:ring-ring/50">
                {#each battActions as [val, key]}
                  <option value={val}>{t(key)}</option>
                {/each}
              </select>
            </div>
            <div class="flex justify-between items-center">
              <label for="fs-batt-volt" class="text-xs text-muted-foreground">{t('failsafe.voltage')}</label>
              <div class="flex items-center gap-1">
                <input id="fs-batt-volt" type="number" bind:value={battVoltage}
                       min="0" max="60" step="0.1"
                       class="w-20 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground
                              focus:outline-none focus:ring-1 focus:ring-ring/50" />
                <span class="text-[11px] text-muted-foreground w-4">V</span>
              </div>
            </div>
            <div class="flex justify-between items-center">
              <label for="fs-batt-mah" class="text-xs text-muted-foreground">{t('failsafe.mah')}</label>
              <div class="flex items-center gap-1">
                <input id="fs-batt-mah" type="number" bind:value={battMah}
                       min="0" max="99999" step="100"
                       class="w-20 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground
                              focus:outline-none focus:ring-1 focus:ring-ring/50" />
                <span class="text-[11px] text-muted-foreground w-8">mAh</span>
              </div>
            </div>
            <div class="flex justify-end pt-1">
              <Button variant="default" size="sm" class="h-7 text-xs px-4" onclick={saveBattery}>
                {t('failsafe.save')}
              </Button>
            </div>
          </div>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- 2. RC Loss                                    -->
        <!-- ════════════════════════════════════════════ -->
        <div class="rounded-lg border border-border bg-card overflow-hidden border-l-[3px] border-l-orange-500">
          <div class="px-4 py-2.5 flex items-center justify-between bg-muted/30">
            <div class="flex items-center gap-2">
              <Radio size={14} class="text-orange-500" />
              <span class="text-xs font-semibold text-foreground uppercase tracking-wider">{t('failsafe.rcLoss')}</span>
            </div>
            <button type="button" role="switch" aria-checked={rcEnable > 0}
                    class="relative inline-flex items-center cursor-pointer"
                    onclick={() => { rcEnable = rcEnable > 0 ? 0 : 1; }}>
              <div class="w-9 h-5 rounded-full transition-colors
                          after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                          after:bg-white after:rounded-full after:h-4 after:w-4
                          after:transition-all {rcEnable > 0 ? 'bg-orange-500 after:translate-x-full' : 'bg-muted-foreground/30'}"></div>
              <span class="ml-2 text-[11px] text-muted-foreground">
                {rcEnable > 0 ? t('failsafe.enable') : t('failsafe.disable')}
              </span>
            </button>
          </div>
          <div class="px-4 py-3 space-y-2.5">
            <div class="flex justify-between items-center">
              <label for="fs-rc-action" class="text-xs text-muted-foreground">{t('failsafe.action')}</label>
              <select id="fs-rc-action" bind:value={rcAction}
                      class="w-36 h-7 px-2 bg-input border border-border rounded-md text-xs text-foreground
                             focus:outline-none focus:ring-1 focus:ring-ring/50">
                {#each rcActions as [val, key]}
                  <option value={val}>{t(key)}</option>
                {/each}
              </select>
            </div>
            <div class="flex justify-between items-center">
              <label for="fs-rc-pwm" class="text-xs text-muted-foreground">{t('failsafe.rcPwm')}</label>
              <div class="flex items-center gap-1">
                <input id="fs-rc-pwm" type="number" bind:value={rcPwm}
                       min="800" max="1200" step="1"
                       class="w-20 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground
                              focus:outline-none focus:ring-1 focus:ring-ring/50" />
                <span class="text-[11px] text-muted-foreground w-8">PWM</span>
              </div>
            </div>
            <div class="flex justify-end pt-1">
              <Button variant="default" size="sm" class="h-7 text-xs px-4" onclick={saveRc}>
                {t('failsafe.save')}
              </Button>
            </div>
          </div>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- 3. GCS Loss                                   -->
        <!-- ════════════════════════════════════════════ -->
        <div class="rounded-lg border border-border bg-card overflow-hidden border-l-[3px] border-l-yellow-500">
          <div class="px-4 py-2.5 flex items-center justify-between bg-muted/30">
            <div class="flex items-center gap-2">
              <Wifi size={14} class="text-yellow-500" />
              <span class="text-xs font-semibold text-foreground uppercase tracking-wider">{t('failsafe.gcsLoss')}</span>
            </div>
            <button type="button" role="switch" aria-checked={gcsEnable > 0}
                    class="relative inline-flex items-center cursor-pointer"
                    onclick={() => { gcsEnable = gcsEnable > 0 ? 0 : 1; }}>
              <div class="w-9 h-5 rounded-full transition-colors
                          after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                          after:bg-white after:rounded-full after:h-4 after:w-4
                          after:transition-all {gcsEnable > 0 ? 'bg-yellow-500 after:translate-x-full' : 'bg-muted-foreground/30'}"></div>
              <span class="ml-2 text-[11px] text-muted-foreground">
                {gcsEnable > 0 ? t('failsafe.enable') : t('failsafe.disable')}
              </span>
            </button>
          </div>
          <div class="px-4 py-3 space-y-2.5">
            <div class="flex justify-between items-center">
              <label for="fs-gcs-action" class="text-xs text-muted-foreground">{t('failsafe.action')}</label>
              <select id="fs-gcs-action" bind:value={gcsAction}
                      class="w-36 h-7 px-2 bg-input border border-border rounded-md text-xs text-foreground
                             focus:outline-none focus:ring-1 focus:ring-ring/50">
                {#each gcsActions as [val, key]}
                  <option value={val}>{t(key)}</option>
                {/each}
              </select>
            </div>
            <div class="flex justify-end pt-1">
              <Button variant="default" size="sm" class="h-7 text-xs px-4" onclick={saveGcs}>
                {t('failsafe.save')}
              </Button>
            </div>
          </div>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- 4. EKF / GPS                                  -->
        <!-- ════════════════════════════════════════════ -->
        <div class="rounded-lg border border-border bg-card overflow-hidden border-l-[3px] border-l-blue-500">
          <div class="px-4 py-2.5 flex items-center justify-between bg-muted/30">
            <div class="flex items-center gap-2">
              <Navigation size={14} class="text-blue-500" />
              <span class="text-xs font-semibold text-foreground uppercase tracking-wider">{t('failsafe.ekf')}</span>
            </div>
            <button type="button" role="switch" aria-checked={ekfAction > 0}
                    class="relative inline-flex items-center cursor-pointer"
                    onclick={() => { ekfAction = ekfAction > 0 ? 0 : 1; }}>
              <div class="w-9 h-5 rounded-full transition-colors
                          after:content-[''] after:absolute after:top-[2px] after:left-[2px]
                          after:bg-white after:rounded-full after:h-4 after:w-4
                          after:transition-all {ekfAction > 0 ? 'bg-blue-500 after:translate-x-full' : 'bg-muted-foreground/30'}"></div>
              <span class="ml-2 text-[11px] text-muted-foreground">
                {ekfAction > 0 ? t('failsafe.enable') : t('failsafe.disable')}
              </span>
            </button>
          </div>
          <div class="px-4 py-3 space-y-2.5">
            <div class="flex justify-between items-center">
              <label for="fs-ekf-action" class="text-xs text-muted-foreground">{t('failsafe.action')}</label>
              <select id="fs-ekf-action" bind:value={ekfAction}
                      class="w-36 h-7 px-2 bg-input border border-border rounded-md text-xs text-foreground
                             focus:outline-none focus:ring-1 focus:ring-ring/50">
                {#each ekfActions as [val, key]}
                  <option value={val}>{t(key)}</option>
                {/each}
              </select>
            </div>
            <div class="flex justify-between items-center">
              <label for="fs-ekf-thresh" class="text-xs text-muted-foreground">{t('failsafe.threshold')}</label>
              <div class="flex items-center gap-1">
                <input id="fs-ekf-thresh" type="number" bind:value={ekfThresh}
                       min="0.1" max="1.0" step="0.05"
                       class="w-20 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground
                              focus:outline-none focus:ring-1 focus:ring-ring/50" />
              </div>
            </div>
            <div class="flex justify-end pt-1">
              <Button variant="default" size="sm" class="h-7 text-xs px-4" onclick={saveEkf}>
                {t('failsafe.save')}
              </Button>
            </div>
          </div>
        </div>

      {/if}
    </div>
  </div>
</div>
