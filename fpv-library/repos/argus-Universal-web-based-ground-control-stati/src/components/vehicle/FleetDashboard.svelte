<script lang="ts">
  import { app, addToast } from '../../lib/stores.svelte';
  import { sendCommand } from '../../lib/ws';
  import { t } from '../../lib/i18n.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Radio } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let vehicles = $derived(app.drone.vehicles || []);

  function statusColor(v: { armed?: boolean; t?: number }): string {
    if (v.armed) return 'bg-destructive';
    if (Date.now() / 1000 - (v.t || 0) > 5) return 'bg-muted-foreground/30';
    return 'bg-green-500';
  }

  function switchVehicle(sysid: number) {
    sendCommand('switch_vehicle', sysid);
    addToast(`${t('fleet.switched')} #${sysid}`, 'info');
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[500px] max-h-[80vh] flex flex-col overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Radio size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('fleet.title')}</h2>
        <span class="text-[10px] text-muted-foreground">({vehicles.length + 1} {t('fleet.online')})</span>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 overflow-y-auto p-4 space-y-2">
      <!-- Active vehicle -->
      <div class="p-3 rounded-lg border-2 border-primary bg-primary/5">
        <div class="flex items-center gap-2">
          <div class="w-3 h-3 rounded-full {app.drone.armed ? 'bg-destructive animate-pulse' : 'bg-green-500'}"></div>
          <span class="font-bold text-sm">#{app.drone.vtype_raw > 0 ? 1 : '---'}</span>
          <span class="text-xs text-muted-foreground">{app.drone.vtype || '---'}</span>
          <span class="text-xs ml-auto font-mono text-primary">{t('fleet.active')}</span>
        </div>
        <div class="grid grid-cols-4 gap-2 mt-2 text-[11px]">
          <div>
            <div class="text-muted-foreground/60">{t('telem.battery')}</div>
            <div class="font-mono">{app.drone.voltage.toFixed(1)}V</div>
          </div>
          <div>
            <div class="text-muted-foreground/60">{t('ctrl.altitude')}</div>
            <div class="font-mono">{app.drone.alt_rel.toFixed(1)}m</div>
          </div>
          <div>
            <div class="text-muted-foreground/60">{t('telem.speed')}</div>
            <div class="font-mono">{app.drone.gs.toFixed(1)}m/s</div>
          </div>
          <div>
            <div class="text-muted-foreground/60">{t('label.mode')}</div>
            <div class="font-mono">{app.drone.mode}</div>
          </div>
        </div>
      </div>

      <!-- Other vehicles -->
      {#each vehicles as v}
        <div class="p-3 rounded-lg border border-border hover:bg-muted/30 transition-colors">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full {statusColor(v)}"></div>
            <span class="font-bold text-sm">#{v.sysid}</span>
            <span class="text-xs text-muted-foreground">
              {v.lat.toFixed(5)}, {v.lon.toFixed(5)}
            </span>
            <Button variant="outline" size="xs" class="ml-auto text-[10px]" onclick={() => switchVehicle(v.sysid)}>
              {t('fleet.switch')}
            </Button>
          </div>
          <div class="grid grid-cols-3 gap-2 mt-1.5 text-[10px]">
            <div>
              <div class="text-muted-foreground/60">{t('label.alt')}</div>
              <div class="font-mono">{v.alt.toFixed(1)}m</div>
            </div>
            <div>
              <div class="text-muted-foreground/60">{t('label.hdg')}</div>
              <div class="font-mono">{v.hdg.toFixed(0)}</div>
            </div>
            <div>
              <div class="text-muted-foreground/60">{t('label.armed')}</div>
              <div class="font-mono {v.armed ? 'text-destructive' : ''}">
                {v.armed ? t('label.yes') : t('label.no')}
              </div>
            </div>
          </div>
        </div>
      {/each}

      {#if vehicles.length === 0}
        <div class="text-center py-6 text-muted-foreground/50 text-sm">
          {t('fleet.noOther')}
        </div>
      {/if}
    </div>
  </div>
</div>
