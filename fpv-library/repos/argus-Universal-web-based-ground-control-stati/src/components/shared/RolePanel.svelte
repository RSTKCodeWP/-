<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Shield, Eye, Crown } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  type Role = 'pilot' | 'observer' | 'commander';

  interface RoleDef {
    id: Role;
    icon: typeof Shield;
    nameKey: string;
    descZh: string;
    descEn: string;
  }

  const roles: RoleDef[] = [
    {
      id: 'pilot',
      icon: Shield,
      nameKey: 'role.pilot',
      descZh: '完全控制 — 可发送指令',
      descEn: 'Full control — can send commands',
    },
    {
      id: 'observer',
      icon: Eye,
      nameKey: 'role.observer',
      descZh: '仅查看 — 遥测和地图，不可发送指令',
      descEn: 'View only — telemetry and map, no commands',
    },
    {
      id: 'commander',
      icon: Crown,
      nameKey: 'role.commander',
      descZh: '完全控制 + 可管理其他用户',
      descEn: 'Full control + can manage other users',
    },
  ];

  /* ── Persist role to localStorage ── */
  function loadRole(): Role {
    try {
      const v = localStorage.getItem('argus_role');
      if (v === 'pilot' || v === 'observer' || v === 'commander') return v;
    } catch {}
    return 'pilot';
  }

  let currentRole: Role = $state(loadRole());

  function selectRole(r: Role) {
    currentRole = r;
    try {
      localStorage.setItem('argus_role', r);
    } catch {}
    addToast(`${t('role.set')}: ${t('role.' + r)}`, 'info');
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[350px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Shield size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('role.current')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-2">
      <!-- Honesty banner: argus_role is written but nothing enforces it yet —
           without this note a "viewer" selection looks like a safety control. -->
      <div class="p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
        <span class="text-[11px] text-yellow-600 dark:text-yellow-400">{t('role.notEnforced')}</span>
      </div>
      {#each roles as role (role.id)}
        {@const active = currentRole === role.id}
        <div
          role="presentation"
          class="p-3 rounded-lg border transition-colors cursor-pointer
            {active ? 'bg-primary/10 border-primary/30' : 'bg-muted/30 border-border hover:bg-muted/50'}"
          onclick={() => selectRole(role.id)}
        >
          <div class="flex items-center gap-3">
            <div
              class="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
              {active ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground'}"
            >
              <role.icon size={16} />
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-foreground">{t(role.nameKey)}</span>
                {#if active}
                  <span class="text-[10px] font-medium text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                    {t('role.current')}
                  </span>
                {/if}
              </div>
              <p class="text-xs text-muted-foreground mt-0.5">{role.descEn}</p>
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>
