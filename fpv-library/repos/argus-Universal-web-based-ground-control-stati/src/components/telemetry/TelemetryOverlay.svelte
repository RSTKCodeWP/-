<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';

  const d = app.drone;
  function fmtTime(s: number): string {
    const m = Math.floor(s / 60),
      sec = s % 60;
    return `${m}:${sec < 10 ? '0' : ''}${sec}`;
  }
  let aglColor = $derived(
    d.terrain_alt < 0
      ? 'text-foreground'
      : d.terrain_alt < 10
        ? 'text-destructive'
        : d.terrain_alt < 30
          ? 'text-warning'
          : 'text-success',
  );

  let snapAlt = $state(0);
  let snapDist = $state(0);

  $effect(() => {
    const timer = setInterval(() => {
      snapAlt = d.alt_rel;
      snapDist = d.dist_home;
    }, 1500);
    return () => clearInterval(timer);
  });

  let altTrend = $derived(!d.armed ? '' : d.alt_rel > snapAlt + 0.3 ? '↑' : d.alt_rel < snapAlt - 0.3 ? '↓' : '');
  let altTrendColor = $derived(altTrend === '↑' ? 'text-success' : altTrend === '↓' ? 'text-warning' : '');

  let distTrend = $derived(!d.armed ? '' : d.dist_home > snapDist + 2 ? '↑' : d.dist_home < snapDist - 2 ? '↓' : '');
  let distTrendColor = $derived(distTrend === '↑' ? 'text-warning' : distTrend === '↓' ? 'text-success' : '');
</script>

<div
  class="absolute bottom-8 left-1/2 -translate-x-1/2 z-[1001]
  flex items-center bg-card/90 backdrop-blur-sm border border-border rounded-full
  px-4 py-1 shadow-lg pointer-events-auto"
>
  <div class="flex flex-col items-center px-2.5 min-w-[40px]">
    <span class="text-base font-bold text-foreground leading-tight tabular-nums"
      >{d.alt_rel.toFixed(1)}<span class="text-[10px] text-muted-foreground ml-0.5">m</span>{#if altTrend}<span
          class="text-[10px] ml-0.5 {altTrendColor}">{altTrend}</span
        >{/if}</span
    >
    <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.alt')}</span>
  </div>
  <div class="w-px h-6 bg-border"></div>
  <div class="flex flex-col items-center px-2.5 min-w-[40px]">
    <span class="text-base font-bold text-foreground leading-tight tabular-nums"
      >{d.alt_msl.toFixed(0)}<span class="text-[10px] text-muted-foreground ml-0.5">m</span></span
    >
    <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.msl')}</span>
  </div>
  {#if d.terrain_alt >= 0}
    <div class="w-px h-6 bg-border"></div>
    <div class="flex flex-col items-center px-2.5 min-w-[40px]">
      <span class="text-base font-bold leading-tight tabular-nums {aglColor}"
        >{d.terrain_alt.toFixed(1)}<span class="text-[10px] text-muted-foreground ml-0.5">m</span></span
      >
      <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.agl')}</span>
    </div>
  {/if}
  <div class="w-px h-6 bg-border"></div>
  <div class="flex flex-col items-center px-2.5 min-w-[40px]">
    <span class="text-base font-bold text-foreground leading-tight tabular-nums"
      >{d.gs.toFixed(1)}<span class="text-[10px] text-muted-foreground ml-0.5">m/s</span></span
    >
    <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.speed')}</span>
  </div>
  {#if d.airspeed > 0.5}
    <div class="w-px h-6 bg-border"></div>
    <div class="flex flex-col items-center px-2.5 min-w-[40px]">
      <span class="text-base font-bold text-foreground leading-tight tabular-nums"
        >{d.airspeed.toFixed(1)}<span class="text-[10px] text-muted-foreground ml-0.5">m/s</span></span
      >
      <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.aspd')}</span>
    </div>
  {/if}
  <div class="w-px h-6 bg-border"></div>
  <div class="flex flex-col items-center px-2.5 min-w-[40px]">
    <span
      class="text-base font-bold leading-tight tabular-nums
      {d.vz > 0.3 ? 'text-success' : d.vz < -0.3 ? 'text-destructive' : 'text-foreground'}"
      >{d.vz.toFixed(1)}<span class="text-[10px] text-muted-foreground ml-0.5">m/s</span></span
    >
    <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.vs')}</span>
  </div>
  {#if d.armed}
    <div class="w-px h-6 bg-border"></div>
    <div class="flex flex-col items-center px-2.5 min-w-[40px]">
      <span class="text-base font-bold text-foreground leading-tight tabular-nums"
        >{d.throttle}<span class="text-[10px] text-muted-foreground ml-0.5">%</span></span
      >
      <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.thr')}</span>
    </div>
  {/if}
  <div class="w-px h-6 bg-border"></div>
  <div class="flex flex-col items-center px-2.5 min-w-[40px]">
    <span class="text-base font-bold text-foreground leading-tight tabular-nums"
      >{d.dist_home.toFixed(0)}<span class="text-[10px] text-muted-foreground ml-0.5">m</span>{#if distTrend}<span
          class="text-[10px] ml-0.5 {distTrendColor}">{distTrend}</span
        >{/if}</span
    >
    <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.dist')}</span>
  </div>
  <div class="w-px h-6 bg-border"></div>
  <div class="flex flex-col items-center px-2.5 min-w-[40px]">
    <span class="text-base font-bold text-foreground leading-tight tabular-nums">{d.hdg.toFixed(0)}&deg;</span>
    <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.hdg')}</span>
  </div>
  {#if d.flight_time > 0}
    <div class="w-px h-6 bg-border"></div>
    <div class="flex flex-col items-center px-2.5 min-w-[40px]">
      <span class="text-base font-bold text-foreground leading-tight tabular-nums">{fmtTime(d.flight_time)}</span>
      <span class="text-[9px] text-muted-foreground tracking-wider">{t('telem.flight')}</span>
    </div>
  {/if}
</div>
