<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { inspectorState } from '../../lib/inspectorStore.svelte';
  import { sendCommand } from '../../lib/ws';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Pause, Play, Trash2, Search } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let filter = $state('');
  let expandedId = $state<number | null>(null);
  let sorted = $derived.by(() => {
    let msgs = [...inspectorState.messages];
    if (filter) {
      const q = filter.toLowerCase();
      msgs = msgs.filter((m) => String(m.id).includes(q) || m.name.toLowerCase().includes(q));
    }
    msgs.sort((a, b) => b.hz - a.hz);
    return msgs;
  });

  function togglePause() {
    inspectorState.paused = !inspectorState.paused;
  }

  function clearMessages() {
    inspectorState.messages = [];
    expandedId = null;
  }

  function toggleExpand(id: number) {
    expandedId = expandedId === id ? null : id;
  }

  function fmtHz(hz: number): string {
    if (hz >= 100) return hz.toFixed(0);
    if (hz >= 10) return hz.toFixed(1);
    return hz.toFixed(2);
  }

  function fmtFieldValue(v: unknown): string {
    if (typeof v === 'number') {
      if (Number.isInteger(v)) return String(v);
      return v.toFixed(4);
    }
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (v === null || v === undefined) return 'null';
    if (Array.isArray(v)) return `[${v.join(', ')}]`;
    return String(v);
  }

  onMount(() => {
    sendCommand('inspector_toggle');
  });

  onDestroy(() => {
    sendCommand('inspector_toggle');
    inspectorState.paused = false;
  });
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[700px] max-w-[90vw] max-h-[80vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <h3 class="text-base font-bold text-primary">{t('inspector.title')}</h3>
        {#if inspectorState.paused}
          <span
            class="px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-warning/20 text-warning border border-warning/50 rounded"
          >
            {t('inspector.paused')}
          </span>
        {/if}
      </div>
      <div class="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-xs"
          onclick={togglePause}
          title={inspectorState.paused ? t('inspector.resume') : t('inspector.pause')}
          aria-label={inspectorState.paused ? t('inspector.resume') : t('inspector.pause')}
        >
          {#if inspectorState.paused}<Play size={14} />{:else}<Pause size={14} />{/if}
        </Button>
        <Button
          variant="ghost"
          size="icon-xs"
          onclick={clearMessages}
          title={t('inspector.clear')}
          aria-label={t('inspector.clear')}
        >
          <Trash2 size={14} />
        </Button>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>

    <div class="px-4 py-2 shrink-0">
      <div class="relative">
        <Search size={14} class="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <input
          type="text"
          placeholder={t('inspector.filter')}
          bind:value={filter}
          class="w-full h-7 pl-7 pr-2 text-xs bg-input border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50"
        />
      </div>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto px-4 pb-3">
      {#if sorted.length === 0}
        <div class="text-center py-8 text-muted-foreground text-sm">{t('inspector.noData')}</div>
      {:else}
        <table class="w-full text-xs">
          <thead class="sticky top-0 bg-card z-10">
            <tr class="text-[10px] text-muted-foreground uppercase tracking-wider border-b border-border">
              <th class="text-left py-1.5 px-1 w-16 font-semibold">{t('inspector.msgId')}</th>
              <th class="text-left py-1.5 px-1 font-semibold">{t('inspector.name')}</th>
              <th class="text-right py-1.5 px-1 w-16 font-semibold">{t('inspector.hz')}</th>
              <th class="text-right py-1.5 px-1 w-16 font-semibold">{t('inspector.count')}</th>
              <th class="text-right py-1.5 px-1 w-14 font-semibold">{t('inspector.size')}</th>
            </tr>
          </thead>
          <tbody>
            {#each sorted as msg (msg.id)}
              <tr
                class="border-b border-border/30 hover:bg-muted/50 cursor-pointer transition-colors {expandedId ===
                msg.id
                  ? 'bg-muted/30'
                  : ''}"
                tabindex="0"
                role="button"
                onclick={() => toggleExpand(msg.id)}
                onkeydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggleExpand(msg.id);
                  }
                }}
              >
                <td class="py-1 px-1 font-mono text-muted-foreground">{msg.id}</td>
                <td class="py-1 px-1 font-semibold text-foreground">{msg.name}</td>
                <td class="py-1 px-1 text-right font-mono text-primary">{fmtHz(msg.hz)}</td>
                <td class="py-1 px-1 text-right font-mono text-muted-foreground">{msg.count}</td>
                <td class="py-1 px-1 text-right font-mono text-muted-foreground">{msg.size}</td>
              </tr>
              {#if expandedId === msg.id}
                <tr>
                  <td colspan="5" class="px-1 pb-2">
                    <div class="bg-muted/40 border border-border/50 rounded-md p-2 mt-0.5">
                      <div class="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 font-semibold">
                        {t('inspector.lastValue')}
                      </div>
                      {#if msg.last_fields && Object.keys(msg.last_fields).length > 0}
                        <div class="grid grid-cols-2 gap-x-4 gap-y-0.5">
                          {#each Object.entries(msg.last_fields) as [key, val]}
                            <div class="flex items-baseline gap-1.5 text-[11px]">
                              <span class="text-muted-foreground shrink-0">{key}:</span>
                              <span class="font-mono text-foreground truncate">{fmtFieldValue(val)}</span>
                            </div>
                          {/each}
                        </div>
                      {:else}
                        <span class="text-[11px] text-muted-foreground/60">--</span>
                      {/if}
                    </div>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  </div>
</div>
