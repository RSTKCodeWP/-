<script lang="ts">
  import { app, pushUndo, saveWaypoints, addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  type CmdType = 'servo' | 'roi' | 'cam_trig' | 'delay' | 'yaw' | 'vtol_transition';

  const cmdDefs: { id: CmdType; labelKey: string; code: number }[] = [
    { id: 'servo', labelKey: 'advcmd.servo', code: 183 },
    { id: 'roi', labelKey: 'advcmd.roi', code: 201 },
    { id: 'cam_trig', labelKey: 'advcmd.camTrig', code: 206 },
    { id: 'delay', labelKey: 'advcmd.delay', code: 112 },
    { id: 'yaw', labelKey: 'advcmd.yaw', code: 115 },
    { id: 'vtol_transition', labelKey: 'advcmd.vtolTransition', code: 3000 },
  ];

  let selected = $state<CmdType>('servo');
  let insertAfter = $state(0);

  /* ── Per-command fields ── */
  let servoNum = $state(1);
  let servoPwm = $state(1500);
  let roiLat = $state(0);
  let roiLon = $state(0);
  let roiAlt = $state(30);
  let camDist = $state(10);
  let delaySec = $state(5);
  let yawDeg = $state(0);
  let yawDir = $state<'cw' | 'ccw'>('cw');
  let vtolMode = $state<'hover' | 'plane'>('plane');

  function insert() {
    if (app.waypoints.length === 0) {
      addToast(t('wp.clickToAdd'), 'warn');
      return;
    }

    const idx = Math.min(insertAfter, app.waypoints.length - 1);
    const targetWp = app.waypoints[idx];

    pushUndo();

    const cmd = cmdDefs.find((c) => c.id === selected)!;

    if (selected === 'servo') {
      targetWp.cmd_servo = { num: servoNum, pwm: servoPwm };
    } else if (selected === 'roi') {
      targetWp.cmd_roi = { lat: roiLat, lon: roiLon, alt: roiAlt };
    } else if (selected === 'cam_trig') {
      targetWp.cmd_cam_trig = { dist: camDist };
    } else if (selected === 'delay') {
      targetWp.delay = delaySec;
    } else if (selected === 'yaw') {
      targetWp.cmd_yaw = { deg: yawDeg, dir: yawDir === 'cw' ? 1 : -1 };
    } else if (selected === 'vtol_transition') {
      targetWp.cmd_vtol = { mode: vtolMode === 'hover' ? 4 : 3 };
    }

    saveWaypoints();
    addToast(`${t(cmd.labelKey)} (${cmd.code}) -> WP #${idx + 1}`, 'success');
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
      <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('advcmd.title')}</h2>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      <!-- Command type selector -->
      <div class="flex flex-wrap gap-1.5 mb-4">
        {#each cmdDefs as cmd (cmd.id)}
          <button
            class="px-3 py-1.5 text-xs font-semibold rounded-md transition-all
              {selected === cmd.id
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
            onclick={() => {
              selected = cmd.id;
            }}
          >
            {t(cmd.labelKey)}
          </button>
        {/each}
      </div>

      <!-- Command-specific form -->
      <div class="rounded-lg border border-border bg-muted/30 p-3 mb-4">
        {#if selected === 'servo'}
          <div class="flex flex-col gap-2.5">
            <div class="flex items-center gap-2">
              <label for="ac-servo-num" class="text-xs text-muted-foreground w-20 shrink-0"
                >{t('advcmd.servoNum')}</label
              >
              <input
                id="ac-servo-num"
                type="number"
                min="1"
                max="16"
                step="1"
                bind:value={servoNum}
                class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
              />
              <span class="text-[10px] text-muted-foreground">1-16</span>
            </div>
            <div class="flex items-center gap-2">
              <label for="ac-servo-pwm" class="text-xs text-muted-foreground w-20 shrink-0"
                >{t('advcmd.servoPwm')}</label
              >
              <input
                id="ac-servo-pwm"
                type="number"
                min="500"
                max="2500"
                step="10"
                bind:value={servoPwm}
                class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
              />
              <input type="range" min="500" max="2500" step="10" bind:value={servoPwm} class="flex-1 accent-primary" />
              <span class="text-[10px] text-muted-foreground min-w-[40px] text-right">{servoPwm}</span>
            </div>
          </div>
        {:else if selected === 'roi'}
          <div class="flex flex-col gap-2.5">
            <div class="flex items-center gap-2">
              <label for="ac-roi-lat" class="text-xs text-muted-foreground w-20 shrink-0">{t('advcmd.roiLat')}</label>
              <input
                id="ac-roi-lat"
                type="number"
                step="0.00001"
                bind:value={roiLat}
                class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
              />
            </div>
            <div class="flex items-center gap-2">
              <label for="ac-roi-lon" class="text-xs text-muted-foreground w-20 shrink-0">{t('advcmd.roiLon')}</label>
              <input
                id="ac-roi-lon"
                type="number"
                step="0.00001"
                bind:value={roiLon}
                class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
              />
            </div>
            <div class="flex items-center gap-2">
              <label for="ac-roi-alt" class="text-xs text-muted-foreground w-20 shrink-0">{t('telem.alt')}</label>
              <input
                id="ac-roi-alt"
                type="number"
                min="0"
                max="500"
                step="1"
                bind:value={roiAlt}
                class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
              />
              <span class="text-[10px] text-muted-foreground">m</span>
            </div>
          </div>
        {:else if selected === 'cam_trig'}
          <div class="flex items-center gap-2">
            <label for="ac-cam-dist" class="text-xs text-muted-foreground w-20 shrink-0">{t('advcmd.camDist')}</label>
            <input
              id="ac-cam-dist"
              type="number"
              min="0"
              max="1000"
              step="1"
              bind:value={camDist}
              class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
            />
            <span class="text-[10px] text-muted-foreground">m (0 = {t('failsafe.disable')})</span>
          </div>
        {:else if selected === 'delay'}
          <div class="flex items-center gap-2">
            <label for="ac-delay" class="text-xs text-muted-foreground w-20 shrink-0">{t('advcmd.delaySec')}</label>
            <input
              id="ac-delay"
              type="number"
              min="0"
              max="600"
              step="1"
              bind:value={delaySec}
              class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
            />
            <input type="range" min="0" max="60" step="1" bind:value={delaySec} class="flex-1 accent-primary" />
            <span class="text-[10px] text-muted-foreground min-w-[30px] text-right">{delaySec}s</span>
          </div>
        {:else if selected === 'yaw'}
          <div class="flex flex-col gap-2.5">
            <div class="flex items-center gap-2">
              <label for="ac-yaw-deg" class="text-xs text-muted-foreground w-20 shrink-0">{t('advcmd.yawDeg')}</label>
              <input
                id="ac-yaw-deg"
                type="number"
                min="0"
                max="360"
                step="1"
                bind:value={yawDeg}
                class="w-20 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
              />
              <input type="range" min="0" max="360" step="5" bind:value={yawDeg} class="flex-1 accent-primary" />
              <span class="text-[10px] text-muted-foreground min-w-[30px] text-right">{yawDeg}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-muted-foreground w-20 shrink-0">{t('rc.yaw')}</span>
              <button
                class="px-3 py-1 text-xs rounded-md transition-all
                  {yawDir === 'cw'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
                onclick={() => (yawDir = 'cw')}>{t('label.cw')}</button
              >
              <button
                class="px-3 py-1 text-xs rounded-md transition-all
                  {yawDir === 'ccw'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
                onclick={() => (yawDir = 'ccw')}>{t('label.ccw')}</button
              >
            </div>
          </div>
        {:else if selected === 'vtol_transition'}
          <div class="flex items-center gap-2">
            <span class="text-xs text-muted-foreground w-20 shrink-0">{t('advcmd.vtolTransition')}</span>
            <button
              class="px-3 py-1.5 text-xs font-semibold rounded-md transition-all
                {vtolMode === 'hover'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
              onclick={() => (vtolMode = 'hover')}>{t('label.hover')}</button
            >
            <button
              class="px-3 py-1.5 text-xs font-semibold rounded-md transition-all
                {vtolMode === 'plane'
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground hover:bg-muted'}"
              onclick={() => (vtolMode = 'plane')}>{t('label.plane')}</button
            >
          </div>
        {/if}
      </div>

      <!-- Insert position -->
      <div class="flex items-center gap-2 mb-4">
        <label for="ac-insert-after" class="text-xs text-muted-foreground shrink-0">{t('advcmd.insert')} #</label>
        <select
          id="ac-insert-after"
          bind:value={insertAfter}
          class="flex-1 h-7 px-2 bg-input border border-border rounded-md text-xs text-foreground
                       focus:outline-none focus:ring-1 focus:ring-ring/50"
        >
          {#each app.waypoints as wp, i}
            <option value={i}>WP {i + 1} ({wp.lat.toFixed(5)}, {wp.lon.toFixed(5)}, {wp.alt}m)</option>
          {/each}
          {#if app.waypoints.length === 0}
            <option value={0}>--</option>
          {/if}
        </select>
      </div>

      <!-- Insert button -->
      <Button variant="default" class="w-full" onclick={insert} disabled={app.waypoints.length === 0}>
        {t('advcmd.insert')}
      </Button>

      {#if app.waypoints.length === 0}
        <p class="mt-2 text-center text-[11px] text-muted-foreground">{t('wp.clickToAdd')}</p>
      {/if}
    </div>
  </div>
</div>
