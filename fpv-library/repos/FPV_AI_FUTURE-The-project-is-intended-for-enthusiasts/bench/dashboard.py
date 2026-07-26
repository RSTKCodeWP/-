"""The single-page dashboard served at GET /.

Kept as a module-level string so the server stays dependency-light (no template dir).
Vanilla JS: polls /telemetry, renders the HUD, and POSTs control changes.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Block-3 Seeker Bench</title>
<style>
  :root{--bg:#0d1014;--panel:#161b22;--line:#263040;--txt:#dbe3ee;--dim:#7d8aa0;
        --grn:#3ddc6b;--amb:#f5b948;--cyn:#46c6ff;--org:#ff8a3d;--red:#ff5a5a;--mono:'SFMono-Regular',Menlo,Consolas,monospace}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);font-family:Inter,system-ui,sans-serif;font-size:14px}
  header{display:flex;align-items:center;gap:14px;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
  header h1{font-size:15px;margin:0;letter-spacing:.5px;font-weight:600}
  header .sub{color:var(--dim);font-size:12px}
  .live{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--dim)}
  .wrap{display:grid;grid-template-columns:minmax(520px,1fr) 360px;gap:14px;padding:14px;align-items:start}
  .view{background:#000;border:1px solid var(--line);border-radius:10px;overflow:hidden;line-height:0}
  .view img{width:100%;display:block;image-rendering:pixelated}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px}
  .panel h2{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--dim);margin:0 0 10px}
  .state{font-family:var(--mono);font-size:22px;font-weight:700;letter-spacing:.5px}
  .badge{display:inline-block;padding:2px 9px;border-radius:6px;font-family:var(--mono);font-size:12px;font-weight:700;margin-left:8px;vertical-align:3px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;font-family:var(--mono)}
  .grid .k{color:var(--dim);font-size:11px}
  .grid .v{font-size:16px;font-weight:600}
  .bar{height:14px;background:#0b0e12;border:1px solid var(--line);border-radius:4px;position:relative;margin:3px 0 9px;overflow:hidden}
  .bar .mid{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--line)}
  .bar .fill{position:absolute;top:0;bottom:0;background:var(--cyn);opacity:.85}
  .blab{display:flex;justify-content:space-between;font-family:var(--mono);font-size:11px;color:var(--dim)}
  .ctl{display:flex;align-items:center;justify-content:space-between;margin:9px 0;font-size:13px}
  .ctl input[type=range]{width:150px}
  .ctl .val{font-family:var(--mono);color:var(--cyn);min-width:34px;text-align:right}
  button{background:#21304a;color:var(--txt);border:1px solid var(--line);border-radius:7px;padding:7px 12px;cursor:pointer;font-size:13px}
  button:hover{background:#2b3f60}
  button.rec.on{background:#5a1d1d;border-color:var(--red)}
  select{background:#0b0e12;color:var(--txt);border:1px solid var(--line);border-radius:6px;padding:5px}
  .sw{position:relative;width:38px;height:20px}
  .sw input{opacity:0;width:0;height:0}
  .sl{position:absolute;inset:0;background:#0b0e12;border:1px solid var(--line);border-radius:20px;transition:.15s}
  .sl:before{content:"";position:absolute;height:14px;width:14px;left:2px;top:2px;background:var(--dim);border-radius:50%;transition:.15s}
  .sw input:checked + .sl{background:#16351f;border-color:var(--grn)}
  .sw input:checked + .sl:before{transform:translateX(18px);background:var(--grn)}
  .note{color:var(--dim);font-size:11px;margin-top:10px;line-height:1.5}
  .mode{font-family:var(--mono);font-size:18px;font-weight:700;padding:3px 12px;border-radius:6px;background:#23262d;color:var(--dim)}
  .mode.engaged{background:#3a1414;color:#ff8a80}
  button.big{flex:1;padding:13px;font-size:15px;font-weight:700}
  button.launch{background:#16351f;border-color:var(--grn);color:var(--grn)}
  button.launch:disabled{background:#1a1d22;border-color:var(--line);color:#4a5260;cursor:not-allowed}
  button.safe{background:#3a1414;border-color:var(--red);color:#ff8a80}
</style>
</head>
<body>
<header>
  <h1>BLOCK-3 · THERMAL SEEKER BENCH</h1>
  <span class="sub">read-only · no FC commands</span>
  <span class="live" id="live">connecting…</span>
</header>
<div class="wrap">
  <div class="view"><img id="view" src="/stream" alt="thermal view"></div>
  <div>
    <div class="panel">
      <h2>Source · video</h2>
      <div class="ctl" style="margin:0 0 10px"><span>Now running</span><span class="val" id="curvid" style="min-width:0;max-width:210px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">—</span></div>
      <div style="display:flex;gap:8px;align-items:center">
        <select id="videosel" style="flex:1"></select>
        <button id="loadvid">Load &amp; run</button>
      </div>
      <div style="display:flex;gap:10px;margin-top:10px">
        <button id="pausebtn" class="big" style="flex:1">⏸ Pause</button>
      </div>
      <div class="note">Pick a clip → <b>Load &amp; run</b> restarts the seeker on it (acquisition resets to STANDBY). <b>Pause</b> freezes the running system.</div>
    </div>
    <div class="panel">
      <h2>Engagement · read-only</h2>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
        <span class="mode" id="mode">STANDBY</span>
        <span class="note" style="margin:0">no FC connected · guidance preview only</span>
      </div>
      <div style="margin-bottom:12px">
        <div class="k" style="margin-bottom:5px">Mission chain (supervisor)</div>
        <div id="mission-chain" style="display:flex;gap:4px;flex-wrap:wrap;font-family:var(--mono);font-size:10px"></div>
      </div>
      <div style="display:flex;gap:10px">
        <button id="launch" class="big launch" disabled>▶ LAUNCH</button>
        <button id="safe" class="big safe">■ SAFE</button>
      </div>
      <div class="ctl" style="margin-top:12px"><span>Aim reticle</span><input type="range" id="designation_box_px" min="80" max="400" step="20" value="240"><span class="val" id="vret">240</span></div>
      <div class="note">Put the centre reticle on your target → wait for the green LOCK → press LAUNCH. SAFE returns to standby and re-arms acquisition. Only targets inside the reticle can lock.</div>
    </div>
    <div class="panel">
      <h2>Tracking</h2>
      <div><span class="state" id="state">—</span><span class="badge" id="lock">—</span></div>
      <div class="grid" style="margin-top:12px">
        <div><div class="k">λ̇ az (rad/s)</div><div class="v" id="lam_az">—</div></div>
        <div><div class="k">λ̇ el (rad/s)</div><div class="v" id="lam_el">—</div></div>
        <div><div class="k">bearing az°</div><div class="v" id="az_deg">—</div></div>
        <div><div class="k">bearing el°</div><div class="v" id="el_deg">—</div></div>
        <div><div class="k">blobs</div><div class="v" id="n_blobs">—</div></div>
        <div><div class="k">threshold</div><div class="v" id="thr">—</div></div>
        <div><div class="k">top snr</div><div class="v" id="snr">—</div></div>
        <div><div class="k">top area</div><div class="v" id="area">—</div></div>
      </div>
    </div>
    <div class="panel">
      <h2>Guidance command (preview)</h2>
      <div class="blab"><span>roll</span><span id="vroll">—</span></div>
      <div class="bar"><div class="mid"></div><div class="fill" id="broll"></div></div>
      <div class="blab"><span>yaw rate</span><span id="vyaw">—</span></div>
      <div class="bar"><div class="mid"></div><div class="fill" id="byaw"></div></div>
      <div class="blab"><span>pitch</span><span id="vpitch">—</span></div>
      <div class="bar"><div class="mid"></div><div class="fill" id="bpitch"></div></div>
      <div class="blab"><span>throttle</span><span id="vthr">—</span></div>
      <div class="bar"><div class="fill" id="bthrottle" style="left:0"></div></div>
    </div>
    <div class="panel">
      <h2>Calibration</h2>
      <div class="ctl"><span>Clutter mask <span id="maskpx" style="color:var(--dim)"></span></span>
        <label class="sw"><input type="checkbox" id="mask_on" checked><span class="sl"></span></label></div>
      <div class="ctl"><span>Invert (black-hot)</span>
        <label class="sw"><input type="checkbox" id="invert"><span class="sl"></span></label></div>
      <div class="ctl"><span>Border crop</span><input type="range" id="border_crop" min="0" max="80" value="24"><span class="val" id="vborder">24</span></div>
      <div class="ctl"><span>Min SNR</span><input type="range" id="min_snr" min="0" max="20" step="0.5" value="2"><span class="val" id="vsnr">2</span></div>
      <div class="ctl"><span>Min area</span><input type="range" id="min_area" min="1" max="60" value="2"><span class="val" id="varea">2</span></div>
      <div class="ctl"><span>Colormap</span><select id="colormap"></select></div>
      <div class="ctl" style="margin-top:12px">
        <button id="recal">Recalibrate mask</button>
        <button id="record" class="rec">● Record</button>
      </div>
      <div style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px">
        <div class="k" style="margin-bottom:6px">Y16 dataset capture · lossless</div>
        <div class="ctl" style="margin:0 0 8px"><span>Class</span>
          <select id="y16class"><option>DRONE</option><option>BIRD</option><option>AIRPLANE</option><option>HELICOPTER</option><option>BALLOON</option><option>CLUTTER</option></select></div>
        <div class="ctl" style="margin:0 0 8px">
          <label style="font-size:12px;color:var(--dim)"><input type="checkbox" id="y16radio"> radiometric Y16</label>
          <button id="y16rec" class="rec">● Record clip</button></div>
        <div class="note" id="y16status">Raw u16 → y16_dataset/. Only radiometric Y16 counts toward field-readiness; 8-bit is recorded honestly-flagged.</div>
      </div>
      <div class="note">Point the camera at a cool background, then move a small hot source. The green box is the LOCK; the yellow arrow is where guidance would steer.</div>
    </div>
  </div>
</div>
<script>
const $=id=>document.getElementById(id);
const COL={NO_TARGET:'var(--dim)',CANDIDATE:'var(--amb)',ACQUIRING:'var(--amb)',TRACKING:'var(--cyn)',
  PREDICTIVE_TRACK:'var(--cyn)',LOCKED:'var(--grn)',REACQUIRE:'var(--org)',ERROR:'var(--red)',STARTING:'var(--dim)'};
const MPHASES=['IDLE','ACQUIRE','STUDY','READY','ENGAGING'];
const MCOL={IDLE:'var(--dim)',ACQUIRE:'var(--amb)',STUDY:'var(--cyn)',READY:'var(--grn)',
  ENGAGING:'var(--org)',COMPLETE:'var(--grn)',ABORTED:'var(--red)'};
function renderMissionChain(ph){
  const host=$('mission-chain'); if(!host) return;
  if(!host.dataset.built){host.innerHTML=MPHASES.map(p=>
    '<span data-p="'+p+'" style="padding:2px 7px;border-radius:5px;border:1px solid var(--line);color:var(--dim)">'+p+'</span>'
  ).join('<span style="color:var(--dim)">›</span>'); host.dataset.built='1';}
  const active=ph||'IDLE';
  host.querySelectorAll('[data-p]').forEach(el=>{const on=el.dataset.p===active;
    el.style.background=on?(MCOL[active]||'var(--cyn)'):'transparent';
    el.style.color=on?'#06210f':'var(--dim)'; el.style.borderColor=on?(MCOL[active]||'var(--cyn)'):'var(--line)';
    el.style.fontWeight=on?'700':'400';});
}
function bipolar(el,v){v=Math.max(-1,Math.min(1,v||0));const V=$(el);V.style.left=(v>=0?50:50+v*50)+'%';V.style.width=Math.abs(v)*50+'%';
  V.style.background=v>=0?'var(--cyn)':'var(--amb)';}
function uni(el,v){v=Math.max(0,Math.min(1,v||0));$(el).style.left='0';$(el).style.width=(v*100)+'%';$(el).style.background='var(--grn)';}
let cmaps=false;
async function poll(){
  try{
    const t=await (await fetch('/telemetry')).json();
    $('live').textContent=(t.fps_total||0)+' fps · frame '+(t.frame_id||0)+' · '+(t.resolution?t.resolution.join('×'):'');
    $('state').textContent=t.state||'—';$('state').style.color=COL[t.state]||'var(--txt)';
    const lk=$('lock');lk.textContent=t.locked?'LOCK':'no lock';
    lk.style.background=t.locked?'var(--grn)':'#0b0e12';lk.style.color=t.locked?'#06210f':'var(--dim)';
    const md=$('mode');md.textContent=t.mode||'STANDBY';md.classList.toggle('engaged',!!t.engaged);
    renderMissionChain(t.mission_phase);
    $('launch').disabled = !t.can_launch;
    for(const k of ['lam_az','lam_el','az_deg','el_deg','n_blobs']) $(k).textContent=(t[k]==null?'—':t[k]);
    $('thr').textContent=t.threshold==null?'—':t.threshold;
    $('snr').textContent=t.top?t.top.snr:'—';$('area').textContent=t.top?t.top.area:'—';
    $('maskpx').textContent=t.mask_on?('('+(t.mask_px||0)+' px)'):'(off)';
    const c=t.command;
    $('vroll').textContent=c?c.roll:'—';$('vyaw').textContent=c?c.yaw:'—';$('vpitch').textContent=c?c.pitch:'—';$('vthr').textContent=c?c.throttle:'—';
    bipolar('broll',c?c.roll:0);bipolar('byaw',c?c.yaw:0);bipolar('bpitch',c?c.pitch:0);uni('bthrottle',c?c.throttle:0.5);
    if(!cmaps&&t.colormaps){cmaps=true;const s=$('colormap');t.colormaps.forEach(m=>{const o=document.createElement('option');o.value=o.textContent=m;if(m==t.colormap)o.selected=true;s.appendChild(o);});}
    if(t.video)$('curvid').textContent=t.video;
    if(typeof t.paused==='boolean')setPaused(t.paused);
  }catch(e){$('live').textContent='disconnected';}
}
async function ctl(obj){try{return await (await fetch('/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)})).json();}catch(e){return null;}}
let paused=false;
async function loadVideos(){
  try{
    const v=await (await fetch('/videos')).json();
    const s=$('videosel');const keep=s.value;s.innerHTML='';
    (v.videos||[]).forEach(name=>{const o=document.createElement('option');o.value=o.textContent=name;if(name===(keep||v.current))o.selected=true;s.appendChild(o);});
    if(!(v.videos||[]).length){const o=document.createElement('option');o.textContent='(no clips in folder)';s.appendChild(o);}
    $('curvid').textContent=v.current||'—';
    setPaused(!!v.paused);
  }catch(e){}
}
function setPaused(p){paused=p;const b=$('pausebtn');b.textContent=p?'▶ Resume':'⏸ Pause';b.classList.toggle('launch',p);}
$('loadvid').onclick=async()=>{const name=$('videosel').value;if(!name)return;$('loadvid').textContent='…';await ctl({load_video:name});await loadVideos();$('loadvid').textContent='Load & run';};
$('pausebtn').onclick=async()=>{await ctl({paused:!paused});setPaused(!paused);};
$('mask_on').onchange=e=>ctl({mask_on:e.target.checked});
$('invert').onchange=e=>ctl({invert:e.target.checked});
$('border_crop').oninput=e=>{$('vborder').textContent=e.target.value;};
$('border_crop').onchange=e=>ctl({border_crop:+e.target.value});
$('min_snr').oninput=e=>{$('vsnr').textContent=e.target.value;};
$('min_snr').onchange=e=>ctl({min_snr:+e.target.value});
$('min_area').oninput=e=>{$('varea').textContent=e.target.value;};
$('min_area').onchange=e=>ctl({min_area:+e.target.value});
$('colormap').onchange=e=>ctl({colormap:e.target.value});
$('launch').onclick=()=>ctl({launch:true});
$('safe').onclick=()=>ctl({safe:true});
$('designation_box_px').oninput=e=>{$('vret').textContent=e.target.value;};
$('designation_box_px').onchange=e=>ctl({designation_box_px:+e.target.value});
$('recal').onclick=()=>ctl({recalibrate_mask:true});
let rec=false;$('record').onclick=()=>{rec=!rec;$('record').classList.toggle('on',rec);$('record').textContent=rec?'■ Stop':'● Record';ctl({record:rec});};
let y16=false;$('y16rec').onclick=async()=>{y16=!y16;$('y16rec').classList.toggle('on',y16);$('y16rec').textContent=y16?'■ Stop clip':'● Record clip';
  const radio=$('y16radio').checked;const meta={class_label:$('y16class').value,is_radiometric_y16:radio,sensor:radio?'Y16_radiometric':'FT640_CVBS_8bit'};
  const r=await ctl({record_y16:y16,y16_meta:meta});if(r&&r.state&&r.state.record_y16)$('y16status').textContent=r.state.record_y16.info||'';};
loadVideos();setInterval(poll,150);poll();
</script>
</body>
</html>
"""
