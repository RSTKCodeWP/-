<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, LayoutDashboard, Settings2 } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Widget definitions ── */
  interface Widget {
    id: string;
    labelKey: string;
    unit: string;
    getValue: () => number | string;
    getStatus: () => 'good' | 'warn' | 'bad' | 'neutral';
  }

  const widgets: Widget[] = [
    {
      id: 'altitude',
      labelKey: 'dashboard.altitude',
      unit: 'm',
      getValue: () => app.drone.alt_rel?.toFixed(1) ?? '--',
      getStatus: () => ((app.drone.alt_rel ?? 0) > 120 ? 'warn' : 'good'),
    },
    {
      id: 'speed',
      labelKey: 'dashboard.speed',
      unit: 'm/s',
      getValue: () => app.drone.gs?.toFixed(1) ?? '--',
      getStatus: () => ((app.drone.gs ?? 0) > 20 ? 'warn' : 'good'),
    },
    {
      id: 'vs',
      labelKey: 'dashboard.vs',
      unit: 'm/s',
      getValue: () => app.drone.vz?.toFixed(1) ?? '--',
      getStatus: () => (Math.abs(app.drone.vz ?? 0) > 5 ? 'warn' : 'good'),
    },
    {
      id: 'distance',
      labelKey: 'dashboard.distance',
      unit: 'm',
      getValue: () => app.drone.dist_home?.toFixed(0) ?? '--',
      getStatus: () => ((app.drone.dist_home ?? 0) > 2000 ? 'warn' : 'good'),
    },
    {
      id: 'heading',
      labelKey: 'dashboard.heading',
      unit: '°',
      getValue: () => app.drone.hdg?.toFixed(0) ?? '--',
      getStatus: () => 'neutral',
    },
    {
      id: 'voltage',
      labelKey: 'dashboard.voltage',
      unit: 'V',
      getValue: () => app.drone.voltage?.toFixed(1) ?? '--',
      getStatus: () => ((app.drone.voltage ?? 99) < 21 ? 'bad' : (app.drone.voltage ?? 99) < 22.5 ? 'warn' : 'good'),
    },
    {
      id: 'current',
      labelKey: 'dashboard.current',
      unit: 'A',
      getValue: () => app.drone.current?.toFixed(1) ?? '--',
      getStatus: () => ((app.drone.current ?? 0) > 40 ? 'warn' : 'good'),
    },
    {
      id: 'battery',
      labelKey: 'dashboard.battery',
      unit: '%',
      getValue: () => app.drone.remaining?.toFixed(0) ?? '--',
      getStatus: () =>
        (app.drone.remaining ?? 100) < 20 ? 'bad' : (app.drone.remaining ?? 100) < 40 ? 'warn' : 'good',
    },
    {
      id: 'gpsfix',
      labelKey: 'dashboard.gpsFix',
      unit: '',
      getValue: () => {
        const f = app.drone.gps_fix_raw ?? 0;
        return f >= 3 ? t('rtk.fix3d') : f >= 2 ? '2D' : t('rtk.none');
      },
      getStatus: () =>
        (app.drone.gps_fix_raw ?? 0) >= 3 ? 'good' : (app.drone.gps_fix_raw ?? 0) >= 2 ? 'warn' : 'bad',
    },
    {
      id: 'sats',
      labelKey: 'dashboard.sats',
      unit: '',
      getValue: () => app.drone.gps_sats?.toFixed(0) ?? '--',
      getStatus: () => ((app.drone.gps_sats ?? 0) >= 10 ? 'good' : (app.drone.gps_sats ?? 0) >= 6 ? 'warn' : 'bad'),
    },
    {
      id: 'flighttime',
      labelKey: 'dashboard.flightTime',
      unit: '',
      getValue: () => {
        const s = app.drone.flight_time ?? 0;
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return `${m}:${sec.toString().padStart(2, '0')}`;
      },
      getStatus: () => ((app.drone.flight_time ?? 0) > 1200 ? 'warn' : 'good'),
    },
    {
      id: 'mode',
      labelKey: 'dashboard.mode',
      unit: '',
      getValue: () => app.drone.mode || '--',
      getStatus: () => 'neutral',
    },
    {
      id: 'roll',
      labelKey: 'dashboard.roll',
      unit: '°',
      getValue: () => app.drone.roll?.toFixed(1) ?? '--',
      getStatus: () => (Math.abs(app.drone.roll ?? 0) > 30 ? 'warn' : 'good'),
    },
    {
      id: 'pitch',
      labelKey: 'dashboard.pitch',
      unit: '°',
      getValue: () => app.drone.pitch?.toFixed(1) ?? '--',
      getStatus: () => (Math.abs(app.drone.pitch ?? 0) > 30 ? 'warn' : 'good'),
    },
    {
      id: 'yaw',
      labelKey: 'dashboard.yaw',
      unit: '°',
      getValue: () => app.drone.yaw?.toFixed(1) ?? '--',
      getStatus: () => 'neutral',
    },
    {
      id: 'windspeed',
      labelKey: 'dashboard.windSpeed',
      unit: 'm/s',
      getValue: () => app.drone.wind_speed?.toFixed(1) ?? '--',
      getStatus: () => ((app.drone.wind_speed ?? 0) > 10 ? 'warn' : 'good'),
    },
    {
      id: 'winddir',
      labelKey: 'dashboard.windDir',
      unit: '°',
      getValue: () => app.drone.wind_dir?.toFixed(0) ?? '--',
      getStatus: () => 'neutral',
    },
    {
      id: 'ekfvel',
      labelKey: 'dashboard.ekfVel',
      unit: '',
      getValue: () => app.drone.ekf_vel?.toFixed(2) ?? '--',
      getStatus: () => ((app.drone.ekf_vel ?? 0) > 0.8 ? 'bad' : (app.drone.ekf_vel ?? 0) > 0.5 ? 'warn' : 'good'),
    },
    {
      id: 'ekfpos',
      labelKey: 'dashboard.ekfPos',
      unit: '',
      getValue: () => app.drone.ekf_pos_h?.toFixed(2) ?? '--',
      getStatus: () => ((app.drone.ekf_pos_h ?? 0) > 0.8 ? 'bad' : (app.drone.ekf_pos_h ?? 0) > 0.5 ? 'warn' : 'good'),
    },
  ];

  /* ── Selected widgets (persisted) ── */
  const STORAGE_KEY = 'argus_dashboard_widgets';

  function loadSelection(): Set<string> {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return new Set(JSON.parse(raw));
    } catch {}
    return new Set(['altitude', 'speed', 'vs', 'voltage', 'battery', 'sats', 'mode', 'distance', 'heading']);
  }

  let selected = $state(loadSelection());
  let showPicker = $state(false);

  function toggleWidget(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected = next;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
    } catch {}
  }

  let activeWidgets = $derived(widgets.filter((w) => selected.has(w.id)));

  const statusColor: Record<string, string> = {
    good: 'text-green-400',
    warn: 'text-amber-400',
    bad: 'text-red-400',
    neutral: 'text-foreground',
  };

  const statusBorder: Record<string, string> = {
    good: 'border-green-500/30',
    warn: 'border-amber-500/30',
    bad: 'border-red-500/30',
    neutral: 'border-border',
  };
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center"
  onclick={onclose}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div
    role="presentation"
    class="bg-card border border-border rounded-2xl overflow-hidden w-[600px] max-h-[85vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <!-- Header -->
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <LayoutDashboard size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('dashboard.title')}</h3>
      </div>
      <div class="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-xs"
          onclick={() => (showPicker = !showPicker)}
          aria-label={t('ui.widgetPicker')}
        >
          <Settings2 size={16} />
        </Button>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>

    <div class="overflow-y-auto px-5 py-3 space-y-4">
      <!-- Widget picker -->
      {#if showPicker}
        <div class="bg-muted/30 rounded-lg p-3 space-y-2">
          <div class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            {t('dashboard.selectWidgets')}
          </div>
          <div class="grid grid-cols-3 gap-1.5">
            {#each widgets as w}
              <div
                role="presentation"
                class="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-muted/50 transition-colors"
                onclick={() => toggleWidget(w.id)}
              >
                <input
                  type="checkbox"
                  checked={selected.has(w.id)}
                  class="h-3 w-3 accent-primary rounded"
                  onchange={() => toggleWidget(w.id)}
                />
                <span class="text-xs text-foreground">{t(w.labelKey)}</span>
              </div>
            {/each}
          </div>
          <div class="text-[10px] text-muted-foreground text-center">{t('dashboard.savedAuto')}</div>
        </div>
      {/if}

      <!-- Dashboard tiles -->
      {#if activeWidgets.length === 0}
        <div class="text-center text-sm text-muted-foreground py-8">{t('dashboard.noWidgets')}</div>
      {:else}
        <div class="grid grid-cols-3 gap-2.5">
          {#each activeWidgets as w}
            {@const val = w.getValue()}
            {@const st = w.getStatus()}
            <div
              class="bg-muted/20 border {statusBorder[
                st
              ]} rounded-xl p-3 flex flex-col items-center justify-center min-h-[80px] transition-colors"
            >
              <div class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                {t(w.labelKey)}
              </div>
              <div class="text-2xl font-bold font-mono {statusColor[st]} leading-tight">{val}</div>
              {#if w.unit}
                <div class="text-[10px] text-muted-foreground mt-0.5">{w.unit}</div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}

      {#if !app.drone.connected}
        <p class="text-[11px] text-muted-foreground text-center italic">{t('dashboard.connectHint')}</p>
      {/if}
    </div>
  </div>
</div>
