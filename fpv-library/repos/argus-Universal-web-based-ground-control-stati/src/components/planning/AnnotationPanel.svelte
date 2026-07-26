<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, MapPin, Trash2 } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  interface Annotation {
    id: number;
    name: string;
    note: string;
    lat: number;
    lon: number;
  }

  const STORAGE_KEY = 'argus_annotations';

  let annotations: Annotation[] = $state(loadAnnotations());
  let showForm = $state(false);
  let formName = $state('');
  let formNote = $state('');
  let formLat = $state(0);
  let formLon = $state(0);

  function loadAnnotations(): Annotation[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch {}
    return [];
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(annotations));
    } catch {}
  }

  function addAnnotation() {
    if (!formName.trim()) {
      addToast(t('annotation.name'), 'warn');
      return;
    }
    const id = Date.now();
    annotations.push({
      id,
      name: formName.trim(),
      note: formNote.trim(),
      lat: formLat,
      lon: formLon,
    });
    persist();
    formName = '';
    formNote = '';
    formLat = 0;
    formLon = 0;
    showForm = false;
    addToast(t('annotation.save'), 'success');
  }

  function deleteAnnotation(id: number) {
    const idx = annotations.findIndex((a) => a.id === id);
    if (idx >= 0) {
      annotations.splice(idx, 1);
      persist();
    }
  }

  function clearAll() {
    annotations.length = 0;
    persist();
    addToast(t('annotation.clear'), 'info');
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
    role="presentation"
    class="bg-card border border-border rounded-2xl overflow-hidden w-[450px] max-h-[80vh] shadow-2xl flex flex-col"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <MapPin size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('annotation.title')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="overflow-y-auto px-5 py-3 space-y-3">
      {#if !showForm}
        <Button variant="outline" class="w-full" onclick={() => (showForm = true)}>
          + {t('annotation.add')}
        </Button>
      {:else}
        <div class="bg-muted/30 rounded-lg p-3 space-y-2">
          <div class="flex items-center gap-2">
            <label for="ann-name" class="text-xs text-muted-foreground w-12 shrink-0">{t('annotation.name')}</label>
            <input
              id="ann-name"
              type="text"
              bind:value={formName}
              placeholder="..."
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-2">
            <label for="ann-note" class="text-xs text-muted-foreground w-12 shrink-0">{t('annotation.note')}</label>
            <input
              id="ann-note"
              type="text"
              bind:value={formNote}
              placeholder="..."
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-2">
            <label for="ann-lat" class="text-xs text-muted-foreground w-12 shrink-0">Lat</label>
            <input
              id="ann-lat"
              type="number"
              step="0.000001"
              bind:value={formLat}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex items-center gap-2">
            <label for="ann-lon" class="text-xs text-muted-foreground w-12 shrink-0">Lon</label>
            <input
              id="ann-lon"
              type="number"
              step="0.000001"
              bind:value={formLon}
              class="flex-1 h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
          </div>
          <div class="flex gap-2">
            <Button variant="default" size="sm" class="flex-1" onclick={addAnnotation}>
              {t('annotation.save')}
            </Button>
            <Button variant="ghost" size="sm" onclick={() => (showForm = false)}>
              {t('map.cancel')}
            </Button>
          </div>
        </div>
      {/if}

      {#if annotations.length > 0}
        <div class="space-y-1">
          {#each annotations as ann (ann.id)}
            <div class="flex items-start gap-2 bg-muted/20 rounded-lg p-2 group">
              <MapPin size={14} class="text-primary mt-0.5 shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="text-xs font-medium text-foreground truncate">{ann.name}</div>
                {#if ann.note}
                  <div class="text-[11px] text-muted-foreground truncate">{ann.note}</div>
                {/if}
                <div class="text-[10px] text-muted-foreground font-mono">
                  {ann.lat.toFixed(6)}, {ann.lon.toFixed(6)}
                </div>
              </div>
              <button
                class="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-destructive hover:bg-destructive/10 rounded"
                onclick={() => deleteAnnotation(ann.id)}
              >
                <Trash2 size={13} />
              </button>
            </div>
          {/each}
        </div>

        <Button variant="ghost" size="sm" class="w-full text-destructive" onclick={clearAll}>
          {t('annotation.clear')}
        </Button>
      {:else}
        <div class="text-xs text-muted-foreground text-center py-4 italic">No annotations</div>
      {/if}
    </div>
  </div>
</div>
