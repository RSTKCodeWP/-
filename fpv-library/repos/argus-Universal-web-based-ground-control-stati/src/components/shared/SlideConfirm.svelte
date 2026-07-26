<script lang="ts">
  import { slideState, completeSlide, cancelSlide } from '../../lib/stores.svelte';
  import { ChevronRight, Check } from '@lucide/svelte';

  let trackEl: HTMLDivElement = $state(null!);
  let dragging = $state(false);
  let progress = $state(0);
  let done = $state(false);
  let trackW = $state(288);

  const HANDLE = 44;

  const COLORS: Record<string, { bg: string; fill: string }> = {
    orange: { bg: '#ea580c', fill: 'rgba(234,88,12,0.25)' },
    red: { bg: '#dc2626', fill: 'rgba(220,38,38,0.25)' },
    teal: { bg: '#0d9488', fill: 'rgba(13,148,136,0.25)' },
    blue: { bg: '#2563eb', fill: 'rgba(37,99,235,0.25)' },
  };

  let c = $derived(COLORS[slideState.color] || COLORS.orange);
  let maxTravel = $derived(trackW - HANDLE - 8);
  let offsetPx = $derived(progress * maxTravel);

  function onDown(e: PointerEvent) {
    if (done) return;
    dragging = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    if (trackEl) trackW = trackEl.clientWidth;
  }

  function onMove(e: PointerEvent) {
    if (!dragging || !trackEl || done) return;
    const rect = trackEl.getBoundingClientRect();
    const x = e.clientX - rect.left - HANDLE / 2 - 4;
    progress = Math.max(0, Math.min(1, x / maxTravel));
    if (progress >= 0.85) {
      done = true;
      dragging = false;
      progress = 1;
      setTimeout(() => completeSlide(), 300);
    }
  }

  function onUp() {
    dragging = false;
    if (!done) progress = 0;
  }

  $effect(() => {
    if (slideState.visible) {
      progress = 0;
      done = false;
      requestAnimationFrame(() => {
        if (trackEl) trackW = trackEl.clientWidth;
      });
    }
  });

  $effect(() => {
    if (!slideState.visible) return;
    const timer = setTimeout(cancelSlide, 8000);
    return () => clearTimeout(timer);
  });
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key === 'Escape' && slideState.visible) cancelSlide();
  }}
/>

{#if slideState.visible}
  <div
    role="presentation"
    class="slide-backdrop"
    onclick={cancelSlide}
    onkeydown={(e) => {
      if (e.key === 'Escape') cancelSlide();
    }}
  >
    <div
      role="presentation"
      class="slide-container"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <div bind:this={trackEl} class="slide-track">
        <div class="slide-fill" style="width: {progress * 100}%; background: {c.fill}"></div>
        <div class="slide-label" style="color: {c.bg}; opacity: {done ? 1 : 0.5}">
          {#if done}
            <Check size={16} class="inline -mt-0.5 mr-0.5" />OK
          {:else}
            {slideState.text}
          {/if}
        </div>
        <div
          class="slide-handle"
          role="slider"
          tabindex="0"
          aria-label={slideState.text}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          style="background: {c.bg}; transform: translateX({offsetPx}px); transition: {dragging
            ? 'none'
            : 'transform 0.3s ease-out'}"
          onpointerdown={onDown}
          onpointermove={onMove}
          onpointerup={onUp}
          onpointercancel={onUp}
        >
          {#if done}<Check size={18} />{:else}<ChevronRight size={18} />{/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .slide-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9998;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding-bottom: 5rem;
    background: rgba(0, 0, 0, 0.15);
    animation: fadeIn 0.15s ease-out;
  }
  .slide-container {
    width: 20rem;
    animation: slideUp 0.2s ease-out;
  }
  .slide-track {
    position: relative;
    height: 3rem;
    border-radius: 9999px;
    overflow: hidden;
    background: hsl(var(--card) / 0.95);
    backdrop-filter: blur(12px);
    border: 1px solid hsl(var(--border));
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  }
  .slide-fill {
    position: absolute;
    inset: 0;
    right: auto;
    border-radius: 9999px;
  }
  .slide-label {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.875rem;
    font-weight: 700;
    pointer-events: none;
    user-select: none;
  }
  .slide-handle {
    position: absolute;
    top: 4px;
    left: 4px;
    width: 40px;
    height: 40px;
    border-radius: 9999px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: grab;
    color: white;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    touch-action: none;
  }
  .slide-handle:active {
    cursor: grabbing;
  }
  @keyframes fadeIn {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes slideUp {
    from {
      transform: translateY(10px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
</style>
