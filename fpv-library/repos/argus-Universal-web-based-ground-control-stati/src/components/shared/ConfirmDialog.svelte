<script lang="ts">
  import { confirmState, resolveConfirm } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { AlertTriangle } from '@lucide/svelte';

  let dialogEl: HTMLDivElement | undefined = $state();

  $effect(() => {
    if (confirmState.visible && dialogEl) {
      dialogEl.focus();
    }
  });

  function onKey(e: KeyboardEvent) {
    if (!confirmState.visible) return;
    if (e.key === 'Enter') {
      e.preventDefault();
      resolveConfirm(true);
    }
    if (e.key === 'Escape') resolveConfirm(false);
  }

  function onBackdropKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      resolveConfirm(false);
    }
  }
</script>

<svelte:window onkeydown={onKey} />

{#if confirmState.visible}
  <div
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm"
    role="presentation"
    onclick={() => resolveConfirm(false)}
    onkeydown={onBackdropKeydown}
  >
    <div
      bind:this={dialogEl}
      class="bg-card border border-border rounded-xl shadow-2xl p-5 w-[360px] max-w-[90vw]"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-msg"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div class="flex items-start gap-3 mb-4">
        {#if confirmState.danger}
          <div class="shrink-0 w-9 h-9 rounded-full bg-destructive/15 flex items-center justify-center">
            <AlertTriangle size={18} class="text-destructive" />
          </div>
        {/if}
        <p id="confirm-msg" class="text-sm text-foreground whitespace-pre-line leading-relaxed pt-1.5">
          {confirmState.message}
        </p>
      </div>
      <div class="flex justify-end gap-2">
        <Button variant="outline" size="sm" onclick={() => resolveConfirm(false)}>{t('map.cancel')}</Button>
        <Button variant={confirmState.danger ? 'destructive' : 'default'} size="sm" onclick={() => resolveConfirm(true)}
          >{t('summary.confirm')}</Button
        >
      </div>
    </div>
  </div>
{/if}
