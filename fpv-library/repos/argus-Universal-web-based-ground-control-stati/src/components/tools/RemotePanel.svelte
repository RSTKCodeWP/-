<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { apiUrl } from '../../lib/backend';
  import { X, Wifi, Users } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Session polling ── */
  let clientCount = $state(0);
  let fetchError = $state(false);

  async function fetchSession() {
    try {
      const res = await fetch(apiUrl('/api/session'));
      if (res.ok) {
        const data = await res.json();
        clientCount = data.clients ?? data.count ?? 0;
        fetchError = false;
      } else {
        fetchError = true;
      }
    } catch {
      fetchError = true;
    }
  }

  $effect(() => {
    fetchSession();
    const id = setInterval(fetchSession, 5000);
    return () => clearInterval(id);
  });

  /* ── Link freshness ──
   * ms since the last telemetry frame. `age` is SECONDS (backend rounds to
   * 0.1s in drone_link.py:433 as time.time() - last_frame_time), so it must be
   * ×1000 for milliseconds — the previous Math.round(seconds) collapsed every
   * healthy link to ~0 ms, making the 200/500 ms color thresholds dead. This is
   * frame staleness (how far behind the link is), not a round-trip ping. */
  let latencyMs = $derived.by(() => {
    const hist = app.linkHistory;
    if (hist.length < 1) return -1;
    const last = hist[hist.length - 1];
    return Math.round(last.age * 1000);
  });

  /* ── Copy URL helper ── */
  let copied = $state(false);
  function copyUrl() {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => {
        copied = true;
        setTimeout(() => {
          copied = false;
        }, 2000);
      })
      .catch(() => {});
  }
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[420px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Wifi size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('remote.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
      <!-- Status section -->
      <div class="space-y-2">
        <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('remote.status')}</span>

        <div class="p-3 rounded-lg bg-muted/30 border border-border space-y-2">
          <!-- Backend URL -->
          <div class="flex items-center justify-between text-xs">
            <span class="text-muted-foreground">Backend URL</span>
            <span class="font-mono text-foreground truncate max-w-[200px]">{apiUrl('') || window.location.origin}</span>
          </div>

          <!-- WebSocket -->
          <div class="flex items-center justify-between text-xs">
            <span class="text-muted-foreground">WebSocket</span>
            <span class="font-medium {app.wsConnected ? 'text-green-500' : 'text-destructive'}">
              {app.wsConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          <!-- Connected clients -->
          <div class="flex items-center justify-between text-xs">
            <span class="text-muted-foreground">{t('remote.clients')}</span>
            <div class="flex items-center gap-1.5">
              <Users size={12} class="text-muted-foreground" />
              <span class="font-mono font-medium text-foreground">
                {fetchError ? '---' : clientCount}
              </span>
            </div>
          </div>

          <!-- Latency -->
          <div class="flex items-center justify-between text-xs">
            <span class="text-muted-foreground">{t('remote.latency')}</span>
            <span
              class="font-mono font-medium {latencyMs >= 0 && latencyMs < 200
                ? 'text-green-500'
                : latencyMs >= 200 && latencyMs < 500
                  ? 'text-yellow-500'
                  : 'text-muted-foreground'}"
            >
              {latencyMs >= 0 ? `${latencyMs} ms` : '---'}
            </span>
          </div>
        </div>
      </div>

      <!-- Share section -->
      <div class="space-y-2">
        <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Share</span>

        <div class="p-3 rounded-lg bg-muted/30 border border-border space-y-3">
          <p class="text-xs text-muted-foreground">Share this URL with team members to observe the flight session.</p>

          <div class="flex items-center gap-2">
            <div
              class="flex-1 bg-background border border-border rounded px-2 py-1.5 text-xs font-mono text-foreground truncate"
            >
              {window.location.href}
            </div>
            <Button variant="outline" size="xs" onclick={copyUrl}>
              {copied ? 'Copied!' : 'Copy URL'}
            </Button>
          </div>
        </div>
      </div>

      <!-- Hint -->
      <div class="p-3 rounded-lg bg-primary/5 border border-primary/20">
        <p class="text-xs text-muted-foreground leading-relaxed">
          {t('remote.hint')}
        </p>
      </div>
    </div>
  </div>
</div>
