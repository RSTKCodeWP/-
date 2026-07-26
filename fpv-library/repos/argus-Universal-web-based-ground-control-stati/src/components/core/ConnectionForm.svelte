<script lang="ts">
  import { onMount } from 'svelte';
  import { app, addToast } from '../../lib/stores.svelte';
  import { sendConnect, sendDisconnect } from '../../lib/ws';
  import { t } from '../../lib/i18n.svelte';
  import { apiUrl } from '../../lib/backend';
  import { webSerialAvailable, connectSerial, disconnectSerial, isSerialConnected } from '../../lib/transport';
  import { buildSerialHandlers } from '../../lib/serialHandlers';
  import Button from '$lib/components/ui/button/button.svelte';
  import { Usb } from '@lucide/svelte';

  let port = $state('tcp:localhost:5770');
  let baud = $state(57600);
  let protocol = $state('auto');
  let portHistory: string[] = $state([]);
  let showHistory = $state(false);
  let connecting = $state(false);

  interface ConnProfile {
    name: string;
    port: string;
    baud: number;
    protocol: string;
  }
  let profiles: ConnProfile[] = $state([]);
  let showProfileSave = $state(false);
  let profileName = $state('');

  onMount(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('argus_port_history') || '[]');
      if (Array.isArray(saved)) portHistory = saved;
      const lastPort = localStorage.getItem('argus_last_port');
      if (lastPort) port = lastPort;
      const lastBaud = localStorage.getItem('argus_last_baud');
      if (lastBaud) baud = parseInt(lastBaud);
      const profs = JSON.parse(localStorage.getItem('argus_profiles') || '[]');
      if (Array.isArray(profs)) profiles = profs;
    } catch {}
    fetchPorts();
  });

  function saveProfile() {
    const name = profileName.trim() || port;
    profiles = [...profiles.filter((p) => p.name !== name), { name, port, baud, protocol }];
    try {
      localStorage.setItem('argus_profiles', JSON.stringify(profiles));
    } catch {}
    showProfileSave = false;
    profileName = '';
  }

  function loadProfile(p: ConnProfile) {
    port = p.port;
    baud = p.baud;
    protocol = p.protocol;
    showHistory = false;
  }

  function deleteProfile(name: string) {
    profiles = profiles.filter((p) => p.name !== name);
    try {
      localStorage.setItem('argus_profiles', JSON.stringify(profiles));
    } catch {}
  }

  const PRESETS = ['tcp:localhost:5770', 'udp:14550', 'udp:14551'];

  async function fetchPorts() {
    try {
      const r = await fetch(apiUrl('/api/ports'));
      const data = await r.json();
      (data.ports || []).forEach((p: string) => {
        if (!portHistory.includes(p)) portHistory.push(p);
      });
    } catch {}
    PRESETS.forEach((p) => {
      if (!portHistory.includes(p)) portHistory.push(p);
    });
  }

  function savePortHistory() {
    if (port && !portHistory.includes(port)) portHistory = [port, ...portHistory].slice(0, 10);
    else if (port) portHistory = [port, ...portHistory.filter((p) => p !== port)].slice(0, 10);
    try {
      localStorage.setItem('argus_port_history', JSON.stringify(portHistory));
      localStorage.setItem('argus_last_port', port);
      localStorage.setItem('argus_last_baud', String(baud));
    } catch {}
  }

  let connectTimeout = $state(false);
  let connectTimer: ReturnType<typeof setTimeout> | null = null;

  function toggle() {
    if (app.drone.connected) {
      sendDisconnect();
    } else {
      // Mutex: USB-direct mode owns drone state; reject WS connect while it's
      // active (see updateState in stores.svelte for the matching defense).
      if (app.activeTransport === 'serial' || isSerialConnected()) {
        addToast(t('conn.serialBusy'), 'error');
        return;
      }
      app.activeTransport = 'ws';
      connecting = true;
      connectTimeout = false;
      savePortHistory();
      sendConnect(port, Number(baud), protocol);
      if (connectTimer) clearTimeout(connectTimer);
      connectTimer = setTimeout(() => {
        if (connecting && !app.drone.connected) {
          connectTimeout = true;
          connecting = false;
          // Connect attempt failed — release the lock so the user can retry
          // or switch transports.
          if (!app.drone.connected) app.activeTransport = 'none';
        }
        connectTimer = null;
      }, 8000);
    }
  }

  $effect(() => {
    if (app.drone.connected) {
      connecting = false;
      connectTimeout = false;
      if (connectTimer) {
        clearTimeout(connectTimer);
        connectTimer = null;
      }
    }
  });

  let serialConnecting = $state(false);
  async function toggleSerial() {
    if (isSerialConnected()) {
      await disconnectSerial();
      app.activeTransport = 'none';
      addToast(t('conn.serialDisconnected'), 'info');
      return;
    }
    // Mutex: WS-backend mode owns drone state; reject serial connect while
    // a backend FC link is up.
    if (app.activeTransport === 'ws' || app.drone.connected) {
      addToast(t('conn.wsBusy'), 'error');
      return;
    }
    app.activeTransport = 'serial';
    serialConnecting = true;
    try {
      // Telemetry→store mapping lives in serialHandlers.ts so the dual-stack
      // state-parity contract can drive the real code.
      const ok = await connectSerial(115200, buildSerialHandlers());
      if (!ok) {
        addToast(t('conn.serialFailed'), 'error');
        app.activeTransport = 'none';
      }
    } catch {
      addToast(t('conn.serialFailed'), 'error');
      app.activeTransport = 'none';
    } finally {
      serialConnecting = false;
    }
  }

  export function isConnecting() {
    return connecting;
  }
  export function isTimeout() {
    return connectTimeout;
  }
</script>

<div class="flex items-center gap-1.5">
  {#if !app.drone.connected}
    <div class="relative">
      <input
        bind:value={port}
        placeholder={t('conn.placeholder')}
        class="w-40 h-7 px-2 text-xs font-mono bg-input border border-border rounded-md text-foreground
                    placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 port-input"
        onfocus={() => (showHistory = true)}
        onblur={() => setTimeout(() => (showHistory = false), 200)}
      />
      {#if showHistory && (portHistory.length > 0 || profiles.length > 0)}
        <div
          class="absolute top-full left-0 right-0 z-[9999] mt-1 bg-popover border border-border rounded-md shadow-lg overflow-hidden min-w-[220px]"
        >
          {#if profiles.length > 0}
            <div class="px-2 pt-1.5 pb-0.5 text-[9px] font-semibold text-muted-foreground/50 uppercase">
              {t('conn.profiles')}
            </div>
            {#each profiles as prof}
              <div class="flex items-center group">
                <button
                  class="flex-1 text-left px-2 py-1.5 text-xs text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                  onmousedown={() => loadProfile(prof)}
                >
                  <span class="font-semibold">{prof.name}</span>
                  <span class="text-[10px] text-muted-foreground ml-1 font-mono">{prof.port}</span>
                </button>
                <button
                  class="px-1.5 opacity-0 group-hover:opacity-60 hover:!opacity-100 text-destructive transition-opacity"
                  onmousedown={() => deleteProfile(prof.name)}
                  title={t('label.delete')}>×</button
                >
              </div>
            {/each}
            <div class="border-t border-border/50"></div>
          {/if}
          {#each portHistory as p}
            <button
              class="block w-full text-left px-2 py-1.5 text-xs font-mono text-popover-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
              onmousedown={() => {
                port = p;
                showHistory = false;
              }}>{p}</button
            >
          {/each}
          <div class="border-t border-border/50">
            <button
              class="block w-full text-left px-2 py-1.5 text-[11px] text-primary hover:bg-accent transition-colors"
              onmousedown={() => {
                showProfileSave = true;
                showHistory = false;
              }}>+ {t('conn.saveProfile')}</button
            >
          </div>
        </div>
      {/if}
      {#if showProfileSave}
        <div
          class="absolute top-full left-0 z-[9999] mt-1 bg-popover border border-border rounded-md shadow-lg p-2 flex gap-1"
        >
          <input
            bind:value={profileName}
            placeholder={t('conn.profileName')}
            class="w-28 h-6 px-1.5 text-xs bg-input border border-border rounded text-foreground"
          />
          <button
            class="px-2 h-6 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90"
            onclick={saveProfile}>{t('conn.saveProfile')}</button
          >
          <button
            class="px-1.5 h-6 text-xs text-muted-foreground hover:text-foreground"
            onclick={() => (showProfileSave = false)}>×</button
          >
        </div>
      {/if}
    </div>
    {#if !port.startsWith('tcp:') && !port.startsWith('udp:')}
      <select
        bind:value={baud}
        class="h-7 px-1 text-xs bg-input border border-border rounded-md text-foreground cursor-pointer"
        title={t('tip.baudRate')}
      >
        <option value={9600}>9600</option>
        <option value={19200}>19200</option>
        <option value={38400}>38400</option>
        <option value={57600}>57600</option>
        <option value={115200}>115200</option>
        <option value={230400}>230400</option>
        <option value={460800}>460800</option>
        <option value={921600}>921600</option>
      </select>
    {/if}
    <select
      bind:value={protocol}
      class="h-7 px-1 text-xs bg-input border border-border rounded-md text-foreground cursor-pointer"
      title={t('conn.protocol')}
    >
      <option value="auto">{t('conn.auto')}</option>
      <option value="standard">{t('conn.standard')}</option>
      <option value="pllink">{t('conn.pllink')}</option>
    </select>
  {/if}
  <Button
    variant={app.drone.connected ? 'destructive' : 'default'}
    size="sm"
    disabled={connecting && !app.drone.connected}
    onclick={toggle}
    class={connecting ? 'animate-pulse' : ''}
  >
    {app.drone.connected ? t('conn.disconnect') : connecting ? t('conn.connecting') : t('conn.connect')}
  </Button>
  {#if !app.drone.connected && !connecting}
    <Button
      variant="outline"
      size="sm"
      class="text-[10px] px-2 opacity-60 hover:opacity-100"
      onclick={() => {
        port = 'udp:14550';
        protocol = 'standard';
        toggle();
      }}
      title={t('tip.sitl')}>SITL</Button
    >
    {#if webSerialAvailable()}
      <Button
        variant="outline"
        size="sm"
        class="text-[10px] px-2 gap-1 {serialConnecting ? 'animate-pulse' : ''} {isSerialConnected()
          ? 'border-success text-success'
          : 'opacity-60 hover:opacity-100'}"
        onclick={toggleSerial}
        title={t('conn.serialTitle')}
      >
        <Usb size={12} />USB
      </Button>
    {/if}
  {/if}
</div>
