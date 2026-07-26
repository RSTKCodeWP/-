<script lang="ts">
  import { onMount } from 'svelte';
  import { connectWs, sendCommand } from './lib/ws';
  import { dispatch } from './lib/transport';
  import { app, loadSettings, saveSettings, isPlane, addToast } from './lib/stores.svelte';
  import { checkAlerts, beep, speak } from './lib/audio';
  import { t, loadLocale, i18nState } from './lib/i18n.svelte';
  import LazyPanelHost from './components/core/LazyPanelHost.svelte';
  import StatusBar from './components/core/StatusBar.svelte';
  import ControlPanel from './components/core/ControlPanel.svelte';
  import MapView from './components/core/MapView.svelte';
  import EventLog from './components/core/EventLog.svelte';
  import ToastContainer from './components/core/ToastContainer.svelte';
  import MissionProgress from './components/mission/MissionProgress.svelte';
  import TelemetryOverlay from './components/telemetry/TelemetryOverlay.svelte';
  import ConfirmDialog from './components/shared/ConfirmDialog.svelte';
  import SlideConfirm from './components/shared/SlideConfirm.svelte';
  import { showConfirm, showSlide, undo } from './lib/stores.svelte';
  import { migrateLocalStorage } from './lib/migrate';
  import { startScheduler } from './lib/scheduler.svelte';
  import { panels } from './lib/panels.svelte';
  import { apiUrl } from './lib/backend';
  import {
    ChevronUp,
    ChevronDown,
    CornerDownLeft,
    Pause,
    HardDrive,
    Wrench,
    Video,
    SlidersHorizontal,
    PanelLeftClose,
    Plane,
    MapPinned,
    Activity,
    Settings2,
    X as XIcon,
    Globe,
  } from '@lucide/svelte';
  import type { Component } from 'svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  type View = 'fly' | 'plan' | 'monitor' | 'params';
  let view = $state<View>('fly');
  let flyEventsOpen = $state(false);
  // Identity-based marker (time|text) survives backend/frontend events-array trim.
  // A length cursor would go stale once `app.events` shrinks via stores.svelte.ts:62.
  let lastSeenKey = $state('');
  let controlsOpen = $state(false);
  let unseenStartIdx = $derived.by(() => {
    if (!lastSeenKey) return 0;
    const idx = app.events.findIndex((e) => `${e.time}|${e.text}` === lastSeenKey);
    return idx < 0 ? 0 : idx + 1;
  });
  let unseenEvents = $derived(Math.max(0, app.events.length - unseenStartIdx));
  const URGENT_TYPES = new Set([
    'rtl',
    'force_disarm',
    'cmd_ack_fail',
    'mission_ack_fail',
    'fence_ack_fail',
    'link_lost',
    'connect_fail',
  ]);
  let hasUrgentEvent = $derived(
    unseenEvents > 0 &&
      app.events.slice(unseenStartIdx).some((e) => URGENT_TYPES.has(e.event_type) || e.text.includes('!!!')),
  );
  function markEventsSeen() {
    const last = app.events[app.events.length - 1];
    lastSeenKey = last ? `${last.time}|${last.text}` : '';
  }
  let showCmdPalette = $state(false);
  const p = panels;

  let Map3DViewModule: Component | null = $state(null);
  let MonitorMods: { Rc: Component; Servo: Component; Vibe: Component; Ekf: Component; Chart: Component } | null =
    $state(null);
  let PlanMods: { Mission: Component; Survey: Component; Fence: Component } | null = $state(null);
  let ParamMod: Component | null = $state(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- dynamic import components have heterogeneous props
  type DynComp = Component<any>;
  let SettingsMod: DynComp | null = $state(null);
  let CmdPaletteMod: DynComp | null = $state(null);
  let FlightSummaryMod: DynComp | null = $state(null);
  let PreflightMod: DynComp | null = $state(null);
  let ReplayMod: DynComp | null = $state(null);
  let LoginMod: DynComp | null = $state(null);
  let authGate = $state(false);

  $effect(() => {
    if (app.mapMode === '3d' && !Map3DViewModule) {
      import('./components/map/Map3DView.svelte')
        .then((m) => (Map3DViewModule = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (view === 'monitor' && !MonitorMods) {
      Promise.all([
        import('./components/telemetry/RcPanel.svelte'),
        import('./components/telemetry/ServoPanel.svelte'),
        import('./components/telemetry/VibrationPanel.svelte'),
        import('./components/telemetry/EkfPanel.svelte'),
        import('./components/core/ChartPanel.svelte'),
      ])
        .then(([rc, servo, vibe, ekf, chart]) => {
          MonitorMods = {
            Rc: rc.default,
            Servo: servo.default,
            Vibe: vibe.default,
            Ekf: ekf.default,
            Chart: chart.default,
          };
        })
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (view === 'plan' && !PlanMods) {
      Promise.all([
        import('./components/mission/MissionPanel.svelte'),
        import('./components/mission/SurveyPanel.svelte'),
        import('./components/mission/FencePanel.svelte'),
      ])
        .then(([mission, survey, fence]) => {
          PlanMods = { Mission: mission.default, Survey: survey.default, Fence: fence.default };
        })
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (view === 'params' && !ParamMod) {
      import('./components/params/ParamPanel.svelte')
        .then((m) => (ParamMod = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (app.showSettings && !SettingsMod) {
      import('./components/shared/SettingsPanel.svelte')
        .then((m) => (SettingsMod = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (showCmdPalette && !CmdPaletteMod) {
      import('./components/shared/CommandPalette.svelte')
        .then((m) => (CmdPaletteMod = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (app.summaryShown && !FlightSummaryMod) {
      import('./components/shared/FlightSummary.svelte')
        .then((m) => (FlightSummaryMod = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (app.drone.connected && !app.drone.armed && !PreflightMod) {
      import('./components/shared/PreflightPanel.svelte')
        .then((m) => (PreflightMod = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });
  $effect(() => {
    if (!app.drone.connected && view === 'fly' && !ReplayMod) {
      import('./components/tools/ReplayPanel.svelte')
        .then((m) => (ReplayMod = m.default))
        .catch(() => addToast(t('error.loadFailed'), 'error'));
    }
  });

  async function checkAuth() {
    try {
      const res = await fetch(apiUrl('/api/auth/status'));
      const data = await res.json();
      if (data.auth_required && !localStorage.getItem('argus_auth_token')) {
        authGate = true;
        import('./components/shared/LoginDialog.svelte').then((m) => (LoginMod = m.default));
        return;
      }
    } catch {
      /* backend down — proceed without auth gate */
    }
    connectWs();
  }

  function onAuthSuccess() {
    authGate = false;
    connectWs();
  }

  onMount(() => {
    migrateLocalStorage();
    loadLocale();
    loadSettings();
    checkAuth();
    startScheduler();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  $effect(() => {
    if (app.darkTheme) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  });

  $effect(() => {
    document.documentElement.dir = i18nState.locale === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.lang = i18nState.locale;
  });

  $effect(() => {
    const d = app.drone;
    checkAlerts(d.connected, d.armed, d.remaining, d.link_age);
    if (d.flight_summary && !app.summaryShown) app.summaryShown = true;
  });

  $effect(() => {
    if (view === 'monitor') app.chartsOpen = true;
  });

  let prevWsConnected = true;
  $effect(() => {
    const ws = app.wsConnected;
    if (!ws && prevWsConnected) {
      beep(150, 1000, 2, 300);
      speak(t('conn.serviceDown'));
    }
    prevWsConnected = ws;
  });

  $effect(() => {
    const d = app.drone;
    if (d.connected) {
      const parts = [d.mode];
      if (d.armed) parts.push(t('label.armed'));
      parts.push(`${d.voltage.toFixed(1)}V`);
      if (d.gps_fix) parts.push(d.gps_fix);
      let warn = '';
      if ((d.remaining >= 0 && d.remaining < 10) || d.ekf_flags & 0x480) warn = '[!!] ';
      else if ((d.remaining >= 0 && d.remaining < 20) || d.link_age > 3) warn = '[!] ';
      document.title = `${warn}Argus — ${parts.join(' | ')}`;
    } else {
      document.title = `${t('app.name')} ${t('welcome.subtitle')}`;
    }
  });

  function onKey(e: KeyboardEvent) {
    if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'SELECT') return;
    const k = e.key.toLowerCase();
    if (k === ' ') {
      e.preventDefault();
      dispatch('mode', isPlane() ? 19 : 5);
    } else if (k === 'r') {
      showConfirm(t('slide.rtl') + '?', true).then((ok) => ok && dispatch('rtl'));
    } else if (k === 'a') {
      showConfirm(t('slide.arm') + '?', true).then((ok) => ok && dispatch('arm'));
    } else if (k === 'd') dispatch('disarm');
    else if (k === 'l') {
      app.darkTheme = !app.darkTheme;
      saveSettings();
    } else if (k === 'm') app.mapExpanded = !app.mapExpanded;
    else if (k === 'f' && !e.ctrlKey) {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen().catch(() => {});
    } else if (k === 'escape') {
      p.close('shortcuts');
    } else if (k === '?' || (k === '/' && e.shiftKey)) {
      p.toggle('shortcuts');
    } else if (k === 'k' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      showCmdPalette = !showCmdPalette;
    } else if (k === 's' && e.ctrlKey) {
      e.preventDefault();
      app.showSettings = !app.showSettings;
    } else if (k === 'z' && e.ctrlKey) {
      e.preventDefault();
      undo();
    } else if (e.ctrlKey && k >= '1' && k <= '4') {
      e.preventDefault();
      const views: View[] = ['fly', 'plan', 'monitor', 'params'];
      view = views[parseInt(k) - 1];
    } else if (k >= '1' && k <= '9') {
      const btns = app.drone.mode_btns;
      const idx = parseInt(k) - 1;
      if (idx < btns.length) dispatch('mode', btns[idx][0]);
    }
  }

  function toggleTheme() {
    app.darkTheme = !app.darkTheme;
    saveSettings();
  }

  const tabKeys: { id: View; key: string; icon: Component }[] = [
    { id: 'fly', key: 'tab.fly', icon: Plane },
    { id: 'plan', key: 'tab.plan', icon: MapPinned },
    { id: 'monitor', key: 'tab.monitor', icon: Activity },
    { id: 'params', key: 'tab.params', icon: Settings2 },
  ];

  let monitorWarn = $derived(
    app.drone.connected &&
      (Math.max(app.drone.vibe[0], app.drone.vibe[1], app.drone.vibe[2]) > 30 ||
        (app.drone.ekf_flags & 0x480) !== 0 ||
        Math.max(app.drone.ekf_vel, app.drone.ekf_pos_h, app.drone.ekf_pos_v, app.drone.ekf_compass) > 0.8),
  );
  let planCount = $derived(app.waypoints.length);
  let paramProgress = $derived(app.drone.param_fetching);
  let isMobile = $state(false);
  onMount(() => {
    const check = () => {
      isMobile = window.innerWidth < 768;
    };
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  });
</script>

<a
  href="#main-content"
  class="sr-only focus:not-sr-only focus:absolute focus:z-[99999] focus:bg-primary focus:text-primary-foreground focus:p-2 focus:rounded-md focus:top-2 focus:left-2"
>
  {t('ui.skipToContent')}
</a>
<div class="flex flex-col h-screen overflow-hidden" role="application">
  <StatusBar {toggleTheme} onSettings={() => (app.showSettings = !app.showSettings)} />

  <nav
    class="flex items-center gap-1 px-3 py-1 bg-card border-b border-border shrink-0 overflow-x-auto scrollbar-hide max-md:hidden"
  >
    {#each tabKeys as tab}
      <button
        class="flex items-center gap-1.5 px-4 max-sm:px-2.5 py-1.5 text-xs font-semibold tracking-wide uppercase rounded-md transition-all
          {view === tab.id
          ? 'bg-primary text-primary-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'}"
        onclick={() => (view = tab.id)}
      >
        <tab.icon size={14} />
        {t(tab.key)}
        {#if tab.id === 'monitor' && monitorWarn && view !== 'monitor'}
          <span class="w-2 h-2 rounded-full bg-destructive animate-pulse"></span>
        {/if}
        {#if tab.id === 'plan' && planCount > 0 && view !== 'plan'}
          <span class="px-1 py-px rounded-full bg-primary/20 text-primary text-[9px] font-bold leading-none"
            >{planCount}</span
          >
        {/if}
        {#if tab.id === 'params' && paramProgress}
          <span class="w-2 h-2 rounded-full bg-warning animate-pulse"></span>
        {/if}
      </button>
    {/each}

    {#if app.drone.connected}
      <div class="ml-auto flex items-center gap-1.5 shrink-0">
        <Button
          size="sm"
          class="bg-red-600 hover:bg-red-700 text-white font-bold gap-1"
          onclick={() => showSlide(t('slide.rtl'), 'red', () => dispatch('rtl'))}
          title="{t('ctrl.rtl')} (R)"
        >
          <CornerDownLeft size={13} />{t('nav.rtl')}
        </Button>
        <Button
          size="sm"
          class="bg-amber-600 hover:bg-amber-700 text-white font-bold gap-1"
          onclick={() => dispatch('mode', isPlane() ? 19 : 5)}
          title="{t('ctrl.pause')} (Space)"
        >
          <Pause size={13} />{t('nav.pause')}
        </Button>
        <Button variant="secondary" size="sm" class="gap-1" onclick={() => p.open('logPanel')} title={t('nav.logs')}>
          <HardDrive size={13} />{t('nav.logs')}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          class="gap-1"
          onclick={() => p.open('calibration')}
          title={t('nav.calibrate')}
        >
          <Wrench size={13} />{t('nav.calibrate')}
        </Button>
        {#if view === 'fly'}
          <Button
            variant={app.mapMode === '3d' ? 'default' : 'secondary'}
            size="sm"
            class="gap-1"
            onclick={() => (app.mapMode = app.mapMode === '3d' ? '2d' : '3d')}
            title={app.mapMode === '3d' ? t('ui.map2d') : t('ui.globe3d')}
          >
            <Globe size={13} />{app.mapMode === '3d' ? '3D' : '2D'}
          </Button>
          <Button
            variant={p.isOpen('video') ? 'default' : 'secondary'}
            size="sm"
            class="gap-1"
            onclick={() => p.toggle('video')}
            title={t('ui.rtspVideo')}
          >
            <Video size={13} />{t('nav.video')}
          </Button>
          <Button
            variant={controlsOpen ? 'default' : 'secondary'}
            size="sm"
            class="gap-1"
            onclick={() => (controlsOpen = !controlsOpen)}
            title={t('nav.controls')}
          >
            {#if controlsOpen}<PanelLeftClose size={13} />{t('nav.collapse')}{:else}<SlidersHorizontal size={13} />{t(
                'nav.controls',
              )}{/if}
          </Button>
        {/if}
      </div>
    {/if}
  </nav>

  <svelte:boundary onerror={(e) => console.error('View render error:', e)}>
    {#snippet failed(error, reset)}
      <div class="flex-1 flex items-center justify-center bg-background">
        <div class="text-center p-6">
          <p class="text-destructive font-bold text-sm">{t('ui.renderError')}</p>
          <p class="text-xs text-muted-foreground mt-1 max-w-xs break-all">
            {error instanceof Error ? error.message : String(error)}
          </p>
          <button class="mt-3 px-3 py-1.5 bg-primary text-primary-foreground text-xs rounded-md" onclick={reset}
            >{t('ui.retry')}</button
          >
        </div>
      </div>
    {/snippet}

    {#if view === 'fly'}
      <div id="main-content" class="flex-1 flex overflow-hidden">
        {#if app.drone.connected && controlsOpen}
          <div class="shrink-0 border-r border-border bg-card z-[1002] overflow-y-auto">
            <ControlPanel />
          </div>
        {/if}
        <div class="flex-1 relative min-h-0 flex flex-col min-w-0">
          {#if app.mapMode === '3d' && Map3DViewModule}
            <Map3DViewModule />
          {:else}
            <MapView />
          {/if}
          {#if app.drone.connected}
            <TelemetryOverlay />
          {:else}
            <div class="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[1001] pointer-events-none">
              <div
                class="bg-card/90 backdrop-blur-md border border-border rounded-2xl shadow-2xl px-8 py-6 text-center min-w-[280px]"
              >
                <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/15 mb-3">
                  <svg
                    viewBox="0 0 24 24"
                    width="28"
                    height="28"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.5"
                    class="text-primary"
                  >
                    <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                  </svg>
                </div>
                <h2 class="text-lg font-bold text-primary tracking-wide">{t('app.name')}</h2>
                <p class="text-xs text-muted-foreground mt-1">{t('welcome.subtitle')}</p>
                <div class="mt-4 pt-3 border-t border-border/50">
                  <p class="text-xs text-muted-foreground">{t('welcome.hint')}</p>
                  <div class="flex items-center justify-center gap-3 mt-2 text-[11px] text-muted-foreground/70">
                    <span
                      ><kbd class="px-1 py-px bg-muted border border-border rounded text-[10px] font-mono">Ctrl+K</kbd>
                      {t('cmd.openPalette')}</span
                    >
                    <span
                      ><kbd class="px-1 py-px bg-muted border border-border rounded text-[10px] font-mono">?</kbd>
                      {t('welcome.shortcuts')}</span
                    >
                    <span
                      ><kbd class="px-1 py-px bg-muted border border-border rounded text-[10px] font-mono">Ctrl+S</kbd>
                      {t('welcome.settings')}</span
                    >
                  </div>
                </div>
                {#if !app.wsConnected}
                  <div class="mt-3 text-destructive text-[11px] font-bold animate-pulse">
                    {t('welcome.backendDown')}
                  </div>
                {/if}
              </div>
            </div>
          {/if}
          <MissionProgress />
          {#if app.drone.connected && !app.drone.armed && PreflightMod}
            <div
              class="absolute bottom-12 right-3 z-[1001] w-[400px] max-h-56 overflow-auto bg-popover/95 backdrop-blur border border-border rounded-xl shadow-lg"
            >
              <PreflightMod />
            </div>
          {/if}
          <div class="absolute bottom-0 left-0 right-0 z-[1001]" class:max-h-52={flyEventsOpen}>
            <button
              class="w-full backdrop-blur flex items-center justify-center gap-1 py-1 text-[11px] cursor-pointer border-t hover:text-primary transition-colors
            {hasUrgentEvent
                ? 'bg-destructive/15 border-destructive/40 text-destructive animate-pulse'
                : 'bg-card/90 border-border text-muted-foreground'}"
              onclick={() => {
                flyEventsOpen = !flyEventsOpen;
                if (flyEventsOpen) markEventsSeen();
              }}
            >
              {t('event.title')} ({app.events.length})
              {#if unseenEvents > 0 && !flyEventsOpen}
                <span
                  class="px-1.5 py-px rounded-full text-[10px] font-bold {hasUrgentEvent
                    ? 'bg-destructive text-white'
                    : 'bg-primary text-primary-foreground'}">{unseenEvents}</span
                >
              {/if}
              {#if flyEventsOpen}<ChevronDown size={12} />{:else}<ChevronUp size={12} />{/if}
            </button>
            {#if flyEventsOpen}
              <EventLog />
            {/if}
          </div>
        </div>
      </div>
    {:else if view === 'plan'}
      {#if PlanMods}
        <div class="flex-1 flex flex-col overflow-auto">
          <div class="flex max-md:flex-col gap-2 p-2 flex-1 min-h-72">
            <MapView showHud={false} />
            <PlanMods.Mission />
          </div>
          {#if app.showSurvey}<PlanMods.Survey />{/if}
          {#if app.showFence}<PlanMods.Fence />{/if}
        </div>
      {/if}
    {:else if view === 'monitor'}
      {#if MonitorMods}
        <div class="flex-1 overflow-auto p-3">
          <div class="grid grid-cols-3 gap-3 max-lg:grid-cols-2 max-sm:grid-cols-1">
            <MonitorMods.Rc />
            <MonitorMods.Servo />
            <MonitorMods.Vibe />
            <MonitorMods.Ekf />
            <div class="max-lg:col-span-2 max-md:col-span-1 col-span-2">
              <MonitorMods.Chart />
            </div>
          </div>
        </div>
      {/if}
    {:else if view === 'params'}
      {#if ParamMod}
        <div class="flex-1 flex flex-col overflow-hidden p-3">
          <ParamMod />
        </div>
      {/if}
    {/if}

    {#if !app.drone.connected && view === 'fly' && ReplayMod}
      <ReplayMod onposition={(lat: number, lon: number, yaw: number) => (app.replayPos = { lat, lon, yaw })} />
    {/if}
  </svelte:boundary>

  <ToastContainer />
  {#if app.summaryShown && app.drone.flight_summary && FlightSummaryMod}
    <FlightSummaryMod
      summary={app.drone.flight_summary}
      onclose={() => {
        app.summaryShown = false;
        sendCommand('clear_summary');
      }}
    />
  {/if}
  {#if app.showSettings && SettingsMod}
    <SettingsMod onclose={() => (app.showSettings = false)} />
  {/if}
  <ConfirmDialog />
  <SlideConfirm />
  {#if showCmdPalette && CmdPaletteMod}
    <CmdPaletteMod
      onclose={() => (showCmdPalette = false)}
      onnavigate={(v: string) => {
        view = v as View;
        showCmdPalette = false;
      }}
    />
  {/if}
  <LazyPanelHost />
  {#if authGate && LoginMod}
    <LoginMod onlogin={onAuthSuccess} />
  {/if}
  {#if p.isOpen('shortcuts')}
    <div
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
      role="button"
      tabindex="-1"
      onclick={() => p.close('shortcuts')}
      onkeydown={(e) => {
        if (e.key === 'Escape') p.close('shortcuts');
      }}
    >
      <div
        class="bg-card border border-border rounded-xl shadow-2xl p-5 w-[380px]"
        role="presentation"
        onclick={(e) => e.stopPropagation()}
      >
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('shortcuts.title')}</h2>
          <Button variant="ghost" size="icon-xs" onclick={() => p.close('shortcuts')}>
            <XIcon size={16} />
          </Button>
        </div>
        <div class="space-y-1 text-xs">
          {#each [['Space', t('shortcut.hold')], ['R', t('shortcut.rtl')], ['A', t('shortcut.arm')], ['D', t('shortcut.disarm')], ['1-9', t('shortcut.modes')], ['Ctrl+1~4', t('shortcut.views')], ['M', t('shortcut.mapExpand')], ['G', t('shortcut.guided')], ['F', t('shortcut.fullscreen')], ['L', t('shortcut.theme')], ['Ctrl+Z', t('shortcut.undo')], ['Ctrl+S', t('shortcut.settings')], ['?', t('shortcut.showPanel')], ['Ctrl+K', t('cmd.openPalette')], ['Esc', t('shortcut.close')]] as [key, desc]}
            <div class="flex items-center gap-3 py-1 border-b border-border/50">
              <kbd
                class="min-w-[60px] px-2 py-0.5 bg-muted border border-border rounded text-[11px] font-mono font-bold text-center"
                >{key}</kbd
              >
              <span class="text-muted-foreground">{desc}</span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  {/if}

  <!-- Mobile bottom navigation -->
  {#if isMobile}
    <nav
      class="md:hidden fixed bottom-0 left-0 right-0 z-[2000] bg-card border-t border-border flex items-center justify-around py-1.5 safe-area-bottom"
    >
      {#each tabKeys as tab}
        <button
          class="flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-all min-w-[56px]
          {view === tab.id ? 'text-primary' : 'text-muted-foreground'}"
          onclick={() => (view = tab.id)}
        >
          <tab.icon size={20} />
          <span class="text-[9px] font-semibold">{t(tab.key)}</span>
        </button>
      {/each}
    </nav>
  {/if}
</div>
