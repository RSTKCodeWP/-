<script lang="ts">
  import { app, clearEvents } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let logEl: HTMLDivElement;
  let filter = $state('');
  let sevFilter = $state<'all' | 'warn' | 'error'>('all');

  type SevLevel = 'critical' | 'error' | 'warn' | 'ok' | 'info';

  const CRITICAL_TYPES = new Set(['rtl', 'force_disarm']);
  const ERROR_TYPES = new Set([
    'cmd_ack_fail',
    'mission_ack_fail',
    'fence_ack_fail',
    'connect_fail',
    'reconnect_fail',
    'reconnect_err',
    'link_lost',
  ]);
  const WARN_TYPES = new Set(['reconnecting']);
  const OK_TYPES = new Set([
    'connected',
    'reconnected',
    'armed',
    'mission_ack_ok',
    'fence_ack_ok',
    'param_done',
    'mission_dl_done',
    'log_dl_done',
  ]);

  function severity(ev: { text: string; event_type: string }): SevLevel {
    const et = ev.event_type;
    if (et) {
      if (CRITICAL_TYPES.has(et)) return 'critical';
      if (ERROR_TYPES.has(et)) return 'error';
      if (WARN_TYPES.has(et)) return 'warn';
      if (OK_TYPES.has(et)) return 'ok';
    }
    if (ev.text.includes('!!!')) return 'critical';
    return 'info';
  }

  let filtered = $derived.by(() => {
    let list = app.events;
    if (sevFilter === 'error') list = list.filter((e) => severity(e) === 'critical' || severity(e) === 'error');
    else if (sevFilter === 'warn') list = list.filter((e) => severity(e) !== 'info' && severity(e) !== 'ok');
    if (filter) {
      const lf = filter.toLowerCase();
      list = list.filter((e) => e.text.toLowerCase().includes(lf) || e.time.includes(filter));
    }
    return list;
  });

  const sevStyle: Record<SevLevel, string> = {
    critical: 'bg-destructive/15 text-destructive',
    error: 'bg-destructive/8 text-red-300',
    warn: 'text-warning',
    ok: 'text-success',
    info: '',
  };

  const sevDot: Record<SevLevel, string> = {
    critical: 'bg-red-500',
    error: 'bg-red-400',
    warn: 'bg-yellow-500',
    ok: 'bg-green-500',
    info: 'bg-muted-foreground/30',
  };

  function exportLog() {
    if (!app.events.length) return;
    const lines = app.events.map((e) => `${e.time}\t${e.text}`).join('\n');
    const blob = new Blob([lines], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'events_' + new Date().toISOString().slice(0, 16).replace(':', '') + '.txt';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  $effect(() => {
    if (app.events.length && logEl) {
      logEl.scrollTop = logEl.scrollHeight;
    }
  });
</script>

<div class="bg-card border-t border-border p-2">
  <div class="flex items-center justify-between mb-1.5">
    <h2 class="text-[11px] font-semibold text-primary uppercase tracking-wider">{t('event.title')}</h2>
    <div class="flex items-center gap-1.5">
      {#each [['all', t('event.all')], ['warn', t('event.warn')], ['error', t('event.error')]] as [key, label]}
        <button
          class="px-1.5 py-px rounded text-[10px] font-semibold transition-all
          {sevFilter === key ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}"
          onclick={() => (sevFilter = key as typeof sevFilter)}>{label}</button
        >
      {/each}
      <Button variant="ghost" size="xs" onclick={() => clearEvents()} disabled={app.events.length === 0}
        >{t('event.clear')}</Button
      >
      <Button variant="outline" size="xs" onclick={exportLog}>{t('event.export')}</Button>
      <input
        bind:value={filter}
        placeholder={t('tip.filter')}
        class="w-20 h-5 px-1.5 text-[11px] bg-input border border-border rounded text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
      />
    </div>
  </div>
  <div
    bind:this={logEl}
    class="bg-background rounded-lg p-2 h-24 max-sm:h-16 overflow-y-auto text-xs font-mono"
    aria-live="polite"
    aria-label={t('ui.eventLog')}
  >
    {#each filtered as ev}
      {@const sev = severity(ev)}
      <div class="flex items-start gap-1.5 py-0.5 px-1 border-b border-border/50 rounded {sevStyle[sev]}">
        <span class="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 {sevDot[sev]}"></span>
        <span class="text-muted-foreground shrink-0">{ev.time}</span>
        <span class="min-w-0">{ev.text}</span>
      </div>
    {:else}
      <div class="text-muted-foreground text-center py-3">{t('event.empty')}</div>
    {/each}
  </div>
</div>
