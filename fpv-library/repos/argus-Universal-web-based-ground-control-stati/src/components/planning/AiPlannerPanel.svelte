<script lang="ts">
  import { app, pushUndo, saveWaypoints, addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import type { Waypoint } from '../../lib/types';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, Sparkles, Send, Loader2 } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let prompt = $state('');
  let history: { role: 'user' | 'ai'; text: string }[] = $state([]);
  let loading = $state(false);

  const EXAMPLES = [
    'Plan a rectangular survey at 50m altitude, 200m x 300m, centered on current position',
    'Create a 6-waypoint circle with 100m radius at 30m altitude',
    'Add a waypoint at 500m north of home at 40m',
    'Reverse the current route',
  ];

  async function send() {
    if (!prompt.trim()) return;
    const userMsg = prompt.trim();
    history.push({ role: 'user', text: userMsg });
    prompt = '';
    loading = true;

    const context = {
      currentPosition: { lat: app.drone.lat, lon: app.drone.lon, alt: app.drone.alt_rel },
      homePosition: { lat: app.drone.home_lat, lon: app.drone.home_lon },
      waypointCount: app.waypoints.length,
      defaultAlt: app.defaultAlt,
      defaultSpeed: app.defaultSpeed,
      vehicleType: app.drone.vtype,
    };

    const result = parseLocalCommand(userMsg, context);
    if (result) {
      history.push({ role: 'ai', text: result.message });
      if (result.waypoints) {
        pushUndo();
        app.waypoints = [...app.waypoints, ...result.waypoints];
        saveWaypoints();
        addToast(`AI: +${result.waypoints.length} waypoints`, 'success');
      }
    } else {
      history.push({
        role: 'ai',
        text: 'I can help with: circle routes, survey grids, adding waypoints by direction/distance, reversing routes. Try one of the examples below.',
      });
    }
    loading = false;
  }

  interface PlanContext {
    currentPosition: { lat: number; lon: number; alt: number };
    homePosition: { lat: number; lon: number };
    waypointCount: number;
    defaultAlt: number;
    defaultSpeed: number;
    vehicleType: string;
  }

  function parseLocalCommand(text: string, ctx: PlanContext): { message: string; waypoints?: Waypoint[] } | null {
    const lower = text.toLowerCase();

    if (lower.includes('circle') || lower.includes('圆') || lower.includes('环绕')) {
      const radiusMatch = lower.match(/(\d+)\s*m?\s*(?:radius|半径)/i) || lower.match(/(?:radius|半径)\s*(\d+)/i);
      const radius = radiusMatch ? parseInt(radiusMatch[1]) : 100;
      const countMatch = lower.match(/(\d+)[\s-]*(waypoint|point|点|wp)/i);
      const count = countMatch ? parseInt(countMatch[1]) : 8;
      const altMatch = lower.match(/(\d+)\s*m?\s*(alt|高度|altitude)/i);
      const alt = altMatch ? parseInt(altMatch[1]) : ctx.defaultAlt;
      const center = ctx.currentPosition.lat !== 0 ? ctx.currentPosition : ctx.homePosition;
      const wps = [];
      for (let i = 0; i < count; i++) {
        const angle = (i / count) * 2 * Math.PI;
        const dlat = (radius * Math.cos(angle)) / 111320;
        const dlon = (radius * Math.sin(angle)) / (111320 * Math.cos((center.lat * Math.PI) / 180));
        wps.push({
          lat: center.lat + dlat,
          lon: center.lon + dlon,
          alt,
          drop: false,
          delay: 0,
          speed: 0,
          type: 'wp' as const,
          loiter_param: 0,
        });
      }
      return { message: `Generated ${count}-point circle, radius ${radius}m, altitude ${alt}m`, waypoints: wps };
    }

    if (lower.includes('survey') || lower.includes('测绘') || lower.includes('grid') || lower.includes('网格')) {
      const dimMatch = lower.match(/(\d+)\s*m?\s*[x×]\s*(\d+)/);
      const w = dimMatch ? parseInt(dimMatch[1]) : 200;
      const h = dimMatch ? parseInt(dimMatch[2]) : 200;
      const altMatch = lower.match(/(\d+)\s*m?\s*(alt|高度|altitude)/i);
      const alt = altMatch ? parseInt(altMatch[1]) : ctx.defaultAlt;
      const spacing = 30;
      const center = ctx.currentPosition.lat !== 0 ? ctx.currentPosition : ctx.homePosition;
      const wps = [];
      const lines = Math.ceil(w / spacing);
      for (let i = 0; i <= lines; i++) {
        const x = -w / 2 + i * spacing;
        const y1 = i % 2 === 0 ? -h / 2 : h / 2;
        const y2 = i % 2 === 0 ? h / 2 : -h / 2;
        for (const y of [y1, y2]) {
          const dlat = y / 111320;
          const dlon = x / (111320 * Math.cos((center.lat * Math.PI) / 180));
          wps.push({
            lat: center.lat + dlat,
            lon: center.lon + dlon,
            alt,
            drop: false,
            delay: 0,
            speed: 0,
            type: 'wp' as const,
            loiter_param: 0,
          });
        }
      }
      return { message: `Generated ${w}×${h}m survey grid, ${wps.length} waypoints at ${alt}m`, waypoints: wps };
    }

    if (lower.includes('reverse') || lower.includes('反转')) {
      if (app.waypoints.length > 0) {
        pushUndo();
        app.waypoints.reverse();
        saveWaypoints();
        return { message: `Reversed ${app.waypoints.length} waypoints` };
      }
    }

    if (lower.match(/(\d+)\s*m?\s*(north|south|east|west|北|南|东|西)/i)) {
      const m = lower.match(/(\d+)\s*m?\s*(north|south|east|west|北|南|东|西)/i)!;
      const dist = parseInt(m[1]);
      const dir = m[2].toLowerCase();
      const altMatch = lower.match(/(\d+)\s*m?\s*(alt|高度)/i);
      const alt = altMatch ? parseInt(altMatch[1]) : ctx.defaultAlt;
      const base = ctx.currentPosition.lat !== 0 ? ctx.currentPosition : ctx.homePosition;
      let dlat = 0,
        dlon = 0;
      if (dir === 'north' || dir === '北') dlat = dist / 111320;
      if (dir === 'south' || dir === '南') dlat = -dist / 111320;
      if (dir === 'east' || dir === '东') dlon = dist / (111320 * Math.cos((base.lat * Math.PI) / 180));
      if (dir === 'west' || dir === '西') dlon = -dist / (111320 * Math.cos((base.lat * Math.PI) / 180));
      const wp = {
        lat: base.lat + dlat,
        lon: base.lon + dlon,
        alt,
        drop: false,
        delay: 0,
        speed: 0,
        type: 'wp' as const,
        loiter_param: 0,
      };
      return { message: `Added waypoint ${dist}m ${dir} at ${alt}m`, waypoints: [wp] };
    }

    return null;
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
    class="bg-card border border-border rounded-2xl overflow-hidden w-[550px] max-h-[80vh] shadow-2xl flex flex-col"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-purple-500/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <Sparkles size={16} class="text-purple-400" />
        <h3 class="text-base font-bold text-purple-400">{t('panel.aiPlanner')}</h3>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 overflow-y-auto px-5 py-3 space-y-3">
      {#if history.length === 0}
        <p class="text-xs text-muted-foreground mb-2">{t('panel.aiPlanner.desc')}</p>
        <div class="mb-2 p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
          <span class="text-[11px] text-yellow-600 dark:text-yellow-400">{t('panel.aiPlanner.localNote')}</span>
        </div>
        <div class="space-y-1.5">
          {#each EXAMPLES as ex}
            <button
              class="block w-full text-left px-3 py-2 text-xs text-muted-foreground bg-muted/50 rounded-lg hover:bg-muted transition-colors cursor-pointer border-none"
              onclick={() => {
                prompt = ex;
              }}>"{ex}"</button
            >
          {/each}
        </div>
      {/if}
      {#each history as msg}
        <div class="flex {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
          <div
            class="max-w-[80%] px-3 py-2 rounded-xl text-xs
            {msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'}"
          >
            {msg.text}
          </div>
        </div>
      {/each}
      {#if loading}
        <div class="flex justify-start">
          <div class="px-3 py-2 bg-muted rounded-xl">
            <Loader2 size={14} class="animate-spin text-muted-foreground" />
          </div>
        </div>
      {/if}
    </div>

    <div class="px-5 py-3 border-t border-border flex gap-2">
      <input
        bind:value={prompt}
        placeholder={t('panel.aiPlanner.placeholder')}
        class="flex-1 h-8 px-3 text-xs bg-input border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
        onkeydown={(e) => {
          if (e.key === 'Enter') send();
        }}
      />
      <Button variant="default" size="sm" onclick={send} disabled={loading}>
        <Send size={13} />
      </Button>
    </div>
  </div>
</div>
