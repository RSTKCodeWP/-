<script lang="ts">
  import { app, saveSettings, isPlane } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { apiUrl } from '../../lib/backend';
  import ConnectionForm from './ConnectionForm.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import Badge from '$lib/components/ui/badge/badge.svelte';
  import { Volume2, VolumeOff, Sun, Moon, Settings, Satellite } from '@lucide/svelte';

  let { toggleTheme, onSettings }: { toggleTheme: () => void; onSettings: () => void } = $props();

  let showVehicles = $state(false);
  let connForm = $state<ConnectionForm>();

  let linkBars = $derived(
    !app.drone.connected || app.drone.link_age < 0
      ? 0
      : app.drone.link_age < 0.5
        ? 4
        : app.drone.link_age < 1
          ? 3
          : app.drone.link_age < 2
            ? 2
            : app.drone.link_age < 3
              ? 1
              : 0,
  );
  let barColor = $derived(linkBars >= 3 ? '#22c55e' : linkBars >= 2 ? '#eab308' : linkBars >= 1 ? '#ef4444' : '#666');

  let prevFrames = $state(0);
  let msgRate = $state(0);
  $effect(() => {
    const timer = setInterval(() => {
      const f = app.drone.frames;
      msgRate = Math.round((f - prevFrames) / 2);
      prevFrames = f;
      if (app.drone.connected) {
        app.linkHistory.push({ t: Date.now(), rate: msgRate, age: app.drone.link_age });
        if (app.linkHistory.length > 120) app.linkHistory.splice(0, app.linkHistory.length - 90);
      }
    }, 2000);
    return () => clearInterval(timer);
  });

  let battColor = $derived(
    app.drone.remaining < 20 ? 'text-destructive' : app.drone.remaining < 40 ? 'text-warning' : 'text-success',
  );

  const EMERGENCY_MODE_IDS = new Set([6, 9, 11, 20, 21]);
  const MANUAL_MODE_IDS_COPTER = new Set([0, 1, 13, 14]);
  const MANUAL_MODE_IDS_PLANE = new Set([0, 2, 4]);
  let modeVariant = $derived.by((): 'default' | 'secondary' | 'destructive' => {
    const m = app.drone.mode_id;
    if (EMERGENCY_MODE_IDS.has(m)) return 'destructive';
    const manualSet = isPlane() ? MANUAL_MODE_IDS_PLANE : MANUAL_MODE_IDS_COPTER;
    if (manualSet.has(m)) return 'secondary';
    return 'default';
  });

  let gpsOk = $derived(app.drone.gps_fix_raw >= 3);
  let gpsVariant = $derived.by((): 'default' | 'secondary' | 'destructive' => {
    if (app.drone.gps_fix_raw >= 6) return 'default';
    if (gpsOk && app.drone.gps_sats >= 10) return 'default';
    if (gpsOk) return 'secondary';
    return 'destructive';
  });

  const EKF_CONST_POS = 128;
  const EKF_UNINITIALIZED = 1024;

  let ekfLevel = $derived.by(() => {
    const f = app.drone.ekf_flags;
    if (f & EKF_CONST_POS || f & EKF_UNINITIALIZED) return 'red';
    const vars = [app.drone.ekf_vel, app.drone.ekf_pos_h, app.drone.ekf_pos_v, app.drone.ekf_compass];
    if (vars.some((v) => v > 0.8)) return 'yellow';
    if (vars.every((v) => v < 0.5)) return 'green';
    return 'yellow';
  });

  let ekfVariant = $derived(
    ekfLevel === 'red'
      ? ('destructive' as const)
      : ekfLevel === 'yellow'
        ? ('secondary' as const)
        : ('default' as const),
  );

  let ekfLabel = $derived(
    ekfLevel === 'red' ? t('status.navError') : ekfLevel === 'yellow' ? t('status.navWarn') : t('status.nav'),
  );

  let ekfTooltip = $derived(
    `${t('ekf.vel')}: ${app.drone.ekf_vel.toFixed(3)}\n${t('ekf.posH')}: ${app.drone.ekf_pos_h.toFixed(3)}\n${t('ekf.posV')}: ${app.drone.ekf_pos_v.toFixed(3)}\n${t('ekf.compass')}: ${app.drone.ekf_compass.toFixed(3)}\nFlags: 0x${app.drone.ekf_flags.toString(16).toUpperCase()}`,
  );

  function fmtBatTime(s: number): string {
    const h = Math.floor(s / 3600),
      m = Math.floor((s % 3600) / 60);
    return h > 0 ? `~${h}h${m}m` : `~${m}m`;
  }

  function downloadLog() {
    window.open(apiUrl('/api/log'), '_blank');
  }
</script>

<header
  class="flex items-center justify-between gap-3 px-3 max-sm:px-1.5 py-1.5 shrink-0 min-w-0 overflow-x-auto scrollbar-hide transition-colors duration-300
  {app.drone.armed ? 'bg-destructive/8 border-b-2 border-destructive/60' : 'bg-card border-b-2 border-border'}"
>
  <div class="flex items-center gap-2">
    <span class="text-sm font-bold text-primary tracking-wider max-sm:hidden">{t('app.name')}</span>
    <ConnectionForm bind:this={connForm} />
  </div>

  <div class="flex items-center gap-2 text-xs max-sm:gap-1 max-sm:text-[10px]">
    {#if app.drone.connected}
      <Badge variant={modeVariant} class="text-xs font-bold">{app.drone.mode}</Badge>
      {#if app.drone.armed}
        <Badge variant="destructive" class="text-[10px] font-bold animate-pulse">{t('status.armed')}</Badge>
      {/if}

      <span
        class="flex items-center gap-0.5"
        title="Link {app.drone.link_age >= 0 ? app.drone.link_age.toFixed(1) + 's' : '---'} · {msgRate} Hz"
        aria-label={t('ui.linkQuality').replace('{rate}', String(msgRate))}
      >
        <svg width="16" height="12" viewBox="0 0 16 12" class="shrink-0">
          <rect x="0" y="9" width="3" height="3" rx="0.5" fill={linkBars >= 1 ? barColor : '#555'} />
          <rect x="4.5" y="6" width="3" height="6" rx="0.5" fill={linkBars >= 2 ? barColor : '#555'} />
          <rect x="9" y="3" width="3" height="9" rx="0.5" fill={linkBars >= 3 ? barColor : '#555'} />
          <rect x="13" y="0" width="3" height="12" rx="0.5" fill={linkBars >= 4 ? barColor : '#555'} />
        </svg>
        {#if app.drone.connected && msgRate > 0}
          <span class="text-[10px] font-mono tabular-nums" style="color:{barColor}">{msgRate}</span>
        {/if}
        {#if app.linkHistory.length > 3}
          {@const pts = app.linkHistory.slice(-20)}
          {@const maxR = Math.max(...pts.map((p) => p.rate), 1)}
          <svg width="30" height="10" viewBox="0 0 30 10" class="shrink-0 opacity-50 max-sm:hidden">
            <polyline
              fill="none"
              stroke={barColor}
              stroke-width="1"
              points={pts.map((p, i) => `${(i / (pts.length - 1)) * 30},${10 - (p.rate / maxR) * 9}`).join(' ')}
            />
          </svg>
        {/if}
      </span>

      <Badge variant={gpsVariant} class="font-mono text-[11px] gap-0.5">
        <Satellite size={11} />{app.drone.gps_fix}
        {app.drone.gps_sats}
      </Badge>

      <Badge variant={ekfVariant} class="text-[11px]" title={ekfTooltip}>
        {#if ekfLevel === 'green'}
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-400 mr-0.5"></span>
        {:else if ekfLevel === 'yellow'}
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-yellow-400 mr-0.5"></span>
        {:else}
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-red-400 mr-0.5 animate-pulse"></span>
        {/if}
        {ekfLabel}
      </Badge>

      <span
        class="{battColor} font-bold tabular-nums flex items-center gap-1"
        title="{app.drone.voltage.toFixed(2)}V | {app.drone.current.toFixed(1)}A"
        aria-label={t('ui.battery')
          .replace('{v}', app.drone.voltage.toFixed(1))
          .replace('{pct}', app.drone.remaining >= 0 ? String(app.drone.remaining) : '--')}
      >
        <svg width="22" height="12" viewBox="0 0 22 12" class="shrink-0">
          <rect x="0.5" y="0.5" width="18" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1" />
          <rect x="19" y="3" width="2.5" height="6" rx="1" fill="currentColor" opacity="0.5" />
          {#if app.drone.remaining >= 0}
            <rect
              x="2"
              y="2"
              width={Math.max(0, Math.min(15, (app.drone.remaining / 100) * 15))}
              height="8"
              rx="1"
              fill={app.drone.remaining < 20 ? '#ef4444' : app.drone.remaining < 40 ? '#eab308' : '#22c55e'}
            />
          {/if}
        </svg>
        {app.drone.voltage.toFixed(1)}V{app.drone.remaining >= 0 ? ' ' + app.drone.remaining + '%' : ''}{app.drone
          .current > 0.1
          ? ' ' + app.drone.current.toFixed(1) + 'A'
          : ''}{app.drone.bat_time > 0 ? ' ' + fmtBatTime(app.drone.bat_time) : ''}
      </span>

      {#if app.drone.fw_version}
        <span class="text-muted-foreground text-[10px] max-sm:hidden">{app.drone.fw_version}</span>
      {/if}
      {#if app.drone.parse_errors > 0}
        <span class="text-[9px] text-destructive/70 font-mono" title={t('tip.parseErrors')}
          >E:{app.drone.parse_errors}</span
        >
      {/if}
      {#if app.drone.vehicles && app.drone.vehicles.length > 0}
        <button
          class="relative cursor-pointer bg-transparent border-none p-0"
          onclick={() => (showVehicles = !showVehicles)}
        >
          <Badge variant="outline" class="text-[9px] font-mono gap-0.5">
            +{app.drone.vehicles.length}
          </Badge>
        </button>
        {#if showVehicles}
          <div
            role="presentation"
            class="absolute top-full right-0 mt-1 bg-card border border-border rounded-lg shadow-xl p-2 z-50 min-w-[200px]"
            onclick={(e) => e.stopPropagation()}
            onkeydown={(e) => e.stopPropagation()}
          >
            {#each app.drone.vehicles as v}
              <div class="flex items-center gap-2 px-2 py-1 text-xs border-b border-border/50 last:border-0">
                <span class="font-mono font-bold text-primary">#{v.sysid}</span>
                <span class={v.armed ? 'text-warning' : 'text-muted-foreground'}
                  >{v.armed ? t('status.armed') : '---'}</span
                >
                <span class="text-muted-foreground ml-auto">{v.alt?.toFixed(0) || 0}m</span>
              </div>
            {/each}
          </div>
        {/if}
      {/if}

      {#if app.drone.log_active}
        <Button variant="outline" size="xs" onclick={downloadLog} class="text-success border-success/50"
          >{t('status.log')}</Button
        >
      {/if}
    {:else}
      {#if connForm?.isTimeout()}
        <span class="text-destructive text-[11px] font-bold">{t('conn.timeout')}</span>
      {:else}
        <span class="text-muted-foreground">{t('conn.disconnected')}</span>
      {/if}
    {/if}
    {#if !app.wsConnected}
      <span class="text-destructive text-[10px] font-bold animate-pulse" title={t('conn.serviceDown')}>
        {t('conn.serviceDown')}
      </span>
    {/if}

    <Button
      variant="ghost"
      size="icon-xs"
      onclick={() => {
        app.audioMuted = !app.audioMuted;
        saveSettings();
      }}
      class={app.audioMuted ? 'opacity-40' : ''}
      title={app.audioMuted ? t('label.unmute') : t('label.mute')}
      aria-label={app.audioMuted ? t('label.unmute') : t('label.mute')}
    >
      {#if app.audioMuted}<VolumeOff size={14} />{:else}<Volume2 size={14} />{/if}
    </Button>
    <Button variant="ghost" size="icon-xs" onclick={toggleTheme} title={t('tip.theme')} aria-label={t('tip.theme')}>
      {#if app.darkTheme}<Sun size={14} />{:else}<Moon size={14} />{/if}
    </Button>
    <Button
      variant="ghost"
      size="icon-xs"
      onclick={onSettings}
      title={t('settings.title')}
      aria-label={t('settings.title')}
    >
      <Settings size={14} />
    </Button>
  </div>
</header>
