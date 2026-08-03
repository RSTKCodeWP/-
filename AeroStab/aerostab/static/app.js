const COLS = 16, ROWS = 12;
let maskCells = Array(COLS * ROWS).fill(false);

function $(id) { return document.getElementById(id); }

document.querySelectorAll('.tab').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'mask') drawMask();
  };
});

function renderStats(el, s) {
  if (!el) return;
  el.innerHTML = [
    ['Статус', s.flight_ok ? 'FLIGHT OK' : (s.holding ? 'HOLD LAST' : 'NOT READY')],
    ['FPS', s.fps],
    ['MAVLink', s.mavlink_connected ? ('OK ' + s.heartbeat_age_s + 's') : 'OFF'],
    ['Nav valid', s.nav_valid ? 'YES' : 'NO'],
    ['Health', s.health_ready ? 'OK' : 'CHECK'],
    ['Висота', s.altitude_m + ' m'],
    ['Vx / Vy', s.vx_m_s + ' / ' + s.vy_m_s],
    ['Позиція', s.x_m + ' / ' + s.y_m + ' m'],
    ['Yaw', s.yaw_deg + '°'],
    ['Якість', s.quality],
    ['Точки', s.track_points],
    ['RTL', s.rtl_recording ? ('REC ' + s.rtl_points) : (s.rtl_points + ' pt')],
    ['Uptime', s.uptime_s + ' s'],
  ].map(([k,v]) => `<div class="stat"><span>${k}</span><span>${v}</span></div>`).join('');
}

function updateFlySteps(s) {
  const steps = [
    ['Камера кадри', s.fps > 5],
    ['MAVLink heartbeat', !!s.mavlink_connected || !!s.simulate],
    ['Tracking якість', s.quality >= 0.25 && s.track_points >= 8],
    ['Маска ROI OK', s.mask_fill < 0.33],
    ['NAV warmup', !!s.nav_valid || !!s.simulate],
    ['Health ready', !!s.health_ready || !!s.simulate],
    ['FLIGHT OK → можна PosHold', !!s.flight_ok || (!!s.simulate && !!s.nav_valid)],
  ];
  $('flySteps').innerHTML = steps.map(([t, ok]) =>
    `<li class="${ok?'ok':'bad'}">${ok?'✓':'✗'} ${t}</li>`
  ).join('');
}

async function poll() {
  try {
    const s = await (await fetch('/api/status')).json();
    const b = $('badge');
    if (s.flight_ok) { b.textContent = 'FLIGHT OK'; b.className = 'badge ok'; }
    else if (s.holding) { b.textContent = 'HOLD'; b.className = 'badge hold'; }
    else if (!s.nav_valid) { b.textContent = 'NAV WAIT'; b.className = 'badge wait'; }
    else if (s.simulate) { b.textContent = 'SIM'; b.className = 'badge sim'; }
    else { b.textContent = s.armed ? 'ARMED' : 'READY'; b.className = 'badge live'; }

    const banner = $('armBanner');
    if (!s.flight_ok && !s.armed) banner.classList.remove('hidden');
    else banner.classList.add('hidden');

    renderStats($('stats'), s);
    renderStats($('statsFly'), s);
    updateFlySteps(s);

    if (s.health && s.health.checks) {
      $('healthList').innerHTML = s.health.checks.map(c =>
        `<div class="check ${c.ok?'ok':'bad'}"><span>${c.ok?'✓':'✗'} ${c.name}</span> — ${c.detail}</div>`
      ).join('');
    }
    drawRtl();
  } catch (e) {}
}
setInterval(poll, 500);
poll();

async function loadMask() {
  const r = await fetch('/api/mask');
  const d = await r.json();
  maskCells = d.cells || maskCells;
  drawMask();
}

function drawMask() {
  const c = $('maskCanvas');
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  ctx.fillStyle = '#111';
  ctx.fillRect(0, 0, w, h);
  const cw = w / COLS, ch = h / ROWS;
  for (let r = 0; r < ROWS; r++) {
    for (let col = 0; col < COLS; col++) {
      const i = r * COLS + col;
      ctx.fillStyle = maskCells[i] ? 'rgba(220,40,40,0.75)' : 'rgba(40,60,90,0.3)';
      ctx.fillRect(col * cw + 1, r * ch + 1, cw - 2, ch - 2);
      ctx.strokeStyle = '#333';
      ctx.strokeRect(col * cw, r * ch, cw, ch);
    }
  }
}

$('maskCanvas').onclick = (e) => {
  const c = $('maskCanvas');
  const rect = c.getBoundingClientRect();
  const x = (e.clientX - rect.left) * (c.width / rect.width);
  const y = (e.clientY - rect.top) * (c.height / rect.height);
  const col = Math.floor(x / (c.width / COLS));
  const row = Math.floor(y / (c.height / ROWS));
  const i = row * COLS + col;
  if (i >= 0 && i < maskCells.length) { maskCells[i] = !maskCells[i]; drawMask(); }
};

$('maskClear').onclick = () => { maskCells.fill(false); drawMask(); };
$('maskSave').onclick = async () => {
  await fetch('/api/mask', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({cells: maskCells}) });
  alert('Маску збережено');
};
$('maskReload').onclick = loadMask;

async function loadCfg() {
  const d = await (await fetch('/api/config')).json();
  const f = $('cfgForm');
  f.fov_deg.value = d.camera.fov_deg;
  f.rotation_deg.value = d.camera.rotation_deg;
  f.fps.value = d.camera.fps;
  f.show_grid.checked = d.camera.show_grid;
  f.gps_fusion.checked = d.gps_fusion.enabled;
  f.min_quality.value = d.quality.min_quality;
}

$('cfgForm').onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  await fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      fov_deg: +f.fov_deg.value,
      rotation_deg: +f.rotation_deg.value,
      fps: +f.fps.value,
      show_grid: f.show_grid.checked,
      gps_fusion: f.gps_fusion.checked,
      min_quality: +f.min_quality.value,
    })});
  alert('FOV застосовано одразу. Інші параметри — після перезапуску сервісу.');
};

$('resetOdo').onclick = async () => { await fetch('/api/reset_odometry', {method:'POST'}); };

async function drawRtl() {
  const c = $('rtlCanvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  ctx.fillStyle = '#0a0e12';
  ctx.fillRect(0, 0, w, h);
  try {
    const d = await (await fetch('/api/rtl_path')).json();
    $('rtlHint').textContent = d.recording
      ? `Запис: ${d.points} точок, ${d.length_m} m`
      : `Останній політ: ${d.points} точок, ${d.length_m} m`;
    const path = d.path || [];
    if (path.length < 2) return;
    const xs = path.map(p => p.x), ys = path.map(p => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const pad = 12;
    const sx = (maxX - minX) || 1, sy = (maxY - minY) || 1;
    const scale = Math.min((w - 2*pad) / sx, (h - 2*pad) / sy);
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    const tx = (x) => w/2 + (x - cx) * scale;
    const ty = (y) => h/2 - (y - cy) * scale;
    ctx.strokeStyle = '#3d9eff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(tx(path[0].x), ty(path[0].y));
    for (let i = 1; i < path.length; i++) ctx.lineTo(tx(path[i].x), ty(path[i].y));
    ctx.stroke();
    ctx.fillStyle = '#3dd68c';
    ctx.beginPath(); ctx.arc(tx(path[0].x), ty(path[0].y), 4, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = '#f5a623';
    ctx.beginPath(); ctx.arc(tx(path[path.length-1].x), ty(path[path.length-1].y), 4, 0, Math.PI*2); ctx.fill();
  } catch (e) {}
}

loadMask();
loadCfg();
