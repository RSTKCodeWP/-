<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { t } from '../../lib/i18n.svelte';
  import { paramState } from '../../lib/paramStore.svelte';
  import { X } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Helpers ── */

  function getParam(name: string, fallback: number): number {
    const p = paramState.list.find((p) => p.name === name);
    return p !== undefined ? p.value : fallback;
  }

  let paramsAvailable = $derived(paramState.list.length > 0);

  /* ── Frame class definitions ── */

  interface FrameClassDef {
    value: number;
    labelKey: string;
    ascii: string;
    hasType: boolean;
  }

  const frameClasses: FrameClassDef[] = [
    { value: 1, labelKey: 'frame.quadX', ascii: '  X\n / \\\n|   |\n \\ /\n  X', hasType: true },
    { value: 2, labelKey: 'frame.hexX', ascii: ' X   X\n  \\ /\n   O\n  / \\\n X   X\n  |  |\n  X  X', hasType: true },
    { value: 3, labelKey: 'frame.octaX', ascii: 'X   X\n X X\n  O\n X X\nX   X', hasType: true },
    { value: 4, labelKey: 'frame.octaQuad', ascii: 'XX XX\n  O\nXX XX', hasType: false },
    { value: 5, labelKey: 'frame.triY', ascii: ' X   X\n  \\ /\n   O\n   |\n   X', hasType: false },
    { value: 7, labelKey: 'frame.triY', ascii: ' X\n |\n O\n/ \\\nX   X', hasType: false },
    { value: 13, labelKey: 'frame.single', ascii: '  X\n  |\n  O', hasType: false },
    { value: 15, labelKey: 'frame.plane', ascii: ' __|__\n/  |  \\\n   |\n  / \\', hasType: false },
  ];

  /* ── Frame type definitions (for multi-rotor class with type variants) ── */

  interface FrameTypeDef {
    value: number;
    labelKey: string;
    desc: string;
  }

  const frameTypes: FrameTypeDef[] = [
    { value: 0, labelKey: 'frame.quadPlus', desc: '+' },
    { value: 1, labelKey: 'frame.quadX', desc: 'X' },
    { value: 2, labelKey: 'frame.quadX', desc: 'V' },
    { value: 3, labelKey: 'frame.quadX', desc: 'H' },
    { value: 12, labelKey: 'frame.quadX', desc: 'Y6F' },
  ];

  /* ── State ── */

  let selectedClass = $state(1);
  let selectedType = $state(1);

  /* ── Load current values from paramState (one-shot) ── */
  // paramState.list grows across multiple PARAM_BATCH frames during the
  // initial fetch (~10s, 700-1000 params). A naive $effect would re-fire
  // on every batch and clobber the user's selection mid-stream. Matches
  // the _loaded guard used by sibling panels (FlightModePanel, PidPanel).
  let _loaded = $state(false);
  $effect(() => {
    if (!paramsAvailable || _loaded) return;
    _loaded = true;
    selectedClass = getParam('FRAME_CLASS', 1);
    selectedType = getParam('FRAME_TYPE', 1);
  });

  let currentClassDef = $derived(frameClasses.find((c) => c.value === selectedClass));
  let showTypeGrid = $derived(currentClassDef?.hasType ?? false);

  let currentClassParam = $derived(getParam('FRAME_CLASS', -1));
  let currentTypeParam = $derived(getParam('FRAME_TYPE', -1));

  /* ── Write to FC ── */

  function writeFrame() {
    dispatch('param_set', undefined, { name: 'FRAME_CLASS', value: selectedClass });
    if (showTypeGrid) {
      dispatch('param_set', undefined, { name: 'FRAME_TYPE', value: selectedType });
    }
    addToast(t('frame.saved'), 'success');
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[500px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('frame.title')}</h2>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4">
      {#if !paramsAvailable}
        <div class="p-4 rounded-lg bg-muted/50 border border-border/50 text-center">
          <p class="text-xs text-muted-foreground">{t('param.connectHint')}</p>
        </div>
      {:else}
        <!-- Current values -->
        <div class="flex items-center gap-2 mb-4 text-xs text-muted-foreground">
          <span class="font-semibold">{t('frame.current')}:</span>
          <span class="font-mono">FRAME_CLASS={currentClassParam}</span>
          <span class="font-mono">FRAME_TYPE={currentTypeParam}</span>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- Frame Class grid                              -->
        <!-- ════════════════════════════════════════════ -->
        <div class="mb-4">
          <p class="text-xs font-semibold text-foreground uppercase tracking-wider mb-2">{t('frame.class')}</p>
          <div class="grid grid-cols-4 gap-2">
            {#each frameClasses as fc (fc.value)}
              <button
                class="flex flex-col items-center p-3 rounded-lg border-2 transition-all cursor-pointer
                  {selectedClass === fc.value
                  ? 'border-primary bg-primary/10 shadow-sm'
                  : 'border-border/50 bg-muted/20 hover:border-muted-foreground/30 hover:bg-muted/40'}"
                onclick={() => {
                  selectedClass = fc.value;
                }}
              >
                <pre
                  class="text-[9px] leading-tight font-mono text-center mb-1.5
                  {selectedClass === fc.value ? 'text-primary' : 'text-muted-foreground/70'}">{fc.ascii}</pre>
                <span
                  class="text-[11px] font-medium
                  {selectedClass === fc.value ? 'text-primary' : 'text-foreground'}"
                >
                  {t(fc.labelKey)}
                </span>
                <span class="text-[9px] text-muted-foreground mt-0.5">={fc.value}</span>
              </button>
            {/each}
          </div>
        </div>

        <!-- ════════════════════════════════════════════ -->
        <!-- Frame Type grid (only for multi-rotor)        -->
        <!-- ════════════════════════════════════════════ -->
        {#if showTypeGrid}
          <div class="mb-4">
            <p class="text-xs font-semibold text-foreground uppercase tracking-wider mb-2">{t('frame.type')}</p>
            <div class="grid grid-cols-5 gap-2">
              {#each frameTypes as ft (ft.value)}
                <button
                  class="flex flex-col items-center p-2.5 rounded-lg border-2 transition-all cursor-pointer
                    {selectedType === ft.value
                    ? 'border-primary bg-primary/10 shadow-sm'
                    : 'border-border/50 bg-muted/20 hover:border-muted-foreground/30 hover:bg-muted/40'}"
                  onclick={() => {
                    selectedType = ft.value;
                  }}
                >
                  <span
                    class="text-sm font-bold font-mono mb-1
                    {selectedType === ft.value ? 'text-primary' : 'text-muted-foreground'}"
                  >
                    {ft.desc}
                  </span>
                  <span
                    class="text-[10px]
                    {selectedType === ft.value ? 'text-primary' : 'text-foreground'}"
                  >
                    {ft.desc}
                  </span>
                  <span class="text-[9px] text-muted-foreground mt-0.5">={ft.value}</span>
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Write button -->
        <div class="flex justify-end pt-2">
          <Button
            variant="default"
            size="sm"
            class="h-8 text-xs px-6"
            onclick={writeFrame}
            disabled={!app.drone.connected}
          >
            {t('frame.write')}
          </Button>
        </div>
      {/if}
    </div>
  </div>
</div>
