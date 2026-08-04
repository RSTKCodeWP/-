const COLS = 16, ROWS = 12;
let maskCells = Array(COLS * ROWS).fill(false);
let configData = {};
let configSchema = { sections: {}, fields: {} };

function $(id) { return document.getElementById(id); }

function renderStats(el, s) {
  if (!el) return;
  el.innerHTML = [
    ['Статус', s.flight_ok ? 'FLIGHT OK' : (s.holding ? 'HOLD LAST' : 'NOT READY')],
    ['FPS', s.fps],
    ['MAVLink', s.mavlink_connected ? ('OK ' + s.heartbeat_age_s + 's') : 'OFF'],
    ['Висота', s.altitude_m + ' m (' + (s.altitude_source || '?') + ')'],
    ['Якість / точки', s.quality + ' / ' + s.track_points],
    ['Vx / Vy', s.vx_m_s + ' / ' + s.vy_m_s],
    ['ARM (FC)', s.armed ? 'YES' : 'NO'],
  ].map(([k, v]) => `<div class="stat"><span>${k}</span><span>${v}</span></div>`).join('');
}

function updateFlySteps(s) {
  const minQ = s.min_quality ?? 0.25;
  const minPts = s.min_points ?? 8;
  const minFps = s.min_fps ?? 8;
  const steps = [
    ['Камера', s.fps >= minFps || s.simulate],
    ['MAVLink', s.mavlink_connected || s.simulate],
    ['Tracking', s.quality >= minQ && s.track_points >= minPts],
    ['Маска ROI', s.mask_fill < 0.33],
    ['NAV warmup', s.nav_valid || s.simulate],
    ['FLIGHT OK', s.flight_ok || (s.simulate && s.nav_valid)],
  ];
  $('flySteps').innerHTML = steps.map(([t, ok]) =>
    `<li class="${ok ? 'ok' : 'bad'}">${ok ? '✓' : '✗'} ${t}</li>`
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
    if (s.flight_ok) {
      banner.classList.add('hidden');
    } else if (s.armed && s.holding) {
      banner.textContent = 'HOLD LAST — утримання останньої позиції';
      banner.classList.remove('hidden');
    } else if (s.armed) {
      banner.textContent = 'ARMED — NAV не готовий, не знімайте з місця';
      banner.classList.remove('hidden');
    } else {
      banner.textContent = 'Не армити — навігація не готова';
      banner.classList.remove('hidden');
    }
    renderStats($('stats'), s);
    updateFlySteps(s);

    if (s.health && s.health.checks) {
      $('healthList').innerHTML = s.health.checks.map(c =>
        `<li class="${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '✗'} ${c.name}: ${c.detail}</li>`
      ).join('');
    }
  } catch (e) {}
}
setInterval(poll, 500);
poll();

async function loadMask() {
  const d = await (await fetch('/api/mask')).json();
  maskCells = d.cells || maskCells;
  drawMask();
}

function drawMask() {
  const c = $('maskCanvas');
  if (!c) return;
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
    }
  }
}

const maskCanvas = $('maskCanvas');
if (maskCanvas) {
  maskCanvas.onclick = (e) => {
    const c = maskCanvas;
    const rect = c.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (c.width / rect.width);
    const y = (e.clientY - rect.top) * (c.height / rect.height);
    const col = Math.floor(x / (c.width / COLS));
    const row = Math.floor(y / (c.height / ROWS));
    const i = row * COLS + col;
    if (i >= 0 && i < maskCells.length) { maskCells[i] = !maskCells[i]; drawMask(); }
  };
}
$('maskClear').onclick = () => { maskCells.fill(false); drawMask(); };
$('maskSave').onclick = async () => {
  await fetch('/api/mask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cells: maskCells }),
  });
};

function fieldId(section, key) { return `cfg-${section}-${key}`; }

function renderSettingsForm() {
  const root = $('settingsSections');
  root.innerHTML = '';
  for (const [section, fields] of Object.entries(configSchema.fields || {})) {
    const card = document.createElement('div');
    card.className = 'settings-section';
    card.innerHTML = `<h3>${(configSchema.sections || {})[section] || section}</h3>`;
    const form = document.createElement('div');
    form.className = 'settings-fields';
    for (const f of fields) {
      const val = (configData[section] || {})[f.key];
      const id = fieldId(section, f.key);
      let input = '';
      if (f.type === 'checkbox') {
        input = `<label class="field checkbox"><input id="${id}" type="checkbox" ${val ? 'checked' : ''}/> ${f.label}</label>`;
      } else if (f.type === 'select') {
        const opts = (f.options || []).map(o =>
          `<option value="${o}" ${String(val) === String(o) ? 'selected' : ''}>${o}</option>`
        ).join('');
        input = `<label class="field">${f.label}<select id="${id}">${opts}</select></label>`;
      } else {
        const step = f.step != null ? ` step="${f.step}"` : '';
        input = `<label class="field">${f.label}<input id="${id}" type="${f.type || 'text'}" value="${val ?? ''}"${step}/></label>`;
      }
      const hint = f.hint ? `<span class="field-hint">${f.hint}</span>` : '';
      form.innerHTML += `<div class="field-wrap">${input}${hint}</div>`;
    }
    card.appendChild(form);
    root.appendChild(card);
  }
}

function collectConfigPatch() {
  const patch = {};
  for (const [section, fields] of Object.entries(configSchema.fields || {})) {
    const data = {};
    for (const f of fields) {
      const el = $(fieldId(section, f.key));
      if (!el) continue;
      if (f.type === 'checkbox') data[f.key] = el.checked;
      else if (f.type === 'number') data[f.key] = el.value === '' ? 0 : +el.value;
      else data[f.key] = el.value;
    }
    patch[section] = data;
  }
  return patch;
}

async function loadSettings() {
  const [schemaRes, cfgRes] = await Promise.all([
    fetch('/api/config/schema'),
    fetch('/api/config'),
  ]);
  configSchema = await schemaRes.json();
  configData = await cfgRes.json();
  renderSettingsForm();
}

document.querySelector('details.panel-fold summary')?.addEventListener('click', () => {
  setTimeout(() => { if ($('settingsSections').children.length === 0) loadSettings(); }, 0);
});

$('cfgSave').onclick = async () => {
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(collectConfigPatch()),
  });
  const d = await res.json();
  alert(d.ok ? 'Збережено' : ('Помилка: ' + (d.error || '?')));
};

$('resetOdo').onclick = () => fetch('/api/reset_odometry', { method: 'POST' });

loadMask();
loadSettings();
