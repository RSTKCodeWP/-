<script lang="ts">
  import { app, showSlide, isPlane } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import Badge from '$lib/components/ui/badge/badge.svelte';

  function rtl() {
    showSlide(t('slide.rtl'), 'red', () => dispatch('rtl'));
  }
  function pause() {
    dispatch('mode', isPlane() ? 19 : 5);
  }
  function forceDisarm() {
    showSlide(t('slide.forceDisarm'), 'red', () => dispatch('force_disarm'));
  }

  function fmtTime(s: number): string {
    const m = Math.floor(s / 60),
      sec = s % 60;
    return `${m}:${sec < 10 ? '0' : ''}${sec}`;
  }
</script>

{#if app.mapExpanded && app.drone.connected}
  <div
    class="absolute bottom-9 left-2.5 z-[1000] bg-card/95 backdrop-blur border border-border rounded-xl p-2 flex flex-col gap-1.5 min-w-[220px] shadow-lg"
  >
    <div class="flex items-center gap-2">
      <span class="text-base font-bold text-primary">{app.drone.mode}</span>
      <Badge variant={app.drone.armed ? 'destructive' : 'default'} class="text-[10px]">
        {app.drone.armed ? t('status.armed') : t('ctrl.disarm')}
      </Badge>
      {#if app.drone.flight_time > 0}
        <span class="text-sm text-warning ml-auto font-mono">{fmtTime(app.drone.flight_time)}</span>
      {/if}
    </div>
    <div class="flex gap-1">
      <Button variant="destructive" size="xs" onclick={rtl}>{t('ctrl.rtl')}</Button>
      <Button size="xs" class="bg-amber-600 hover:bg-amber-700 text-white" onclick={pause}>{t('ctrl.pause')}</Button>
      {#if !app.drone.armed}
        <Button
          size="xs"
          class="bg-orange-700 hover:bg-orange-800 text-white"
          onclick={() => showSlide(t('slide.arm'), 'orange', () => dispatch('arm'))}>{t('ctrl.arm')}</Button
        >
      {:else}
        <Button size="xs" class="bg-green-700 hover:bg-green-800 text-white" onclick={() => dispatch('disarm')}
          >{t('ctrl.disarm')}</Button
        >
      {/if}
      {#if app.drone.armed}
        <Button variant="destructive" size="xs" onclick={forceDisarm}>{t('ctrl.forceDisarm')}</Button>
      {/if}
    </div>
    <div class="flex gap-1">
      {#each app.drone.mode_btns.slice(0, 4) as [id, name]}
        <Button
          variant={app.drone.mode_id === id ? 'default' : 'outline'}
          size="xs"
          onclick={() => dispatch('mode', id)}>{name}</Button
        >
      {/each}
    </div>
  </div>
{/if}
