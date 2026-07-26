<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { dispatch } from '../../lib/transport';
  import { paramState } from '../../lib/paramStore.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Upload, ArrowRight, Check } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  type FilterTab = 'all' | 'diff' | 'same' | 'fileOnly' | 'currentOnly';

  let fileParams = $state<Map<string, number> | null>(null);
  let fileName = $state('');
  let filter = $state<FilterTab>('all');
  let search = $state('');
  let applied = $state<Set<string>>(new Set());

  function parseParamFile(text: string): Map<string, number> {
    const map = new Map<string, number>();
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const parts = trimmed.split(/[\t,\s]+/);
      if (parts.length >= 2) {
        const name = parts[0], val = parseFloat(parts[1]);
        if (!isNaN(val)) map.set(name, val);
      }
    }
    return map;
  }

  function loadFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.param,.txt';
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      fileName = file.name;
      const reader = new FileReader();
      reader.onload = (ev: ProgressEvent<FileReader>) => {
        const text = ev.target!.result as string;
        fileParams = parseParamFile(text);
        filter = 'diff';
        applied = new Set();
      };
      reader.readAsText(file);
    };
    input.click();
  }

  interface DiffRow {
    name: string;
    current: number | undefined;
    file: number | undefined;
    status: 'same' | 'diff' | 'fileOnly' | 'currentOnly';
  }

  // $derived.by builds the Map directly; the previous form wrapped a function,
  // so callers had to invoke `currentMap()` and the value wasn't memoised.
  let currentMap = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of paramState.list) m.set(p.name, p.value);
    return m;
  });

  let allRows = $derived.by((): DiffRow[] => {
    if (!fileParams) return [];
    const cur = currentMap;
    const rows: DiffRow[] = [];
    const seen = new Set<string>();

    // parameters in file
    for (const [name, fval] of fileParams) {
      seen.add(name);
      const cval = cur.get(name);
      let status: DiffRow['status'];
      if (cval === undefined) {
        status = 'fileOnly';
      } else if (Math.abs(cval - fval) < 1e-6) {
        status = 'same';
      } else {
        status = 'diff';
      }
      rows.push({ name, current: cval, file: fval, status });
    }

    // parameters only in current
    for (const [name, cval] of cur) {
      if (!seen.has(name)) {
        rows.push({ name, current: cval, file: undefined, status: 'currentOnly' });
      }
    }

    rows.sort((a, b) => a.name.localeCompare(b.name));
    return rows;
  });

  let filtered = $derived.by(() => {
    let list = allRows;
    if (filter !== 'all') {
      list = list.filter(r => r.status === filter);
    }
    if (search) {
      const q = search.toUpperCase();
      list = list.filter(r => r.name.toUpperCase().includes(q));
    }
    return list;
  });

  let diffCount = $derived(allRows.filter(r => r.status === 'diff').length);
  let sameCount = $derived(allRows.filter(r => r.status === 'same').length);
  let fileOnlyCount = $derived(allRows.filter(r => r.status === 'fileOnly').length);
  let currentOnlyCount = $derived(allRows.filter(r => r.status === 'currentOnly').length);

  function tabCount(tab: FilterTab): number {
    if (tab === 'all') return allRows.length;
    if (tab === 'diff') return diffCount;
    if (tab === 'same') return sameCount;
    if (tab === 'fileOnly') return fileOnlyCount;
    return currentOnlyCount;
  }

  function fmtValue(v: number | undefined): string {
    if (v === undefined) return '-';
    if (Number.isInteger(v) || Math.abs(v) >= 100) return v.toFixed(0);
    if (Math.abs(v) >= 1) return v.toFixed(2);
    return v.toFixed(4);
  }

  function applyOne(name: string, value: number) {
    dispatch('param_set', undefined, { name, value });
    applied.add(name);
    applied = new Set(applied);
    addToast(`${name} = ${value}`, 'info', 2000);
  }

  function applyAllDiff() {
    let count = 0;
    for (const row of allRows) {
      if (row.status === 'diff' && row.file !== undefined && !applied.has(row.name)) {
        dispatch('param_set', undefined, { name: row.name, value: row.file });
        applied.add(row.name);
        count++;
      }
    }
    applied = new Set(applied);
    addToast(t('paramdiff.count').replace('{n}', String(count)), 'success');
  }

  function rowBg(row: DiffRow): string {
    if (applied.has(row.name)) return 'bg-primary/10';
    if (row.status === 'same') return 'bg-emerald-500/5';
    if (row.status === 'diff') return 'bg-amber-500/10';
    return 'bg-muted/30';
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }

  const TABS: { key: FilterTab; i18nKey: string }[] = [
    { key: 'all', i18nKey: 'paramdiff.title' },
    { key: 'diff', i18nKey: 'paramdiff.diff' },
    { key: 'same', i18nKey: 'paramdiff.same' },
    { key: 'fileOnly', i18nKey: 'paramdiff.onlyFile' },
    { key: 'currentOnly', i18nKey: 'paramdiff.onlyCurrent' },
  ];
</script>

<svelte:window onkeydown={onKey} />

<div role="dialog" aria-modal="true" tabindex="-1" class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm"
     onclick={onclose} onkeydown={(e) => { if (e.key === "Escape") onclose(); }}>
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[600px] max-w-[95vw] max-h-[85vh] flex flex-col"
       role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>

    <!-- Header -->
    <div class="flex items-center justify-between px-4 pt-4 pb-2">
      <div class="flex items-center gap-2">
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('paramdiff.title')}</h2>
        {#if fileName}
          <span class="text-[10px] text-muted-foreground/60 font-mono truncate max-w-[200px]">{fileName}</span>
        {/if}
      </div>
      <button class="text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-none p-1"
              onclick={onclose}>
        <X size={16} />
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 min-h-0 flex flex-col px-4 pb-4 gap-2">
      {#if paramState.list.length === 0}
        <!-- No params loaded -->
        <div class="flex-1 flex items-center justify-center">
          <p class="text-sm text-muted-foreground">{t('paramdiff.hint')}</p>
        </div>
      {:else if !fileParams}
        <!-- File not loaded yet -->
        <div class="flex-1 flex items-center justify-center">
          <Button variant="default" size="default" onclick={loadFile}>
            <Upload size={14} class="mr-1.5" />
            {t('paramdiff.loadFile')}
          </Button>
        </div>
      {:else}
        <!-- Summary -->
        <div class="flex items-center justify-between">
          <span class="text-xs text-muted-foreground">
            {#if diffCount > 0}
              {t('paramdiff.count').replace('{n}', String(diffCount))}
            {:else}
              {t('paramdiff.noDiff')}
            {/if}
          </span>
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" onclick={loadFile}>
              <Upload size={12} class="mr-1" />
              {t('paramdiff.loadFile')}
            </Button>
            {#if diffCount > 0}
              <Button variant="default" size="sm" onclick={applyAllDiff}>
                <Check size={12} class="mr-1" />
                {t('paramdiff.applyAll')}
              </Button>
            {/if}
          </div>
        </div>

        <!-- Filter tabs -->
        <div class="flex flex-wrap gap-1">
          {#each TABS as tab}
            {@const count = tabCount(tab.key)}
            <button class="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] rounded-md border transition-all cursor-pointer
              {filter === tab.key
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-card text-muted-foreground border-border hover:text-foreground hover:bg-muted'}"
                    onclick={() => filter = tab.key}>
              {t(tab.i18nKey)}
              <span class="text-[9px] opacity-60">{count}</span>
            </button>
          {/each}
        </div>

        <!-- Search -->
        <input type="text" placeholder={t('label.search')} bind:value={search}
               class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50" />

        <!-- Table header -->
        <div class="flex items-center gap-2 px-2 py-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border">
          <div class="w-[180px] shrink-0">{t('param.title')}</div>
          <div class="flex-1 text-right">{t('paramdiff.current')}</div>
          <div class="w-5 shrink-0"></div>
          <div class="flex-1 text-right">{t('paramdiff.file')}</div>
          <div class="w-16 shrink-0"></div>
        </div>

        <!-- Diff rows -->
        <div class="flex-1 min-h-0 overflow-y-auto rounded-lg border border-border">
          {#each filtered as row (row.name)}
            <div class="flex items-center gap-2 px-2 py-1.5 text-xs border-b border-border/50 transition-colors {rowBg(row)}">
              <div class="w-[180px] shrink-0 font-bold font-mono text-[11px] leading-tight truncate" title={row.name}>
                {row.name}
              </div>
              <div class="flex-1 text-right font-mono text-[11px]
                {row.status === 'currentOnly' ? 'text-muted-foreground' : row.status === 'fileOnly' ? 'text-muted-foreground/40' : ''}">
                {fmtValue(row.current)}
              </div>
              <div class="w-5 shrink-0 flex items-center justify-center">
                {#if row.status === 'diff'}
                  <ArrowRight size={10} class="text-amber-500" />
                {:else if row.status === 'same'}
                  <Check size={10} class="text-emerald-500" />
                {/if}
              </div>
              <div class="flex-1 text-right font-mono text-[11px]
                {row.status === 'fileOnly' ? 'text-muted-foreground' : row.status === 'currentOnly' ? 'text-muted-foreground/40' : ''}
                {row.status === 'diff' ? 'text-amber-500 font-semibold' : ''}">
                {fmtValue(row.file)}
              </div>
              <div class="w-16 shrink-0 flex justify-end">
                {#if row.status === 'diff' && row.file !== undefined && !applied.has(row.name)}
                  <Button variant="outline" size="xs" onclick={() => applyOne(row.name, row.file!)}>
                    {t('paramdiff.apply')}
                  </Button>
                {:else if applied.has(row.name)}
                  <span class="text-[10px] text-emerald-500 flex items-center gap-0.5">
                    <Check size={10} />
                  </span>
                {/if}
              </div>
            </div>
          {/each}
          {#if filtered.length === 0}
            <div class="text-center py-6 text-muted-foreground text-xs">{t('paramdiff.noDiff')}</div>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>
