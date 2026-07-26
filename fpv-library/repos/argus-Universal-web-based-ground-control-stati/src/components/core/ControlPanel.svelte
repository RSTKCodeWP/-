<script lang="ts">
  import {
    app,
    showConfirm,
    showSlide,
    addToast,
    saveSettings,
    isPlane,
    loadDownloadedMission,
  } from '../../lib/stores.svelte';
  import { sendCommand } from '../../lib/ws';
  import {
    isSerialConnected,
    serialDownloadMission,
    dispatch,
  } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import {
    Plane,
    ShieldCheck,
    CircleStop,
    ArrowDown,
    CornerDownLeft,
    Play,
    Pause,
    Package,
    ChevronUp,
    ChevronDown,
  } from '@lucide/svelte';

  type Phase = 'disarmed' | 'ground' | 'flying' | 'mission' | 'returning';

  const COPTER_RTL = new Set([6, 21]);
  const COPTER_LAND = new Set([9]);
  const COPTER_AUTO = new Set([3]);
  const PLANE_RTL = new Set([11, 21]);
  const PLANE_LAND = new Set([20]);
  const PLANE_AUTO = new Set([10]);

  let phase = $derived.by((): Phase => {
    const d = app.drone;
    if (!d.armed) return 'disarmed';
    const m = d.mode_id;
    const plane = isPlane();
    if ((plane ? PLANE_RTL : COPTER_RTL).has(m) || (plane ? PLANE_LAND : COPTER_LAND).has(m)) return 'returning';
    if ((plane ? PLANE_AUTO : COPTER_AUTO).has(m)) return 'mission';
    if (d.alt_rel >= 0 && d.alt_rel < 2 && d.gs < 1) return 'ground';
    return 'flying';
  });

  let phaseLabel = $derived(
    phase === 'disarmed'
      ? t('phase.disarmed')
      : phase === 'ground'
        ? t('phase.ground')
        : phase === 'mission'
          ? t('phase.mission')
          : phase === 'returning'
            ? t('phase.returning')
            : t('phase.flying'),
  );

  let phaseColor = $derived(
    phase === 'disarmed'
      ? 'text-muted-foreground'
      : phase === 'ground'
        ? 'text-teal-400'
        : phase === 'mission'
          ? 'text-blue-400'
          : phase === 'returning'
            ? 'text-orange-400'
            : 'text-green-400',
  );

  function arm() {
    showSlide(t('slide.arm'), 'orange', () => dispatch('arm'));
  }
  function disarm() {
    dispatch('disarm');
  }
  function rtl() {
    showSlide(t('slide.rtl'), 'red', () => dispatch('rtl'));
  }
  function forceDisarm() {
    showSlide(t('slide.forceDisarm'), 'red', () => dispatch('force_disarm'));
  }
  function pauseMode() {
    dispatch('mode', isPlane() ? 19 : 5);
  }
  function takeoff() {
    showSlide(`${t('slide.takeoff')} ${app.defaultAlt}m`, 'teal', () =>
      dispatch('takeoff', undefined, { alt: app.defaultAlt }),
    );
  }
  function startMission() {
    showSlide(t('slide.mission'), 'blue', () => dispatch('mission_start'));
  }
  async function drop() {
    if (await showConfirm(t('ctrl.drop') + '?', true)) dispatch('drop');
  }
  function adjustAlt(delta: number) {
    const d = app.drone;
    if (!d.connected || !d.armed || d.lat === 0) return;
    const newAlt = Math.max(5, Math.round(d.alt_rel + delta));
    dispatch('guided_goto', undefined, { lat: d.lat, lon: d.lon, alt: newAlt });
    addToast(`${t('ctrl.altitude')} → ${newAlt}m`, 'info', 2000);
  }
</script>

<div class="bg-card border-r border-border p-3 w-44 shrink-0 flex flex-col gap-2">
  <div class="flex items-center gap-2 px-1">
    <span class="w-2 h-2 rounded-full {phase === 'disarmed' ? 'bg-gray-500' : 'bg-current animate-pulse'} {phaseColor}"
    ></span>
    <span class="text-[11px] font-bold uppercase tracking-wider {phaseColor}">{phaseLabel}</span>
  </div>

  {#if phase === 'disarmed'}
    <Button size="sm" class="w-full bg-orange-700 hover:bg-orange-800 text-white font-bold gap-1.5" onclick={arm}>
      <ShieldCheck size={14} />{t('ctrl.arm')}
    </Button>
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.mode')}</div>
    <div class="flex flex-col gap-1">
      {#each app.drone.mode_btns as [id, name]}
        <Button
          variant={app.drone.mode_id === id ? 'default' : 'secondary'}
          size="sm"
          class="w-full justify-start"
          onclick={() => dispatch('mode', id)}>{name}</Button
        >
      {/each}
    </div>
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.mission')}</div>
    <Button
      variant="outline"
      size="sm"
      class="w-full"
      onclick={() => {
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
      }}>{t('ctrl.downloadMission')}</Button
    >
    <Button
      variant="outline"
      size="sm"
      class="w-full"
      onclick={async () => {
        if (await showConfirm(t('ctrl.clearMission') + '?'))
          dispatch('mission_clear');
      }}>{t('ctrl.clearMission')}</Button
    >
  {:else if phase === 'ground'}
    <div class="flex gap-1">
      <Button size="sm" class="flex-1 bg-teal-700 hover:bg-teal-800 text-white font-bold gap-1" onclick={takeoff}>
        <Plane size={14} />{t('ctrl.takeoff')}
      </Button>
      <div class="flex items-center gap-0.5 bg-muted rounded-md px-1">
        <input
          type="number"
          bind:value={app.defaultAlt}
          min="5"
          max="200"
          step="5"
          onchange={() => saveSettings()}
          class="w-9 h-7 px-0.5 text-center text-xs font-bold bg-transparent border-none text-foreground focus:outline-none"
        />
        <span class="text-[10px] text-muted-foreground">m</span>
      </div>
    </div>
    {#if app.waypoints.length > 0}
      <Button
        size="sm"
        class="w-full bg-blue-700 hover:bg-blue-800 text-white font-bold gap-1.5"
        onclick={startMission}
      >
        <Play size={14} />{t('ctrl.startMission')}
      </Button>
    {/if}
    <Button size="sm" class="w-full bg-green-700 hover:bg-green-800 text-white" onclick={disarm}
      >{t('ctrl.disarm')}</Button
    >
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.mode')}</div>
    <div class="flex flex-col gap-1">
      {#each app.drone.mode_btns.slice(0, 4) as [id, name]}
        <Button
          variant={app.drone.mode_id === id ? 'default' : 'secondary'}
          size="sm"
          class="w-full justify-start"
          onclick={() => dispatch('mode', id)}>{name}</Button
        >
      {/each}
    </div>
  {:else if phase === 'flying'}
    <Button variant="destructive" size="sm" class="w-full font-bold gap-1.5" onclick={rtl}>
      <CornerDownLeft size={14} />{t('ctrl.rtl')}
    </Button>
    <Button size="sm" class="w-full bg-amber-600 hover:bg-amber-700 text-white font-bold gap-1.5" onclick={pauseMode}>
      <Pause size={14} />{t('ctrl.pause')}
    </Button>
    {#if app.waypoints.length > 0}
      <Button size="sm" class="w-full bg-blue-700 hover:bg-blue-800 text-white gap-1.5" onclick={startMission}>
        <Play size={14} />{t('ctrl.startMission')}
      </Button>
    {/if}
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.altitude')}</div>
    <div class="flex items-center gap-1">
      <Button variant="outline" size="xs" class="px-1.5" onclick={() => adjustAlt(-5)}><ChevronDown size={12} /></Button
      >
      <span class="flex-1 text-center text-xs font-bold tabular-nums">{app.drone.alt_rel.toFixed(0)}m</span>
      <Button variant="outline" size="xs" class="px-1.5" onclick={() => adjustAlt(5)}><ChevronUp size={12} /></Button>
    </div>
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.payload')}</div>
    <div class="flex gap-1.5">
      <Button size="sm" class="flex-1 bg-orange-700 hover:bg-orange-800 text-white font-bold" onclick={drop}>
        <Package size={12} />{t('ctrl.drop')}
      </Button>
      <Button size="sm" variant="secondary" class="flex-1" onclick={() => dispatch('drop_stop')}
        >{t('ctrl.dropStop')}</Button
      >
    </div>
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.mode')}</div>
    <div class="flex flex-col gap-1">
      {#each app.drone.mode_btns as [id, name]}
        <Button
          variant={app.drone.mode_id === id ? 'default' : 'secondary'}
          size="sm"
          class="w-full justify-start"
          onclick={() => dispatch('mode', id)}>{name}</Button
        >
      {/each}
    </div>
    <Button variant="ghost" size="xs" class="w-full text-destructive mt-1" onclick={forceDisarm}
      >{t('ctrl.forceDisarm')}</Button
    >
  {:else if phase === 'mission'}
    <Button size="sm" class="w-full bg-amber-600 hover:bg-amber-700 text-white font-bold gap-1.5" onclick={pauseMode}>
      <Pause size={14} />{t('ctrl.pauseMission')}
    </Button>
    <Button variant="destructive" size="sm" class="w-full font-bold gap-1.5" onclick={rtl}>
      <CornerDownLeft size={14} />{t('ctrl.abortRtl')}
    </Button>
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.payload')}</div>
    <div class="flex gap-1.5">
      <Button size="sm" class="flex-1 bg-orange-700 hover:bg-orange-800 text-white font-bold" onclick={drop}
        >{t('ctrl.drop')}</Button
      >
      <Button size="sm" variant="secondary" class="flex-1" onclick={() => dispatch('drop_stop')}
        >{t('ctrl.dropStop')}</Button
      >
    </div>
    <div class="text-[11px] text-muted-foreground font-semibold mt-1 tracking-wide uppercase">{t('ctrl.mode')}</div>
    <div class="flex flex-col gap-1">
      {#each app.drone.mode_btns.slice(0, 4) as [id, name]}
        <Button
          variant={app.drone.mode_id === id ? 'default' : 'secondary'}
          size="sm"
          class="w-full justify-start"
          onclick={() => dispatch('mode', id)}>{name}</Button
        >
      {/each}
    </div>
    <Button variant="ghost" size="xs" class="w-full text-destructive mt-1" onclick={forceDisarm}
      >{t('ctrl.forceDisarm')}</Button
    >
  {:else if phase === 'returning'}
    <Button size="sm" class="w-full bg-amber-600 hover:bg-amber-700 text-white font-bold gap-1.5" onclick={pauseMode}>
      <CircleStop size={14} />{t('ctrl.cancelRtl')}
    </Button>
    <Button
      size="sm"
      class="w-full bg-teal-700 hover:bg-teal-800 text-white gap-1.5"
      onclick={() => dispatch('mode', isPlane() ? 20 : 9)}
    >
      <ArrowDown size={14} />{t('ctrl.land')}
    </Button>
    <Button variant="ghost" size="xs" class="w-full text-destructive mt-2" onclick={forceDisarm}
      >{t('ctrl.forceDisarm')}</Button
    >
  {/if}
</div>
