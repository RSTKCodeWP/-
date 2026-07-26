import { analyze, parseMotorSize } from "./sizer-calculator.js";

const STORAGE_KEY = "prop-motor-sizer.inputs.v1";

const FIELD_IDS = [
  "style",
  "diameter",
  "pitch",
  "blades",
  "motor-size",
  "kv",
  "cells",
  "auw",
  "motor-count",
];

// Advanced fields tune the model rather than describe the build, so
// changing them keeps the selected preset label.
const ADVANCED_IDS = [
  "chemistry",
  "volt-basis",
  "load-factor",
  "altitude",
  "capacity",
  "measured-thrust",
];

const ADVANCED_DEFAULTS = {
  chemistry: "lipo",
  "volt-basis": "full",
  "load-factor": "75",
  altitude: "",
  capacity: "",
  "measured-thrust": "",
};

// Per-cell voltage by chemistry and basis. "nominal" also sets the voltage
// used for battery-energy (endurance) math.
const CHEMISTRY = {
  lipo: { full: 4.2, nominal: 3.7, load: 3.5 },
  lihv: { full: 4.35, nominal: 3.8, load: 3.6 },
  liion: { full: 4.2, nominal: 3.6, load: 3.3 },
};

const PRESETS = {
  whoop: {
    style: "freestyle",
    diameter: "1.2",
    pitch: "0.9",
    blades: "3",
    "motor-size": "0802",
    kv: "25000",
    cells: "1",
    auw: "27",
    "motor-count": "4",
  },
  "3in4s": {
    style: "freestyle",
    diameter: "3",
    pitch: "2.5",
    blades: "3",
    "motor-size": "1404",
    kv: "3800",
    cells: "4",
    auw: "250",
    "motor-count": "4",
  },
  "5in6s": {
    style: "freestyle",
    diameter: "5",
    pitch: "4.5",
    blades: "3",
    "motor-size": "2207",
    kv: "1800",
    cells: "6",
    auw: "680",
    "motor-count": "4",
  },
  "5in4s-race": {
    style: "racing",
    diameter: "5.1",
    pitch: "4.9",
    blades: "3",
    "motor-size": "2306",
    kv: "2600",
    cells: "4",
    auw: "550",
    "motor-count": "4",
  },
  "7in6s-lr": {
    style: "longrange",
    diameter: "7",
    pitch: "4",
    blades: "2",
    "motor-size": "2806.5",
    kv: "1300",
    cells: "6",
    auw: "1100",
    "motor-count": "4",
  },
};

const $ = (id) => document.getElementById(id);

function num(id) {
  const v = $(id).value.trim();
  if (v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}

function readInputs() {
  const chem = CHEMISTRY[$("chemistry").value] ?? CHEMISTRY.lipo;
  return {
    diameterIn: num("diameter"),
    pitchIn: num("pitch"),
    blades: num("blades"),
    motorSize: $("motor-size").value.trim() || undefined,
    kv: num("kv"),
    cells: num("cells"),
    auwGrams: num("auw"),
    motorCount: num("motor-count"),
    style: $("style").value,
    cellVoltage: chem[$("volt-basis").value] ?? chem.full,
    cellVoltageFull: chem.full,
    cellVoltageNominal: chem.nominal,
    loadFactor: (num("load-factor") ?? 75) / 100,
    altitudeM: num("altitude"),
    capacityMah: num("capacity"),
    measuredThrustG: num("measured-thrust"),
  };
}

const fmtInt = (n) => Math.round(n).toLocaleString("en-US");

function metricCard({ label, value, sub, highlight }) {
  return `<div class="metric${highlight ? " highlight" : ""}">
    <div class="metric-label">${label}</div>
    <div class="metric-value">${value}</div>
    ${sub ? `<div class="metric-sub">${sub}</div>` : ""}
  </div>`;
}

function renderMetrics(m) {
  const cards = [];
  if (m.twr !== undefined) {
    cards.push(metricCard({
      label: "Thrust : weight",
      value: `${m.twr.toFixed(1)} : 1`,
      highlight: true,
    }));
  }
  if (m.hoverThrottlePct !== undefined) {
    cards.push(metricCard({
      label: "Hover throttle",
      value: `≈ ${Math.round(m.hoverThrottlePct)}%`,
    }));
  }
  if (m.thrustPerMotorG !== undefined) {
    cards.push(metricCard({
      label: "Static thrust",
      value: `${fmtInt(m.thrustPerMotorG)} g/motor`,
      sub: `${fmtInt(m.totalThrustG)} g total`,
    }));
  }
  if (m.loadedRpm !== undefined) {
    cards.push(metricCard({
      label: "RPM under load",
      value: `≈ ${fmtInt(m.loadedRpm)}`,
      sub: `unloaded ceiling ${fmtInt(m.maxRpm)} at ${m.voltage.toFixed(1)} V`,
    }));
  }
  if (m.hoverFlightTimeMin !== undefined) {
    cards.push(metricCard({
      label: "Hover endurance",
      value: `≈ ${m.hoverFlightTimeMin.toFixed(0)} min`,
      sub: "ideal hover, 80% usable — mixed flying is far less",
    }));
  }
  if (m.tipSpeedMs !== undefined) {
    cards.push(metricCard({
      label: "Tip speed",
      value: `${Math.round(m.tipSpeedMs)} m/s`,
      sub: `Mach ${m.tipMach.toFixed(2)}`,
    }));
  }
  if (m.pitchSpeedKmh !== undefined) {
    cards.push(metricCard({
      label: "Pitch speed",
      value: `${Math.round(m.pitchSpeedKmh)} km/h`,
      sub: `${Math.round(m.pitchSpeedMph)} mph (zero-slip top speed)`,
    }));
  }
  if (m.hoverCurrentA !== undefined) {
    cards.push(metricCard({
      label: "Hover draw",
      value: `≈ ${m.hoverCurrentA.toFixed(1)} A`,
      sub: `${fmtInt(m.hoverPowerW)} W`,
    }));
  }
  if (m.maxCurrentA !== undefined) {
    cards.push(metricCard({
      label: "Full-throttle draw",
      value: `≈ ${fmtInt(m.maxCurrentA)} A`,
      sub: `${Math.round(m.maxCurrentPerMotorA)} A/motor · ${fmtInt(m.maxPowerW)} W`,
    }));
  }
  if (m.discLoadingGCm2 !== undefined) {
    cards.push(metricCard({
      label: "Disc loading",
      value: `${m.discLoadingGCm2.toFixed(2)} g/cm²`,
    }));
  }
  if (m.statorVolumeMm3 !== undefined) {
    cards.push(metricCard({
      label: "Stator volume",
      value: `${fmtInt(m.statorVolumeMm3)} mm³`,
    }));
  }
  if (m.airDensity !== undefined) {
    cards.push(metricCard({
      label: "Air density",
      value: `${m.airDensity.toFixed(3)} kg/m³`,
      sub: `${Math.round((m.airDensity / 1.225 - 1) * 100)}% vs sea level`,
    }));
  }
  return cards.join("");
}

const REC_RENDERERS = {
  kv: (r) => ["Motor KV", `${fmtInt(r.min)}–${fmtInt(r.max)} KV`, `ideal ≈ ${fmtInt(r.ideal)} KV`],
  cells: (r) => [
    "Battery",
    r.min === r.max ? `${r.ideal}S` : `${r.min}S–${r.max}S`,
    `ideal ${r.ideal}S`,
  ],
  motorSizes: (r) => ["Motor size", r.sizes.join(", "), null],
  diameter: (r) => ["Prop diameter", `${r.min}–${r.max}″`, `ideal ≈ ${r.ideal}″`],
  pitch: (r) => ["Prop pitch", `${r.min}–${r.max}″`, null],
  auw: (r) => ["All-up weight", `${fmtInt(r.min)}–${fmtInt(r.max)} g`, null],
};

function renderRecommendations(recs) {
  return Object.entries(recs).map(([key, rec]) => {
    const renderer = REC_RENDERERS[key];
    if (!renderer) return "";
    const [label, value, detail] = renderer(rec);
    return `<li>
      <span class="rec-field">${label}:</span>
      <span class="rec-value">${value}</span>${
      detail ? ` <span class="rec-basis">${detail}</span>` : ""
    }
      <span class="rec-basis">based on ${rec.basis}</span>
    </li>`;
  }).join("");
}

function render() {
  const inputs = readInputs();
  const { metrics, recommendations, verdicts } = analyze(inputs);

  // Flag an unparseable motor size right on the field
  const motorField = $("motor-size");
  const motorText = motorField.value.trim();
  motorField.style.borderColor = motorText && !parseMotorSize(motorText) ? "var(--color-bad)" : "";

  const hasMetrics = Object.keys(metrics).length > 0;
  const hasRecs = Object.keys(recommendations).length > 0;
  const hasVerdicts = verdicts.length > 0;

  $("empty-state").hidden = hasMetrics || hasRecs;
  $("verdicts-section").hidden = !hasVerdicts;
  $("metrics-section").hidden = !hasMetrics;
  $("recs-section").hidden = !hasRecs;

  $("verdicts").innerHTML = verdicts
    .map((v) => `<li class="${v.level}">${v.text}</li>`)
    .join("");
  $("metrics").innerHTML = renderMetrics(metrics);
  $("recommendations").innerHTML = renderRecommendations(recommendations);
}

function saveInputs() {
  const state = {};
  for (const id of [...FIELD_IDS, ...ADVANCED_IDS]) state[id] = $(id).value;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Private browsing or storage full - persistence is best-effort
  }
}

function loadInputs() {
  try {
    const state = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    for (const id of [...FIELD_IDS, ...ADVANCED_IDS]) {
      if (typeof state[id] === "string") $(id).value = state[id];
    }
  } catch {
    // Corrupt state - start fresh
  }
}

function syncLoadFactorOut() {
  $("load-factor-out").textContent = `${$("load-factor").value}%`;
}

function applyPreset(name) {
  const preset = PRESETS[name];
  if (!preset) return;
  for (const [id, value] of Object.entries(preset)) $(id).value = value;
}

function init() {
  loadInputs();
  syncLoadFactorOut();

  for (const id of FIELD_IDS) {
    $(id).addEventListener("input", () => {
      $("preset").value = "";
      saveInputs();
      render();
    });
  }

  for (const id of ADVANCED_IDS) {
    $(id).addEventListener("input", () => {
      syncLoadFactorOut();
      saveInputs();
      render();
    });
  }

  $("preset").addEventListener("change", (e) => {
    applyPreset(e.target.value);
    saveInputs();
    render();
  });

  $("reset").addEventListener("click", () => {
    for (const id of FIELD_IDS) $(id).value = "";
    $("blades").value = "3";
    $("motor-count").value = "4";
    $("style").value = "freestyle";
    $("preset").value = "";
    for (const [id, value] of Object.entries(ADVANCED_DEFAULTS)) $(id).value = value;
    syncLoadFactorOut();
    saveInputs();
    render();
  });

  render();
}

init();
