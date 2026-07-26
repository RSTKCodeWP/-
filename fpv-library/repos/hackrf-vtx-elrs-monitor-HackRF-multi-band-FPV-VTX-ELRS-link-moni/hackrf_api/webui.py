"""The single-page dashboard served at / by webapp.py (no external assets).

Shows three band panels (VTX 5 GHz, 2.4 GHz ELRS, 900 MHz ELRS), each with its
own spectrum + waterfall, a prominent ELRS-detected status strip, and the VTX
channel grid. All bands update in bursts as the radio rotates to them.
"""

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FPV Spectrum Analysis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  /* ===== Talented Hobbyists — House Brand System v1.0 (dark) =====
     orange = brand energy (scalpel only) · red = danger only · go-green = armed/active */
  :root {
    --bg:#15171A; --panel:#1C1F23; --raised:#282C31; --line:#3A3F45;
    --txt:#FBF9F3; --dim:#8B9298;
    --brand:#EF5A1E; --brand-hi:#FB7440;       /* orange — brand accent, used sparingly */
    --accent:#38BFD2; --accent-deep:#0E8DA1;   /* cyan — links / data highlight */
    --hot:#3E9E4E;                              /* go-500 green — active / armed */
    --warn:#E6A015;                             /* caution */
    --red:#CF3A2E;                              /* danger only */
    --font-display:'Archivo',system-ui,sans-serif;
    --font-body:'Inter',system-ui,sans-serif;
    --font-mono:'JetBrains Mono',ui-monospace,Menlo,monospace;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:13px/1.45 var(--font-mono); -webkit-font-smoothing:antialiased; }
  header { display:flex; flex-wrap:nowrap; align-items:center; gap:16px; overflow:hidden;
           padding:0 16px; height:52px; background:color-mix(in srgb,var(--bg) 88%,transparent);
           border-bottom:1px solid var(--line); position:sticky; top:0; z-index:50; backdrop-filter:blur(8px); }
  #vtx-active-wrap { min-width:0; overflow:hidden; }
  #vtx-active { display:inline-block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
                max-width:300px; vertical-align:middle; }
  /* rotor wordmark */
  .wordmark { font-family:var(--font-display); font-weight:800; font-size:15px; letter-spacing:-.01em;
              color:var(--txt); display:inline-flex; align-items:center; gap:8px; white-space:nowrap; text-transform:lowercase; }
  .wordmark .rotor { width:22px; height:22px; color:var(--brand); flex:none; }
  /* eyebrow-style header stats (mono, uppercase) */
  .stat { color:var(--dim); font-family:var(--font-mono); font-size:11px; letter-spacing:.06em;
          text-transform:uppercase; }
  .stat b { color:var(--txt); font-weight:700; }
  .hazard { height:6px; width:100%;
            background:repeating-linear-gradient(-45deg,var(--brand) 0 12px,var(--bg) 12px 24px); }
  main { padding:12px 16px; display:flex; flex-direction:column; gap:12px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:10px 12px; }
  /* panel labels read as brand eyebrows: mono, uppercase, accent, tracked */
  .card h2 { font-family:var(--font-mono); font-size:11px; text-transform:uppercase; letter-spacing:.14em;
             color:var(--brand); font-weight:600; margin:0 0 8px; display:flex;
             justify-content:space-between; align-items:center; }
  canvas { width:100%; display:block; border-radius:2px; }
  .spec { height:96px; image-rendering:auto; }
  .wf { height:210px; image-rendering:auto; }
  /* status strip (VTX + 2 ELRS) */
  #elrs-strip { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
  /* Fixed height so changing content (e.g. multiple VTX detected) never reflows
     the page. All three strip cards share a grid row, so any one growing would
     push everything below — pinning the height prevents that. */
  .elrs-card { display:flex; align-items:center; gap:14px; padding:12px 16px; height:88px; overflow:hidden;
               border-radius:8px; border:1px solid var(--line); background:var(--panel); }
  .elrs-mid { flex:1; min-width:0; }   /* min-width:0 lets the text lines ellipsize */
  .elrs-light { width:40px; height:40px; border-radius:50%; background:var(--raised);
                box-shadow:0 0 0 2px var(--line) inset; flex:none; transition:all .3s; }
  .elrs-card.on .elrs-light { background:var(--hot); box-shadow:0 0 16px var(--hot), 0 0 0 2px var(--hot) inset; }
  .elrs-card.on { border-color:var(--hot); }
  .elrs-card.warn .elrs-light { background:var(--warn); box-shadow:0 0 16px var(--warn), 0 0 0 2px var(--warn) inset; }
  .elrs-card.warn { border-color:var(--warn); }
  .elrs-card.warn .elrs-state, .elrs-card.warn .elrs-conf .pct { color:var(--warn); }
  .elrs-name { font-family:var(--font-mono); font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--dim); }
  .elrs-state { font-family:var(--font-display); font-size:19px; font-weight:700; color:var(--txt); letter-spacing:-.01em;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:1px; }
  .elrs-card.on .elrs-state { color:var(--hot); }
  .elrs-meta { font-family:var(--font-mono); font-size:11px; color:var(--dim); margin-top:3px;
               font-variant-numeric:tabular-nums; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .elrs-conf { margin-left:auto; text-align:right; flex:none; min-width:58px; }
  .elrs-conf .pct { font-family:var(--font-display); font-size:24px; font-weight:800; font-variant-numeric:tabular-nums; }
  .elrs-card.on .elrs-conf .pct { color:var(--hot); }
  /* chips → brand badges (mono, uppercase, currentColor border) */
  .chip { font-family:var(--font-mono); font-size:10px; letter-spacing:.08em; text-transform:uppercase;
          padding:3px 8px; border-radius:2px; background:transparent; border:1px solid currentColor;
          color:var(--dim); min-width:104px; text-align:center; white-space:nowrap; }
  .chip.on { color:var(--hot); }
  .chip.scan { color:var(--warn); }
  .panels { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .panels .span2 { grid-column:1 / -1; }   /* VTX 5.8 GHz spans the full width */
  @media (max-width:900px){ .panels { grid-template-columns:1fr; } }
  .badge { font-family:var(--font-mono); font-size:10px; letter-spacing:.06em; text-transform:uppercase;
           background:transparent; color:var(--hot); border:1px solid currentColor; border-radius:2px;
           padding:2px 7px; font-weight:500; margin-right:4px; }
  .badge.dig { color:var(--accent); }
  .badge.none { color:var(--dim); }
  .grid { display:grid; grid-template-columns:repeat(9, 1fr); gap:3px; margin-top:8px; }
  .gh { color:var(--dim); font-size:10px; display:flex; align-items:center; justify-content:center; }
  .cell { position:relative; background:var(--bg); border:1px solid var(--line); border-radius:2px;
          padding:3px 2px; text-align:center; overflow:hidden; }
  .cell .nm { font-family:var(--font-mono); font-weight:700; font-size:11px; }
  .cell .fq { font-family:var(--font-mono); font-size:9px; color:var(--dim); font-variant-numeric:tabular-nums; }
  .cell .bar { position:absolute; left:0; bottom:0; height:3px; background:var(--accent); width:0%; }
  .cell.on { border-color:var(--hot); box-shadow:0 0 0 1px var(--hot) inset; }
  .cell.on .nm { color:var(--hot); } .cell.on .bar { background:var(--hot); }
  .cell.on.dig { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent) inset; }
  .cell.on.dig .nm { color:var(--accent); }
  .age { font-size:10px; color:var(--dim); font-weight:400; text-transform:none; letter-spacing:0; }
  /* emit (TX) control */
  /* form fields — brand .field look */
  .emit-row { display:flex; flex-wrap:wrap; align-items:center; gap:12px; }
  .emit-row label { font-family:var(--font-mono); font-size:11px; letter-spacing:.06em; text-transform:uppercase;
      color:var(--dim); display:flex; align-items:center; gap:5px; }
  .emit-row select, .emit-row input, .bc-row select { background:var(--bg); color:var(--txt);
      border:1px solid var(--line); border-radius:2px; padding:5px 8px; font:inherit; }
  .emit-row select:focus, .emit-row input:focus, .bc-row select:focus { outline:none; border-color:var(--brand); }
  .emit-row input { width:62px; }
  #emit-freq { font-size:12px; font-variant-numeric:tabular-nums; }
  /* TX buttons: orange brand-primary idle → red danger when live (transmitting) */
  .btn-tx, #emit-btn { font-family:var(--font-mono); font-size:12px; font-weight:700; letter-spacing:.08em;
      text-transform:uppercase; background:var(--brand); color:#15171A; border:1px solid var(--brand);
      border-radius:2px; padding:8px 18px; cursor:pointer; transition:.15s; }
  #emit-btn { margin-left:auto; }
  .btn-tx:hover:not(:disabled), #emit-btn:hover:not(:disabled) { background:var(--brand-hi); border-color:var(--brand-hi); }
  .btn-tx:disabled, #emit-btn:disabled { opacity:.45; cursor:default; }
  .btn-tx.live, #emit-btn.live { background:var(--red); border-color:var(--red); color:#fff; animation:emitpulse 1s infinite; }
  @keyframes emitpulse { 50% { opacity:.55; } }
  .emit-note { color:var(--dim); font-size:11px; margin-top:8px; }
  #emit-status.live { color:var(--red); } #emit-status.err { color:var(--red); }
  #emit-status.done { color:var(--hot); }
  /* tabs — brand nav (mono, uppercase, accent underline) */
  nav.tabs { display:flex; gap:0; margin-left:10px; align-self:stretch; }
  .tab { background:transparent; color:var(--dim); border:none; border-bottom:2px solid transparent;
         padding:0 16px; font-family:var(--font-mono); font-size:12px; letter-spacing:.06em; text-transform:uppercase;
         font-weight:600; cursor:pointer; }
  .tab:hover { color:var(--txt); }
  .tab.on { color:var(--txt); border-bottom-color:var(--brand); }
  .page[hidden] { display:none; }
  .spk { margin-left:auto; }
  /* secondary button — brand .btn-secondary */
  .btn-sec { font-family:var(--font-mono); font-size:12px; text-transform:uppercase; letter-spacing:.06em;
             background:transparent; color:var(--txt); border:1px solid var(--line); border-radius:2px;
             padding:7px 12px; cursor:pointer; transition:.15s; }
  .btn-sec:hover { border-color:var(--brand); }
  .bc-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
  .bc-row .rm { background:transparent; border:none; color:var(--red); cursor:pointer; font-size:15px; }
  .bc-freq { font-size:12px; color:var(--dim); min-width:120px; font-variant-numeric:tabular-nums; }
  #bc-status.live { color:var(--red); } #bc-status.done { color:var(--hot); } #bc-status.err { color:var(--red); }
  #sw-status.on { color:var(--red); } #sw-status.err { color:var(--red); }
  .caveat { color:var(--warn); }
  /* FPV voice announcer — brand toggle (go-green when armed) */
  .vbtn { margin-left:auto; cursor:pointer; font-family:var(--font-mono); font-size:11px; font-weight:700;
          letter-spacing:.06em; text-transform:uppercase; color:var(--hot);
          background:transparent; border:1px solid currentColor; border-radius:2px; padding:5px 10px; }
  .vbtn.off { color:var(--dim); }
  /* per-band pause control — brand toggle */
  .h2r { display:flex; align-items:center; gap:8px; }
  .pausebtn { cursor:pointer; font-family:var(--font-mono); font-weight:700; font-size:10px; letter-spacing:.06em;
              text-transform:uppercase; color:var(--dim); background:transparent; border:1px solid var(--line);
              border-radius:2px; padding:3px 8px; }
  .pausebtn:hover { border-color:var(--brand); color:var(--txt); }
  .pausebtn.paused { color:var(--warn); border-color:var(--warn); }
  .card.paused { opacity:.82; }
  .card.paused canvas { filter:grayscale(.45) brightness(.78); }
  .card.paused .chruler { opacity:.5; }
  #toast { position:fixed; right:18px; bottom:18px; max-width:380px; z-index:50;
           background:var(--raised); color:var(--hot); border:1px solid var(--hot); border-radius:4px;
           padding:12px 16px; font-family:var(--font-mono); font-size:15px; font-weight:700; box-shadow:var(--shadow-2,0 6px 24px rgba(0,0,0,.5));
           opacity:0; transform:translateY(10px); transition:opacity .25s, transform .25s; pointer-events:none; }
  #toast.show { opacity:1; transform:translateY(0); }
  /* VTX channel-label ruler — one color-coded row per band (L / A / F / R) */
  .chruler { position:relative; margin:4px 0 2px; }
  .rrow { position:absolute; left:0; right:0; height:13px; }
  .rtick { position:absolute; transform:translateX(-50%); top:0; font-size:8px; line-height:13px;
           white-space:nowrap; font-weight:700; }
  .rleg { position:absolute; left:0; top:0; font-size:8px; line-height:13px; font-weight:700; opacity:.9;
          background:var(--panel); padding-right:2px; }
</style>
</head>
<body>
<header>
  <span class="wordmark"><svg class="rotor" viewBox="0 0 64 64" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><circle cx="32" cy="32" r="5"/><line x1="32" y1="32" x2="13" y2="13"/><line x1="32" y1="32" x2="51" y2="13"/><line x1="32" y1="32" x2="13" y2="51"/><line x1="32" y1="32" x2="51" y2="51"/><circle cx="13" cy="13" r="8"/><circle cx="51" cy="13" r="8"/></g></svg>talented&nbsp;hobbyists</span>
  <nav class="tabs">
    <button class="tab on" data-tab="spectrum">Spectrum Analysis</button>
    <button class="tab" data-tab="broadcast">Broadcasting</button>
  </nav>
  <span class="stat">scanning <b id="active-band">–</b></span>
  <span class="stat">cycle <b id="cycle">0</b></span>
  <span class="stat" id="vtx-active-wrap">VTX: <span id="vtx-active"></span></span>
  <button id="voicebtn" class="vbtn" title="Speak a callout when a 5.8 GHz VTX is detected — including whether it's an analog or digital video feed; says 'multiple VTX channels detected' when several are up">🔊 ANNOUNCE: ON</button>
</header>
<div class="hazard"></div>
<main>
  <section id="page-spectrum" class="page">
    <div id="elrs-strip"></div>
    <div class="panels" id="panels"></div>
    <div class="card" id="vtx-grid-card">
      <h2>VTX channels (5.8 GHz analog plan) — lit = active</h2>
      <div class="grid" id="chgrid"></div>
    </div>
  </section>

  <section id="page-broadcast" class="page" hidden>
    <div class="card">
      <h2>Broadcast VTX channels (TX) <span class="age" id="bc-status">idle</span></h2>
      <div id="bc-rows"></div>
      <div class="emit-row" style="margin-top:10px">
        <button id="bc-add" class="btn-sec">+ add channel</button>
        <label>duration <input id="bc-secs" type="number" value="30" min="0" step="5"></label><span class="age">s &nbsp;(0 = until stopped)</span>
        <label>TX gain <input id="bc-gain" type="number" value="47" min="0" max="47"></label><span class="age">dB (max 47 — louder; not real mW)</span>
        <button id="bc-go" class="btn-tx">BROADCAST</button>
      </div>
      <div class="emit-note">One channel = a steady carrier; multiple channels = a fast round-robin that
        reads as simultaneous on a <b>max-hold</b> waterfall (one radio can't truly do 37-MHz-spaced
        channels at once). <b>mW is a relative loudness target, not real power.</b> Monitoring pauses
        while transmitting. Only transmit where you are legally permitted.</div>
    </div>
    <div class="card">
      <h2>Spectrum sweep — Raceband (TX) <span class="age" id="sw-status">off</span></h2>
      <div class="emit-row">
        <label>on <input id="sw-on" type="number" value="10" min="1"></label><span class="age">s</span>
        <label>off <input id="sw-off" type="number" value="3" min="0"></label><span class="age">s</span>
        <label>TX gain <input id="sw-gain" type="number" value="47" min="0" max="47"></label><span class="age">dB</span>
        <button id="sw-toggle" class="btn-tx">START SWEEP</button>
      </div>
      <div class="emit-note">Cycles Raceband R1→R8 (CW carriers), <b>on</b> then <b>off</b>, looping until
        you switch it off — same as the CLI sweep.</div>
    </div>
  </section>
</main>
<div id="toast"></div>
<script>
function turbo(t){
  t=Math.min(1,Math.max(0,t));
  const r=34.61+t*(1172.33+t*(-10793.56+t*(33300.12+t*(-38394.49+t*14825.05))));
  const g=23.31+t*(557.33+t*(1225.33+t*(-3574.96+t*(1073.77+t*707.56))));
  const b=27.2+t*(3211.1+t*(-15327.97+t*(27814+t*(-22569.18+t*6838.66))));
  return [Math.min(255,Math.max(0,r))|0,Math.min(255,Math.max(0,g))|0,Math.min(255,Math.max(0,b))|0];
}
const P={};      // panel state by band id
let META=null, chCells={};

// ---- FPV channel voice announcer -------------------------------------------
// When a *new* VTX channel lights up in the 5.8 GHz panel, speak a random
// quirky callout (and flash a toast). Debounced so it never spams.
const VTX_BAND_SPOKEN={L:'Low band',A:'Band A',B:'Band B',E:'Band E',F:'Fat Shark',R:'Race band'};
const VTX_NUM=['','one','two','three','four','five','six','seven','eight'];
const PHRASES=[
  "Yo! FPV drone on {CH}!",
  "Heads up — somebody's ripping {CH}!",
  "Incoming! {CH} just went hot!",
  "We got a bandit on {CH}!",
  "Whoop whoop — {CH} is live!",
  "Drone spotted! {CH}, baby!",
  "Buckle up, {CH} is transmitting!",
  "Eyes up! Video on {CH}!",
  "Somebody's airborne on {CH}!",
  "{CH} lit up like a Christmas tree!",
  "Brraap! {CH} is in the air!",
  "New contact: {CH}!",
  "Pilot detected on {CH}!",
  "Look alive — {CH} is broadcasting!",
  "Zoom zoom! {CH} is flying!",
  "Radar ping: {CH}!",
  "We've got company on {CH}!",
  "Hot mic on {CH}!",
  "Throttle up — {CH} is online!",
  "Beep boop, drone on {CH}!",
  "{CH} just crashed the party!",
  "Signal lock: {CH}!",
  "Goggles on! {CH} is sending video!",
  "Sound the {CH} alarm!",
  "That's a {CH}, no doubt about it!",
  "FPV alert! {CH} engaged!",
  "Drone o'clock on {CH}!",
  "{CH} is bumpin'!",
  "Catch me if you can — {CH}!",
  "Props spinning on {CH}!",
  "Watch the skies: {CH}!",
  "Bogey on {CH}!",
  "{CH} just punched in!",
  "Live from {CH}, it's a drone!",
  "Ooh, fresh video on {CH}!",
  "{CH} is on the menu!",
  "Lock and load — {CH}!",
  "We have liftoff on {CH}!",
  "Static cleared, {CH} is here!",
  "The {CH} squad has arrived!",
  "Ding ding! {CH}!",
  "Somebody's shredding {CH}!",
  "{CH} — full send!",
  "Tally-ho! {CH} in sight!",
  "New blip on {CH}!",
  "Quad in the air: {CH}!",
  "{CH} is screaming!",
  "Hot signal alert — {CH}!",
  "Boom! {CH} detected!",
  "{CH} just woke up!",
  "Roger that — {CH} flying!",
  "Get the goggles, {CH}'s up!",
  "{CH} entering the arena!",
  "Vroom! {CH} on air!",
  "Spectrum says: {CH}!",
  "Pilot in the house on {CH}!",
  "{CH} is going brrr!",
  "Sky's busy — {CH}!",
  "Fresh meat on {CH}!",
  "{CH} popped up!",
  "Mayday? Nah, just {CH}!",
  "{CH} is sending it!",
  "Contact, contact — {CH}!",
  "Whoa, {CH} came alive!",
  "Drone bingo: {CH}!",
  "{CH} just keyed up!",
  "Eyes on {CH}!",
  "{CH} cranking out video!",
  "Heads up pilots — {CH}!",
  "The air's hot on {CH}!",
  "{CH} reporting for duty!",
  "Zip! {CH} streaking by!",
  "{CH} is live and loud!",
  "New flyer on {CH}!",
  "{CH} just hit the gas!",
  "Blip blip — {CH}!",
  "{CH}'s in the building!",
  "Somebody's cookin' on {CH}!",
  "Wakey wakey, {CH}!",
  "{CH} — that's a transmit!",
  "Spotted a quad on {CH}!",
  "{CH} buzzing the tower!",
  "Send it on {CH}!",
  "{CH} is throwing photons!",
  "Got a live one: {CH}!",
  "{CH} just lit the band!",
  "Look out below — {CH}!",
  "{CH} is on the loose!",
  "Fresh signal: {CH}!",
  "{CH} ripping the sky!",
  "Beep! Drone {CH}!",
  "{CH} on the prowl!",
  "Channel check: {CH} is hot!",
  "{CH} flexin' on the spectrum!",
  "Pew pew — {CH}!",
  "{CH} just went full throttle!",
  "New kid on {CH}!",
  "{CH} smashed the airwaves!",
  "Stand by — {CH} inbound!",
  "Yeehaw! {CH} is flying!"
];
let voiceOn=true, vtxPrev=new Set(), lastAnnounce=0;
const ANNOUNCE_GAP_MS=3000;
function spokenChannel(name){
  if(!name) return 'a mystery channel';
  const b=VTX_BAND_SPOKEN[name[0]]||('Band '+name[0]);
  const n=VTX_NUM[parseInt(name.slice(1),10)]||name.slice(1);
  return (b+' '+n).trim();
}
function phraseFor(name){
  const ph=PHRASES[Math.floor(Math.random()*PHRASES.length)];
  return ph.replace('{CH}', spokenChannel(name));
}
function showToast(txt){
  const t=document.getElementById('toast');
  t.textContent='📣 '+txt; t.classList.add('show');
  clearTimeout(showToast._h); showToast._h=setTimeout(()=>t.classList.remove('show'),4000);
}
function pickVoice(){
  const vs=(window.speechSynthesis.getVoices()||[]);
  return vs.find(v=>/en[-_]US/i.test(v.lang) && /Samantha|Alex|Daniel|Karen|Google US English/i.test(v.name))
      || vs.find(v=>/en[-_]US/i.test(v.lang))
      || vs.find(v=>/^en/i.test(v.lang)) || null;
}
function speak(txt){
  try{ const u=new SpeechSynthesisUtterance(txt);
    const v=pickVoice(); if(v){ u.voice=v; u.lang=v.lang; } else { u.lang='en-US'; }
    u.rate=1.05; u.pitch=1.1; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);
  }catch(e){}
}
function announceVtx(sortedSigs){
  // sortedSigs is power-descending. Several channels -> "Multiple VTX channels
  // detected" + the Raceband-first label list. A single NEW channel -> the
  // quirky one-liner, with any very-close cross-band alternative spoken too.
  const prim=s=>(s.primary||(s.candidates&&s.candidates[0]));
  const cur=new Set((sortedSigs||[]).map(prim).filter(Boolean));
  if(!cur.size){ vtxPrev=cur; announceVtx._last=''; return; }
  const kindByName={}; (sortedSigs||[]).forEach(s=>{const p=prim(s); if(p) kindByName[p]=s.kind;});
  const spokenKind=k=>(k==='digital'?'digital':(k==='analog'?'analog':''));
  let line, key;
  if(cur.size>=2){
    const names=[...cur].sort();
    key='multi:'+names.join(',');
    line='Multiple VTX channels detected: '+names.map(spokenChannel).join(', ');
    // if every feed is the same type, call it out (e.g. "all digital video")
    const kinds=new Set(names.map(n=>spokenKind(kindByName[n])).filter(Boolean));
    if(kinds.size===1 && names.every(n=>spokenKind(kindByName[n]))) line+=' — all '+[...kinds][0]+' video.';
  } else {
    const name=[...cur][0];
    key='one:'+name;
    if(vtxPrev.has(name)){ vtxPrev=cur; return; }   // only quirk on a NEW channel
    const s=(sortedSigs||[]).find(x=>prim(x)===name)||{};
    const alts=(s.alt||[]).map(x=>x.name);
    const k=spokenKind(s.kind);
    line=phraseFor(name);
    if(alts.length) line+=' …or maybe '+alts.map(spokenChannel).join(' or ')+'.';
    if(k) line+=' Looks like '+(k==='analog'?'an ':'a ')+k+' video feed.';
  }
  vtxPrev=cur;
  if(key===announceVtx._last) return;
  const now=Date.now();
  if(now-lastAnnounce<ANNOUNCE_GAP_MS) return;
  announceVtx._last=key; lastAnnounce=now;
  showToast(line);
  if(voiceOn) speak(line);
}
function toggleVoice(){
  voiceOn=!voiceOn;
  const b=document.getElementById('voicebtn');
  b.textContent=voiceOn?'🔊 ANNOUNCE: ON':'🔇 ANNOUNCE: OFF';
  b.classList.toggle('off',!voiceOn);
  try{ window.speechSynthesis.resume(); }catch(e){}
  if(voiceOn) speak('Announcer armed.');
}

async function init(){
  META=await (await fetch('/api/meta')).json();
  const strip=document.getElementById('elrs-strip');
  const panels=document.getElementById('panels');
  for(const b of META.bands){
    // panel  (VTX 5.8 GHz spans the full width; the two ELRS bands share the next row)
    const card=document.createElement('div'); card.className='card'+(b.kind==='vtx'?' span2':''); card.id='card-'+b.id;
    const ruler = b.kind==='vtx' ? `<div class="chruler" id="ruler-${b.id}"></div>` : '';
    card.innerHTML=`<h2><span>${b.name} &nbsp;<span class="age">${b.lo_mhz}-${b.hi_mhz} MHz · ${b.bin_hz/1e3} kHz bins</span></span>`+
      `<span class="h2r"><span class="chip scan" id="chip-${b.id}">…</span><button class="pausebtn" id="pause-${b.id}">⏸ pause</button></span></h2>`+
      ruler+
      `<canvas class="spec" id="spec-${b.id}"></canvas><canvas class="wf" id="wf-${b.id}"></canvas>`;
    panels.appendChild(card);
    document.getElementById('pause-'+b.id).onclick=()=>togglePause(b.id);
    // status card in the strip
    if(b.kind==='vtx'){
      const vc=document.createElement('div'); vc.className='elrs-card'; vc.id='vtxstat';
      vc.innerHTML=`<div class="elrs-light"></div>`+
        `<div class="elrs-mid"><div class="elrs-name">VTX 5.8 GHz — loudest</div><div class="elrs-state">SCANNING…</div>`+
        `<div class="elrs-meta" id="vtxstatmeta">waiting for first dwell</div></div>`+
        `<div class="elrs-conf"><div class="pct" id="vtxstatpct">–</div><div class="elrs-name" id="vtxstatlbl">channel</div></div>`;
      strip.appendChild(vc);
    }
    if(b.kind==='elrs'){
      const ec=document.createElement('div'); ec.className='elrs-card'; ec.id='elrs-'+b.id;
      ec.innerHTML=`<div class="elrs-light"></div>`+
        `<div class="elrs-mid"><div class="elrs-name">${b.name}</div><div class="elrs-state">SCANNING…</div>`+
        `<div class="elrs-meta" id="elrsmeta-${b.id}">waiting for first dwell</div></div>`+
        `<div class="elrs-conf"><div class="pct" id="elrspct-${b.id}">–</div><div class="elrs-name">confidence</div></div>`;
      strip.appendChild(ec);
    }
    const nb=b.num_bins||Math.round((b.hi_mhz-b.lo_mhz)*1e6/b.bin_hz);
    const off=document.createElement('canvas'); off.width=nb; off.height=META.history;
    const offctx=off.getContext('2d'); offctx.fillStyle='#05070b'; offctx.fillRect(0,0,nb,META.history);
    P[b.id]={cfg:b, cursor:0, nb, off, offctx, rowImg:offctx.createImageData(nb,1),
             vmin:-90, vmax:-30, freqs:b.freqs_mhz||[], paused:!!b.paused};
    const wf=document.getElementById('wf-'+b.id); wf.width=nb; wf.height=META.history;
    const sp=document.getElementById('spec-'+b.id); sp.width=nb; sp.height=96;
    if(b.kind==='vtx'){
      // Focus the 5.8 GHz view on the raceband cluster: condense everything below
      // ~5640 MHz (the low 'L' band) into a thin strip; give the rest most of the width.
      P[b.id].view={split:5640, leftFrac:0.12};
      const chans=[];
      for(const bn in b.bands){ b.bands[bn].forEach((f,i)=>chans.push({name:bn+(i+1), f:+f, race:bn==='R'})); }
      P[b.id].channels=chans;
      buildGrid(b);
      buildRuler(b, P[b.id]);
    }
    loopBand(b.id);
  }
  setupTabs();
  setupBroadcast();
}

// ---- tabs ----
function setupTabs(){
  document.querySelectorAll('.tab').forEach(t=>{
    t.onclick=()=>{
      document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===t));
      document.getElementById('page-spectrum').hidden = t.dataset.tab!=='spectrum';
      document.getElementById('page-broadcast').hidden = t.dataset.tab!=='broadcast';
    };
  });
}

// ---- broadcasting page ----
let EMIT_FREQS={};
function setupBroadcast(){
  const vb=(META.bands||[]).find(b=>b.kind==='vtx');
  if(!vb||!vb.bands){ document.getElementById('page-broadcast').innerHTML=
      '<div class="card">No VTX band configured — broadcasting unavailable.</div>'; return; }
  EMIT_FREQS=vb.bands;
  addBcRow();
  document.getElementById('bc-add').onclick=addBcRow;
  document.getElementById('bc-go').onclick=onBroadcastClick;
  document.getElementById('sw-toggle').onclick=onSweepClick;
  pollEmit();
}
function addBcRow(){
  const rows=document.getElementById('bc-rows');
  const row=document.createElement('div'); row.className='bc-row';
  const bandSel=document.createElement('select');
  Object.keys(EMIT_FREQS).forEach(bn=>{const o=document.createElement('option');o.value=bn;o.textContent=bn;bandSel.appendChild(o);});
  const chSel=document.createElement('select');
  for(let i=1;i<=8;i++){const o=document.createElement('option');o.value=i;o.textContent=i;chSel.appendChild(o);}
  bandSel.value=EMIT_FREQS['R']?'R':Object.keys(EMIT_FREQS)[0];
  const freq=document.createElement('span'); freq.className='bc-freq';
  const rm=document.createElement('button'); rm.className='rm'; rm.textContent='✕'; rm.title='remove channel';
  const upd=()=>{const f=(EMIT_FREQS[bandSel.value]||[])[(+chSel.value)-1]; freq.textContent=f?('· '+f+' MHz'):'–';};
  bandSel.onchange=upd; chSel.onchange=upd;
  rm.onclick=()=>{ if(document.querySelectorAll('#bc-rows .bc-row').length>1) row.remove(); };
  row.append(document.createTextNode('band '),bandSel,document.createTextNode(' ch '),chSel,freq,rm);
  rows.appendChild(row); upd();
}
function gatherChannels(){
  return [...document.querySelectorAll('#bc-rows .bc-row')].map(r=>{
    const s=r.querySelectorAll('select'); return s[0].value+s[1].value; });
}
function setBc(cls,txt){const el=document.getElementById('bc-status'); el.className='age '+(cls||''); el.textContent=txt;}
function setSw(cls,txt){const el=document.getElementById('sw-status'); el.className='age '+(cls||''); el.textContent=txt;}

async function onBroadcastClick(){
  const e=await (await fetch('/api/emit')).json();
  if(e.status==='running' && e.mode==='broadcast'){ await fetch('/api/emit/stop',{method:'POST'}); return; }
  const chans=gatherChannels();
  const secs=+document.getElementById('bc-secs').value;
  const gain=+document.getElementById('bc-gain').value;
  const dur = secs>0 ? (secs+'s') : 'until stopped';
  // No confirmation dialog — clicking BROADCAST transmits immediately.
  const r=await (await fetch('/api/emit/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({mode:'broadcast',channels:chans,seconds:secs,gain:gain,confirm:true})})).json();
  if(!r.ok) setBc('err','error: '+(r.error||r.detail||'failed'));
}
async function onSweepClick(){
  const e=await (await fetch('/api/emit')).json();
  if(e.status==='running' && e.mode==='sweep'){ await fetch('/api/emit/stop',{method:'POST'}); return; }
  const on=+document.getElementById('sw-on').value, off=+document.getElementById('sw-off').value;
  const gain=+document.getElementById('sw-gain').value;
  // No confirmation dialog — clicking starts the sweep immediately.
  const r=await (await fetch('/api/emit/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({mode:'sweep',seconds_each:on,gap_s:off,gain:gain,confirm:true})})).json();
  if(!r.ok) setSw('err','error: '+(r.error||r.detail||'failed'));
}
async function pollEmit(){
  try{
    const e=await (await fetch('/api/emit')).json();
    const bcBtn=document.getElementById('bc-go'), swBtn=document.getElementById('sw-toggle');
    const runBc = e.status==='running' && e.mode==='broadcast';
    const runSw = e.status==='running' && e.mode==='sweep';
    bcBtn.classList.toggle('live',runBc); bcBtn.textContent=runBc?'STOP':'BROADCAST'; bcBtn.disabled=runSw;
    swBtn.classList.toggle('live',runSw); swBtn.textContent=runSw?'STOP SWEEP':'START SWEEP'; swBtn.disabled=runBc;
    if(runBc){ const cur=e.current?(' · '+e.current.channel+' '+e.current.freq_mhz+'MHz'):'';
      setBc('live','● TX '+(e.label||(e.channels||[]).join(' + '))+cur+(e.remaining_s!=null?(' · '+e.remaining_s+'s left'):'')); }
    else if(!runSw){ if(e.status==='done') setBc('done','done'); else if(e.status==='error') setBc('err','error: '+(e.error||'')); else setBc('','idle'); }
    if(runSw){ const cur=e.current?(e.current.channel+' '+e.current.freq_mhz+'MHz'):''; setSw('on','● sweeping '+cur); }
    else if(!runBc){ if(e.status==='error') setSw('err','error: '+(e.error||'')); else setSw('','off'); }
  }catch(e){}
  setTimeout(pollEmit, 600);
}

function buildGrid(b){
  const grid=document.getElementById('chgrid'); grid.innerHTML='';
  const corner=document.createElement('div'); corner.className='gh'; corner.textContent='band'; grid.appendChild(corner);
  for(let i=1;i<=8;i++){const h=document.createElement('div');h.className='gh';h.textContent=i;grid.appendChild(h);}
  for(const band of Object.keys(b.bands)){
    const lab=document.createElement('div'); lab.className='gh'; lab.textContent=band; grid.appendChild(lab);
    b.bands[band].forEach((f,idx)=>{
      const name=band+(idx+1);
      const cell=document.createElement('div'); cell.className='cell';
      cell.innerHTML=`<div class="nm">${name}</div><div class="fq">${f}</div><div class="bar"></div>`;
      grid.appendChild(cell); chCells[name]=cell;
    });
  }
}

async function togglePause(id){
  const p=P[id]; const want=!p.paused;
  try{ const r=await (await fetch('/api/pause?id='+id+'&paused='+(want?1:0))).json();
       p.paused = (typeof r.paused==='boolean') ? r.paused : want; }
  catch(e){ p.paused=want; }
  applyPause(id);
}
function applyPause(id){
  const p=P[id], btn=document.getElementById('pause-'+id), card=document.getElementById('card-'+id);
  if(btn){ btn.textContent=p.paused?'▶ resume':'⏸ pause'; btn.classList.toggle('paused',p.paused); }
  if(card) card.classList.toggle('paused',p.paused);
}

async function loopBand(id){
  try{
    const p=P[id];
    const d=await (await fetch('/api/band?id='+id+'&since='+p.cursor)).json();
    if(d) renderBand(id,d);
  }catch(e){}
  setTimeout(()=>loopBand(id), 600);
}

function adaptScale(p, ref){
  let lo=Infinity, hi=-Infinity;
  for(const v of ref){ if(v<lo)lo=v; if(v>hi)hi=v; }
  if(!isFinite(lo)) return;
  p.vmin += ((lo-3)-p.vmin)*0.25; p.vmax += ((hi+3)-p.vmax)*0.25;
}

function pushRows(p, rows){
  const nb=p.nb, h=META.history, k=Math.min(rows.length,h);
  p.offctx.drawImage(p.off,0,k,nb,h-k,0,0,nb,h-k);
  const start=rows.length-k;
  for(let j=0;j<k;j++){
    const row=rows[start+j], px=p.rowImg.data;
    for(let x=0;x<nb;x++){
      const t=(row[x]-p.vmin)/(p.vmax-p.vmin), c=turbo(t), o=x*4;
      px[o]=c[0];px[o+1]=c[1];px[o+2]=c[2];px[o+3]=255;
    }
    p.offctx.putImageData(p.rowImg,0,h-k+j);
  }
  const wctx=document.getElementById('wf-'+p.cfg.id).getContext('2d');
  if(p.view){
    // Remap the waterfall the same way as the spectrum: squeeze the low band
    // into leftFrac, stretch the raceband cluster across the rest.
    const v=p.view, splitBin=Math.round((v.split-p.cfg.lo_mhz)/(p.cfg.hi_mhz-p.cfg.lo_mhz)*nb);
    const lw=Math.max(1,Math.round(v.leftFrac*nb));
    wctx.imageSmoothingEnabled=false; wctx.clearRect(0,0,nb,h);
    if(splitBin>0) wctx.drawImage(p.off, 0,0, splitBin,h, 0,0, lw,h);
    wctx.drawImage(p.off, splitBin,0, nb-splitBin,h, lw,0, nb-lw,h);
    // channel grid drawn once per fresh waterfall paint (no alpha build-up)
    drawChannelGrid(wctx, p, nb, h, 0.45, 0.10);
  } else {
    wctx.drawImage(p.off,0,0);
  }
}

// Map a frequency (MHz) to an x position in [0,W]. For panels with a focus
// 'view' (the VTX 5.8 GHz panel) this is piecewise: everything below the split
// is squeezed into leftFrac of the width, the raceband cluster gets the rest.
function viewX(p, fMhz, W){
  const b=p.cfg, v=p.view;
  const f=Math.min(b.hi_mhz, Math.max(b.lo_mhz, fMhz));
  if(v){
    if(f<=v.split) return ((f-b.lo_mhz)/(v.split-b.lo_mhz))*v.leftFrac*W;
    return (v.leftFrac + ((f-v.split)/(b.hi_mhz-v.split))*(1-v.leftFrac))*W;
  }
  return ((f-b.lo_mhz)/(b.hi_mhz-b.lo_mhz))*W;
}

// Bands we label + their colors. R highlighted; B/E stay as faint unlabeled grid lines.
const LABELED_BANDS=['L','A','F','R'];
const BAND_LABEL_COLOR={L:'#7c8aa0', A:'#ffb454', F:'#c98bff', R:'#39b8ff'};
const BAND_GRID_RGB={L:'124,138,160', A:'255,180,84', F:'201,139,255', R:'57,184,255'};

function buildRuler(b, p){
  const r=document.getElementById('ruler-'+b.id); if(!r) return;
  r.innerHTML='';
  const rows=LABELED_BANDS.filter(bn=>b.bands[bn]);
  r.style.height=(rows.length*13+2)+'px';
  rows.forEach((bn,ri)=>{
    const row=document.createElement('div'); row.className='rrow'; row.style.top=(ri*13)+'px';
    const col=BAND_LABEL_COLOR[bn]||'var(--accent)';
    const leg=document.createElement('span'); leg.className='rleg'; leg.style.color=col; leg.textContent=bn; row.appendChild(leg);
    b.bands[bn].forEach((f,i)=>{
      const s=document.createElement('span'); s.className='rtick'; s.style.color=col;
      s.style.left=(viewX(p,+f,1)*100)+'%'; s.textContent=bn+(i+1);
      row.appendChild(s);
    });
    r.appendChild(row);
  });
}

// Vertical channel reference lines on a canvas (W×H). Labeled bands (L/A/F/R)
// are drawn in their band color; the rest (B/E) stay faint, so you can see
// which band a peak lines up with.
function drawChannelGrid(ctx, p, W, H, strongAlpha, faintAlpha){
  if(!p.channels) return;
  ctx.lineWidth=1;
  for(const c of p.channels){
    const rgb=BAND_GRID_RGB[c.name[0]];
    const x=Math.round(viewX(p,c.f,W))+0.5;
    ctx.strokeStyle = rgb ? ('rgba('+rgb+','+strongAlpha+')') : ('rgba(170,185,205,'+faintAlpha+')');
    ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke();
  }
}

// Trace drawer that honors the focus mapping (linear when p.view is unset).
function drawTraceView(ctx,arr,p,W,y,style,wd){
  const lo=p.cfg.lo_mhz, hi=p.cfg.hi_mhz, n=arr.length;
  ctx.strokeStyle=style; ctx.lineWidth=wd; ctx.beginPath();
  for(let i=0;i<n;i++){
    const f=lo+(i/(n-1))*(hi-lo), px=viewX(p,f,W), py=y(arr[i]);
    i?ctx.lineTo(px,py):ctx.moveTo(px,py);
  }
  ctx.stroke();
}

function drawTrace(ctx,arr,W,y,style,wd){
  ctx.strokeStyle=style; ctx.lineWidth=wd; ctx.beginPath();
  for(let x=0;x<arr.length;x++){const px=(x/(arr.length-1))*W, py=y(arr[x]); x?ctx.lineTo(px,py):ctx.moveTo(px,py);}
  ctx.stroke();
}

function drawSpec(p, d){
  const b=p.cfg, cv=document.getElementById('spec-'+b.id), ctx=cv.getContext('2d');
  const W=cv.width,H=cv.height; ctx.fillStyle='#0a0f16'; ctx.fillRect(0,0,W,H);
  const y=v=>H-((v-p.vmin)/(p.vmax-p.vmin))*H;
  // VTX: condensed-low-band divider + full channel grid behind the trace
  if(b.kind==='vtx' && p.view){
    const xd=viewX(p,p.view.split,W);
    ctx.strokeStyle='rgba(124,138,160,.5)'; ctx.setLineDash([3,3]);
    ctx.beginPath(); ctx.moveTo(xd,0); ctx.lineTo(xd,H); ctx.stroke(); ctx.setLineDash([]);
    drawChannelGrid(ctx, p, W, H, 0.35, 0.12);
  }
  // ELRS focus sub-band shading + hop markers
  if(b.kind==='elrs' && b.focus_lo_mhz){
    const x0=viewX(p,b.focus_lo_mhz,W), x1=viewX(p,b.focus_hi_mhz,W);
    ctx.fillStyle='rgba(57,184,255,.06)'; ctx.fillRect(x0,0,x1-x0,H);
    const a=d.analysis||{};
    for(const hf of (a.hop_freqs_mhz||[])){
      const x=viewX(p,hf,W);
      ctx.strokeStyle='rgba(52,227,107,.5)'; ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke();
    }
  }
  // ELRS shows max-hold (the hop comb); VTX shows smoothed avg
  if(b.kind==='elrs'){
    if(d.avg) drawTraceView(ctx,d.avg,p,W,y,'rgba(120,140,165,.4)',1);
    if(d.maxhold) drawTraceView(ctx,d.maxhold,p,W,y,'#34e36b',1.4);
  } else {
    if(d.rows && d.rows.length) drawTraceView(ctx,d.rows[d.rows.length-1],p,W,y,'rgba(120,140,165,.4)',1);
    if(d.avg) drawTraceView(ctx,d.avg,p,W,y,'#39b8ff',1.5);
    const a=d.analysis||{};
    for(const s of (a.signals||[])){
      const x=viewX(p,s.freq_mhz,W);
      ctx.strokeStyle='rgba(52,227,107,.7)'; ctx.lineWidth=1.5;
      ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); ctx.lineWidth=1;
      ctx.fillStyle='#34e36b'; ctx.font='bold 10px monospace'; ctx.textAlign='center';
      ctx.fillText(s.candidates[0]||'', x, 10);
    }
  }
}

function renderBand(id,d){
  const p=P[id]; p.cursor=d.count;
  if(typeof d.paused==='boolean' && d.paused!==p.paused){ p.paused=d.paused; applyPause(id); }
  document.getElementById('active-band').textContent=d.active_band||'–';
  document.getElementById('cycle').textContent=d.cycle||0;
  const ref = (d.cfg && d.cfg.kind==='elrs') ? d.maxhold : (d.avg||[]);
  if(d.maxhold) adaptScale(p, d.maxhold); else if(d.avg) adaptScale(p,d.avg);
  if(d.rows && d.rows.length){ pushRows(p,d.rows); }
  drawSpec(p,d);
  const chip=document.getElementById('chip-'+id);
  if(p.cfg.kind==='elrs'){ updateElrs(id,d,chip); }
  else { updateVtx(d,chip); }
}

function updateElrs(id,d,chip){
  const a=d.analysis||{};
  const verdict=a.verdict||'quiet';
  const present=verdict==='tx_active';
  // headline % = FHSS detection confidence (so strong 2.4 WiFi still reads 100%,
  // just labelled "WiFi / ambient"); the verdict drives the colour.
  const conf=Math.round((a.confidence_smoothed!=null?a.confidence_smoothed:(a.confidence||0))*100);
  const card=document.getElementById('elrs-'+id);
  card.classList.toggle('on',present);
  card.classList.toggle('warn',verdict==='ambient');
  const stateEl=card.querySelector('.elrs-state');
  if(present){ stateEl.textContent='● ELRS TX ACTIVE'; }
  else if(verdict==='ambient'){ stateEl.textContent='⚠ WiFi / ambient'; }
  else if(verdict==='weak'){ stateEl.textContent='◐ faint (rx-only?)'; }
  else { stateEl.textContent='○ no TX'; }
  document.getElementById('elrspct-'+id).textContent=conf+'%';
  const aa=(a.above_ambient_db!=null)?(' · '+(a.above_ambient_db>=0?'+':'')+a.above_ambient_db+' dB vs ambient'):'';
  document.getElementById('elrsmeta-'+id).textContent=
    (a.n_hops||0)+' hops · interm '+(a.intermittency_db||0)+' dB · pk '+(a.peak_dbm!=null?a.peak_dbm:'–')+' dBm'+aa;
  card.title=a.note||'';
  chip.className='chip '+(present?'on':((verdict==='weak'||verdict==='ambient')?'scan':''));
  chip.textContent=present?('TX ACTIVE '+conf+'%'):(verdict==='ambient'?('WiFi '+conf+'%'):(verdict==='weak'?'faint':'quiet'));
}

function updateVtxStatus(d){
  const a=d.analysis||{};
  const card=document.getElementById('vtxstat'); if(!card) return;
  const stateEl=card.querySelector('.elrs-state');
  const pct=document.getElementById('vtxstatpct'), meta=document.getElementById('vtxstatmeta');
  const lbl=document.getElementById('vtxstatlbl');
  const sigs=(a.signals||[]).slice().sort((x,y)=>y.power_dbm-x.power_dbm);
  card.classList.remove('on','warn');
  if(!sigs.length){
    stateEl.textContent='○ no VTX'; pct.textContent='–'; lbl.textContent='channel';
    meta.textContent='no active video transmitter'; card.title='';
    return;
  }
  // primary = Raceband-first assumed label; alts = very-close cross-band options
  const fmt=s=>({prim:(s.primary||(s.candidates&&s.candidates[0])||s.freq_mhz.toFixed(0)),
                 alts:(s.alt||[]).map(x=>x.name)});
  if(sigs.length>=2){
    card.classList.add('warn');
    stateEl.textContent='⚠ MULTIPLE VTX';
    pct.textContent=sigs.length+'×'; lbl.textContent='channels';
    // Compact single-line summary (full per-channel detail lives in the tooltip)
    // so the card height never changes with the number of channels.
    meta.innerHTML=sigs.map(s=>{
      const f=fmt(s);
      return `<b style="color:var(--warn)">${f.prim}</b> <span style="color:var(--dim)">${Math.round(s.power_dbm)}dBm</span>`;
    }).join('<span style="color:var(--line)"> · </span>');
    card.title='Multiple VTX channels: '+sigs.map(s=>{const f=fmt(s);
      return f.prim+' '+s.freq_mhz.toFixed(1)+'MHz '+s.power_dbm+'dBm'+(f.alts.length?(' (or '+f.alts.join('/')+')'):'');}).join(',  ');
  } else {
    const s=sigs[0], f=fmt(s);
    card.classList.add('on');
    stateEl.textContent=f.prim+'  ('+(s.kind||'')+')';
    pct.textContent=Math.round(s.power_dbm); lbl.textContent='dBm';
    let m=s.freq_mhz.toFixed(1)+' MHz';
    if(f.alts.length) m+=`  ·  <span class="caveat">could also be ${f.alts.join(' / ')}</span>`;
    meta.innerHTML=m;
    card.title=f.alts.length?('Shared frequency — could be '+[f.prim].concat(f.alts).join(' or ')):'';
  }
}

function updateVtx(d,chip){
  const a=d.analysis||{};
  const sigs=a.signals||[];
  updateVtxStatus(d);
  announceVtx(sigs.slice().sort((x,y)=>y.power_dbm-x.power_dbm));
  // header chip + top strip
  chip.className='chip '+(sigs.length?'on':'scan');
  chip.textContent=sigs.length?(sigs.length+' active'):'clear';
  const el=document.getElementById('vtx-active'); el.innerHTML='';
  if(!sigs.length){ el.innerHTML='<span class="badge none">none</span>'; }
  for(const s of sigs){
    const bd=document.createElement('span'); bd.className='badge'+(s.kind==='digital'?' dig':'');
    const prim=s.primary||s.candidates[0]||s.freq_mhz.toFixed(0);
    const amb=(s.alt&&s.alt.length)?'<small style="color:var(--warn)">*</small>':'';
    bd.innerHTML=prim+amb+' <small>'+(s.kind==='digital'?'D':'A')+'</small>';
    bd.title=`${s.freq_mhz} MHz ${s.power_dbm} dBm duty ${(s.occupancy*100||0).toFixed(0)}%`+
             (s.alt&&s.alt.length?(' — or '+s.alt.map(x=>x.name).join(' / ')):'');
    el.appendChild(bd);
  }
  // grid
  const byName={}; (a.channels||[]).forEach(c=>byName[c.name]=c);
  for(const name in chCells){
    const c=byName[name]; if(!c) continue; const cell=chCells[name];
    cell.classList.toggle('on',c.active); cell.classList.toggle('dig',c.active&&c.kind==='digital');
    cell.querySelector('.bar').style.width=Math.round((c.occupancy||0)*100)+'%';
  }
}

document.getElementById('voicebtn').onclick=toggleVoice;
// Chrome needs a user gesture before audio; the first click anywhere unlocks it.
document.addEventListener('click',()=>{try{window.speechSynthesis.resume();}catch(e){}},{once:true});
init();
</script>
</body>
</html>
"""
