<script lang="ts">
  import { inspectorState } from '../../lib/inspectorStore.svelte';
  import { sendCommand } from '../../lib/ws';
  import { t } from '../../lib/i18n.svelte';
  import { app } from '../../lib/stores.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Terminal, Trash2, Send } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let inputValue = $state('');
  let outputDiv: HTMLDivElement = $state(null!);
  let commandHistory: string[] = $state([]);
  let historyIndex = $state(-1);

  const MAX_HISTORY = 50;

  function submit() {
    const text = inputValue.trim();
    if (!text) return;
    sendCommand('serial_control', undefined, { text });
    if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== text) {
      commandHistory.push(text);
      if (commandHistory.length > MAX_HISTORY) {
        commandHistory.splice(0, commandHistory.length - MAX_HISTORY);
      }
    }
    historyIndex = -1;
    inputValue = '';
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      submit();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (commandHistory.length === 0) return;
      if (historyIndex === -1) {
        historyIndex = commandHistory.length - 1;
      } else if (historyIndex > 0) {
        historyIndex--;
      }
      inputValue = commandHistory[historyIndex];
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex === -1) return;
      if (historyIndex < commandHistory.length - 1) {
        historyIndex++;
        inputValue = commandHistory[historyIndex];
      } else {
        historyIndex = -1;
        inputValue = '';
      }
    }
  }

  function clearConsole() {
    inspectorState.consoleLines.length = 0;
  }

  $effect(() => {
    // track length to trigger scroll on new lines
    inspectorState.consoleLines.length;
    if (outputDiv) {
      // defer to allow DOM update
      requestAnimationFrame(() => {
        outputDiv.scrollTop = outputDiv.scrollHeight;
      });
    }
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[640px] max-w-[95vw] h-[520px] max-h-[85vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <!-- Header -->
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-4 py-2.5 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <Terminal size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('console.title')}</h3>
      </div>
      <div class="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon-xs"
          onclick={clearConsole}
          title={t('inspector.clear')}
          aria-label={t('inspector.clear')}
        >
          <Trash2 size={14} />
        </Button>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}>
          <X size={16} />
        </Button>
      </div>
    </div>

    {#if !app.drone.connected}
      <!-- Not connected state -->
      <div class="flex-1 flex items-center justify-center">
        <p class="text-sm text-muted-foreground">{t('console.notConnected')}</p>
      </div>
    {:else}
      <!-- Terminal output -->
      <div
        bind:this={outputDiv}
        class="flex-1 overflow-y-auto bg-black/90 px-3 py-2 font-mono text-xs leading-relaxed select-text"
      >
        {#if inspectorState.consoleLines.length === 0}
          <p class="text-emerald-600/60 italic">{t('console.hint')}</p>
        {:else}
          {#each inspectorState.consoleLines as line}
            <div class="text-emerald-400 whitespace-pre-wrap break-all">{line}</div>
          {/each}
        {/if}
      </div>

      <!-- Input area -->
      <div class="shrink-0 border-t border-border bg-black/80 px-3 py-2 flex items-center gap-2">
        <span class="text-emerald-500 font-mono text-xs select-none">$</span>
        <input
          type="text"
          bind:value={inputValue}
          onkeydown={handleKeydown}
          placeholder={t('console.placeholder')}
          class="flex-1 bg-transparent border-none outline-none text-emerald-300 font-mono text-xs placeholder:text-emerald-800 caret-emerald-400"
        />
        <Button variant="ghost" size="icon-xs" onclick={submit} aria-label={t('ui.sendCommand')}>
          <Send size={14} class="text-emerald-500" />
        </Button>
      </div>
    {/if}
  </div>
</div>
