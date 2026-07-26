// ===== State =====
let allTricks = [];
let allDrills = [];
let allResources = [];
let allSchedule = [];
let allPlans = [];
let activePlan = null;
let currentSessionId = null;
let currentSessionData = null;

// ===== API helpers =====
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined
  });
  return res.json();
}

// ===== Navigation =====
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.page).classList.add('active');
    // Load data for the target page
    const page = btn.dataset.page;
    if (page === 'page-today') loadToday();
    else if (page === 'page-sessions') loadSessions();
    else if (page === 'page-progress') loadProgress();
    else if (page === 'page-tricks') loadTricks();
    else if (page === 'page-denver') loadDenver();
  });
});

// Form tabs
document.querySelectorAll('.form-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    tab.parentElement.querySelectorAll('.form-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const parent = tab.closest('.modal-content') || tab.closest('.page');
    parent.querySelectorAll('.form-tab-content').forEach(c => c.classList.remove('active'));
    parent.querySelector('#' + tab.dataset.tab).classList.add('active');
  });
});

// Sub-tabs (tricks page)
document.querySelectorAll('.sub-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    tab.parentElement.querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('.subtab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(tab.dataset.subtab).classList.add('active');
  });
});

// ===== TODAY PAGE =====
async function loadToday() {
  if (!allSchedule.length) allSchedule = await api('/tricks/schedule/all');
  if (!allTricks.length) allTricks = await api('/tricks');

  const stats = await api('/progress/stats');
  const gates = await api('/progress/gates');

  const plan = activePlan || {};
  const programStart = new Date((plan.start_date || '2026-02-01') + 'T00:00:00');
  const totalWeeks = plan.total_weeks || 20;
  const goalDate = new Date((plan.goal_date || '2026-07-01') + 'T00:00:00');
  const goalDesc = plan.goal_description || 'Denver';

  const now = new Date();
  const weekNum = Math.max(1, Math.min(totalWeeks, Math.floor((now - programStart) / (7 * 86400000)) + 1));
  const currentWeek = allSchedule.find(w => w.week_number === weekNum) || allSchedule[0];
  const phase = currentWeek ? currentWeek.phase : 1;
  const phaseNames = { 1: 'Indoor Acro', 2: 'Outdoor Transition', 3: 'Flow & Lines', 4: 'Denver Confidence' };

  document.getElementById('today-week').textContent = `Week ${weekNum} of ${totalWeeks}`;
  document.getElementById('today-phase').textContent = `Phase ${phase}: ${phaseNames[phase] || ''}`;

  const daysLeft = Math.max(0, Math.ceil((goalDate - now) / 86400000));
  document.getElementById('today-countdown').innerHTML = `<strong>${daysLeft}</strong> days until ${esc(goalDesc)}`;

  // Streak
  document.getElementById('today-streak').innerHTML = `
    <div class="stat-value">${stats.streak}</div>
    <div class="stat-label">day streak &middot; ${stats.total_hours}h total &middot; ${stats.total_packs} packs</div>
  `;

  // This week's schedule
  if (currentWeek) {
    document.getElementById('today-schedule').innerHTML = `
      <h4>This Week's Drills</h4>
      <p class="detail">${currentWeek.primary_drills}</p>
      <p class="detail" style="margin-top:6px"><strong>Target:</strong> ${currentWeek.target}</p>
      <p class="detail"><strong>Sim:</strong> ${currentWeek.sim_focus}</p>
      <p class="detail"><strong>Gate:</strong> ${currentWeek.go_nogo}</p>
    `;
  }

  // Upcoming gates
  const phaseGates = gates.filter(g => g.phase === phase && !g.met);
  document.getElementById('today-gates').innerHTML = phaseGates.length
    ? phaseGates.map(g => `
      <div class="gate-item ${g.is_hard_gate ? 'hard-gate' : ''}">
        <span class="gate-text">${g.is_hard_gate ? '&#9632; ' : ''}${g.item_text}</span>
      </div>
    `).join('')
    : '<div class="card"><p class="detail">All phase gates cleared!</p></div>';
}

// ===== SESSIONS PAGE =====
async function loadSessions() {
  const sessions = await api('/sessions');
  const list = document.getElementById('session-list');
  if (!sessions.length) {
    list.innerHTML = '<div class="empty">No sessions yet. Start your first one!</div>';
    return;
  }
  list.innerHTML = sessions.map(s => `
    <div class="session-item" onclick="openSession(${s.id})">
      <div class="si-date">${formatDate(s.date)}</div>
      <div class="si-info">${s.location} &middot; ${s.platform} &middot; ${s.session_type}</div>
      <div class="si-stats">${s.pack_count}pk ${s.crash_count > 0 ? s.crash_count + '💥' : ''}</div>
    </div>
  `).join('');
}

function formatDate(d) {
  if (!d) return '';
  const parts = d.split('-');
  return `${parts[1]}/${parts[2]}`;
}

async function populatePlanSelect(selectedId) {
  if (!allPlans.length) allPlans = await api('/plans');
  const el = document.getElementById('sf-plan');
  const selId = selectedId != null ? String(selectedId) : '';
  el.innerHTML = '<option value="">— no plan —</option>' + allPlans.map(p =>
    `<option value="${p.id}"${String(p.id) === selId ? ' selected' : ''}>${esc(p.name)}</option>`
  ).join('');
}

// New session buttons
document.getElementById('btn-new-session').addEventListener('click', () => newSession());
document.getElementById('btn-new-session-2').addEventListener('click', () => newSession());

async function newSession() {
  currentSessionId = null;
  currentSessionData = null;
  const now = new Date();
  document.getElementById('sf-date').value = now.toISOString().split('T')[0];
  document.getElementById('sf-time-start').value = now.toTimeString().slice(0, 5);
  document.getElementById('sf-time-end').value = '';
  document.getElementById('sf-location').value = 'home-room-A';
  document.getElementById('sf-platform').value = 'Air65';
  document.getElementById('sf-weather').value = 'indoor';
  await populatePlanSelect(activePlan?.id);
  document.getElementById('sf-type').value = 'blocked-drill';
  document.getElementById('sf-notes').value = '';
  document.getElementById('pack-list').innerHTML = '';
  document.getElementById('trick-attempt-list').innerHTML = '';
  document.getElementById('crash-list-form').innerHTML = '';
  clearReviewForm();

  document.getElementById('session-form-title').textContent = 'New Session';
  document.getElementById('btn-delete-session').hidden = true;

  // Always open to the Info tab
  document.querySelectorAll('.form-tab').forEach(t => t.classList.remove('active'));
  document.querySelector('.form-tab[data-tab="tab-header"]').classList.add('active');
  document.querySelectorAll('.form-tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById('tab-header').classList.add('active');

  document.getElementById('session-form').hidden = false;

  // Create session immediately so sub-items can attach
  const result = await api('/sessions', {
    method: 'POST',
    body: {
      date: document.getElementById('sf-date').value,
      time_start: document.getElementById('sf-time-start').value,
      location: document.getElementById('sf-location').value,
      platform: document.getElementById('sf-platform').value,
      weather: document.getElementById('sf-weather').value,
      session_type: document.getElementById('sf-type').value,
      training_plan_id: document.getElementById('sf-plan').value || null,
    }
  });
  currentSessionId = result.id;

  // Auto-save header fields on change
  setupAutoSave();
}

async function openSession(id) {
  currentSessionId = id;
  const data = await api(`/sessions/${id}`);
  currentSessionData = data;

  document.getElementById('sf-date').value = data.date;
  document.getElementById('sf-time-start').value = data.time_start || '';
  document.getElementById('sf-time-end').value = data.time_end || '';
  document.getElementById('sf-location').value = data.location;
  document.getElementById('sf-platform').value = data.platform;
  document.getElementById('sf-weather').value = data.weather;
  document.getElementById('sf-type').value = data.session_type;
  document.getElementById('sf-notes').value = data.notes || '';
  await populatePlanSelect(data.training_plan_id);

  // Render packs
  renderPacks(data.packs);

  // Render trick attempts
  renderTrickAttempts(data.trick_attempts);

  // Render crashes
  renderCrashes(data.crashes);

  // Render review
  if (data.review) {
    document.getElementById('sf-good1').value = data.review.good_1 || '';
    document.getElementById('sf-good2').value = data.review.good_2 || '';
    document.getElementById('sf-good3').value = data.review.good_3 || '';
    document.getElementById('sf-improve1').value = data.review.improve_1 || '';
    document.getElementById('sf-improve2').value = data.review.improve_2 || '';
    document.getElementById('sf-improve3').value = data.review.improve_3 || '';
    document.getElementById('sf-fatigue').value = data.review.fatigue || 'good';
    document.getElementById('sf-frustration').value = data.review.frustration || 'none';
    document.getElementById('sf-stopped').checked = !!data.review.stopped_before_bad;
    document.getElementById('sf-tomorrow').value = data.review.tomorrow_focus || '';
    document.getElementById('sf-sim-drill').value = data.review.sim_drill_tonight || '';
    document.getElementById('sf-dvr').value = data.review.dvr_timestamps || '';
    document.getElementById('sf-blackbox').checked = !!data.review.blackbox_recorded;
  } else {
    clearReviewForm();
  }

  document.getElementById('session-form-title').textContent = `Session ${formatDate(data.date)}`;
  document.getElementById('btn-delete-session').hidden = false;
  document.getElementById('session-form').hidden = false;
  setupAutoSave();
}

async function deleteSession() {
  if (!confirm('Delete this session and all its data?')) return;
  await api(`/sessions/${currentSessionId}`, { method: 'DELETE' });
  currentSessionId = null;
  document.getElementById('session-form').hidden = true;
  loadSessions();
}

function clearReviewForm() {
  ['sf-good1','sf-good2','sf-good3','sf-improve1','sf-improve2','sf-improve3','sf-tomorrow','sf-sim-drill','sf-dvr'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('sf-fatigue').value = 'good';
  document.getElementById('sf-frustration').value = 'none';
  document.getElementById('sf-stopped').checked = true;
  document.getElementById('sf-blackbox').checked = false;
}

function closeSessionForm() {
  document.getElementById('session-form').hidden = true;
  saveSessionHeader();
  loadSessions();
}

// Auto-save header on blur
function setupAutoSave() {
  const fields = ['sf-date','sf-time-start','sf-time-end','sf-location','sf-platform','sf-weather','sf-type','sf-plan','sf-notes'];
  fields.forEach(id => {
    const el = document.getElementById(id);
    el.onchange = () => saveSessionHeader();
    el.onblur = () => saveSessionHeader();
  });
}

async function saveSessionHeader() {
  if (!currentSessionId) return;
  await api(`/sessions/${currentSessionId}`, {
    method: 'PUT',
    body: {
      date: document.getElementById('sf-date').value,
      time_start: document.getElementById('sf-time-start').value,
      time_end: document.getElementById('sf-time-end').value,
      location: document.getElementById('sf-location').value,
      platform: document.getElementById('sf-platform').value,
      weather: document.getElementById('sf-weather').value,
      session_type: document.getElementById('sf-type').value,
      notes: document.getElementById('sf-notes').value,
      training_plan_id: document.getElementById('sf-plan').value || null,
    }
  });
}

// ===== PACKS =====
function renderPacks(packs) {
  const list = document.getElementById('pack-list');
  list.innerHTML = packs.map(p => `
    <div class="pack-card" data-pack-id="${p.id}">
      <div class="pack-header">
        <strong>Pack ${p.pack_number}</strong>
        <button class="btn-delete" onclick="deletePack(${p.id})">remove</button>
      </div>
      <div class="row">
        <label>V start <input type="number" step="0.01" value="${p.voltage_start || ''}" onchange="updatePack(${p.id}, this.parentElement.parentElement)"></label>
        <label>V end <input type="number" step="0.01" value="${p.voltage_end || ''}" onchange="updatePack(${p.id}, this.parentElement.parentElement)"></label>
        <label>Crashes <input type="number" min="0" value="${p.crashes || 0}" onchange="updatePack(${p.id}, this.parentElement.parentElement)"></label>
      </div>
      <label>Focus <input type="text" value="${esc(p.focus)}" onchange="updatePack(${p.id}, this.parentElement.parentElement.parentElement)"></label>
    </div>
  `).join('');
}

document.getElementById('btn-add-pack').addEventListener('click', async () => {
  if (!currentSessionId) return;
  await api(`/sessions/${currentSessionId}/packs`, { method: 'POST', body: {} });
  const data = await api(`/sessions/${currentSessionId}`);
  renderPacks(data.packs);
});

async function updatePack(packId, container) {
  const card = container.closest('.pack-card');
  const inputs = card.querySelectorAll('input');
  await api(`/sessions/${currentSessionId}/packs/${packId}`, {
    method: 'PUT',
    body: {
      voltage_start: parseFloat(inputs[0].value) || null,
      voltage_end: parseFloat(inputs[1].value) || null,
      crashes: parseInt(inputs[2].value) || 0,
      focus: inputs[3].value,
      notes: ''
    }
  });
}

async function deletePack(packId) {
  await api(`/sessions/${currentSessionId}/packs/${packId}`, { method: 'DELETE' });
  const data = await api(`/sessions/${currentSessionId}`);
  renderPacks(data.packs);
}

// ===== TRICK ATTEMPTS =====
function renderTrickAttempts(attempts) {
  const list = document.getElementById('trick-attempt-list');
  list.innerHTML = attempts.map(ta => {
    const rate = ta.attempts > 0 ? Math.round(100 * ta.landed / ta.attempts) : 0;
    const color = rate >= 90 ? 'var(--green)' : rate >= 70 ? 'var(--yellow)' : rate >= 50 ? 'var(--orange)' : 'var(--accent)';
    return `
    <div class="trick-row" data-ta-id="${ta.id}">
      <span class="tr-name">${ta.trick_name || 'Trick #' + ta.trick_id}</span>
      <input type="number" min="0" value="${ta.attempts}" placeholder="att" onchange="updateTrickAttempt(${ta.id})">
      <input type="number" min="0" value="${ta.landed}" placeholder="land" onchange="updateTrickAttempt(${ta.id})">
      <span class="tr-rate" style="color:${color}">${rate}%</span>
      <button class="btn-delete" onclick="deleteTrickAttempt(${ta.id})">×</button>
    </div>`;
  }).join('');
}

document.getElementById('btn-add-trick-attempt').addEventListener('click', () => showTrickPicker());

async function showTrickPicker() {
  if (!allTricks.length) {
    allTricks = await api('/tricks');
  }
  if (!allTricks.length) return;
  const picker = document.createElement('div');
  picker.className = 'trick-picker';
  picker.innerHTML = `
    <div class="trick-picker-content">
      <h3 style="padding:0 0 8px">Select Trick</h3>
      ${allTricks.map(t => `
        <div class="trick-picker-item" data-id="${t.id}">
          <span class="badge" style="margin-right:6px">L${t.level}</span> ${t.name}
        </div>
      `).join('')}
    </div>
  `;
  picker.addEventListener('click', async (e) => {
    const item = e.target.closest('.trick-picker-item');
    if (item) {
      await api(`/sessions/${currentSessionId}/tricks`, {
        method: 'POST',
        body: { trick_id: parseInt(item.dataset.id), attempts: 0, landed: 0 }
      });
      const data = await api(`/sessions/${currentSessionId}`);
      renderTrickAttempts(data.trick_attempts);
    }
    picker.remove();
  });
  // Close on background click
  picker.querySelector('.trick-picker-content').addEventListener('click', e => e.stopPropagation());
  picker.addEventListener('click', () => picker.remove());
  document.body.appendChild(picker);
}

async function updateTrickAttempt(taId) {
  const row = document.querySelector(`[data-ta-id="${taId}"]`);
  const inputs = row.querySelectorAll('input');
  const attempts = parseInt(inputs[0].value) || 0;
  const landed = parseInt(inputs[1].value) || 0;
  await api(`/sessions/${currentSessionId}/tricks/${taId}`, {
    method: 'PUT',
    body: { trick_id: 0, attempts, landed, notes: '' }
  });
  // Recalc rate display
  const rate = attempts > 0 ? Math.round(100 * landed / attempts) : 0;
  const color = rate >= 90 ? 'var(--green)' : rate >= 70 ? 'var(--yellow)' : rate >= 50 ? 'var(--orange)' : 'var(--accent)';
  row.querySelector('.tr-rate').textContent = rate + '%';
  row.querySelector('.tr-rate').style.color = color;
}

async function deleteTrickAttempt(taId) {
  await api(`/sessions/${currentSessionId}/tricks/${taId}`, { method: 'DELETE' });
  const data = await api(`/sessions/${currentSessionId}`);
  renderTrickAttempts(data.trick_attempts);
}

// ===== CRASHES =====
const FAILURE_TYPES = ['orient', 'throttle', 'timing', 'spatial', 'propwash', 'muscle', 'signal', 'environ'];
const ROOT_CAUSES = ['pilot', 'tune', 'mech', 'signal', 'environ'];

function renderCrashes(crashes) {
  const list = document.getElementById('crash-list-form');
  list.innerHTML = crashes.map(cr => `
    <div class="crash-row" data-crash-id="${cr.id}">
      <select>${FAILURE_TYPES.map(f => `<option value="${f}" ${cr.failure_type === f ? 'selected' : ''}>${f}</option>`).join('')}</select>
      <select>${ROOT_CAUSES.map(r => `<option value="${r}" ${cr.root_cause === r ? 'selected' : ''}>${r}</option>`).join('')}</select>
      <input type="text" value="${esc(cr.action_item)}" placeholder="action item">
      <button class="btn-delete" onclick="deleteCrash(${cr.id})">×</button>
    </div>
  `).join('');
}

document.getElementById('btn-add-crash').addEventListener('click', async () => {
  if (!currentSessionId) return;
  await api(`/sessions/${currentSessionId}/crashes`, {
    method: 'POST',
    body: { failure_type: 'orient', root_cause: 'pilot' }
  });
  const data = await api(`/sessions/${currentSessionId}`);
  renderCrashes(data.crashes);
});

async function deleteCrash(crashId) {
  await api(`/sessions/${currentSessionId}/crashes/${crashId}`, { method: 'DELETE' });
  const data = await api(`/sessions/${currentSessionId}`);
  renderCrashes(data.crashes);
}

// ===== REVIEW =====
async function saveReview() {
  if (!currentSessionId) return;
  await api(`/sessions/${currentSessionId}/review`, {
    method: 'POST',
    body: {
      good_1: document.getElementById('sf-good1').value,
      good_2: document.getElementById('sf-good2').value,
      good_3: document.getElementById('sf-good3').value,
      improve_1: document.getElementById('sf-improve1').value,
      improve_2: document.getElementById('sf-improve2').value,
      improve_3: document.getElementById('sf-improve3').value,
      fatigue: document.getElementById('sf-fatigue').value,
      frustration: document.getElementById('sf-frustration').value,
      stopped_before_bad: document.getElementById('sf-stopped').checked,
      tomorrow_focus: document.getElementById('sf-tomorrow').value,
      sim_drill_tonight: document.getElementById('sf-sim-drill').value,
      dvr_timestamps: document.getElementById('sf-dvr').value,
      blackbox_recorded: document.getElementById('sf-blackbox').checked,
    }
  });
  // Brief feedback
  const btn = document.querySelector('#tab-review .btn-primary');
  const orig = btn.textContent;
  btn.textContent = 'Saved!';
  setTimeout(() => btn.textContent = orig, 1000);
}

// ===== PROGRESS PAGE =====
async function loadProgress() {
  const [stats, mastery] = await Promise.all([
    api('/progress/stats'),
    api('/progress/mastery')
  ]);

  document.getElementById('stats-cards').innerHTML = `
    <div class="stat-card"><div class="stat-value">${stats.sessions}</div><div class="stat-label">Sessions</div></div>
    <div class="stat-card"><div class="stat-value">${stats.total_packs}</div><div class="stat-label">Packs</div></div>
    <div class="stat-card"><div class="stat-value">${stats.total_hours}</div><div class="stat-label">Hours</div></div>
    <div class="stat-card"><div class="stat-value">${stats.streak}</div><div class="stat-label">Day Streak</div></div>
  `;

  // Mastery table
  const table = document.getElementById('mastery-table');
  table.innerHTML = mastery.map(m => {
    const rate = m.overall_rate != null ? m.overall_rate + '%' : '—';
    let statusBadge = '';
    if (m.overall_rate === null) statusBadge = '<span class="badge">not started</span>';
    else if (m.overall_rate >= 90) statusBadge = '<span class="badge badge-green">mastered</span>';
    else if (m.overall_rate >= 70) statusBadge = '<span class="badge badge-yellow">reliable</span>';
    else if (m.overall_rate >= 50) statusBadge = '<span class="badge badge-red">learning</span>';
    else statusBadge = '<span class="badge badge-red">learning</span>';
    return `
      <div class="mastery-row">
        <span class="mr-level">L${m.level}</span>
        <span class="mr-name">${m.name}</span>
        ${statusBadge}
        <span class="mr-rate">${rate}</span>
      </div>`;
  }).join('');

  // Crash patterns
  const cp = document.getElementById('crash-patterns');
  if (stats.crash_patterns.length) {
    const maxCount = Math.max(...stats.crash_patterns.map(c => c.count));
    cp.innerHTML = stats.crash_patterns.map(c => `
      <div class="crash-bar">
        <span class="cb-label">${c.failure_type}</span>
        <div class="cb-fill" style="width: ${(c.count / maxCount) * 150}px"></div>
        <span class="cb-count">${c.count}</span>
      </div>
    `).join('');
  } else {
    cp.innerHTML = '<div class="card"><p class="detail">No crashes logged yet.</p></div>';
  }
}

// ===== TRICKS PAGE =====
async function loadTricks() {
  if (!allTricks.length) allTricks = await api('/tricks');
  if (!allDrills.length) allDrills = await api('/tricks/drills/all');
  if (!allResources.length) allResources = await api('/tricks/resources/all');

  // Tricks grouped by level
  const byLevel = {};
  allTricks.forEach(t => {
    if (!byLevel[t.level]) byLevel[t.level] = [];
    byLevel[t.level].push(t);
  });
  const levelNames = { 1: 'Foundation', 2: 'Acro Vocabulary', 3: 'Multi-Axis', 4: 'Technical', 5: 'Aspirational' };

  let html = '';
  for (const [level, tricks] of Object.entries(byLevel)) {
    html += `<div class="level-header">Level ${level}: ${levelNames[level] || ''}</div>`;
    html += tricks.map(t => {
      let links = '';
      try {
        const refs = JSON.parse(t.reference_links || '[]');
        if (refs.length) {
          links = '<div class="links">' + refs.map(r => `<a href="${r.url}" target="_blank" rel="noopener">${r.label}</a>`).join('') + '</div>';
        }
      } catch(e) {}
      return `
        <div class="trick-card">
          <h4><span class="badge">L${t.level}</span> ${t.name}</h4>
          <p>${t.description}</p>
          ${t.indoor_notes ? `<p><strong>Indoor:</strong> ${t.indoor_notes}</p>` : ''}
          ${links}
        </div>`;
    }).join('');
  }
  document.getElementById('tricks-list').innerHTML = html;

  // Drills
  document.getElementById('drills-list').innerHTML = allDrills.map(d => `
    <div class="trick-card">
      <h4>${d.name}</h4>
      <p>${d.description}</p>
      <p><strong>Mastery:</strong> ${d.mastery_criteria}</p>
    </div>
  `).join('');

  // Resources
  const byType = {};
  allResources.forEach(r => {
    if (!byType[r.type]) byType[r.type] = [];
    byType[r.type].push(r);
  });
  const typeOrder = ['youtube', 'website', 'sim', 'app', 'tool', 'community'];
  let resHtml = '';
  for (const type of typeOrder) {
    const items = byType[type];
    if (!items) continue;
    resHtml += `<div class="level-header">${type.toUpperCase()}</div>`;
    resHtml += items.map(r => `
      <a href="${r.url}" target="_blank" rel="noopener" class="resource-card" style="display:flex;text-decoration:none">
        <div style="flex:1">
          <div class="rc-name">${r.name}</div>
          <div class="rc-desc">${r.description}</div>
        </div>
      </a>
    `).join('');
  }
  document.getElementById('resources-list').innerHTML = resHtml;
}

// ===== DENVER PAGE =====
async function loadDenver() {
  if (!allSchedule.length) allSchedule = await api('/tricks/schedule/all');
  const gates = await api('/progress/gates');
  const denverItems = await api('/denver');

  const plan = activePlan || {};
  const now = new Date();
  const goalDate = new Date((plan.goal_date || '2026-07-01') + 'T00:00:00');
  const goalDesc = plan.goal_description || 'Denver';
  const programStart = new Date((plan.start_date || '2026-02-01') + 'T00:00:00');
  const totalWeeks = plan.total_weeks || 20;

  document.getElementById('goals-page-title').textContent = plan.name || 'Goals';

  // Countdown
  const daysLeft = Math.max(0, Math.ceil((goalDate - now) / 86400000));
  document.getElementById('denver-countdown').innerHTML = `<strong>${daysLeft}</strong> days until ${esc(goalDesc)}`;

  // Timeline
  const currentWeek = Math.max(1, Math.min(totalWeeks, Math.floor((now - programStart) / (7 * 86400000)) + 1));
  document.getElementById('week-timeline').innerHTML = '<div class="timeline">' +
    allSchedule.map(w => {
      const cls = [
        'timeline-week',
        `phase-${w.phase}`,
        w.week_number === currentWeek ? 'current' : '',
        w.week_number < currentWeek ? 'completed' : ''
      ].join(' ');
      return `<div class="${cls}" title="Week ${w.week_number}: ${w.primary_drills.slice(0, 50)}...">${w.week_number}</div>`;
    }).join('') + '</div>';

  // Phase gates grouped by phase
  const gatesByPhase = {};
  gates.forEach(g => {
    if (!gatesByPhase[g.phase]) gatesByPhase[g.phase] = [];
    gatesByPhase[g.phase].push(g);
  });
  const phaseNames = { 1: 'Phase 1 → 2', 2: 'Phase 2 → 3', 3: 'Phase 3 → 4', 4: 'Final Exam' };
  let gatesHtml = '';
  for (const [phase, items] of Object.entries(gatesByPhase)) {
    gatesHtml += `<div class="level-header">${phaseNames[phase] || 'Phase ' + phase}</div>`;
    gatesHtml += items.map(g => `
      <label class="gate-item ${g.is_hard_gate ? 'hard-gate' : ''} ${g.met ? 'met' : ''}" onclick="event.stopPropagation()">
        <input type="checkbox" ${g.met ? 'checked' : ''} onchange="toggleGate(${g.id}, this.checked)">
        <span class="gate-text">${g.item_text}</span>
      </label>
    `).join('');
  }
  document.getElementById('phase-gates').innerHTML = gatesHtml;

  // Denver prep checklist
  const categories = { locations: 'Locations', legal: 'Legal / FAA', equipment: 'Equipment', logistics: 'Logistics' };
  const byCategory = {};
  denverItems.forEach(item => {
    if (!byCategory[item.category]) byCategory[item.category] = [];
    byCategory[item.category].push(item);
  });
  let denverHtml = '';
  for (const [cat, label] of Object.entries(categories)) {
    const items = byCategory[cat] || [];
    denverHtml += `<div class="denver-category"><h4>${label}</h4>`;
    denverHtml += items.map(item => `
      <label class="gate-item ${item.completed ? 'met' : ''}">
        <input type="checkbox" ${item.completed ? 'checked' : ''} onchange="toggleDenver(${item.id}, this.checked)">
        <span class="gate-text">${item.text}</span>
      </label>
    `).join('');
    denverHtml += '</div>';
  }
  document.getElementById('denver-checklist').innerHTML = denverHtml;
}

async function toggleGate(gateId, met) {
  await api(`/progress/gates/${gateId}`, { method: 'PUT', body: { met } });
}

async function toggleDenver(itemId, completed) {
  await api(`/denver/${itemId}`, { method: 'PUT', body: { completed, notes: '' } });
}

// ===== IMPORT / EXPORT =====
async function exportData() {
  const data = await api('/data/export');
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `fpv-tracker-export-${new Date().toISOString().split('T')[0]}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

async function importData(event) {
  const file = event.target.files[0];
  if (!file) return;
  const text = await file.text();
  let data;
  try { data = JSON.parse(text); } catch(e) { alert('Invalid JSON file'); return; }
  if (!confirm(`Import data? This will add ${data.sessions?.length || 0} sessions (duplicates will be skipped).`)) return;
  const result = await api('/data/import', { method: 'POST', body: data });
  alert(`Imported: ${result.imported.sessions} sessions, ${result.imported.packs} packs, ${result.imported.trick_attempts} trick attempts`);
  loadSessions();
}

// ===== Utilities =====
function esc(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ===== PWA Registration =====
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// ===== Init =====
api('/health').then(data => {
  if (data.version) document.getElementById('app-version').textContent = `v${data.version}`;
}).catch(() => {});

api('/plans/active').then(p => { if (p && !p.error) activePlan = p; }).catch(() => {}).finally(loadToday);
