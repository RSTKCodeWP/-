<script lang="ts">
  import { app, loadDownloadedMission, addToast } from '../../lib/stores.svelte';
  import { sendCommand, sendDisconnect } from '../../lib/ws';
  import {
    isSerialConnected,
    serialDownloadMission,
    dispatch,
  } from '../../lib/transport';
  import { t, i18nState, setLocale } from '../../lib/i18n.svelte';
  import { isPlane, saveSettings, showSlide, showConfirm } from '../../lib/stores.svelte';
  import { paramState } from '../../lib/paramStore.svelte';
  import type { Component } from 'svelte';
  import {
    Plane,
    MapPinned,
    Activity,
    Settings2,
    Radio,
    Wrench,
    Terminal,
    Search,
    Zap,
    CornerDownLeft,
    Play,
    Pause,
    ShieldAlert,
    Upload,
    Download,
    Trash2,
    Sun,
    Moon,
    Volume2,
    VolumeOff,
    Globe,
    Mic,
    MicOff,
    HardDrive,
    Video,
    RotateCcw,
    Power,
    Gauge,
    Navigation,
    Compass,
    ChevronRight,
  } from '@lucide/svelte';

  import { panels, type PanelId } from '../../lib/panels.svelte';

  let { onclose, onnavigate }: { onclose: () => void; onnavigate: (v: 'fly' | 'plan' | 'monitor' | 'params') => void } =
    $props();

  function openPanel(id: PanelId) {
    panels.open(id);
  }

  interface PaletteItem {
    id: string;
    label: string;
    category: string;
    shortcut?: string;
    icon: Component;
    handler: () => void;
    available: boolean;
  }

  let query = $state('');
  let selectedIdx = $state(0);
  let inputEl = $state<HTMLInputElement>(null!);

  $effect(() => {
    inputEl?.focus();
  });

  const d = app.drone;
  const connected = $derived(d.connected);

  let items = $derived.by((): PaletteItem[] => {
    const all: PaletteItem[] = [
      {
        id: 'nav-fly',
        label: t('tab.fly'),
        category: t('cmd.catNav'),
        shortcut: 'Ctrl+1',
        icon: Plane,
        handler: () => onnavigate('fly'),
        available: true,
      },
      {
        id: 'nav-plan',
        label: t('tab.plan'),
        category: t('cmd.catNav'),
        shortcut: 'Ctrl+2',
        icon: MapPinned,
        handler: () => onnavigate('plan'),
        available: true,
      },
      {
        id: 'nav-monitor',
        label: t('tab.monitor'),
        category: t('cmd.catNav'),
        shortcut: 'Ctrl+3',
        icon: Activity,
        handler: () => onnavigate('monitor'),
        available: true,
      },
      {
        id: 'nav-params',
        label: t('tab.params'),
        category: t('cmd.catNav'),
        shortcut: 'Ctrl+4',
        icon: Settings2,
        handler: () => onnavigate('params'),
        available: true,
      },

      {
        id: 'cmd-arm',
        label: t('ctrl.arm'),
        category: t('cmd.catFlight'),
        shortcut: 'A',
        icon: Zap,
        handler: () => showSlide(t('slide.arm'), 'orange', () => dispatch('arm')),
        available: connected && !d.armed,
      },
      {
        id: 'cmd-disarm',
        label: t('ctrl.disarm'),
        category: t('cmd.catFlight'),
        shortcut: 'D',
        icon: Zap,
        handler: () => dispatch('disarm'),
        available: connected && d.armed,
      },
      {
        id: 'cmd-force-disarm',
        label: t('ctrl.forceDisarm'),
        category: t('cmd.catFlight'),
        icon: ShieldAlert,
        handler: () => showSlide(t('slide.forceDisarm'), 'red', () => dispatch('force_disarm')),
        available: connected && d.armed,
      },
      {
        id: 'cmd-takeoff',
        label: t('ctrl.takeoff'),
        category: t('cmd.catFlight'),
        icon: Play,
        handler: () =>
          showSlide(`${t('slide.takeoff')} ${app.defaultAlt}m`, 'teal', () =>
            dispatch('takeoff', undefined, { alt: app.defaultAlt }),
          ),
        available: connected && d.armed,
      },
      {
        id: 'cmd-rtl',
        label: t('ctrl.rtl'),
        category: t('cmd.catFlight'),
        shortcut: 'R',
        icon: CornerDownLeft,
        handler: () => showSlide(t('slide.rtl'), 'red', () => dispatch('rtl')),
        available: connected,
      },
      {
        id: 'cmd-pause',
        label: t('ctrl.pause'),
        category: t('cmd.catFlight'),
        shortcut: 'Space',
        icon: Pause,
        handler: () => dispatch('mode', isPlane() ? 19 : 5),
        available: connected,
      },
      {
        id: 'cmd-mission-start',
        label: t('ctrl.startMission'),
        category: t('cmd.catFlight'),
        icon: Play,
        handler: () => showSlide(t('slide.mission'), 'blue', () => dispatch('mission_start')),
        available: connected,
      },
      {
        id: 'cmd-land',
        label: t('ctrl.land'),
        category: t('cmd.catFlight'),
        icon: Download,
        handler: () => dispatch('mode', isPlane() ? 20 : 9),
        available: connected && d.armed,
      },

      {
        id: 'mission-upload',
        label: t('wp.upload'),
        category: t('ctrl.mission'),
        icon: Upload,
        handler: () => onnavigate('plan'),
        available: true,
      },
      {
        id: 'mission-download',
        label: t('ctrl.downloadMission'),
        category: t('ctrl.mission'),
        icon: Download,
        handler: () => {
          if (isSerialConnected()) {
            serialDownloadMission().then((res) => {
              if (res.ok && res.waypoints) {
                loadDownloadedMission(res.waypoints);
                addToast(`${t('ctrl.downloadMission')}: ${res.waypoints.length}`, 'success', 3000);
              } else if (!res.ok) {
                addToast(`${t('ctrl.downloadMission')}: ${res.error}`, 'error', 4000);
              }
            });
          } else {
            sendCommand('mission_download');
          }
        },
        available: connected,
      },
      {
        id: 'mission-clear',
        label: t('ctrl.clearMission'),
        category: t('ctrl.mission'),
        icon: Trash2,
        handler: () =>
          showConfirm(t('ctrl.clearMission') + '?', true).then(
            (ok) => ok && (dispatch('mission_clear')),
          ),
        available: connected,
      },

      {
        id: 'param-read',
        label: t('param.readAll'),
        category: t('param.title'),
        icon: Download,
        handler: () => {
          onnavigate('params');
          dispatch('param_request_all');
        },
        available: connected,
      },
      {
        id: 'param-export',
        label: t('param.export'),
        category: t('param.title'),
        icon: Upload,
        handler: () => onnavigate('params'),
        available: paramState.list.length > 0,
      },

      {
        id: 'cal-compass',
        label: t('cal.compass'),
        category: t('cal.title'),
        icon: Compass,
        handler: () => {
          openPanel('calibration');
          dispatch('cal_compass');
        },
        available: connected,
      },
      {
        id: 'cal-accel',
        label: t('cal.accel'),
        category: t('cal.title'),
        icon: Gauge,
        handler: () => {
          openPanel('calibration');
          dispatch('cal_accel');
        },
        available: connected,
      },
      {
        id: 'cal-gyro',
        label: t('cal.gyro'),
        category: t('cal.title'),
        icon: RotateCcw,
        handler: () => {
          openPanel('calibration');
          dispatch('cal_gyro');
        },
        available: connected,
      },
      {
        id: 'cal-level',
        label: t('cal.level'),
        category: t('cal.title'),
        icon: Navigation,
        handler: () => {
          openPanel('calibration');
          dispatch('cal_level');
        },
        available: connected,
      },

      {
        id: 'tool-inspector',
        label: t('cmd.inspector'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('inspector'),
        available: true,
      },
      {
        id: 'tool-console',
        label: t('cmd.console'),
        category: t('cmd.catTools'),
        icon: Terminal,
        handler: () => openPanel('console'),
        available: connected,
      },
      {
        id: 'tool-logs',
        label: t('log.title'),
        category: t('cmd.catTools'),
        icon: HardDrive,
        handler: () => openPanel('logPanel'),
        available: connected,
      },
      {
        id: 'tool-video',
        label: t('video.title'),
        category: t('cmd.catTools'),
        icon: Video,
        handler: () => openPanel('video'),
        available: true,
      },
      {
        id: 'tool-motor',
        label: t('cmd.motorTest'),
        category: t('cmd.catTools'),
        icon: Zap,
        handler: () => openPanel('motorTest'),
        available: connected,
      },
      {
        id: 'tool-rccal',
        label: t('rccal.title'),
        category: t('cmd.catTools'),
        icon: Radio,
        handler: () => openPanel('rcCal'),
        available: connected,
      },
      {
        id: 'tool-failsafe',
        label: t('failsafe.title'),
        category: t('cmd.catTools'),
        icon: ShieldAlert,
        handler: () => openPanel('failsafe'),
        available: connected,
      },
      {
        id: 'tool-power',
        label: t('power.title'),
        category: t('cmd.catTools'),
        icon: Zap,
        handler: () => openPanel('powerCal'),
        available: connected,
      },
      {
        id: 'tool-esccal',
        label: t('esccal.title'),
        category: t('cmd.catTools'),
        icon: Zap,
        handler: () => openPanel('escCal'),
        available: connected,
      },
      {
        id: 'tool-frame',
        label: t('frame.title'),
        category: t('cmd.catTools'),
        icon: Plane,
        handler: () => openPanel('frameSelect'),
        available: connected,
      },
      {
        id: 'tool-pid',
        label: t('pid.title'),
        category: t('cmd.catTools'),
        icon: Zap,
        handler: () => openPanel('pid'),
        available: connected,
      },
      {
        id: 'tool-autotune',
        label: t('autotune.title'),
        category: t('cmd.catTools'),
        icon: Zap,
        handler: () => openPanel('autoTune'),
        available: connected,
      },
      {
        id: 'tool-modes',
        label: t('fltmode.title'),
        category: t('cmd.catTools'),
        icon: Plane,
        handler: () => openPanel('flightModes'),
        available: connected,
      },
      {
        id: 'tool-setup',
        label: t('setup.title'),
        category: t('cmd.catTools'),
        icon: Wrench,
        handler: () => openPanel('setupWizard'),
        available: true,
      },
      {
        id: 'tool-paramdiff',
        label: t('paramdiff.title'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('paramDiff'),
        available: paramState.list.length > 0,
      },
      {
        id: 'tool-multivehicle',
        label: t('multi.title'),
        category: t('cmd.catTools'),
        icon: Plane,
        handler: () => openPanel('fleet'),
        available: connected,
      },
      {
        id: 'tool-report',
        label: t('report.title'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('flightReport'),
        available: true,
      },
      {
        id: 'tool-logviewer',
        label: t('logview.title'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('logViewer'),
        available: true,
      },
      {
        id: 'tool-fft',
        label: t('fft.title'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('fft'),
        available: true,
      },
      {
        id: 'tool-compass3d',
        label: t('compass3d.title'),
        category: t('cmd.catTools'),
        icon: Compass,
        handler: () => openPanel('compass3d'),
        available: connected,
      },
      {
        id: 'tool-advcmd',
        label: t('advcmd.title'),
        category: t('ctrl.mission'),
        icon: Zap,
        handler: () => openPanel('advCmd'),
        available: true,
      },
      {
        id: 'tool-overlap',
        label: t('overlap.title'),
        category: t('ctrl.mission'),
        icon: Search,
        handler: () => openPanel('overlapCalc'),
        available: true,
      },
      {
        id: 'tool-corridor',
        label: t('corridor.title'),
        category: t('ctrl.mission'),
        icon: Search,
        handler: () => openPanel('corridor'),
        available: true,
      },
      {
        id: 'tool-poi',
        label: t('poi.title'),
        category: t('ctrl.mission'),
        icon: Search,
        handler: () => openPanel('poi'),
        available: connected,
      },
      {
        id: 'tool-annotation',
        label: t('annotation.title'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('annotation'),
        available: true,
      },
      {
        id: 'tool-remote',
        label: t('remote.title'),
        category: t('cmd.catTools'),
        icon: Radio,
        handler: () => openPanel('remote'),
        available: true,
      },
      {
        id: 'tool-role',
        label: t('role.current'),
        category: t('cmd.catTools'),
        icon: ShieldAlert,
        handler: () => openPanel('role'),
        available: true,
      },
      {
        id: 'tool-airspace',
        label: t('airspace.title'),
        category: t('cmd.catTools'),
        icon: ShieldAlert,
        handler: () => openPanel('airspace'),
        available: true,
      },
      {
        id: 'tool-offlinemap',
        label: t('offmap.title'),
        category: t('cmd.catTools'),
        icon: Search,
        handler: () => openPanel('offlineMap'),
        available: true,
      },
      {
        id: 'tool-mission3d',
        label: '3D Preview',
        category: t('ctrl.mission'),
        icon: Search,
        handler: () => openPanel('mission3d'),
        available: true,
      },
      {
        id: 'tool-terrainProfile',
        label: t('terrain.profileTitle'),
        category: t('ctrl.mission'),
        icon: Search,
        handler: () => openPanel('terrainProfile'),
        available: true,
      },

      {
        id: 'set-theme',
        label: t('settings.darkTheme'),
        category: t('settings.title'),
        shortcut: 'L',
        icon: app.darkTheme ? Sun : Moon,
        handler: () => {
          app.darkTheme = !app.darkTheme;
          saveSettings();
        },
        available: true,
      },
      {
        id: 'set-audio',
        label: t('settings.audio'),
        category: t('settings.title'),
        icon: app.audioMuted ? VolumeOff : Volume2,
        handler: () => {
          app.audioMuted = !app.audioMuted;
          saveSettings();
        },
        available: true,
      },
      {
        id: 'set-voice',
        label: t('settings.voice'),
        category: t('settings.title'),
        icon: app.voiceEnabled ? Mic : MicOff,
        handler: () => {
          app.voiceEnabled = !app.voiceEnabled;
          saveSettings();
        },
        available: true,
      },
      {
        id: 'set-lang-zh',
        label: '中文',
        category: t('settings.language'),
        icon: Globe,
        handler: () => setLocale('zh'),
        available: i18nState.locale !== 'zh',
      },
      {
        id: 'set-lang-en',
        label: 'English',
        category: t('settings.language'),
        icon: Globe,
        handler: () => setLocale('en'),
        available: i18nState.locale !== 'en',
      },
      {
        id: 'set-fullscreen',
        label: t('shortcut.fullscreen'),
        category: t('settings.title'),
        shortcut: 'F',
        icon: Plane,
        handler: () => {
          if (document.fullscreenElement) document.exitFullscreen();
          else document.documentElement.requestFullscreen().catch(() => {});
        },
        available: true,
      },

      {
        id: 'conn-disconnect',
        label: t('conn.disconnect'),
        category: t('cmd.catConn'),
        icon: Power,
        handler: () => sendDisconnect(),
        available: connected,
      },
      {
        id: 'conn-reboot',
        label: t('fw.rebootNormal'),
        category: t('cmd.catConn'),
        icon: RotateCcw,
        handler: () => dispatch('reboot'),
        available: connected,
      },
    ];

    if (connected && d.mode_btns.length > 0) {
      for (const [modeId, modeName] of d.mode_btns) {
        all.push({
          id: `mode-${modeId}`,
          label: modeName,
          category: t('ctrl.mode'),
          icon: Plane,
          handler: () => dispatch('mode', modeId),
          available: true,
        });
      }
    }

    if (paramState.list.length > 0 && query.length >= 2) {
      const q = query.toUpperCase();
      const matched = paramState.list.filter((p) => p.name.includes(q)).slice(0, 8);
      for (const p of matched) {
        all.push({
          id: `param-${p.name}`,
          label: `${p.name} = ${Number.isInteger(p.value) ? p.value : p.value.toFixed(4)}`,
          category: t('param.title'),
          icon: Settings2,
          handler: () => onnavigate('params'),
          available: true,
        });
      }
    }

    return all;
  });

  let filtered = $derived.by(() => {
    if (!query) return items.filter((i) => i.available);
    const q = query.toLowerCase();
    return items.filter(
      (i) =>
        i.available &&
        (i.label.toLowerCase().includes(q) || i.category.toLowerCase().includes(q) || i.id.toLowerCase().includes(q)),
    );
  });

  let grouped = $derived.by(() => {
    const map = new Map<string, PaletteItem[]>();
    for (const item of filtered) {
      const list = map.get(item.category) || [];
      list.push(item);
      map.set(item.category, list);
    }
    return map;
  });

  let flatList = $derived(filtered);

  $effect(() => {
    selectedIdx = 0;
    query;
  });

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onclose();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIdx = Math.min(selectedIdx + 1, flatList.length - 1);
      scrollToSelected();
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIdx = Math.max(selectedIdx - 1, 0);
      scrollToSelected();
    }
    if (e.key === 'Enter' && flatList[selectedIdx]) {
      doExec(flatList[selectedIdx]);
    }
  }

  function doExec(item: PaletteItem) {
    onclose();
    requestAnimationFrame(() => item.handler());
  }

  function scrollToSelected() {
    const el = document.querySelector(`[data-palette-idx="${selectedIdx}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  aria-label={t('cmd.placeholder')}
  class="fixed inset-0 z-[99999] flex items-start justify-center pt-[15vh] bg-black/50 backdrop-blur-sm"
  onclick={onclose}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div
    class="w-[520px] max-h-[60vh] bg-card border border-border rounded-xl shadow-2xl flex flex-col overflow-hidden"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={onKeydown}
  >
    <div class="flex items-center gap-2 px-4 py-3 border-b border-border">
      <Search size={16} class="text-muted-foreground shrink-0" />
      <input
        bind:this={inputEl}
        bind:value={query}
        placeholder={t('cmd.placeholder')}
        class="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none"
      />
      <kbd class="text-[10px] text-muted-foreground/50 border border-border rounded px-1.5 py-0.5 font-mono">ESC</kbd>
    </div>
    <div class="overflow-y-auto flex-1 py-1">
      {#if flatList.length === 0}
        <div class="px-4 py-8 text-center text-sm text-muted-foreground">{t('cmd.noResults')}</div>
      {:else}
        {#each [...grouped] as [category, categoryItems]}
          <div class="px-3 pt-2 pb-1">
            <span class="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider">{category}</span>
          </div>
          {#each categoryItems as item}
            {@const idx = flatList.indexOf(item)}
            <div
              data-palette-idx={idx}
              role="option"
              tabindex="-1"
              aria-selected={idx === selectedIdx}
              class="flex items-center gap-3 px-4 py-2 mx-1 rounded-lg cursor-pointer transition-colors
                   {idx === selectedIdx ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-muted'}"
              onclick={() => doExec(item)}
              onkeydown={(e) => {
                if (e.key === 'Enter') doExec(item);
              }}
              onmouseenter={() => (selectedIdx = idx)}
            >
              <item.icon size={15} class="shrink-0 opacity-60" />
              <span class="flex-1 text-sm truncate">{item.label}</span>
              {#if item.shortcut}
                <kbd
                  class="text-[10px] text-muted-foreground/50 border border-border rounded px-1.5 py-0.5 font-mono shrink-0"
                  >{item.shortcut}</kbd
                >
              {/if}
              <ChevronRight size={12} class="opacity-30 shrink-0" />
            </div>
          {/each}
        {/each}
      {/if}
    </div>
    <div class="px-4 py-2 border-t border-border flex items-center gap-4 text-[10px] text-muted-foreground/50">
      <span><kbd class="border border-border rounded px-1 py-px font-mono">↑↓</kbd> {t('cmd.hintNav')}</span>
      <span><kbd class="border border-border rounded px-1 py-px font-mono">↵</kbd> {t('cmd.hintExec')}</span>
      <span><kbd class="border border-border rounded px-1 py-px font-mono">ESC</kbd> {t('cmd.hintClose')}</span>
    </div>
  </div>
</div>
