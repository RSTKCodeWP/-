<script lang="ts">
  import { app, isPlane } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { fmtDist } from '../../lib/units';

  const d = app.drone;

  let isAutoMode = $derived(isPlane() ? d.mode_id === 10 : d.mode_id === 3);

  let wpCount = $derived(app.waypoints.length);
  let currentWpIdx = $derived(d.wp_idx);
  let progress = $derived(wpCount > 0 ? Math.min(100, (currentWpIdx / wpCount) * 100) : 0);

  let remainingDist = $derived.by(() => {
    if (wpCount === 0 || currentWpIdx >= wpCount) return 0;
    let dist = 0;
    if (currentWpIdx < wpCount && d.lat !== 0) {
      const wp = app.waypoints[currentWpIdx];
      const dlat = (wp.lat - d.lat) * 111320;
      const dlon = (wp.lon - d.lon) * 111320 * Math.cos((d.lat * Math.PI) / 180);
      dist += Math.sqrt(dlat * dlat + dlon * dlon);
    }
    for (let i = currentWpIdx + 1; i < wpCount; i++) {
      const a = app.waypoints[i - 1],
        b = app.waypoints[i];
      const dlat = (b.lat - a.lat) * 111320;
      const dlon = (b.lon - a.lon) * 111320 * Math.cos((a.lat * Math.PI) / 180);
      dist += Math.sqrt(dlat * dlat + dlon * dlon);
    }
    return dist;
  });

  let eta = $derived(d.gs > 0.5 ? Math.round(remainingDist / d.gs) : -1);

  function fmtEta(s: number): string {
    if (s < 0) return '---';
    const m = Math.floor(s / 60),
      sec = s % 60;
    return `${m}:${sec < 10 ? '0' : ''}${sec}`;
  }
</script>

{#if isAutoMode && d.armed && wpCount > 0}
  <div
    class="absolute top-2 left-1/2 -translate-x-1/2 z-[1001] w-80 bg-card/90 backdrop-blur border border-border rounded-xl px-4 py-2 shadow-lg"
  >
    <div class="flex justify-between text-xs text-muted-foreground mb-1">
      <span>{t('ctrl.mission')} #{d.wp_idx + 1}</span>
      <span>{currentWpIdx}/{wpCount} WP</span>
    </div>
    <div class="relative h-2 bg-muted rounded-full overflow-visible">
      <div
        class="h-full bg-gradient-to-r from-blue-600 to-sky-400 rounded-full transition-all duration-500"
        style="width:{progress}%"
      ></div>
      {#each Array(wpCount) as _, i}
        <div
          class="absolute top-[-2px] w-1 h-3 rounded-sm -translate-x-1/2 transition-colors
          {i < currentWpIdx ? 'bg-sky-400' : i === currentWpIdx ? 'bg-warning w-1.5' : 'bg-muted-foreground/30'}"
          style="left:{((i + 1) / wpCount) * 100}%"
        ></div>
      {/each}
    </div>
    <div class="flex justify-between text-[11px] text-muted-foreground mt-1">
      <span>{fmtDist(remainingDist)}</span>
      <span>ETA {fmtEta(eta)}</span>
      <span>{d.gs.toFixed(1)} m/s</span>
    </div>
  </div>
{/if}
