<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { Check, X as XIcon, Settings2 } from '@lucide/svelte';

  const d = app.drone;

  interface CheckItem {
    key: string;
    name: string;
    ok: boolean;
    detail: string;
    critical: boolean;
  }

  /* ── Customization state ── */
  const CONFIG_KEY = 'argus_preflight_config';

  function loadConfig(): Record<string, boolean> {
    try {
      const raw = localStorage.getItem(CONFIG_KEY);
      if (raw) return JSON.parse(raw);
    } catch {}
    return {};
  }

  function saveConfig(cfg: Record<string, boolean>) {
    try {
      localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
    } catch {}
  }

  let customConfig: Record<string, boolean> = $state(loadConfig());
  let showEditor = $state(false);

  function isCheckEnabled(key: string): boolean {
    return customConfig[key] !== false;
  }

  function toggleCheck(key: string) {
    customConfig[key] = !isCheckEnabled(key);
    customConfig = { ...customConfig };
    saveConfig(customConfig);
  }

  /* ── All available checks ── */
  let allChecks = $derived.by((): CheckItem[] => {
    const gpsOk = d.gps_fix_raw >= 3;
    return [
      { key: 'gps', name: t('check.gps'), ok: gpsOk, detail: `${d.gps_fix}`, critical: true },
      { key: 'sats', name: t('check.sats'), ok: d.gps_sats >= 10, detail: `${d.gps_sats} (>=10)`, critical: true },
      { key: 'batV', name: t('check.batV'), ok: d.voltage > 22, detail: `${d.voltage.toFixed(1)}V`, critical: true },
      {
        key: 'batPct',
        name: t('check.batPct'),
        ok: d.remaining >= 30 || d.remaining < 0,
        detail: d.remaining >= 0 ? `${d.remaining}%` : '---',
        critical: true,
      },
      {
        key: 'home',
        name: t('check.home'),
        ok: d.home_lat !== 0,
        detail: d.home_lat !== 0 ? `${d.home_lat.toFixed(5)}, ${d.home_lon.toFixed(5)}` : '---',
        critical: true,
      },
      {
        key: 'link',
        name: t('check.link'),
        ok: d.connected && d.link_age >= 0 && d.link_age < 2,
        detail: d.connected ? `${d.link_age.toFixed(1)}s` : '---',
        critical: true,
      },
      {
        key: 'nav',
        name: t('check.nav'),
        ok: !(d.ekf_flags & 0x480) && Math.max(d.ekf_vel, d.ekf_pos_h, d.ekf_pos_v, d.ekf_compass) < 1.0,
        detail:
          d.ekf_flags & 0x480
            ? 'ERR'
            : Math.max(d.ekf_vel, d.ekf_pos_h, d.ekf_pos_v, d.ekf_compass) < 0.5
              ? 'OK'
              : 'WARN',
        critical: true,
      },
      {
        key: 'vibe',
        name: t('check.vibe'),
        ok: Math.max(d.vibe[0], d.vibe[1], d.vibe[2]) < 30,
        detail: `${Math.max(d.vibe[0], d.vibe[1], d.vibe[2]).toFixed(0)} m/s2`,
        critical: true,
      },
      {
        key: 'compass',
        name: t('check.compass'),
        ok: d.ekf_compass < 0.8,
        detail: d.ekf_compass < 0.5 ? 'OK' : d.ekf_compass < 0.8 ? 'WARN' : `${d.ekf_compass.toFixed(2)}`,
        critical: true,
      },
      {
        key: 'baro',
        name: t('check.baro'),
        ok: d.alt_msl !== 0 || d.alt_rel !== 0 || !d.connected,
        detail: d.connected ? `MSL ${d.alt_msl.toFixed(1)}m` : '---',
        critical: true,
      },
      {
        key: 'ahrs',
        name: t('check.ahrs'),
        ok: !(d.ekf_flags & 0x800) && d.ekf_vel < 1.0 && d.ekf_pos_v < 1.0,
        detail: d.ekf_flags & 0x800 ? 'ERR' : d.ekf_vel < 0.5 && d.ekf_pos_v < 0.5 ? 'OK' : 'WARN',
        critical: true,
      },
      {
        key: 'rc',
        name: t('check.rc'),
        ok: d.rc_rssi > 0 || d.rc[0] > 0,
        detail: d.rc_rssi > 0 ? `RSSI ${d.rc_rssi}` : d.rc[0] > 0 ? 'OK' : '---',
        critical: false,
      },
      {
        key: 'mission',
        name: t('check.mission'),
        ok: app.waypoints.length > 0,
        detail: app.waypoints.length > 0 ? `${app.waypoints.length} WP` : '---',
        critical: false,
      },
      {
        key: 'vtype',
        name: t('check.vtype'),
        ok: d.vtype_raw > 0,
        detail:
          d.vtype_raw > 0
            ? t(
                [1, 19, 20, 21, 22, 23, 24, 25].includes(d.vtype_raw)
                  ? 'vtype.plane'
                  : d.vtype_raw === 10
                    ? 'vtype.rover'
                    : d.vtype_raw === 12
                      ? 'vtype.sub'
                      : 'vtype.copter',
              )
            : '---',
        critical: false,
      },
      {
        key: 'notArmed',
        name: t('check.notArmed'),
        ok: !d.armed,
        detail: d.armed ? t('status.armed') : 'OK',
        critical: false,
      },
    ];
  });

  /* ── Filtered checks based on user config ── */
  let checks = $derived(allChecks.filter((c) => isCheckEnabled(c.key)));

  let allCriticalOk = $derived(checks.filter((c) => c.critical).every((c) => c.ok));
  let passCount = $derived(checks.filter((c) => c.ok).length);
</script>

<div class="p-3">
  <div class="flex items-center justify-between mb-2">
    <h2 class="text-xs font-semibold text-primary uppercase tracking-wider">{t('preflight.title')}</h2>
    <div class="flex items-center gap-2">
      <span class="text-[11px] font-medium {allCriticalOk ? 'text-success' : 'text-muted-foreground'}">
        {passCount}/{checks.length}
        {allCriticalOk ? t('preflight.ready') : t('preflight.notReady')}
      </span>
      <button
        class="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-muted/50"
        onclick={() => {
          showEditor = !showEditor;
        }}
      >
        <Settings2 size={12} />
        <span>{t('preflight.customize')}</span>
      </button>
    </div>
  </div>

  <!-- Customization editor -->
  {#if showEditor}
    <div class="mb-3 p-2.5 rounded-lg border border-border bg-muted/20">
      <div class="flex items-center justify-between mb-2">
        <span class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider"
          >{t('preflight.customizeTitle')}</span
        >
      </div>
      <div class="grid grid-cols-2 gap-x-3 gap-y-1 max-sm:grid-cols-1">
        {#each allChecks as c}
          <label class="flex items-center gap-2 py-0.5 cursor-pointer group">
            <input
              type="checkbox"
              checked={isCheckEnabled(c.key)}
              onchange={() => toggleCheck(c.key)}
              class="w-3.5 h-3.5 rounded border-border accent-primary"
            />
            <span class="text-xs text-foreground group-hover:text-primary transition-colors">{c.name}</span>
            {#if c.critical}
              <span class="text-[9px] text-muted-foreground">*</span>
            {/if}
          </label>
        {/each}
      </div>
    </div>
  {/if}

  <div class="grid grid-cols-2 gap-x-3 gap-y-1 max-sm:grid-cols-1">
    {#each checks as c}
      <div class="flex items-center gap-1.5 py-0.5">
        <span
          class="w-4.5 h-4.5 rounded-full flex items-center justify-center shrink-0
          {c.ok
            ? 'bg-green-700 text-white'
            : c.critical
              ? 'bg-destructive text-white'
              : 'bg-muted text-muted-foreground'}"
        >
          {#if c.ok}<Check size={11} strokeWidth={3} />{:else}<XIcon size={11} strokeWidth={3} />{/if}
        </span>
        <span class="text-xs font-semibold whitespace-nowrap">{c.name}</span>
        <span class="text-[11px] text-muted-foreground truncate">{c.detail}</span>
      </div>
    {/each}
  </div>
  {#if allCriticalOk}
    <div
      class="mt-2 py-1.5 bg-green-900/40 text-success text-center rounded-lg text-xs font-bold border border-green-700/30"
    >
      {t('preflight.allPass')}
    </div>
  {/if}
  {#if d.prearm && d.prearm.length > 0}
    <div class="mt-2 pt-2 border-t border-border/50">
      <span class="text-[10px] font-semibold text-destructive uppercase tracking-wider">{t('prearm.title')}</span>
      <div class="mt-1 space-y-0.5">
        {#each d.prearm as msg}
          <div class="flex items-center gap-1.5 text-[11px] text-destructive/80">
            <XIcon size={10} class="shrink-0" />
            <span>{msg}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
