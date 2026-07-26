import fs from 'fs/promises';
import path from 'path';

const USERNAME = 'bobberdolle1';
const API_URL = `https://api.github.com/users/${USERNAME}/repos?sort=stargazers&per_page=100`;

// Ivanovo is UTC+3 (MSK). Single source of truth for the signal waveform —
// if the author relocates, change this and the label together.
const TZ_OFFSET_HOURS = 3;
const TZ_LABEL = 'UTC+3';

const REST_HEADERS = {
    'User-Agent': 'bobberdolle1-readme-generator',
    ...(process.env.GITHUB_TOKEN ? { Authorization: `token ${process.env.GITHUB_TOKEN}` } : {})
};

// PS2 boot-screen grade: cold blue-white light in a black void.
// No magenta — synthwave pink was fighting the console look.
const COLORS = {
    bg: '#01030a',
    void: '#000206',
    edge: '#020713',  // every block's bottom gradient stop; blocks below start here
    ice: '#cfeeff',   // hottest tower light
    cyan: '#7fd4ff',
    blue: '#1d6fb8',
    deep: '#0a2c55',
    white: '#ffffff',
    gray: '#4a5a70',
    darkGray: '#0a1018'
};

// Deterministic PRNG for decorative randomness (dust positions, flicker
// phases). Seeded once so a rebuild with identical data is a byte-identical
// file — the 6h Actions run must not churn diffs with cosmetic noise.
function mulberry32(seed) {
    let a = seed >>> 0;
    return () => {
        a |= 0; a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

/* ------------------------------------------------------------------ *
 * data
 * ------------------------------------------------------------------ */

// Returns every public non-fork repo plus the top slice for the cards.
// Stats must be computed over ALL repos — an earlier version sliced to 6
// first and then reported "PUBLIC REPOS: 6" for a 21-repo profile.
async function fetchRepos() {
    const res = await fetch(API_URL, { headers: REST_HEADERS });
    if (!res.ok) throw new Error(`repo list: ${res.status} ${res.statusText}`);
    const data = await res.json();
    const own = data.filter(repo => !repo.fork && repo.name !== USERNAME);
    return {
        all: own,
        top: [...own].sort((a, b) => b.stargazers_count - a.stargazers_count).slice(0, 6)
    };
}

async function fetchUser() {
    const res = await fetch(`https://api.github.com/users/${USERNAME}`, { headers: REST_HEADERS });
    if (!res.ok) throw new Error(`user: ${res.status} ${res.statusText}`);
    return res.json();
}

async function graphql(query, variables) {
    const token = process.env.GITHUB_TOKEN;
    if (!token) throw new Error('GITHUB_TOKEN is required for the GraphQL API');
    const res = await fetch('https://api.github.com/graphql', {
        method: 'POST',
        headers: {
            Authorization: `bearer ${token}`,
            'Content-Type': 'application/json',
            'User-Agent': REST_HEADERS['User-Agent']
        },
        body: JSON.stringify({ query, variables })
    });
    const json = await res.json();
    if (!json.data) throw new Error(`GraphQL: ${JSON.stringify(json).slice(0, 300)}`);
    return json.data;
}

// Exact per-day counts via GraphQL. The old version scraped the contributions
// HTML page for data-level (0-4), which quantised an 80-commit day and a
// 5-commit day into the same tower. Real counts give a real skyline.
async function fetchContributions() {
    const data = await graphql(`query($login:String!){
        user(login:$login){
            contributionsCollection{
                contributionCalendar{
                    totalContributions
                    weeks{ contributionDays{ date contributionCount weekday } }
                }
            }
        }
    }`, { login: USERNAME });
    const cal = data?.user?.contributionsCollection?.contributionCalendar;
    if (!cal) throw new Error('GraphQL returned no calendar');
    return cal;
}

// Aggregate language bytes across public sources only (privacy: PUBLIC), so
// local runs with a broad token and Actions runs with the repo-scoped
// GITHUB_TOKEN produce identical art.
async function fetchLanguages() {
    const data = await graphql(`query($login:String!){
        user(login:$login){
            repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC){
                nodes{ languages(first:10, orderBy:{field:SIZE, direction:DESC}){
                    edges{ size node{ name } }
                } }
            }
        }
    }`, { login: USERNAME });
    const nodes = data?.user?.repositories?.nodes;
    if (!nodes) throw new Error('GraphQL returned no repositories');
    const totals = new Map();
    // Partial GraphQL failures null out individual nodes/fields while the
    // top-level data key survives — skip the holes instead of crashing.
    for (const n of nodes)
        for (const e of n?.languages?.edges ?? [])
            if (e) totals.set(e.node.name, (totals.get(e.node.name) || 0) + e.size);
    const sum = [...totals.values()].reduce((a, b) => a + b, 0) || 1;
    return [...totals.entries()]
        .map(([name, size]) => ({ name, share: size / sum }))
        .sort((a, b) => b.share - a.share);
}

// Commit timestamps with hour precision. The events API only reaches back a
// few days on an active account, so instead we walk the default-branch
// history of the most recently pushed repos, filtered to the author — this
// yields months of real committedDate data.
async function fetchCommitHours(authorId, repoNames) {
    // Zero non-fork repos (or only the profile repo itself) must not build an
    // empty GraphQL selection set — that's a query error and a dead CI run.
    if (repoNames.length === 0) return { hours: Array(24).fill(0), sample: 0 };
    const fields = repoNames.map((n, i) =>
        `r${i}: repository(owner:${JSON.stringify(USERNAME)}, name:${JSON.stringify(n)}){
            defaultBranchRef{ target{ ... on Commit {
                history(first:80, author:{id:${JSON.stringify(authorId)}}){ nodes{ committedDate } }
            } } }
        }`).join('\n');
    const data = await graphql(`query{\n${fields}\n}`);
    const hours = Array(24).fill(0);
    let sample = 0;
    for (const key of Object.keys(data)) {
        const target = data[key]?.defaultBranchRef?.target;
        if (!target?.history) continue;
        for (const c of target.history.nodes) {
            const utc = parseInt(c.committedDate.slice(11, 13), 10);
            hours[(utc + TZ_OFFSET_HOURS + 24) % 24]++;
            sample++;
        }
    }
    return { hours, sample };
}

/* ------------------------------------------------------------------ *
 * helpers
 * ------------------------------------------------------------------ */

function escapeHtml(unsafe) {
    return (unsafe || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function lerpHex(a, b, t) {
    const pa = [1, 3, 5].map(i => parseInt(a.slice(i, i + 2), 16));
    const pb = [1, 3, 5].map(i => parseInt(b.slice(i, i + 2), 16));
    const mix = pa.map((v, i) => Math.round(v + (pb[i] - v) * Math.max(0, Math.min(1, t))));
    return '#' + mix.map(v => v.toString(16).padStart(2, '0')).join('');
}

const r2 = n => Math.round(n * 100) / 100;

function longestStreak(cal) {
    const days = cal.weeks.flatMap(w => w.contributionDays)
        .sort((a, b) => a.date.localeCompare(b.date));
    let cur = 0, best = 0;
    for (const d of days) {
        cur = d.contributionCount > 0 ? cur + 1 : 0;
        if (cur > best) best = cur;
    }
    return best;
}

/* ------------------------------------------------------------------ *
 * shared defs
 * ------------------------------------------------------------------ */

// Every block's sky ends at COLORS.edge; blocks below the header begin there
// too, so stacked <img> elements tonally continue one void even across the
// README's gaps. Only the header starts from true black (page opening).
function createDefs(skyTop = COLORS.edge) {
    return `
    <defs>
        <linearGradient id="skyFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${skyTop}" />
            <stop offset="55%" stop-color="${COLORS.bg}" />
            <stop offset="100%" stop-color="${COLORS.edge}" />
        </linearGradient>
        <radialGradient id="horizonGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#0a4a86" stop-opacity="0.55" />
            <stop offset="60%" stop-color="#062a52" stop-opacity="0.18" />
            <stop offset="100%" stop-color="${COLORS.bg}" stop-opacity="0" />
        </radialGradient>
        <filter id="bloom" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <style>
            .t-title { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-weight: 300; letter-spacing: 6px; fill: ${COLORS.ice}; }
            .t-sub   { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-weight: 300; letter-spacing: 3px; fill: ${COLORS.gray}; }
            .t-mono  { font-family: "SFMono-Regular", Consolas, "Courier New", monospace; fill: ${COLORS.cyan}; }
            .t-num   { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-weight: 200; fill: ${COLORS.ice}; }
            /* Animation contract for every class below: the resting state is
               fully visible. A renderer that never advances the timeline shows
               a complete, slightly-still page — never an empty one. Negative
               delays put looping effects mid-flight at frame 0. */
            @keyframes rise { from { transform: translateY(18px); } to { transform: translateY(0); } }
            .tw { animation: rise 0.75s cubic-bezier(0.16, 0.84, 0.24, 1) both; }
            @keyframes dustRise { from { transform: translateY(0); } to { transform: translateY(-20px); } }
            .dust { animation: dustRise 12s ease-in-out infinite alternate; }
            @keyframes beamFlicker { 0% { opacity: 0.12; } 50% { opacity: 0.28; } 100% { opacity: 0.12; } }
            .beam { animation: beamFlicker 8s ease-in-out infinite; }
            @keyframes beaconPulse { from { opacity: 0.12; } to { opacity: 0.38; } }
            .beacon { animation: beaconPulse 1.5s ease-in-out infinite alternate; }
            @keyframes pulseFade { 0% { opacity: 0.15; } 50% { opacity: 0.6; } 100% { opacity: 0.15; } }
            .pulse { animation: pulseFade 4s ease-in-out infinite; }
            @keyframes scanSweep { from { transform: translateX(0); } to { transform: translateX(1100px); } }
            .scan { animation: scanSweep 14s linear infinite; }
            @media (prefers-reduced-motion: reduce) {
                .tw, .rb1, .rb2, .dust, .beam, .beacon, .pulse, .scan { animation: none; }
            }
        </style>
    </defs>`;
}

/* ------------------------------------------------------------------ *
 * towers — the centrepiece
 * ------------------------------------------------------------------ */

function generateTowersSvg(cal) {
    const weeks = cal.weeks;
    const GRID_W = weeks.length;          // 53
    const GRID_H = 7;

    const counts = Array.from({ length: GRID_W }, () => Array(GRID_H).fill(0));
    let max = 0;
    let activeDays = 0;
    weeks.forEach((w, wi) => {
        w.contributionDays.forEach(d => {
            counts[wi][d.weekday] = d.contributionCount;
            if (d.contributionCount > max) max = d.contributionCount;
            if (d.contributionCount > 0) activeDays++;
        });
    });
    if (max === 0) max = 1;

    const WIDTH = 1000;
    const HEIGHT = 356;
    const PAD = 0.12;

    // Anisotropic isometry: a symmetric grid turns 53x7 into a thin diagonal
    // sliver. Stretching the week axis across the canvas and letting the day
    // axis fall away to the lower-left gives a wide, shallow field that still
    // reads left-to-right like the contribution graph it is.
    const WX = 16.4, WY = 1.05;    // one week step
    const DX = -8.4, DY = 7.1;     // one day step
    const X0 = 96, Y0 = 232;

    const px = (x, y) => r2(X0 + x * WX + y * DX);
    const py = (x, y, z = 0) => r2(Y0 + x * WY + y * DY - z);

    // Compress the range so one 80-commit spike doesn't flatten everything else,
    // but a big day still visibly towers over a 1-commit day.
    const heightFor = c => (c <= 0 ? 0 : 10 + 96 * Math.pow(c / max, 0.55));

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${HEIGHT}" width="100%" role="img" aria-label="${cal.totalContributions} contributions in the last year, rendered as PS2 boot towers">
  ${createDefs()}
  <defs>
    <linearGradient id="beamGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${COLORS.white}" stop-opacity="0" />
        <stop offset="100%" stop-color="${COLORS.white}" stop-opacity="0.9" />
    </linearGradient>
    <radialGradient id="vignette" cx="50%" cy="46%" r="72%">
        <stop offset="0%" stop-color="${COLORS.void}" stop-opacity="0" />
        <stop offset="62%" stop-color="${COLORS.void}" stop-opacity="0" />
        <stop offset="100%" stop-color="${COLORS.void}" stop-opacity="0.5" />
    </radialGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#skyFade)" />
  <ellipse cx="${WIDTH / 2}" cy="${Y0 + 30}" rx="520" ry="120" fill="url(#horizonGlow)" />
`;

    // Ground: one path for all 371 tiles instead of 371 <polygon> elements.
    let ground = '';
    for (let x = 0; x < GRID_W; x++) {
        for (let y = 0; y < GRID_H; y++) {
            ground += `M${px(x, y)},${py(x, y)}L${px(x + 1, y)},${py(x + 1, y)}` +
                `L${px(x + 1, y + 1)},${py(x + 1, y + 1)}L${px(x, y + 1)},${py(x, y + 1)}Z`;
        }
    }
    svg += `  <path d="${ground}" fill="none" stroke="#0d2440" stroke-width="0.5" opacity="0.55" />\n`;

    // Month ticks along the projected baseline: the field becomes a readable
    // timeline. A tick lands where the month changes between week columns.
    const monthNames = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
    let ticks = '';
    let prevMonth = null;
    weeks.forEach((w, wi) => {
        const first = w.contributionDays[0];
        if (!first) return;
        const m = parseInt(first.date.slice(5, 7), 10) - 1;
        if (prevMonth !== null && m !== prevMonth) {
            const tx = px(wi, 7.9), ty = py(wi, 7.9);
            if (tx > 40 && tx < WIDTH - 40)
                ticks += `<text x="${tx}" y="${ty}" class="t-mono" font-size="7.5" fill="${COLORS.gray}" opacity="0.5" text-anchor="middle">${monthNames[m]}</text>`;
        }
        prevMonth = m;
    });
    svg += `  <g>${ticks}</g>\n`;

    // Back-to-front by projected baseline, so nearer towers overlap farther ones.
    const cells = [];
    for (let x = 0; x < GRID_W; x++) {
        for (let y = 0; y < GRID_H; y++) {
            if (counts[x][y] > 0) cells.push({ x, y, c: counts[x][y], depth: py(x, y) });
        }
    }
    cells.sort((a, b) => a.depth - b.depth);

    // The newest active day gets a beacon: one quiet pulse at the field's
    // leading edge that says the machine is on.
    let newest = null;
    weeks.forEach((w, wi) => w.contributionDays.forEach(d => {
        if (d.contributionCount > 0 && (!newest || d.date > newest.date))
            newest = { date: d.date, x: wi, y: d.weekday };
    }));

    let towers = '';
    let beacon = '';
    for (const { x, y, c } of cells) {
        const h = heightFor(c);
        const t = Math.pow(c / max, 0.5);           // 0..1 intensity
        const top = lerpHex(COLORS.blue, COLORS.ice, t);
        const left = lerpHex('#061c38', COLORS.deep, t);
        const right = lerpHex(COLORS.deep, COLORS.blue, t);
        const edge = lerpHex(COLORS.cyan, COLORS.white, t);

        const x1 = x + PAD, y1 = y + PAD;
        const x2 = x + 1 - PAD, y2 = y + 1 - PAD;

        const bB = [px(x1, y1), py(x1, y1)];
        const bR = [px(x2, y1), py(x2, y1)];
        const bL = [px(x1, y2), py(x1, y2)];
        const bF = [px(x2, y2), py(x2, y2)];
        const tB = [bB[0], r2(bB[1] - h)];
        const tR = [bR[0], r2(bR[1] - h)];
        const tL = [bL[0], r2(bL[1] - h)];
        const tF = [bF[0], r2(bF[1] - h)];

        // Stagger the rise left-to-right like the PS2 field filling in.
        const delay = r2(x * 0.028 + y * 0.012);

        // CSS animation, not SMIL: with animation-fill-mode "both" the
        // towers are plainly visible if the animation never runs. The old
        // SMIL version started at opacity 0, so a renderer that skipped the
        // timeline showed an empty field.
        towers += `<g class="tw" style="animation-delay:${delay}s">` +
            `<polygon points="${tL[0]},${tL[1]} ${bL[0]},${bL[1]} ${bF[0]},${bF[1]} ${tF[0]},${tF[1]}" fill="${left}"/>` +
            `<polygon points="${tR[0]},${tR[1]} ${bR[0]},${bR[1]} ${bF[0]},${bF[1]} ${tF[0]},${tF[1]}" fill="${right}"/>` +
            `<polygon points="${tB[0]},${tB[1]} ${tR[0]},${tR[1]} ${tF[0]},${tF[1]} ${tL[0]},${tL[1]}" fill="${top}"/>` +
            `<path d="M${tL[0]},${tL[1]}L${tB[0]},${tB[1]}L${tR[0]},${tR[1]}" fill="none" stroke="${edge}" stroke-width="0.7" opacity="0.85"/>` +
            `<line x1="${tF[0]}" y1="${tF[1]}" x2="${bF[0]}" y2="${bF[1]}" stroke="${edge}" stroke-width="0.6" opacity="0.5"/>` +
            `</g>\n`;

        if (newest && x === newest.x && y === newest.y) {
            // A breathing white wash over the top face — an outline read as a
            // detached wireframe at README scale; a fill reads as light.
            beacon = `<polygon points="${tB[0]},${tB[1]} ${tR[0]},${tR[1]} ${tF[0]},${tF[1]} ${tL[0]},${tL[1]}" ` +
                `fill="${COLORS.white}" opacity="0.25" class="beacon"/>\n`;
        }
    }

    // Light beams over the brightest days — the literal PS2 tower gesture.
    // Height grows with the day's weight; flicker phases are seeded so a
    // rebuild with the same data emits the same bytes.
    const rand = mulberry32(0x50533200);
    const brightest = [...cells].sort((a, b) => b.c - a.c).slice(0, 5);
    let beams = '';
    for (const { x, y, c } of brightest) {
        const h = heightFor(c);
        const cx = px(x + 0.5, y + 0.5);
        const topY = py(x + 0.5, y + 0.5) - h;
        const beamH = r2(45 + 25 * Math.sqrt(c / max));
        const dur = r2(7 + rand() * 2);
        const del = r2(-rand() * 7);
        beams += `<rect x="${r2(cx - 0.6)}" y="${r2(topY - beamH)}" width="1.2" height="${beamH}" ` +
            `fill="url(#beamGrad)" opacity="0.22" class="beam" style="animation-duration:${dur}s;animation-delay:${del}s"/>\n`;
    }

    // The brightest towers get a bloom pass; everything else stays crisp.
    svg += `  <g filter="url(#bloom)">\n${towers}${beams}${beacon}  </g>\n`;

    // Vignette last: pushes the field into cinematic depth.
    svg += `  <rect width="100%" height="100%" fill="url(#vignette)" />\n`;

    const year = cal.totalContributions;
    svg += `  <text x="46" y="52" class="t-title" font-size="17">CONTRIBUTION FIELD</text>
  <text x="46" y="74" class="t-sub" font-size="10.5">LAST 365 DAYS // ${USERNAME}</text>
  <text x="${WIDTH - 46}" y="52" class="t-num" font-size="30" text-anchor="end">${year}</text>
  <text x="${WIDTH - 46}" y="72" class="t-sub" font-size="9.5" text-anchor="end">CONTRIBUTIONS · ${activeDays} ACTIVE DAYS · PEAK ${max}/DAY</text>
  <line x1="46" y1="88" x2="${WIDTH - 46}" y2="88" stroke="${COLORS.blue}" stroke-width="0.75" opacity="0.35"/>
</svg>`;

    return svg;
}

/* ------------------------------------------------------------------ *
 * header
 * ------------------------------------------------------------------ */

// A closed band following a sine curve. The path spans one wavelength past
// the canvas so a translateX(-lambda) loop is perfectly seamless.
function ribbonPath(W, yMid, amp, thick, lambda, phase) {
    const span = W + lambda;
    const N = Math.ceil(span / 8);
    const pts = [];
    for (let i = 0; i <= N; i++) {
        const x = (i * span) / N;
        pts.push([r2(x), r2(yMid + amp * Math.sin((2 * Math.PI * x) / lambda + phase))]);
    }
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) d += `L${pts[i][0]},${pts[i][1]}`;
    for (let i = pts.length - 1; i >= 0; i--) d += `L${pts[i][0]},${r2(pts[i][1] + thick)}`;
    return d + 'Z';
}

function generateHeaderSvg(cal) {
    const W = 1000, H = 190;

    // A low silhouette skyline built from the most recent weeks, so the header
    // and the tower field below are visibly the same world and the same data.
    const recent = cal.weeks.flatMap(w => w.contributionDays.map(d => d.contributionCount)).slice(-98);
    const peak = Math.max(1, ...recent);
    const bw = W / recent.length;
    let skyline = '';
    recent.forEach((c, i) => {
        if (c <= 0) return;
        const h = 5 + 33 * Math.pow(c / peak, 0.6);
        skyline += `<rect x="${r2(i * bw)}" y="${r2(H - h)}" width="${r2(bw - 1.6)}" height="${r2(h)}" fill="${COLORS.blue}"/>`;
    });

    // XMB-style ribbons: uniform horizontal color (any x-gradient would jump
    // at the loop seam), vertical fade so the top edge glows. CSS transform
    // only — the resting state is fully visible if the timeline never runs.
    const L1 = 500, L2 = 340;
    const rb1 = ribbonPath(W, 126, 13, 32, L1, 0.6);
    const rb2 = ribbonPath(W, 147, 9, 22, L2, 2.4);

    // XMB dust: a handful of motes drifting up through the title light.
    // Seeded, negative delays — frame 0 is a naturally scattered field.
    const rand = mulberry32(0x584d4201);
    let dust = '';
    for (let i = 0; i < 14; i++) {
        const x = r2(30 + rand() * 940);
        const y = r2(30 + rand() * 130);
        const r = r2(0.8 + rand() * 0.8);
        const o = r2(0.12 + rand() * 0.23);
        const dur = r2(9 + rand() * 7);
        const del = r2(-rand() * 8);
        const fill = i % 2 ? COLORS.cyan : COLORS.ice;
        dust += `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" opacity="${o}" class="dust" style="animation-duration:${dur}s;animation-delay:${del}s"/>`;
    }

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="vibecoder37 — RF, embedded, computer vision, Rust — Ivanovo, RU">
  ${createDefs(COLORS.void)}
  <defs>
    <linearGradient id="ribbonGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${COLORS.ice}" stop-opacity="0.55" />
      <stop offset="45%" stop-color="${COLORS.cyan}" stop-opacity="0.22" />
      <stop offset="100%" stop-color="${COLORS.blue}" stop-opacity="0" />
    </linearGradient>
    <style>
      @keyframes drift1 { to { transform: translateX(-${L1}px); } }
      @keyframes drift2 { to { transform: translateX(-${L2}px); } }
      .rb1 { animation: drift1 26s linear infinite; }
      .rb2 { animation: drift2 18s linear infinite; }
      /* Must be re-stated here: this style block comes after createDefs' in
         document order, so its .rb rules would otherwise out-cascade the
         shared reduced-motion override (media queries add no priority). */
      @media (prefers-reduced-motion: reduce) { .rb1, .rb2 { animation: none; } }
    </style>
  </defs>
  <rect width="100%" height="100%" fill="url(#skyFade)" />
  <ellipse cx="${W / 2}" cy="${H}" rx="460" ry="120" fill="url(#horizonGlow)" />
  <path class="rb1" d="${rb1}" fill="url(#ribbonGrad)" opacity="0.35" />
  <path class="rb2" d="${rb2}" fill="url(#ribbonGrad)" opacity="0.22" />
  <g opacity="0.28">${skyline}</g>
  ${dust}
  <g filter="url(#bloom)">
    <text x="${W / 2}" y="80" class="t-title" font-size="46" text-anchor="middle">vibecoder37</text>
  </g>
  <text x="${W / 2}" y="108" class="t-sub" font-size="11" text-anchor="middle">RF · EMBEDDED · COMPUTER VISION · RUST</text>
  <line x1="${W / 2 - 150}" y1="125" x2="${W / 2 + 150}" y2="125" stroke="${COLORS.blue}" stroke-width="0.75" opacity="0.5" class="pulse"/>
  <text x="${W / 2}" y="143" class="t-sub" font-size="9.5" text-anchor="middle" style="fill:#a3bedd">IVANOVO, RU</text>
</svg>`;
}

/* ------------------------------------------------------------------ *
 * signal — commit-hour waveform
 * ------------------------------------------------------------------ */

// One thin oscilloscope trace of when the machine runs. Degradation ladder
// keeps it honest at any sample size: <30 commits → 2-hour bins, <10 → a
// flat carrier line captioned SIGNAL LOW instead of a lying spiky curve.
function generateSignalSvg(hourData) {
    const W = 1000, H = 116;
    const X = 46, BW = W - 92;
    const BASE = 72, AMP = 34;

    const { hours, sample } = hourData;
    const lowSample = sample < 10;
    const binHours = !lowSample && sample < 30 ? 2 : 1;
    const nBins = 24 / binHours;

    const bins = Array(nBins).fill(0);
    hours.forEach((c, h) => { bins[Math.floor(h / binHours)] += c; });

    // Circular 3-tap smoothing, then normalise. The wave wraps at midnight —
    // hour 24 is hour 0, so the day reads as one continuous cycle.
    const smooth = bins.map((_, i) =>
        0.25 * bins[(i - 1 + nBins) % nBins] + 0.5 * bins[i] + 0.25 * bins[(i + 1) % nBins]);
    const maxV = Math.max(1, ...smooth);
    const val = i => smooth[((i % nBins) + nBins) % nBins] / maxV;

    const ptX = i => X + (i / nBins) * BW;
    const ptY = i => BASE - (lowSample ? 0.06 : val(i)) * AMP;

    // Catmull-Rom through the 24h cycle (virtual neighbours wrap) → beziers.
    let d = `M${r2(ptX(0))},${r2(ptY(0))}`;
    for (let i = 0; i < nBins; i++) {
        const x0 = ptX(i - 1), y0 = ptY(i - 1);
        const x1 = ptX(i), y1 = ptY(i);
        const x2 = ptX(i + 1), y2 = ptY(i + 1);
        const x3 = ptX(i + 2), y3 = ptY(i + 2);
        const c1x = r2(x1 + (x2 - x0) / 6), c1y = r2(y1 + (y2 - y0) / 6);
        const c2x = r2(x2 - (x3 - x1) / 6), c2y = r2(y2 - (y3 - y1) / 6);
        d += `C${c1x},${c1y} ${c2x},${c2y} ${r2(x2)},${r2(y2)}`;
    }

    const area = `${d}L${X + BW},${BASE + 14}L${X},${BASE + 14}Z`;

    let ticks = '';
    for (const h of [0, 6, 12, 18, 24]) {
        const tx = r2(X + (h / 24) * BW);
        ticks += `<line x1="${tx}" y1="88" x2="${tx}" y2="92" stroke="${COLORS.gray}" stroke-width="0.75" opacity="0.6"/>` +
            `<text x="${tx}" y="103" class="t-mono" font-size="8" fill="${COLORS.gray}" text-anchor="middle">${String(h).padStart(2, '0')}</text>`;
    }

    let peakMark = '';
    if (!lowSample) {
        const peakBin = smooth.indexOf(Math.max(...smooth));
        const phx = r2(ptX(peakBin)), phy = r2(ptY(peakBin));
        const peakHour = String(peakBin * binHours).padStart(2, '0');
        const anchor = phx > W - 160 ? 'end' : 'start';
        const lx = anchor === 'end' ? phx - 8 : phx + 8;
        peakMark = `<circle cx="${phx}" cy="${phy}" r="2" fill="${COLORS.ice}"/>
  <text x="${lx}" y="${r2(phy - 6)}" class="t-mono" font-size="9" text-anchor="${anchor}">PEAK ${peakHour}:00</text>`;
    }

    const caption = lowSample
        ? `SIGNAL LOW // ${sample} COMMITS VISIBLE · ${TZ_LABEL}`
        : `SIGNAL // COMMIT HOURS · RECENT ${sample} COMMITS · ${TZ_LABEL}`;

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Commit activity by hour of day (${TZ_LABEL}), from the last ${sample} commits">
  ${createDefs()}
  <defs>
    <linearGradient id="sigArea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${COLORS.cyan}" stop-opacity="0.14" />
      <stop offset="100%" stop-color="${COLORS.cyan}" stop-opacity="0" />
    </linearGradient>
    <linearGradient id="scanGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="${COLORS.ice}" stop-opacity="0" />
      <stop offset="50%" stop-color="${COLORS.ice}" stop-opacity="0.1" />
      <stop offset="100%" stop-color="${COLORS.ice}" stop-opacity="0" />
    </linearGradient>
    <clipPath id="plotClip"><rect x="${X}" y="26" width="${BW}" height="62" /></clipPath>
  </defs>
  <rect width="100%" height="100%" fill="url(#skyFade)" />
  <text x="${X}" y="24" class="t-sub" font-size="9.5">${caption}</text>
  <path d="${area}" fill="url(#sigArea)" />
  <g filter="url(#bloom)">
    <path d="${d}" fill="none" stroke="${COLORS.cyan}" stroke-width="1.4" />
  </g>
  ${peakMark}
  <g clip-path="url(#plotClip)">
    <rect x="${X - 90}" y="26" width="70" height="62" fill="url(#scanGrad)" class="scan" style="animation-delay:-5s"/>
  </g>
  ${ticks}
</svg>`;
}

/* ------------------------------------------------------------------ *
 * telemetry — languages + the one quiet stat line
 * ------------------------------------------------------------------ */

// The language field: one glowing strip, brightness by rank — the same
// cold-blue world as the towers, not a parrot of per-language brand colors.
// Below it, the profile's remaining numbers as a single mono line: the four
// 40px dashboard numbers are gone, the towers keep the page's only big digit.
function generateTelemetrySvg(langs, cal, repos, user) {
    const W = 1000, H = 132;
    const X = 46, BW = W - 92, Y = 44, BH = 12;
    const top = langs.slice(0, 6);
    const rest = 1 - top.reduce((s, l) => s + l.share, 0);
    const segs = [
        ...top.map(l => ({ label: l.name.toUpperCase(), share: l.share })),
        ...(rest > 0.005 ? [{ label: 'OTHER', share: rest }] : [])
    ];

    let x = X, bars = '';
    segs.forEach((s, i) => {
        const w = Math.max(0, s.share * BW - 2);
        const fill = s.label === 'OTHER'
            ? '#0a1d38'
            : lerpHex(COLORS.ice, COLORS.deep, segs.length <= 1 ? 0 : i / (segs.length - 1));
        bars += `<rect x="${r2(x)}" y="${Y}" width="${r2(w)}" height="${BH}" fill="${fill}"/>`;
        x += s.share * BW;
    });

    const legend = segs.map(s => `${escapeHtml(s.label)} ${(s.share * 100).toFixed(1)}%`).join('  ·  ');

    const streak = longestStreak(cal);
    const stars = repos.all.reduce((s, r) => s + r.stargazers_count, 0);
    const since = (user.created_at || '').slice(0, 4) || '—';
    const num = v => `<tspan fill="${COLORS.cyan}">${v}</tspan>`;
    const lab = t => `<tspan fill="${COLORS.gray}">${t}</tspan>`;
    const sep = `<tspan fill="${COLORS.deep}">  ·  </tspan>`;
    const statLine = [
        `${lab('EST. ')}${num(since)}`,
        `${num(streak + 'D')}${lab(' LONGEST STREAK')}`,
        `${num(stars)}${lab(' STARS')}`,
        `${num(user.followers)}${lab(' FOLLOWERS')}`
    ].join(sep);

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Language composition: ${legend}. Since ${since}, longest streak ${streak} days, ${stars} stars, ${user.followers} followers">
  ${createDefs()}
  <defs>
    <!-- The shared bloom's ±30% region would clip the glow of a 12px-tall
         bar to ~4px; this one gives the strip real vertical headroom. -->
    <filter id="bloomBar" x="-3%" y="-300%" width="106%" height="700%">
      <feGaussianBlur stdDeviation="3.5" result="b" />
      <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
  </defs>
  <rect width="100%" height="100%" fill="url(#skyFade)" />
  <text x="${X}" y="28" class="t-sub" font-size="9.5">CODE COMPOSITION // PUBLIC SOURCE</text>
  <g filter="url(#bloomBar)">${bars}</g>
  <text x="${W / 2}" y="${Y + BH + 26}" class="t-sub" font-size="9.5" text-anchor="middle" style="letter-spacing:1px">${legend}</text>
  <line x1="${X}" y1="100" x2="${W - X}" y2="100" stroke="${COLORS.blue}" stroke-width="0.75" opacity="0.3"/>
  <text x="${W / 2}" y="120" class="t-mono" font-size="10" text-anchor="middle" style="letter-spacing:2px">${statLine}</text>
</svg>`;
}

/* ------------------------------------------------------------------ *
 * project cards — one SVG per repo, clickable from the README
 * ------------------------------------------------------------------ */

function cardDefs() {
    return `<defs><style>
        .t-title { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-weight: 300; fill: ${COLORS.ice}; }
        .t-sub   { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-weight: 300; fill: ${COLORS.gray}; }
        .t-mono  { font-family: "SFMono-Regular", Consolas, "Courier New", monospace; fill: ${COLORS.cyan}; }
    </style></defs>`;
}

// The left spine's brightness encodes recency — a column of cards reads
// warm-to-cold at a glance. Days are computed at generation time; the 6h
// rebuild keeps them honest at day granularity.
function generateCardSvg(repo, now) {
    const W = 480, H = 132;

    const days = Math.max(0, Math.floor((now - Date.parse(repo.pushed_at)) / 86400000));
    const spineOpacity = days < 7 ? 0.9 : days < 30 ? 0.55 : 0.28;
    const pushedLabel = days === 0 ? 'PUSHED TODAY' : `PUSHED ${days}D AGO`;

    const words = (repo.description || '').split(/\s+/).filter(Boolean);
    const lines = [];
    let cur = '';
    for (const w of words) {
        if ((cur + w).length > 48) { if (cur.trim()) lines.push(cur.trim()); cur = w + ' '; }
        else cur += w + ' ';
    }
    if (cur.trim()) lines.push(cur.trim());
    // A single unbroken token (a bare URL description) can't be wrapped by
    // the word loop — hard-cap every line so nothing clips mid-glyph.
    const shown = lines.slice(0, 3).map(l => l.length > 48 ? l.slice(0, 47) + '…' : l);
    if (lines.length > 3) shown[2] = shown[2].slice(0, 44) + '…';

    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${escapeHtml(repo.name)}: ${escapeHtml(repo.description || '')}">
  ${cardDefs()}
  <rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" fill="#050b16" stroke="${COLORS.deep}" stroke-width="1"/>
  <rect width="2.5" height="${H}" fill="${COLORS.cyan}" opacity="${spineOpacity}"/>
  <path d="M${W - 26},10 L${W - 10},10 L${W - 10},26" fill="none" stroke="${COLORS.blue}" stroke-width="1" opacity="0.4"/>
  <text x="20" y="32" class="t-title" font-size="16" style="letter-spacing:2px">${escapeHtml(repo.name)}</text>
${shown.map((l, k) => `  <text x="20" y="${56 + k * 17}" class="t-sub" font-size="11.5" style="letter-spacing:0.5px">${escapeHtml(l)}</text>`).join('\n')}
  <text x="20" y="${H - 16}" class="t-mono" font-size="11">★ ${repo.stargazers_count}</text>
  <text x="70" y="${H - 16}" class="t-mono" font-size="11" fill="${COLORS.gray}">${escapeHtml(repo.language || '—')}</text>
  <text x="${W - 16}" y="${H - 16}" class="t-mono" font-size="9" fill="${COLORS.gray}" opacity="0.8" text-anchor="end">${pushedLabel}</text>
</svg>`;
}

// The section label lives outside the cards so the grid itself stays clean.
function generateLabelWorkSvg() {
    const W = 1000, H = 44;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Selected work">
  ${createDefs()}
  <rect width="100%" height="100%" fill="url(#skyFade)" />
  <text x="46" y="26" class="t-title" font-size="15">SELECTED WORK</text>
  <line x1="46" y1="36" x2="${W - 46}" y2="36" stroke="${COLORS.blue}" stroke-width="0.75" opacity="0.35"/>
</svg>`;
}

// Palette-native link chips replace the shields.io badges — the Telegram
// brand blue was the only off-palette pixel left on the page.
function generateLinkChipSvg(label) {
    const W = 150, H = 34;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${escapeHtml(label)}">
  ${cardDefs()}
  <rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" fill="#050b16" stroke="${COLORS.deep}" stroke-width="1"/>
  <rect width="2.5" height="${H}" fill="${COLORS.cyan}" opacity="0.75"/>
  <text x="${W / 2 + 1}" y="21" class="t-mono" font-size="11" text-anchor="middle" style="letter-spacing:2px">${escapeHtml(label)} ↗</text>
</svg>`;
}

/* ------------------------------------------------------------------ *
 * README card grid — rewritten between markers each run
 * ------------------------------------------------------------------ */

// The top-6-by-stars set changes over time; card files are rank-named
// (card-0.svg…) so image paths stay stable while hrefs must track the repo
// each rank currently points at. Only the marker region is touched.
async function rewriteReadmeCards(top) {
    const readmePath = path.join(process.cwd(), 'README.md');
    const START = '<!-- projects:start -->', END = '<!-- projects:end -->';
    let md;
    try {
        md = await fs.readFile(readmePath, 'utf8');
    } catch {
        console.warn('  README.md not found — card grid not rewritten');
        return;
    }
    const i = md.indexOf(START), j = md.indexOf(END);
    if (i === -1 || j === -1 || j < i) {
        console.warn('  projects markers not found — card grid not rewritten');
        return;
    }

    const rows = [];
    for (let r = 0; r < top.length; r += 2) {
        rows.push(top.slice(r, r + 2).map((repo, k) =>
            `  <a href="${repo.html_url}"><img src="assets/card-${r + k}.svg" width="49%" alt="${escapeHtml(repo.name)}" /></a>`
        ).join('\n'));
    }
    const block = `${START}\n<!-- generated by generate_assets.js — edit that file, not this block -->\n<div align="center">\n${rows.join('\n')}\n</div>\n${END}`;
    await fs.writeFile(readmePath, md.slice(0, i) + block + md.slice(j + END.length));
    console.log('  README.md card grid rewritten');
}

/* ------------------------------------------------------------------ *
 * main
 * ------------------------------------------------------------------ */

async function main() {
    const outDir = path.join(process.cwd(), 'assets');
    await fs.mkdir(outDir, { recursive: true });

    const [repos, cal, user, langs] = await Promise.all([
        fetchRepos(), fetchContributions(), fetchUser(), fetchLanguages()
    ]);
    const recentRepos = [...repos.all]
        .sort((a, b) => b.pushed_at.localeCompare(a.pushed_at))
        .slice(0, 10)
        .map(r => r.name);
    const hourData = await fetchCommitHours(user.node_id, recentRepos);
    console.log(`repos: ${repos.all.length} public, contributions: ${cal.totalContributions}, languages: ${langs.length}, commit sample: ${hourData.sample}`);

    const now = Date.now();
    const files = {
        'header.svg': generateHeaderSvg(cal),
        'towers.svg': generateTowersSvg(cal),
        'signal.svg': generateSignalSvg(hourData),
        'telemetry.svg': generateTelemetrySvg(langs, cal, repos, user),
        'label-work.svg': generateLabelWorkSvg(),
        'link-telegram.svg': generateLinkChipSvg('telegram'),
        'link-github.svg': generateLinkChipSvg('github'),
        ...Object.fromEntries(repos.top.map((repo, i) => [`card-${i}.svg`, generateCardSvg(repo, now)]))
    };

    for (const [name, content] of Object.entries(files)) {
        await fs.writeFile(path.join(outDir, name), content);
        console.log(`  ${name}  ${(content.length / 1024).toFixed(1)} KB`);
    }

    // Blocks that no longer exist as standalone files, plus card ranks
    // beyond the current top set (it can shrink below 6 — a stale committed
    // card would otherwise keep serving a possibly-private repo's name).
    for (const stale of ['stats.svg', 'langs.svg', 'projects.svg']) {
        await fs.rm(path.join(outDir, stale), { force: true });
    }
    for (let i = repos.top.length; i < 6; i++) {
        await fs.rm(path.join(outDir, `card-${i}.svg`), { force: true });
    }

    await rewriteReadmeCards(repos.top);
}

main().catch(e => {
    console.error('generation failed:', e.message);
    process.exit(1);
});
