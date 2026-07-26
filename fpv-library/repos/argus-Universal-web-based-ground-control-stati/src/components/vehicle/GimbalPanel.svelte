<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';

  // All gimbal/camera/ROI commands go through dispatch(): its table carries
  // the WebSerial-native handlers (with backend-parity validation) and falls
  // back to the WS backend otherwise. Calling serialSendCommandLong directly
  // here would bypass those guards — the parity harness assumes dispatch()
  // is the single entry point.
  function sendGimbalAngle(pitch: number, yaw: number): void {
    dispatch('gimbal_angle', undefined, { pitch, yaw });
  }
  function sendGimbalPitchYaw(data: {
    pitch?: number;
    yaw?: number;
    pitch_rate?: number;
    yaw_rate?: number;
    flags?: number;
  }): void {
    dispatch('gimbal_pitchyaw', undefined, data);
  }
  import { X, Aperture, Camera, Video, VideoOff, ZoomIn, Crosshair, RotateCcw } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Gimbal angle state ── */
  let pitch = $state(0);
  let yaw = $state(0);
  let rateMode = $state(false);

  /* ── Camera state ── */
  let recording = $state(false);
  let zoomLevel = $state(1);

  /* ── ROI state ── */
  let roiLat = $state(app.drone.lat || 0);
  let roiLon = $state(app.drone.lon || 0);
  let roiAlt = $state(app.defaultAlt);

  /* ── Live telemetry derived values ── */
  let livePitch = $derived(app.drone.gimbal_pitch ?? null);
  let liveYaw = $derived(app.drone.gimbal_yaw ?? null);

  /* ── Gimbal controls ── */
  function sendAngle() {
    if (rateMode) {
      sendGimbalPitchYaw({ pitch_rate: pitch, yaw_rate: yaw });
      addToast(`${t('gimbal.rate')}: P=${pitch}°/s Y=${yaw}°/s`, 'info', 2000);
    } else {
      sendGimbalAngle(pitch, yaw);
      addToast(`${t('gimbal.angle')}: P=${pitch} Y=${yaw}`, 'info', 2000);
    }
  }

  function centerGimbal() {
    pitch = 0;
    yaw = 0;
    if (rateMode) sendGimbalPitchYaw({ pitch_rate: 0, yaw_rate: 0 });
    else sendGimbalAngle(0, 0);
    addToast(t('gimbal.centered'), 'info', 2000);
  }

  function retractGimbal() {
    // GIMBAL_MANAGER_FLAGS_RETRACT = 1; AP_Mount.cpp:382 short-circuits to
    // set_mode(MAV_MOUNT_MODE_RETRACT) regardless of pitch/yaw payload.
    sendGimbalPitchYaw({ flags: 1 });
    addToast(t('gimbal.retract'), 'info', 2000);
  }

  function neutralGimbal() {
    // GIMBAL_MANAGER_FLAGS_NEUTRAL = 2; AP_Mount.cpp:387.
    sendGimbalPitchYaw({ flags: 2 });
    addToast(t('gimbal.neutral'), 'info', 2000);
  }

  /* ── Camera controls ── */
  function takePhoto() {
    dispatch('camera_trigger');
    addToast(t('camera.photoTaken'), 'success', 2000);
  }

  function toggleVideo() {
    if (recording) {
      dispatch('camera_video_stop');
      recording = false;
      addToast(t('camera.videoStopped'), 'info', 2000);
    } else {
      dispatch('camera_video_start');
      recording = true;
      addToast(t('camera.videoStarted'), 'success', 2000);
    }
  }

  function setZoom() {
    dispatch('camera_zoom', undefined, { zoom: zoomLevel });
    addToast(`${t('camera.zoom')}: ${zoomLevel}x`, 'info', 2000);
  }

  /* ── ROI ── */
  function setRoi() {
    if (roiLat === 0 && roiLon === 0) {
      addToast(t('gimbal.roiHint'), 'warn');
      return;
    }
    dispatch('do_set_roi', undefined, { lat: roiLat, lon: roiLon, alt: roiAlt });
    addToast(`${t('gimbal.roiSet')}: ${roiLat.toFixed(6)}, ${roiLon.toFixed(6)}`, 'success');
  }

  function clearRoi() {
    dispatch('do_set_roi', undefined, { lat: 0, lon: 0, alt: 0 });
    addToast(t('gimbal.roiCleared'), 'info');
  }

  function prefillFromDrone() {
    if (app.drone.lat !== 0 || app.drone.lon !== 0) {
      roiLat = app.drone.lat;
      roiLon = app.drone.lon;
      roiAlt = app.drone.alt_rel || app.defaultAlt;
    }
  }
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[420px] max-h-[85vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <!-- Header -->
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <Aperture size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('gimbal.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="overflow-y-auto px-5 py-3 space-y-4">
      <!-- Live gimbal status -->
      {#if livePitch !== null || liveYaw !== null}
        <div class="bg-muted/30 rounded-lg p-2 flex items-center gap-4">
          <div class="text-[11px] font-semibold text-primary uppercase tracking-wider">{t('gimbal.status')}</div>
          <div class="flex gap-3 text-xs font-mono text-foreground">
            <span>P: {livePitch !== null ? livePitch.toFixed(1) : '--'}°</span>
            <span>Y: {liveYaw !== null ? liveYaw.toFixed(1) : '--'}°</span>
          </div>
        </div>
      {/if}

      <!-- Gimbal angle control -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <div class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            {t('gimbal.angleControl')}
          </div>
          <label class="flex items-center gap-1.5 text-[11px] cursor-pointer select-none">
            <input type="checkbox" bind:checked={rateMode} class="accent-primary cursor-pointer" />
            <span class="text-muted-foreground">{t('gimbal.rateMode')}</span>
          </label>
        </div>
        <div class="space-y-1.5">
          <div class="flex items-center gap-2">
            <label for="gimbal-pitch" class="text-xs text-muted-foreground w-14 shrink-0">{t('gimbal.pitch')}</label>
            <input
              id="gimbal-pitch"
              type="range"
              min={rateMode ? -90 : -90}
              max={rateMode ? 90 : 30}
              step="1"
              bind:value={pitch}
              class="flex-1 h-1.5 accent-primary"
            />
            <span class="text-xs font-mono text-foreground w-12 text-right">{pitch}{rateMode ? '°/s' : '°'}</span>
          </div>
          <div class="flex items-center gap-2">
            <label for="gimbal-yaw" class="text-xs text-muted-foreground w-14 shrink-0">{t('gimbal.yaw')}</label>
            <input
              id="gimbal-yaw"
              type="range"
              min="-180"
              max="180"
              step="1"
              bind:value={yaw}
              class="flex-1 h-1.5 accent-primary"
            />
            <span class="text-xs font-mono text-foreground w-12 text-right">{yaw}{rateMode ? '°/s' : '°'}</span>
          </div>
        </div>
        <div class="flex gap-2">
          <Button variant="default" size="sm" class="flex-1 gap-1" onclick={sendAngle}>
            {t('gimbal.apply')}
          </Button>
          <Button variant="outline" size="sm" class="gap-1" onclick={centerGimbal}>
            <RotateCcw size={13} />{t('gimbal.center')}
          </Button>
        </div>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" class="flex-1 text-xs" onclick={retractGimbal}>
            {t('gimbal.retract')}
          </Button>
          <Button variant="outline" size="sm" class="flex-1 text-xs" onclick={neutralGimbal}>
            {t('gimbal.neutral')}
          </Button>
        </div>
      </div>

      <!-- Separator -->
      <div class="border-t border-border"></div>

      <!-- Camera controls -->
      <div class="space-y-2">
        <div class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{t('camera.title')}</div>
        <div class="flex gap-2">
          <Button variant="default" size="sm" class="flex-1 gap-1.5" onclick={takePhoto}>
            <Camera size={14} />{t('camera.photo')}
          </Button>
          <Button
            variant={recording ? 'destructive' : 'secondary'}
            size="sm"
            class="flex-1 gap-1.5"
            onclick={toggleVideo}
          >
            {#if recording}
              <VideoOff size={14} />{t('camera.videoStop')}
            {:else}
              <Video size={14} />{t('camera.videoStart')}
            {/if}
          </Button>
        </div>
        <div class="flex items-center gap-2">
          <ZoomIn size={14} class="text-muted-foreground shrink-0" />
          <label for="camera-zoom" class="text-xs text-muted-foreground w-10 shrink-0">{t('camera.zoom')}</label>
          <input
            id="camera-zoom"
            type="range"
            min="1"
            max="30"
            step="0.5"
            bind:value={zoomLevel}
            class="flex-1 h-1.5 accent-primary"
          />
          <span class="text-xs font-mono text-foreground w-10 text-right">{zoomLevel}x</span>
          <Button variant="outline" size="sm" class="h-7 px-2 text-xs" onclick={setZoom}>{t('gimbal.apply')}</Button>
        </div>
      </div>

      <!-- Separator -->
      <div class="border-t border-border"></div>

      <!-- ROI -->
      <div class="space-y-2">
        <div class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{t('gimbal.roi')}</div>
        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <label for="roi-lat" class="text-xs text-muted-foreground w-10 shrink-0">Lat</label>
            <input
              id="roi-lat"
              type="number"
              step="0.000001"
              bind:value={roiLat}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-2">
            <label for="roi-lon" class="text-xs text-muted-foreground w-10 shrink-0">Lon</label>
            <input
              id="roi-lon"
              type="number"
              step="0.000001"
              bind:value={roiLon}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-2">
            <label for="roi-alt" class="text-xs text-muted-foreground w-10 shrink-0">Alt</label>
            <input
              id="roi-alt"
              type="number"
              min="0"
              max="500"
              step="5"
              bind:value={roiAlt}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
            <span class="text-xs text-muted-foreground">m</span>
          </div>
        </div>
        {#if app.drone.connected}
          <Button variant="outline" size="sm" class="w-full text-xs" onclick={prefillFromDrone}>
            {t('gimbal.fromDrone')}
          </Button>
        {/if}
        <div class="flex gap-2">
          <Button variant="default" size="sm" class="flex-1 gap-1" onclick={setRoi}>
            <Crosshair size={13} />{t('gimbal.setRoi')}
          </Button>
          <Button variant="outline" size="sm" class="flex-1" onclick={clearRoi}>
            {t('gimbal.clearRoi')}
          </Button>
        </div>
      </div>

      <p class="text-[11px] text-muted-foreground text-center">{t('gimbal.hint')}</p>
    </div>
  </div>
</div>
