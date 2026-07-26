<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { sendCommand } from '../../lib/ws';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Play, Trash2, Save, FileText } from '@lucide/svelte';

  let { onclose: _onclose }: { onclose: () => void } = $props();
  let _aborted = $state(false);

  function onclose() {
    _aborted = true;
    running = false;
    _onclose();
  }

  let code = $state(`// Argus Script Engine
// Available API:
//   drone    — current drone state (read-only)
//   send(cmd, data) — send command
//   wait(ms)  — async delay
//   log(msg)  — output to console
//   waypoints — current waypoint array

log("Vehicle: " + drone.vtype);
log("Mode: " + drone.mode);
log("Position: " + drone.lat + ", " + drone.lon);
log("Alt: " + drone.alt_rel + "m");
`);
  let output: string[] = $state([]);
  let running = $state(false);
  let scripts: { name: string; code: string }[] = $state([]);

  function loadScripts() {
    try {
      const saved = JSON.parse(localStorage.getItem('argus_scripts') || '[]');
      if (Array.isArray(saved)) scripts = saved;
    } catch {}
  }
  loadScripts();

  function saveScript() {
    const name = window.prompt('Script name:') || 'Untitled';
    scripts = [...scripts.filter((s) => s.name !== name), { name, code }];
    try {
      localStorage.setItem('argus_scripts', JSON.stringify(scripts));
    } catch {}
    addToast(`Saved: ${name}`, 'success');
  }

  function loadScript(s: { name: string; code: string }) {
    code = s.code;
  }
  function deleteScript(name: string) {
    scripts = scripts.filter((s) => s.name !== name);
    try {
      localStorage.setItem('argus_scripts', JSON.stringify(scripts));
    } catch {}
  }

  async function runScript() {
    output = [];
    running = true;
    const logs: string[] = [];

    const api = {
      drone: Object.freeze({ ...app.drone }),
      waypoints: Object.freeze([...app.waypoints]),
      send: (cmd: string, data?: Record<string, unknown>) => {
        if (_aborted) throw new Error('Script aborted');
        sendCommand(cmd, undefined, data);
        logs.push(`[CMD] ${cmd} ${JSON.stringify(data || {})}`);
      },
      wait: (ms: number) =>
        new Promise((resolve, reject) => {
          const timer = setTimeout(resolve, Math.min(ms, 10000));
          const check = setInterval(() => {
            if (_aborted) {
              clearTimeout(timer);
              clearInterval(check);
              reject(new Error('Script aborted'));
            }
          }, 100);
          setTimeout(() => clearInterval(check), Math.min(ms, 10000) + 200);
        }),
      log: (msg: string) => {
        logs.push(String(msg));
        output = [...logs];
      },
    };

    // User-authored automation scripts execute intentionally in this GCS context.
    // The API surface is restricted to read-only drone state + command sending.
    try {
      const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
      const fn = new AsyncFunction('drone', 'send', 'wait', 'log', 'waypoints', code);
      await fn(api.drone, api.send, api.wait, api.log, api.waypoints);
      logs.push('[OK] Script completed');
    } catch (err: unknown) {
      logs.push(`[ERROR] ${err instanceof Error ? err.message : String(err)}`);
    }
    output = [...logs];
    running = false;
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[700px] max-h-[85vh] shadow-2xl flex flex-col"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-green-500/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <FileText size={16} class="text-green-400" />
        <h3 class="text-base font-bold text-green-400">{t('panel.script')}</h3>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="default" size="sm" onclick={runScript} disabled={running}>
          <Play size={13} class="mr-1" />{running ? t('panel.script.running') : t('panel.script.run')}
        </Button>
        <Button variant="outline" size="sm" onclick={saveScript}><Save size={13} class="mr-1" />Save</Button>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>
    <div class="flex flex-1 min-h-0">
      {#if scripts.length > 0}
        <div class="w-36 border-r border-border overflow-y-auto p-2 space-y-1">
          {#each scripts as s}
            <div class="flex items-center gap-1 group">
              <button
                class="flex-1 text-left text-xs px-2 py-1 rounded hover:bg-muted transition-colors truncate cursor-pointer border-none bg-transparent text-foreground"
                onclick={() => loadScript(s)}>{s.name}</button
              >
              <button
                class="opacity-0 group-hover:opacity-60 text-destructive border-none bg-transparent cursor-pointer px-0.5"
                onclick={() => deleteScript(s.name)}><Trash2 size={10} /></button
              >
            </div>
          {/each}
        </div>
      {/if}
      <div class="flex-1 flex flex-col min-h-0">
        <textarea
          bind:value={code}
          class="flex-1 min-h-[200px] p-3 bg-black/80 text-green-300 font-mono text-xs resize-none border-none outline-none"
          spellcheck="false"
        ></textarea>
        <div class="h-32 overflow-y-auto bg-black/90 border-t border-border p-2 font-mono text-[11px]">
          {#each output as line}
            <div
              class={line.startsWith('[ERROR]')
                ? 'text-destructive'
                : line.startsWith('[CMD]')
                  ? 'text-warning'
                  : line.startsWith('[OK]')
                    ? 'text-success'
                    : 'text-muted-foreground'}
            >
              {line}
            </div>
          {/each}
          {#if output.length === 0}
            <span class="text-muted-foreground/40">Output will appear here...</span>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>
