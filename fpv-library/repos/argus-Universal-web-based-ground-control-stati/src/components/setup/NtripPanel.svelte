<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { sendCommand } from '../../lib/ws';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Radio, Satellite } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let host = $state('rtk.ntrip.org.cn');
  let port = $state(8001);
  let mountpoint = $state('RTCM32_GGB');
  let username = $state('');
  let password = $state('');
  let connected = $state(false);
  let connecting = $state(false);
  let rtkFixType = $derived(app.drone.gps_fix_raw);

  // Ack-driven connection state: backend emits ntrip_connected /
  // ntrip_disconnected / ntrip_error events from the client thread. We don't
  // trust the click-side optimistic flip — if auth fails or the caster rejects
  // us, the optimistic "connected=true" would stay forever.
  let _lastEventSeq = $state(0);
  $effect(() => {
    for (let i = app.events.length - 1; i >= 0; i--) {
      const ev = app.events[i];
      if (ev.seq !== undefined && ev.seq <= _lastEventSeq) break;
      if (ev.event_type === 'ntrip_connected') {
        connected = true;
        connecting = false;
      } else if (ev.event_type === 'ntrip_disconnected') {
        connected = false;
        connecting = false;
      } else if (ev.event_type === 'ntrip_error') {
        connected = false;
        connecting = false;
        addToast(ev.text, 'error');
      }
    }
    _lastEventSeq = app.events.length > 0 ? (app.events[app.events.length - 1].seq ?? 0) : 0;
  });

  function rtkStatusLabel(): string {
    if (rtkFixType >= 6) return t('rtk.fixed');
    if (rtkFixType >= 5) return t('rtk.float');
    if (rtkFixType >= 4) return t('rtk.dgps');
    if (rtkFixType >= 3) return t('rtk.fix3d');
    return t('rtk.none');
  }

  function rtkStatusColor(): string {
    if (rtkFixType >= 6) return 'text-green-400';
    if (rtkFixType >= 5) return 'text-yellow-400';
    return 'text-muted-foreground';
  }

  async function toggleNtrip() {
    if (connected) {
      sendCommand('ntrip_stop');
      addToast(t('ntrip.stopped'), 'info');
      return;
    }
    connecting = true;
    sendCommand('ntrip_start', undefined, {
      host,
      port,
      mountpoint,
      username,
      password,
    });
    addToast(t('ntrip.started'), 'info');
    // connected flips true only when backend emits 'ntrip_connected' event;
    // see the $effect above. If the caster rejects (bad auth, no mountpoint),
    // we receive 'ntrip_error' instead and connecting clears back to false.
  }

  function saveConfig() {
    try {
      localStorage.setItem('argus_ntrip', JSON.stringify({ host, port, mountpoint, username }));
    } catch {}
  }

  import { onMount } from 'svelte';
  onMount(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('argus_ntrip') || '{}');
      if (saved.host) host = saved.host;
      if (saved.port) port = saved.port;
      if (saved.mountpoint) mountpoint = saved.mountpoint;
      if (saved.username) username = saved.username;
    } catch {}
  });
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm"
  onclick={(e) => {
    if (e.target === e.currentTarget) onclose();
  }}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[380px] flex flex-col overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Satellite size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('ntrip.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="p-4 space-y-3">
      <!-- RTK Status -->
      <div class="flex items-center justify-between p-2 rounded-lg bg-muted/20 border border-border">
        <span class="text-xs text-muted-foreground">{t('ntrip.rtkStatus')}</span>
        <span class="text-xs font-bold {rtkStatusColor()}">{rtkStatusLabel()}</span>
      </div>

      <!-- Connection form -->
      <div class="space-y-2">
        <div class="flex gap-2">
          <input
            bind:value={host}
            placeholder={t('ntrip.host')}
            onchange={saveConfig}
            class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
          <input
            bind:value={port}
            type="number"
            placeholder={t('ntrip.port')}
            onchange={saveConfig}
            class="w-16 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground text-right"
          />
        </div>
        <input
          bind:value={mountpoint}
          placeholder={t('ntrip.mount')}
          onchange={saveConfig}
          class="w-full h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
        />
        <div class="flex gap-2">
          <input
            bind:value={username}
            placeholder={t('ntrip.username')}
            onchange={saveConfig}
            class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
          <input
            bind:value={password}
            type="password"
            placeholder={t('ntrip.password')}
            class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground"
          />
        </div>
      </div>

      <Button
        variant={connected ? 'destructive' : 'default'}
        class="w-full gap-2"
        disabled={connecting}
        onclick={toggleNtrip}
      >
        <Radio size={14} />
        {connected ? t('ntrip.stop') : connecting ? t('ntrip.connecting') : t('ntrip.start')}
      </Button>

      <div class="text-[10px] text-muted-foreground/50 text-center">
        {t('ntrip.hint')}
      </div>
    </div>
  </div>
</div>
