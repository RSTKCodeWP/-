<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import Badge from '$lib/components/ui/badge/badge.svelte';
  import { t } from '../../lib/i18n.svelte';

  const d = app.drone;

  const FLAG_ATTITUDE = 0x001;
  const FLAG_VEL_HORIZ = 0x002;
  const FLAG_VEL_VERT = 0x004;
  const FLAG_POS_HORIZ_REL = 0x008;
  const FLAG_POS_HORIZ_ABS = 0x010;
  const FLAG_POS_VERT_ABS = 0x020;
  const FLAG_POS_VERT_AGL = 0x040;
  const FLAG_CONST_POS = 0x080;
  const FLAG_PRED_POS_REL = 0x100;
  const FLAG_PRED_POS_ABS = 0x200;
  const FLAG_UNINITIALIZED = 0x400;

  interface FlagDef {
    mask: number;
    label: string;
    bad?: boolean;
  }

  const flags: FlagDef[] = $derived([
    { mask: FLAG_ATTITUDE, label: t('ekf.attitude') },
    { mask: FLAG_VEL_HORIZ, label: t('ekf.velH') },
    { mask: FLAG_VEL_VERT, label: t('ekf.velV') },
    { mask: FLAG_POS_HORIZ_REL, label: t('ekf.posHRel') },
    { mask: FLAG_POS_HORIZ_ABS, label: t('ekf.posHAbs') },
    { mask: FLAG_POS_VERT_ABS, label: t('ekf.posVAbs') },
    { mask: FLAG_POS_VERT_AGL, label: t('ekf.posVAgl') },
    { mask: FLAG_CONST_POS, label: t('ekf.constPos'), bad: true },
    { mask: FLAG_PRED_POS_REL, label: t('ekf.predRel') },
    { mask: FLAG_PRED_POS_ABS, label: t('ekf.predAbs') },
    { mask: FLAG_UNINITIALIZED, label: t('ekf.uninit'), bad: true },
  ]);

  interface VarDef {
    key: 'ekf_vel' | 'ekf_pos_h' | 'ekf_pos_v' | 'ekf_compass';
    label: string;
    color: string;
  }

  const variances: VarDef[] = $derived([
    { key: 'ekf_vel', label: t('ekf.vel'), color: '#4fc3f7' },
    { key: 'ekf_pos_h', label: t('ekf.posH'), color: '#69f0ae' },
    { key: 'ekf_pos_v', label: t('ekf.posV'), color: '#ffd54f' },
    { key: 'ekf_compass', label: t('ekf.compass'), color: '#ff8a65' },
  ]);

  function varColor(v: number): string {
    if (v < 0.5) return '#22c55e';
    if (v < 1.0) return '#eab308';
    return '#ef4444';
  }

  function varLevel(v: number): string {
    if (v < 0.5) return t('ekf.good');
    if (v < 1.0) return t('ekf.warn');
    return t('ekf.bad');
  }

  function overallHealth(
    f: number,
    vel: number,
    posH: number,
    posV: number,
    comp: number,
  ): { label: string; variant: 'default' | 'secondary' | 'destructive' } {
    if (f & FLAG_UNINITIALIZED) return { label: t('ekf.uninit'), variant: 'destructive' };
    if (f & FLAG_CONST_POS) return { label: t('ekf.degraded'), variant: 'destructive' };
    const maxVar = Math.max(vel, posH, posV, comp);
    if (maxVar >= 1.0) return { label: t('ekf.bad'), variant: 'destructive' };
    if (maxVar >= 0.5 || !(f & FLAG_POS_HORIZ_ABS)) return { label: t('ekf.warn'), variant: 'secondary' };
    return { label: t('ekf.good'), variant: 'default' };
  }

  let health = $derived(overallHealth(d.ekf_flags, d.ekf_vel, d.ekf_pos_h, d.ekf_pos_v, d.ekf_compass));
</script>

<div class="bg-card border border-border rounded-xl p-4">
  <div class="flex items-center gap-2 mb-3">
    <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('ekf.title')}</h2>
    {#if app.drone.connected}
      <Badge variant={health.variant} class="text-[10px]">{health.label}</Badge>
    {/if}
  </div>

  {#if !app.drone.connected}
    <div class="text-muted-foreground text-xs text-center py-4">{t('ekf.empty')}</div>
  {:else}
    <div class="space-y-2 mb-3">
      {#each variances as v}
        {@const val = d[v.key]}
        {@const pct = Math.min((val / 1.5) * 100, 100)}
        <div class="flex items-center gap-2 text-xs">
          <span class="w-16 text-muted-foreground font-mono truncate">{v.label}</span>
          <div class="flex-1 h-3 bg-muted rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              style="width: {pct}%; background-color: {varColor(val)};"
            ></div>
          </div>
          <span class="w-14 text-right font-mono" style="color: {varColor(val)}">
            {val.toFixed(3)}
          </span>
          <span class="w-6 text-center text-[10px] font-semibold" style="color: {varColor(val)}">
            {varLevel(val)}
          </span>
        </div>
      {/each}
    </div>

    <div class="border-t border-border pt-2">
      <div class="text-[10px] text-muted-foreground mb-1.5 font-semibold">{t('ekf.flags')}</div>
      <div class="flex flex-wrap gap-1">
        {#each flags as f}
          {@const active = !!(d.ekf_flags & f.mask)}
          {#if f.bad}
            {#if active}
              <span
                class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-destructive/15 text-destructive border border-destructive/30"
              >
                {f.label}
              </span>
            {/if}
          {:else}
            <span
              class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors
            {active
                ? 'bg-primary/15 text-primary border border-primary/30'
                : 'bg-muted text-muted-foreground/50 border border-transparent'}"
            >
              {f.label}
            </span>
          {/if}
        {/each}
      </div>
    </div>

    <div class="text-center mt-2 text-[9px] text-muted-foreground">
      {t('ekf.variance')} <span class="text-green-500">&#9632;</span>&lt;0.5 {t('ekf.legendOk')}
      <span class="text-yellow-500"> &#9632;</span>&lt;1.0 {t('ekf.legendWarn')}
      <span class="text-red-500"> &#9632;</span>&ge;1.0 {t('ekf.legendBad')}
    </div>
  {/if}
</div>
