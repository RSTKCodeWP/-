<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { fmtDist } from '../../lib/units';
  import { X, AlertTriangle, Plane as PlaneIcon } from '@lucide/svelte';
  import Button from '$lib/components/ui/button/button.svelte';
  import Switch from '$lib/components/ui/switch/switch.svelte';

  let { onclose }: { onclose: () => void } = $props();

  /* ── Airport database (top 50 Chinese airports by passenger volume) ── */
  const AIRPORTS: { name: string; code: string; lat: number; lon: number; radius: number }[] = [
    { name: '北京首都', code: 'PEK', lat: 40.0801, lon: 116.5846, radius: 8500 },
    { name: '北京大兴', code: 'PKX', lat: 39.5098, lon: 116.4105, radius: 8500 },
    { name: '上海浦东', code: 'PVG', lat: 31.1443, lon: 121.8083, radius: 8500 },
    { name: '上海虹桥', code: 'SHA', lat: 31.1979, lon: 121.3363, radius: 6000 },
    { name: '广州白云', code: 'CAN', lat: 23.3924, lon: 113.2988, radius: 8500 },
    { name: '深圳宝安', code: 'SZX', lat: 22.6393, lon: 113.8107, radius: 6000 },
    { name: '成都双流', code: 'CTU', lat: 30.5785, lon: 103.9471, radius: 8500 },
    { name: '成都天府', code: 'TFU', lat: 30.3194, lon: 104.4419, radius: 8500 },
    { name: '西安咸阳', code: 'XIY', lat: 34.4371, lon: 108.7519, radius: 8500 },
    { name: '杭州萧山', code: 'HGH', lat: 30.2295, lon: 120.4344, radius: 6000 },
    { name: '南京禄口', code: 'NKG', lat: 31.742, lon: 118.862, radius: 6000 },
    { name: '昆明长水', code: 'KMG', lat: 24.9924, lon: 102.7432, radius: 8500 },
    { name: '武汉天河', code: 'WUH', lat: 30.7838, lon: 114.2081, radius: 6000 },
    { name: '重庆江北', code: 'CKG', lat: 29.7192, lon: 106.6417, radius: 8500 },
    { name: '厦门高崎', code: 'XMN', lat: 24.544, lon: 118.1277, radius: 6000 },
    { name: '长沙黄花', code: 'CSX', lat: 28.1892, lon: 113.22, radius: 6000 },
    { name: '青岛胶东', code: 'TAO', lat: 36.3661, lon: 120.0874, radius: 6000 },
    { name: '大连周水子', code: 'DLC', lat: 38.9657, lon: 121.5386, radius: 6000 },
    { name: '沈阳桃仙', code: 'SHE', lat: 41.6398, lon: 123.4834, radius: 6000 },
    { name: '海口美兰', code: 'HAK', lat: 19.9349, lon: 110.459, radius: 6000 },
    { name: '三亚凤凰', code: 'SYX', lat: 18.3029, lon: 109.4122, radius: 6000 },
    { name: '郑州新郑', code: 'CGO', lat: 34.5197, lon: 113.8408, radius: 6000 },
    { name: '乌鲁木齐地窝堡', code: 'URC', lat: 43.9071, lon: 87.4742, radius: 6000 },
    { name: '哈尔滨太平', code: 'HRB', lat: 45.6234, lon: 126.2503, radius: 6000 },
    { name: '天津滨海', code: 'TSN', lat: 39.1244, lon: 117.3462, radius: 6000 },
    { name: '福州长乐', code: 'FOC', lat: 25.9351, lon: 119.6631, radius: 6000 },
    { name: '南宁吴圩', code: 'NNG', lat: 22.6083, lon: 108.1722, radius: 6000 },
    { name: '济南遥墙', code: 'TNA', lat: 36.8572, lon: 117.2158, radius: 6000 },
    { name: '长春龙嘉', code: 'CGQ', lat: 43.9962, lon: 125.6852, radius: 6000 },
    { name: '贵阳龙洞堡', code: 'KWE', lat: 26.5385, lon: 106.8017, radius: 6000 },
    { name: '兰州中川', code: 'LHW', lat: 36.5152, lon: 103.6207, radius: 6000 },
    { name: '银川河东', code: 'INC', lat: 38.3228, lon: 106.3931, radius: 6000 },
    { name: '呼和浩特白塔', code: 'HET', lat: 40.8514, lon: 111.8242, radius: 6000 },
    { name: '石家庄正定', code: 'SJW', lat: 38.2807, lon: 114.6963, radius: 6000 },
    { name: '温州龙湾', code: 'WNZ', lat: 27.9122, lon: 120.8522, radius: 6000 },
    { name: '南通兴东', code: 'NTG', lat: 32.0708, lon: 120.976, radius: 6000 },
    { name: '烟台蓬莱', code: 'YNT', lat: 37.6575, lon: 120.987, radius: 6000 },
    { name: '南昌昌北', code: 'KHN', lat: 28.865, lon: 115.9001, radius: 6000 },
    { name: '西宁曹家堡', code: 'XNN', lat: 36.5275, lon: 102.0433, radius: 6000 },
    { name: '珠海金湾', code: 'ZUH', lat: 22.0064, lon: 113.376, radius: 6000 },
    { name: '丽江三义', code: 'LJG', lat: 26.68, lon: 100.246, radius: 4500 },
    { name: '绵阳南郊', code: 'MIG', lat: 31.4281, lon: 104.7418, radius: 4500 },
    { name: '威海大水泊', code: 'WEH', lat: 36.6463, lon: 122.2289, radius: 4500 },
    { name: '泉州晋江', code: 'JJN', lat: 24.7964, lon: 118.5902, radius: 4500 },
    { name: '合肥新桥', code: 'HFE', lat: 31.98, lon: 116.977, radius: 6000 },
    { name: '太原武宿', code: 'TYN', lat: 37.7469, lon: 112.6285, radius: 6000 },
    { name: '洛阳北郊', code: 'LYA', lat: 34.7411, lon: 112.388, radius: 4500 },
    { name: '西双版纳嘎洒', code: 'JHG', lat: 21.9739, lon: 100.76, radius: 4500 },
    { name: '鄂尔多斯伊金霍洛', code: 'DSN', lat: 39.49, lon: 109.8614, radius: 4500 },
    { name: '拉萨贡嘎', code: 'LXA', lat: 29.2978, lon: 90.9119, radius: 6000 },
  ];

  /* ── Persist enable toggle ── */
  function loadEnabled(): boolean {
    try {
      const v = localStorage.getItem('argus_airspace');
      if (v === 'true' || v === 'false') return v === 'true';
    } catch {}
    return false;
  }

  let enabled = $state(loadEnabled());

  function toggleEnabled(val: boolean) {
    enabled = val;
    try {
      localStorage.setItem('argus_airspace', String(val));
    } catch {}
  }

  /* ── Distance calculation (Haversine) ── */
  function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }


  /* ── Airport list with distance, sorted by distance ── */
  let airportList = $derived.by(() => {
    const droneLat = app.drone.lat;
    const droneLon = app.drone.lon;
    const hasPos = droneLat !== 0 || droneLon !== 0;

    return AIRPORTS.map((ap) => {
      const dist = hasPos ? haversineM(droneLat, droneLon, ap.lat, ap.lon) : -1;
      const inside = hasPos && dist < ap.radius;
      const label = `${ap.name} ${ap.code}`;
      return { ...ap, label, dist, inside };
    }).sort((a, b) => {
      if (a.dist < 0) return 1;
      if (b.dist < 0) return -1;
      return a.dist - b.dist;
    });
  });

  /* ── Any violation? ── */
  let violation = $derived(airportList.some((a) => a.inside));
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
      <div class="flex items-center gap-2">
        <PlaneIcon size={16} class="text-primary" />
        <h2 class="text-sm font-semibold text-primary uppercase tracking-wider">{t('airspace.title')}</h2>
      </div>
      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
          {t('airspace.enabled')}
          <Switch size="sm" checked={enabled} onCheckedChange={toggleEnabled} />
        </label>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>

    <div class="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
      <!-- Demo-data disclaimer: AIRPORTS below is a built-in sample list,
           not an authoritative airspace source — say so where the user
           would otherwise trust the warnings. -->
      <div class="p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30 flex items-center gap-2">
        <AlertTriangle size={14} class="text-yellow-500 shrink-0" />
        <span class="text-[11px] text-yellow-600 dark:text-yellow-400">{t('airspace.demoData')}</span>
      </div>

      <!-- Violation warning -->
      {#if violation && enabled}
        <div class="p-3 rounded-lg bg-destructive/10 border border-destructive/30 flex items-center gap-2">
          <AlertTriangle size={16} class="text-destructive shrink-0" />
          <span class="text-xs font-semibold text-destructive"
            >{t('airspace.noFly')} — Drone is within an airport no-fly zone!</span
          >
        </div>
      {/if}

      <!-- Airport list header -->
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('airspace.airport')}</span
        >
        <span class="text-[10px] text-muted-foreground">({AIRPORTS.length})</span>
      </div>

      <!-- Airport cards -->
      <div class="space-y-2">
        {#each airportList as ap (ap.code)}
          <div
            class="p-3 rounded-lg border transition-colors
            {ap.inside ? 'bg-destructive/5 border-destructive/30' : 'bg-muted/30 border-border'}"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <PlaneIcon size={14} class={ap.inside ? 'text-destructive' : 'text-muted-foreground'} />
                <span class="text-xs font-semibold text-foreground">{ap.label}</span>
                {#if ap.inside}
                  <span class="text-[10px] font-medium text-destructive bg-destructive/10 px-1.5 py-0.5 rounded">
                    {t('airspace.noFly')}
                  </span>
                {/if}
              </div>
              <span class="text-[10px] text-muted-foreground">
                r={fmtDist(ap.radius)}
              </span>
            </div>
            <div class="grid grid-cols-3 gap-x-3 mt-2 text-[11px]">
              <div class="flex justify-between">
                <span class="text-muted-foreground">Lat</span>
                <span class="font-mono text-foreground">{ap.lat.toFixed(4)}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted-foreground">Lon</span>
                <span class="font-mono text-foreground">{ap.lon.toFixed(4)}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-muted-foreground">Dist</span>
                <span class="font-mono font-medium {ap.inside ? 'text-destructive' : 'text-foreground'}">
                  {ap.dist >= 0 ? fmtDist(ap.dist) : '---'}
                </span>
              </div>
            </div>
          </div>
        {/each}
      </div>

      <!-- Hint -->
      {#if !enabled}
        <div class="p-3 rounded-lg bg-primary/5 border border-primary/20">
          <p class="text-xs text-muted-foreground leading-relaxed">
            {t('airspace.restricted')} — Enable the airspace check to see airport no-fly proximity warnings in this panel (demo airport data; not a map overlay).
          </p>
        </div>
      {/if}
    </div>
  </div>
</div>
