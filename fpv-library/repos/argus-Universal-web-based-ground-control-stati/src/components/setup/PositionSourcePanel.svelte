<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { X, Locate, Navigation } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── EKF flag bit masks ── */
  const BIT_ATTITUDE = 0x001; // bit 0
  const BIT_VEL_HORIZ = 0x002; // bit 1
  const BIT_VEL_VERT = 0x004; // bit 2
  const BIT_POS_HORIZ_REL = 0x008; // bit 3
  const BIT_POS_HORIZ_ABS = 0x010; // bit 4
  const BIT_POS_VERT_ABS = 0x020; // bit 5
  const BIT_POS_VERT_AGL = 0x040; // bit 6
  const BIT_CONST_POS = 0x080; // bit 7
  const BIT_UNINITIALIZED = 0x400; // bit 10

  const d = app.drone;

  type StatusLevel = 'good' | 'warn' | 'bad';

  /* ── GPS source ── */
  let gpsStatus: StatusLevel = $derived.by(() => {
    if (d.gps_fix_raw >= 3) return 'good';
    if (d.gps_fix_raw >= 2) return 'warn';
    return 'bad';
  });

  let gpsDetail = $derived(`${d.gps_fix} | ${d.gps_sats} sats`);

  /* ── EKF overall ── */
  let ekfFlags = $derived(d.ekf_flags);

  let ekfStatus: StatusLevel = $derived.by(() => {
    if (ekfFlags & BIT_UNINITIALIZED) return 'bad';
    if (ekfFlags & BIT_CONST_POS) return 'warn';
    const core = BIT_ATTITUDE | BIT_VEL_HORIZ | BIT_POS_HORIZ_ABS;
    if ((ekfFlags & core) === core) return 'good';
    return 'warn';
  });

  /* ── Optical flow (relative position, not absolute) ── */
  let optFlowStatus: StatusLevel = $derived.by(() => {
    const hasRel = (ekfFlags & BIT_POS_HORIZ_REL) !== 0;
    const hasAbs = (ekfFlags & BIT_POS_HORIZ_ABS) !== 0;
    if (hasRel && !hasAbs) return 'good';
    if (hasRel) return 'warn';
    return 'bad';
  });

  /* ── Compass ── */
  let compassStatus: StatusLevel = $derived.by(() => {
    const v = d.ekf_compass;
    if (v < 0.3) return 'good';
    if (v < 0.5) return 'warn';
    return 'bad';
  });

  let compassDetail = $derived(`variance: ${d.ekf_compass.toFixed(2)}`);

  /* ── Overall confidence ── */
  let confidence: StatusLevel = $derived.by(() => {
    if (ekfFlags & BIT_UNINITIALIZED) return 'bad';
    if (ekfFlags & BIT_CONST_POS) return 'warn';
    const allGood = gpsStatus === 'good' && ekfStatus === 'good' && compassStatus !== 'bad';
    if (allGood) return 'good';
    if (gpsStatus === 'bad' && ekfStatus === 'bad') return 'bad';
    return 'warn';
  });

  /* ── EKF decoded flags ── */
  interface FlagEntry {
    label: string;
    active: boolean;
    warn?: boolean;
  }

  let decodedFlags: FlagEntry[] = $derived([
    { label: t('posSource.attOk'), active: (ekfFlags & BIT_ATTITUDE) !== 0 },
    { label: t('posSource.velHOk'), active: (ekfFlags & BIT_VEL_HORIZ) !== 0 },
    { label: t('posSource.velVOk'), active: (ekfFlags & BIT_VEL_VERT) !== 0 },
    { label: t('posSource.posHRel'), active: (ekfFlags & BIT_POS_HORIZ_REL) !== 0 },
    { label: t('posSource.posHAbs'), active: (ekfFlags & BIT_POS_HORIZ_ABS) !== 0 },
    { label: t('posSource.posVAbs'), active: (ekfFlags & BIT_POS_VERT_ABS) !== 0 },
    { label: t('posSource.posVAgl'), active: (ekfFlags & BIT_POS_VERT_AGL) !== 0 },
    { label: t('posSource.constPos'), active: (ekfFlags & BIT_CONST_POS) !== 0, warn: true },
    { label: t('posSource.uninit'), active: (ekfFlags & BIT_UNINITIALIZED) !== 0, warn: true },
  ]);

  interface Source {
    icon: typeof Locate;
    name: string;
    status: StatusLevel;
    detail: string;
  }

  let sources: Source[] = $derived([
    { icon: Navigation, name: 'GPS', status: gpsStatus, detail: gpsDetail },
    { icon: Locate, name: 'EKF', status: ekfStatus, detail: `flags: 0x${ekfFlags.toString(16).padStart(3, '0')}` },
    {
      icon: Locate,
      name: t('posSource.optFlow'),
      status: optFlowStatus,
      detail: t(`posSource.optFlow.${optFlowStatus}`),
    },
    { icon: Locate, name: t('posSource.compass'), status: compassStatus, detail: compassDetail },
  ]);

  function statusColorClass(s: 'good' | 'warn' | 'bad'): string {
    if (s === 'good') return 'bg-green-500';
    if (s === 'warn') return 'bg-yellow-500';
    return 'bg-red-500';
  }

  function statusTextClass(s: 'good' | 'warn' | 'bad'): string {
    if (s === 'good') return 'text-green-400';
    if (s === 'warn') return 'text-yellow-400';
    return 'text-red-400';
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
  <div class="bg-card border border-border rounded-xl shadow-2xl w-[400px] max-h-[85vh] flex flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-border">
      <div class="flex items-center gap-2">
        <Locate size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('posSource.title')}</h2>
      </div>
      <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
      <!-- Overall confidence -->
      <div
        class="p-3 rounded-lg border {confidence === 'good'
          ? 'bg-green-500/5 border-green-500/30'
          : confidence === 'warn'
            ? 'bg-yellow-500/5 border-yellow-500/30'
            : 'bg-red-500/5 border-red-500/30'}"
      >
        <div class="flex items-center gap-2">
          <div class="w-2.5 h-2.5 rounded-full {statusColorClass(confidence)}"></div>
          <span class="text-xs font-semibold {statusTextClass(confidence)}">
            {t('posSource.confidence')}: {t(`posSource.${confidence}`)}
          </span>
        </div>
      </div>

      <!-- Position sources list -->
      <div class="space-y-2">
        <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('posSource.sources')}</div>
        {#each sources as src}
          <div class="flex items-center gap-3 p-2 rounded-lg bg-muted/20 border border-border">
            <div class="w-2.5 h-2.5 rounded-full shrink-0 {statusColorClass(src.status)}"></div>
            <src.icon size={14} class="text-muted-foreground shrink-0" />
            <div class="flex-1 min-w-0">
              <div class="text-xs font-medium text-foreground">{src.name}</div>
              <div class="text-[10px] text-muted-foreground font-mono truncate">{src.detail}</div>
            </div>
            <span class="text-[10px] font-medium {statusTextClass(src.status)}">
              {t(`posSource.${src.status}`)}
            </span>
          </div>
        {/each}
      </div>

      <!-- EKF flags decoded -->
      <div class="space-y-1">
        <div class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {t('posSource.ekfFlags')}
        </div>
        <div class="grid grid-cols-2 gap-1">
          {#each decodedFlags as flag}
            <div class="flex items-center gap-1.5 text-[11px]">
              <div
                class="w-2 h-2 rounded-full {flag.active
                  ? flag.warn
                    ? 'bg-yellow-500'
                    : 'bg-green-500'
                  : 'bg-muted-foreground/30'}"
              ></div>
              <span class={flag.active ? (flag.warn ? 'text-yellow-400' : 'text-foreground') : 'text-muted-foreground'}>
                {flag.label}
              </span>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
</div>
