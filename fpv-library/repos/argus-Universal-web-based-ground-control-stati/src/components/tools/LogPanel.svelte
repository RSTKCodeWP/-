<script lang="ts">
  import { logState, startDownload, cancelDownload } from '../../lib/logStore.svelte';
  import { sendCommand } from '../../lib/ws';
  import { isSerialConnected, serialLogList, serialLogDownload, serialLogCancel } from '../../lib/transport';
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X } from '@lucide/svelte';

  function requestList() {
    if (isSerialConnected()) {
      serialLogList().then((res) => {
        if (!res.ok) addToast(`${t('log.fetchList')}: ${res.error}`, 'error', 4000);
      });
      return;
    }
    sendCommand('log_list');
  }

  function downloadLog(id: number, size: number) {
    if (isSerialConnected()) {
      // serialLogDownload calls startDownload internally; calling it twice
      // would clear _chunks mid-stream.
      serialLogDownload(id).then((res) => {
        if (!res.ok) addToast(`${t('log.download')}: ${res.error}`, 'error', 4000);
      });
      return;
    }
    startDownload(id, size);
    sendCommand('log_download', undefined, { id });
  }

  function cancel() {
    if (isSerialConnected()) {
      serialLogCancel();
      return;
    }
    sendCommand('log_cancel');
    cancelDownload();
  }

  function fmtSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }

  function fmtDate(utc: number): string {
    if (utc === 0) return '---';
    const d = new Date(utc * 1000);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  let { onclose }: { onclose: () => void } = $props();
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[520px] max-h-[80vh] flex flex-col overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('log.title')}</h2>
      <div class="flex items-center gap-2">
        <Button variant="default" size="sm" onclick={requestList} disabled={logState.downloading}>
          {t('log.fetchList')}
        </Button>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      {#if logState.downloading}
        <div class="mb-3 p-3 bg-muted/50 rounded-lg">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-foreground">
              {t('log.downloading')}
              {logState.progress > 0 ? logState.progress + '%' : ''}{logState.downloadSpeed
                ? ' | ' + logState.downloadSpeed
                : ''}
            </span>
            <Button variant="destructive" size="xs" onclick={cancel}>{t('log.cancel')}</Button>
          </div>
          <div class="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              class="h-full bg-primary rounded-full transition-all duration-300"
              style="width:{logState.progress > 0 ? logState.progress : 5}%"
            ></div>
          </div>
        </div>
      {/if}

      {#if logState.list.length > 0}
        <div class="rounded-lg border border-border overflow-hidden">
          <div
            class="grid grid-cols-[60px_1fr_100px_80px] gap-2 px-3 py-2 bg-muted/50 text-[11px] text-muted-foreground font-semibold uppercase"
          >
            <span>{t('log.number')}</span>
            <span>{t('log.date')}</span>
            <span class="text-right">{t('log.size')}</span>
            <span class="text-center">{t('log.action')}</span>
          </div>
          {#each logState.list as log (log.id)}
            <div
              class="grid grid-cols-[60px_1fr_100px_80px] gap-2 px-3 py-1.5 items-center text-xs border-t border-border/50 hover:bg-muted/30 transition-colors"
            >
              <span class="font-mono font-bold">#{log.id}</span>
              <span class="text-muted-foreground font-mono">{fmtDate(log.time_utc)}</span>
              <span class="text-right font-mono">{fmtSize(log.size)}</span>
              <div class="text-center">
                <Button
                  variant="outline"
                  size="xs"
                  disabled={logState.downloading}
                  onclick={() => downloadLog(log.id, log.size)}
                >
                  {t('log.download')}
                </Button>
              </div>
            </div>
          {/each}
        </div>
        <div class="mt-2 text-center text-[10px] text-muted-foreground">
          {t('log.total').replace('{n}', String(logState.list.length))}
        </div>
      {:else if !logState.downloading}
        <div class="text-center py-8 text-muted-foreground text-sm">
          {t('log.hint')}
        </div>
      {/if}
    </div>
  </div>
</div>
