<script lang="ts">
  import { app } from '../../lib/stores.svelte';
  import { t, i18nState } from '../../lib/i18n.svelte';

  const d = app.drone;

  const CX = 150,
    CY = 86;
  const AHI_R = 60,
    COMP_R = 74;
  const PP = 2.0;
  const TT = 8,
    TB = 164,
    TC = 86;
  const SPD_SC = 4,
    ALT_SC = 1.8;

  let po = $derived(d.pitch * PP);
  let rr = $derived(-d.roll);

  const PL = [-30, -25, -20, -15, -10, -5, 5, 10, 15, 20, 25, 30];
  const CC: Record<number, string> = { 0: 'N', 90: 'E', 180: 'S', 270: 'W' };
  const RM = [0, 10, -10, 20, -20, 30, -30, 45, -45, 60, -60];

  let sm = $derived.by(() => {
    const s = d.gs;
    const half = (TB - TT) / 2 / SPD_SC + 2;
    const out: { y: number; v: number; maj: boolean }[] = [];
    for (let v = Math.max(0, Math.floor(s - half)); v <= Math.ceil(s + half); v++) {
      const y = TC - (v - s) * SPD_SC;
      if (y >= TT - 2 && y <= TB + 2) out.push({ y, v, maj: v % 5 === 0 });
    }
    return out;
  });

  let am = $derived.by(() => {
    const a = d.alt_rel;
    const half = (TB - TT) / 2 / ALT_SC + 5;
    const out: { y: number; v: number; maj: boolean }[] = [];
    for (let v = Math.floor((a - half) / 5) * 5; v <= a + half; v += 5) {
      const y = TC - (v - a) * ALT_SC;
      if (y >= TT - 2 && y <= TB + 2) out.push({ y, v, maj: v % 10 === 0 });
    }
    return out;
  });

  const VSH = 56,
    VSM = 5;
  let vsc = $derived(Math.max(-VSM, Math.min(VSM, d.vz)));
  let vspx = $derived((-vsc / VSM) * (VSH / 2));

  let homeBearing = $derived.by(() => {
    if (d.home_lat === 0 || d.lat === 0 || d.dist_home < 5) return -1;
    const dlon = (d.home_lon - d.lon) * Math.cos((d.lat * Math.PI) / 180);
    const dlat = d.home_lat - d.lat;
    return ((Math.atan2(dlon, dlat) * 180) / Math.PI + 360) % 360;
  });

  const CARD: Record<string, string[]> = {
    zh: ['北', '东北', '东', '东南', '南', '西南', '西', '西北'],
    ja: ['北', '北東', '東', '南東', '南', '南西', '西', '北西'],
    ko: ['북', '북동', '동', '남동', '남', '남서', '서', '북서'],
    ru: ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'],
    ar: ['ش', 'شق', 'ق', 'جق', 'ج', 'جغ', 'غ', 'شغ'],
  };
  const CARD_EN = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  function cardinal(h: number): string {
    const idx = Math.round(h / 45) % 8;
    return (CARD[i18nState.locale] || CARD_EN)[idx];
  }
</script>

<svg class="pfd" viewBox="0 0 300 195" xmlns="http://www.w3.org/2000/svg" role="img" aria-label={t('ui.pfd')}>
  <defs>
    <clipPath id="pc"><circle cx={CX} cy={CY} r={AHI_R} /></clipPath>
    <clipPath id="sc"><rect x="2" y={TT} width="50" height={TB - TT} /></clipPath>
    <clipPath id="ac"><rect x="248" y={TT} width="50" height={TB - TT} /></clipPath>
  </defs>

  <rect width="300" height="195" rx="8" fill="rgba(0,0,0,0.78)" stroke="rgba(255,255,255,0.1)" stroke-width="0.8" />

  <!-- Speed Tape -->
  <rect x="2" y={TT} width="50" height={TB - TT} rx="3" fill="rgba(0,0,0,0.35)" />
  <g clip-path="url(#sc)">
    {#each sm as m}
      {#if m.maj}
        <line x1="37" y1={m.y} x2="52" y2={m.y} stroke="white" stroke-width="0.8" opacity="0.6" />
        <text x="35" y={m.y + 3.5} text-anchor="end" fill="white" font-size="9" opacity="0.8" font-family="monospace"
          >{m.v}</text
        >
      {:else}
        <line x1="45" y1={m.y} x2="52" y2={m.y} stroke="white" stroke-width="0.4" opacity="0.25" />
      {/if}
    {/each}
  </g>
  <rect x="3" y={TC - 11} width="46" height="22" rx="2" fill="rgba(0,0,0,0.92)" stroke="#4caf50" stroke-width="1.5" />
  <text x="26" y={TC + 5} text-anchor="middle" fill="#4caf50" font-size="13" font-weight="bold" font-family="monospace"
    >{d.gs.toFixed(1)}</text
  >
  <polygon points="50,{TC - 4} 55,{TC} 50,{TC + 4}" fill="#4caf50" />
  <text x="26" y={TT - 1} text-anchor="middle" fill="#555" font-size="7">{t('telem.speed')} m/s</text>

  <!-- AHI Background -->
  <circle cx={CX} cy={CY} r={AHI_R + 1} fill="rgba(0,0,0,0.5)" stroke="#444" stroke-width="0.5" />

  <!-- AHI Sky/Ground + Pitch Ladder -->
  <g transform="rotate({rr},{CX},{CY})" clip-path="url(#pc)">
    <rect x={CX - 100} y={CY - 130 - po} width="200" height="130" fill="#1565c0" />
    <rect x={CX - 100} y={CY - po} width="200" height="130" fill="#5d4037" />
    <line x1={CX - 100} y1={CY - po} x2={CX + 100} y2={CY - po} stroke="white" stroke-width="1" opacity="0.9" />
    {#each PL as deg}
      {@const py = CY - deg * PP - po}
      {@const hw = Math.abs(deg) % 10 === 0 ? 20 : 11}
      {@const major = Math.abs(deg) % 10 === 0}
      <line
        x1={CX - hw}
        y1={py}
        x2={CX + hw}
        y2={py}
        stroke="white"
        stroke-width={major ? 0.8 : 0.5}
        opacity={major ? 0.65 : 0.4}
        stroke-dasharray={deg < 0 ? '3,2' : 'none'}
      />
      {#if major}
        <text x={CX - hw - 3} y={py + 3} text-anchor="end" fill="white" font-size="7" opacity="0.55">{deg}</text>
        <text x={CX + hw + 3} y={py + 3} text-anchor="start" fill="white" font-size="7" opacity="0.55">{deg}</text>
      {/if}
    {/each}
  </g>

  <!-- Aircraft Reference -->
  <line x1={CX - 20} y1={CY} x2={CX - 7} y2={CY} stroke="#ff9800" stroke-width="2.5" stroke-linecap="round" />
  <line x1={CX + 7} y1={CY} x2={CX + 20} y2={CY} stroke="#ff9800" stroke-width="2.5" stroke-linecap="round" />
  <circle cx={CX} cy={CY} r="2.5" fill="none" stroke="#ff9800" stroke-width="2" />

  <!-- Roll Indicator Marks (fixed) -->
  {#each RM as a}
    {@const rad = ((a - 90) * Math.PI) / 180}
    {@const r1 = AHI_R + 3}
    {@const len = a === 0 ? 7 : Math.abs(a) <= 30 ? 5 : 4}
    <line
      x1={CX + r1 * Math.cos(rad)}
      y1={CY + r1 * Math.sin(rad)}
      x2={CX + (r1 + len) * Math.cos(rad)}
      y2={CY + (r1 + len) * Math.sin(rad)}
      stroke={a === 0 ? '#ff9800' : '#888'}
      stroke-width={Math.abs(a) <= 30 ? 1.2 : 0.6}
    />
  {/each}
  <!-- Roll Pointer (rotates with roll) -->
  <polygon
    points="{CX},{CY - AHI_R - 7} {CX - 3},{CY - AHI_R - 1} {CX + 3},{CY - AHI_R - 1}"
    fill="#ff9800"
    transform="rotate({d.roll},{CX},{CY})"
  />

  <!-- Compass Ring -->
  <circle cx={CX} cy={CY} r={COMP_R} fill="none" stroke="#555" stroke-width="0.7" />
  <g transform="rotate({-d.hdg},{CX},{CY})">
    {#each Array(36) as _, i}
      {@const deg = i * 10}
      {@const isCard = CC[deg] !== undefined}
      <g transform="rotate({deg},{CX},{CY})">
        <line
          x1={CX}
          y1={CY - COMP_R}
          x2={CX}
          y2={CY - COMP_R + (isCard ? 6 : 3)}
          stroke={deg === 0 ? '#f44336' : isCard ? '#bbb' : '#666'}
          stroke-width={isCard ? 1.2 : 0.5}
        />
        {#if isCard}
          <text
            x={CX}
            y={CY - COMP_R + 13}
            text-anchor="middle"
            font-size="8"
            font-weight="bold"
            fill={deg === 0 ? '#f44336' : '#aaa'}
            transform="rotate({-deg},{CX},{CY - COMP_R + 13})">{CC[deg]}</text
          >
        {/if}
      </g>
    {/each}
  </g>
  <polygon points="{CX},{CY - COMP_R - 1} {CX - 3},{CY - COMP_R + 5} {CX + 3},{CY - COMP_R + 5}" fill="#ff9800" />

  <!-- Home Direction on Compass -->
  {#if homeBearing >= 0}
    {@const hRel = (homeBearing - d.hdg + 360) % 360}
    {@const hRad = ((hRel - 90) * Math.PI) / 180}
    <polygon
      points="{CX + COMP_R * Math.cos(hRad)},{CY + COMP_R * Math.sin(hRad)} {CX +
        (COMP_R - 7) * Math.cos(hRad - 0.08)},{CY + (COMP_R - 7) * Math.sin(hRad - 0.08)} {CX +
        (COMP_R - 7) * Math.cos(hRad + 0.08)},{CY + (COMP_R - 7) * Math.sin(hRad + 0.08)}"
      fill="#4caf50"
      opacity="0.9"
    />
  {/if}

  <!-- Altitude Tape -->
  <rect x="248" y={TT} width="50" height={TB - TT} rx="3" fill="rgba(0,0,0,0.35)" />
  <g clip-path="url(#ac)">
    {#each am as m}
      {#if m.maj}
        <line x1="248" y1={m.y} x2="263" y2={m.y} stroke="white" stroke-width="0.8" opacity="0.6" />
        <text x="265" y={m.y + 3.5} text-anchor="start" fill="white" font-size="9" opacity="0.8" font-family="monospace"
          >{m.v}</text
        >
      {:else}
        <line x1="248" y1={m.y} x2="255" y2={m.y} stroke="white" stroke-width="0.4" opacity="0.25" />
      {/if}
    {/each}
  </g>
  <rect x="249" y={TC - 11} width="48" height="22" rx="2" fill="rgba(0,0,0,0.92)" stroke="#42a5f5" stroke-width="1.5" />
  <text x="273" y={TC + 5} text-anchor="middle" fill="#42a5f5" font-size="13" font-weight="bold" font-family="monospace"
    >{d.alt_rel.toFixed(1)}</text
  >
  <polygon points="249,{TC - 4} 244,{TC} 249,{TC + 4}" fill="#42a5f5" />
  <text x="273" y={TT - 1} text-anchor="middle" fill="#555" font-size="7">{t('telem.alt')} m</text>

  <!-- VS Indicator -->
  <rect
    x="230"
    y={CY - VSH / 2}
    width="8"
    height={VSH}
    rx="1.5"
    fill="rgba(255,255,255,0.05)"
    stroke="rgba(255,255,255,0.12)"
    stroke-width="0.5"
  />
  <line x1="228" y1={CY} x2="240" y2={CY} stroke="rgba(255,255,255,0.2)" stroke-width="0.5" />
  {#if Math.abs(d.vz) > 0.1}
    <rect
      x="230"
      y={CY + Math.min(vspx, 0)}
      width="8"
      height={Math.max(1, Math.abs(vspx))}
      fill={d.vz > 0.3 ? '#4caf50' : d.vz < -0.3 ? '#ef4444' : '#888'}
      rx="1.5"
      opacity="0.85"
    />
  {/if}
  <text
    x="234"
    y={CY - VSH / 2 - 2}
    text-anchor="middle"
    fill={d.vz > 0.3 ? '#4caf50' : d.vz < -0.3 ? '#ef4444' : '#888'}
    font-size="7"
    font-family="monospace"
  >
    {d.vz > 0 ? '+' : ''}{d.vz.toFixed(1)}
  </text>

  <!-- Heading Readout -->
  <text x={CX} y="182" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="monospace"
    >{d.hdg.toFixed(0)}&deg;</text
  >
  <text x={CX} y="192" text-anchor="middle" fill="#777" font-size="8">{cardinal(d.hdg)}</text>

  <!-- Wind Indicator (bottom-right) -->
  {#if d.wind_speed > 0.3}
    {@const wr = (d.wind_dir - d.hdg + 360) % 360}
    <g transform="translate(268,185)">
      <g transform="rotate({wr})">
        <line x1="0" y1="8" x2="0" y2="-8" stroke="#69f0ae" stroke-width="1.5" />
        <polygon points="0,-9 -3,-4 3,-4" fill="#69f0ae" />
      </g>
      <text x="0" y="18" text-anchor="middle" fill="#69f0ae" font-size="7" font-family="monospace"
        >{d.wind_speed.toFixed(1)}</text
      >
    </g>
  {/if}
</svg>

<style>
  .pfd {
    position: absolute;
    left: 8px;
    bottom: 30px;
    z-index: 1001;
    width: 220px;
    pointer-events: none;
  }
</style>
