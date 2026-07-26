<script lang="ts">
  import { app, dismissToast } from '../../lib/stores.svelte';
  import { Check, AlertTriangle, X as XIcon, Info } from '@lucide/svelte';

  function toastClass(level: string): string {
    if (level === 'success') return 'bg-green-700 text-white';
    if (level === 'warn') return 'bg-amber-600 text-white';
    if (level === 'error') return 'bg-red-700 text-white';
    return 'bg-primary text-primary-foreground';
  }
</script>

{#if app.toasts.length > 0}
  <div class="fixed top-16 right-5 z-[10000] flex flex-col gap-1.5 pointer-events-none">
    {#each app.toasts as t (t.id)}
      <div
        role="presentation"
        class="pointer-events-auto flex items-center gap-2 px-4 py-2 rounded-lg text-sm cursor-pointer
                  max-w-[350px] shadow-lg animate-in slide-in-from-right {toastClass(t.level)}"
        onclick={() => dismissToast(t.id)}
      >
        <span class="shrink-0">
          {#if t.level === 'success'}<Check size={16} strokeWidth={3} />
          {:else if t.level === 'warn'}<AlertTriangle size={16} />
          {:else if t.level === 'error'}<XIcon size={16} strokeWidth={3} />
          {:else}<Info size={16} />
          {/if}
        </span>
        {t.text}
        {#if t.count > 1}
          <span class="ml-1 px-1.5 py-px rounded-full bg-white/20 text-[10px] font-bold leading-none"
            >&times;{t.count}</span
          >
        {/if}
      </div>
    {/each}
  </div>
{/if}

<style>
  @keyframes slide-in-from-right {
    from {
      opacity: 0;
      transform: translateX(40px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  .animate-in {
    animation: slide-in-from-right 0.3s ease;
  }
</style>
