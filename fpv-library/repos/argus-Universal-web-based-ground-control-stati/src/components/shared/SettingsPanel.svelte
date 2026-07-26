<script lang="ts">
  import { app, saveSettings } from '../../lib/stores.svelte';
  import { t, i18nState, setLocale, VALID_LOCALES, LOCALE_BETA } from '../../lib/i18n.svelte';
  import type { Locale } from '../../lib/i18n.svelte';

  const LOCALE_LABELS: Record<string, string> = {
    zh: '中文',
    en: 'English',
    ja: '日本語',
    ko: '한국어',
    de: 'Deutsch',
    fr: 'Français',
    es: 'Español',
    pt: 'Português',
    ru: 'Русский',
    ar: 'العربية',
  };
  import { gamepad, startGamepad, stopGamepad } from '../../lib/gamepad.svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import FirmwarePanel from '../setup/FirmwarePanel.svelte';
  import {
    X,
    Volume2,
    VolumeOff,
    Mic,
    MicOff,
    Sun,
    Moon,
    Plane,
    ShieldAlert,
    Gauge,
    Globe,
    Gamepad2,
  } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();
  const VERSION = '3.4.0';
  const BUILD = __BUILD_DATE__;
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  aria-label={t('settings.title')}
  class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center"
  onclick={onclose}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div
    class="bg-card border border-border rounded-2xl overflow-hidden min-w-[380px] max-h-[80vh] shadow-2xl flex flex-col"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <h3 class="text-base font-bold text-primary">{t('settings.title')}</h3>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="overflow-y-auto px-5 py-3 space-y-4">
      <div>
        <div class="flex items-center gap-1.5 mb-2">
          <Plane size={14} class="text-primary" />
          <span class="text-[11px] font-semibold text-primary uppercase tracking-wider">{t('settings.flight')}</span>
        </div>
        <div class="space-y-1">
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <label for="s-alt" class="text-sm text-muted-foreground">{t('ctrl.altitude')}</label>
            <div class="flex items-center gap-1">
              <input
                id="s-alt"
                type="number"
                bind:value={app.defaultAlt}
                min="5"
                max="500"
                step="5"
                onchange={saveSettings}
                class="w-16 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
              />
              <span class="text-[11px] text-muted-foreground w-6">m</span>
            </div>
          </div>
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <label for="s-speed" class="text-sm text-muted-foreground">{t('telem.speed')}</label>
            <div class="flex items-center gap-1">
              <input
                id="s-speed"
                type="number"
                bind:value={app.defaultSpeed}
                min="1"
                max="30"
                step="0.5"
                onchange={saveSettings}
                class="w-16 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
              />
              <span class="text-[11px] text-muted-foreground w-6">m/s</span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="flex items-center gap-1.5 mb-2">
          <ShieldAlert size={14} class="text-primary" />
          <span class="text-[11px] font-semibold text-primary uppercase tracking-wider"
            >{t('settings.safetySection')}</span
          >
        </div>
        <div class="flex justify-between items-center py-2 border-b border-border/50">
          <label for="s-radius" class="text-sm text-muted-foreground">{t('map.fence')}</label>
          <div class="flex items-center gap-1">
            <input
              id="s-radius"
              type="number"
              bind:value={app.geoRadius}
              min="0"
              max="10000"
              step="100"
              onchange={saveSettings}
              class="w-16 h-7 px-2 text-right bg-input border border-border rounded-md text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
            />
            <span class="text-[11px] text-muted-foreground w-6">m</span>
          </div>
        </div>
      </div>

      <div>
        <div class="flex items-center gap-1.5 mb-2">
          <Gauge size={14} class="text-primary" />
          <span class="text-[11px] font-semibold text-primary uppercase tracking-wider">{t('settings.uiSection')}</span>
        </div>
        <div class="space-y-1">
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <span class="text-sm text-muted-foreground">{t('settings.audio')}</span>
            <Button
              variant={app.audioMuted ? 'secondary' : 'default'}
              size="sm"
              class="gap-1 h-7 text-xs"
              onclick={() => {
                app.audioMuted = !app.audioMuted;
                saveSettings();
              }}
            >
              {#if app.audioMuted}<VolumeOff size={13} />OFF{:else}<Volume2 size={13} />ON{/if}
            </Button>
          </div>
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <span class="text-sm text-muted-foreground">{t('settings.voice')}</span>
            <Button
              variant={app.voiceEnabled ? 'default' : 'secondary'}
              size="sm"
              class="gap-1 h-7 text-xs"
              onclick={() => {
                app.voiceEnabled = !app.voiceEnabled;
                saveSettings();
              }}
            >
              {#if app.voiceEnabled}<Mic size={13} />ON{:else}<MicOff size={13} />OFF{/if}
            </Button>
          </div>
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <span class="text-sm text-muted-foreground">{t('settings.darkTheme')}</span>
            <Button
              variant={app.darkTheme ? 'default' : 'secondary'}
              size="sm"
              class="gap-1 h-7 text-xs"
              onclick={() => {
                app.darkTheme = !app.darkTheme;
                saveSettings();
              }}
            >
              {#if app.darkTheme}<Moon size={13} />{t('theme.dark')}{:else}<Sun size={13} />{t('theme.light')}{/if}
            </Button>
          </div>
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <label class="text-sm text-muted-foreground"
              ><Gamepad2 size={13} class="inline mr-1" />{t('settings.gamepad')}</label
            >
            <div class="flex items-center gap-1.5">
              {#if gamepad.connected}
                <span class="text-[10px] text-success">{gamepad.name}</span>
              {/if}
              <Button
                variant={gamepad.enabled ? 'default' : 'secondary'}
                size="sm"
                class="h-7 text-xs px-2.5"
                onclick={() => {
                  if (gamepad.enabled) stopGamepad();
                  else startGamepad();
                }}
              >
                {gamepad.enabled ? 'ON' : 'OFF'}
              </Button>
            </div>
          </div>
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <span class="text-sm text-muted-foreground">{t('settings.mapSource')}</span>
            <select
              class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
              value={app.tileSource}
              onchange={(e) => {
                app.tileSource = (e.target as HTMLSelectElement).value;
                app.mapRegion = ['amap', 'tianditu'].includes(app.tileSource) ? 'china' : 'global';
                saveSettings();
              }}
            >
              <optgroup label={t('settings.china')}>
                <option value="amap">{t('map.amap')}</option>
                <option value="tianditu">{t('map.tianditu')}</option>
              </optgroup>
              <optgroup label="Global">
                <option value="google_sat">Google Satellite</option>
                <option value="google_hybrid">Google Hybrid</option>
                <option value="osm">OpenStreetMap</option>
                <option value="esri">Esri Topo + Satellite</option>
                <option value="carto_dark">CartoDB Dark</option>
                <option value="carto_light">CartoDB Light</option>
              </optgroup>
            </select>
          </div>
          <div class="flex justify-between items-center py-2 border-b border-border/50">
            <label class="text-sm text-muted-foreground"
              ><Globe size={13} class="inline mr-1" />{t('settings.language')}</label
            >
            <select
              class="h-7 px-2 text-xs bg-input border border-border rounded-md text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
              value={i18nState.locale}
              onchange={(e) => setLocale((e.target as HTMLSelectElement).value as Locale)}
            >
              {#each VALID_LOCALES as loc}
                <option value={loc}>{LOCALE_LABELS[loc] || loc}{LOCALE_BETA.has(loc) ? ' (beta)' : ''}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>

      <FirmwarePanel />

      <div class="pt-2 border-t border-border text-center">
        <p class="text-[11px] text-muted-foreground font-semibold">{t('app.name')} {t('welcome.subtitle')}</p>
        <p class="text-[10px] text-muted-foreground/60">v{VERSION} · {BUILD}</p>
        <p class="text-[9px] text-muted-foreground/40 mt-0.5">Copter · Plane · Rover · Sub | UDP · TCP · Serial</p>
      </div>
    </div>
  </div>
</div>
