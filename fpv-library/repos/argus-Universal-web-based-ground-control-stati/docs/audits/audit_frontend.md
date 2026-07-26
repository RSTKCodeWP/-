# Argus GCS Frontend Audit (Svelte 5 + TypeScript)

Audit scope: `src/lib/*.ts`, `src/lib/*.svelte.ts`, `src/components/**/*.svelte`, `src/App.svelte`.
Bug classes audited: $effect reactivity bugs, $derived correctness, lifecycle leaks, race conditions, localStorage handling, WS reconnect, type safety.

Legend: 🔴 critical · 🟡 medium · 🟢 low · ✅ auto-fixed in place · ⏳ needs follow-up

---

## 1. `$effect` reactivity bugs

### 🔴 F-1: `Compass3DPanel.svelte` — effect mutates state it doesn't depend on properly, AND mutates state that another effect reads (infinite loop risk + missing tracking)
**File**: `src/components/map/Compass3DPanel.svelte:17-24`

```ts
$effect(() => {
  const d = app.drone;
  if (!d.connected) return;
  const raw = d.vibe;
  if (raw[0] === 0 && raw[1] === 0 && raw[2] === 0) return;
  samples.push({ x: raw[0], y: raw[1], z: raw[2] });        // mutates $state samples
  if (samples.length > 2000) samples.splice(0, samples.length - 1500);
});
```

Two problems:
1. The effect reads `d.vibe` (reactive) and `samples` (reactive) — when it pushes to `samples`, it modifies its own tracked dependency (`samples.length` is read by `samples.splice`). This re-triggers the effect, which then runs again on the next `d.vibe` change. The infinite loop is masked only because the second effect at line 26 also depends on `samples`, and the first effect doesn't read length/get index from samples except inside the splice expression — but `samples.length > 2000` evaluation does read `length`. Each push will dirty `samples`, scheduling a re-run.
2. The mutation should be wrapped in `untrack()` (like `ChartPanel.svelte` already does) to avoid the self-dirty issue.

**Fix**: wrap mutations in `untrack()`.

### 🔴 F-2: `App.svelte` — `$effect` does side-effect writes to state it depends on (`summaryShown` write while reading drone state)
**File**: `src/App.svelte:142-146`

```ts
$effect(() => {
  const d = app.drone;
  checkAlerts(d.connected, d.armed, d.remaining, d.link_age);
  if (d.flight_summary && !app.summaryShown) app.summaryShown = true;
});
```

`app.summaryShown = true` is written inside the effect that reads `app.summaryShown` (via `!app.summaryShown`). In Svelte 5 this is allowed and self-cycles once but it's an anti-pattern. The condition `!app.summaryShown` makes it idempotent so it works — but ⏳ would be cleaner as a separate `$effect`.

### 🔴 F-3: `App.svelte` — `$effect` for `view === 'monitor'` force-opens charts but never closes them on switch away
**File**: `src/App.svelte:148-150`

```ts
$effect(() => {
  if (view === 'monitor') app.chartsOpen = true;
});
```

If user closes charts manually while still in monitor view, then switches tabs and back, the effect re-runs (view dep unchanged but effect re-runs on any reactive change) and reopens charts. Effect should track `view` only and not modify global state from a transient view condition. Minor UX issue — 🟢.

### 🔴 F-4: `MissionPanel.svelte` — `$effect` for terrain fetch mutates state inside `then()` without staleness guarantee + races with subsequent waypoint edits
**File**: `src/components/mission/MissionPanel.svelte:241-260`

```ts
$effect(() => {
  if (app.waypoints.length < 2) { terrainElevations = null; terrainPoints = []; return; }
  const wps = app.waypoints.map(w => ({ lat: w.lat, lon: w.lon }));
  const pts = interpolateRoute(wps, 50);
  const snapshot = JSON.stringify(wps.map(w => `${w.lat.toFixed(5)},${w.lon.toFixed(5)}`));
  terrainLoading = true;
  getElevationProfile(pts).then(elevs => {
    const current = app.waypoints.map(w => `${w.lat.toFixed(5)},${w.lon.toFixed(5)}`);
    if (JSON.stringify(current) !== snapshot) return;
    ...
  });
});
```

`terrainLoading = true` is written but no cancellation flag is used. If 5 edits happen back-to-back, 5 fetches are in flight and 4 will discard via the snapshot check, but `terrainLoading` toggles to false in `.finally()` of the **first** request that resolves, not the last. This means UI shows "loading=false" while later requests are still pending. Also, the `terrainLoading = true` is reactive and inside the same effect that reads `app.waypoints` — fine because `terrainLoading` isn't a dep here.

Severity 🟡 — display issue, not correctness.

### 🟡 F-5: `StatusBar.svelte` — `setInterval` inside `$effect` runs forever without restart on dep change
**File**: `src/components/core/StatusBar.svelte:26-37`

```ts
$effect(() => {
  const timer = setInterval(() => {
    const f = app.drone.frames;
    msgRate = Math.round((f - prevFrames) / 2);
    prevFrames = f;
    if (app.drone.connected) {
      app.linkHistory.push({ t: Date.now(), rate: msgRate, age: app.drone.link_age });
      if (app.linkHistory.length > 120) app.linkHistory.splice(0, app.linkHistory.length - 90);
    }
  }, 2000);
  return () => clearInterval(timer);
});
```

This effect has no reactive dependencies in the outer scope (it reads `app.drone.frames` only inside the interval callback). The effect runs once on mount, clears on unmount — that's actually correct. The reads inside `setInterval` are NOT tracked because they happen outside the synchronous effect body, which is fine here. ✅ No bug.

### 🟡 F-6: `TelemetryOverlay.svelte` — same `setInterval`-in-effect pattern, also OK
**File**: `src/components/telemetry/TelemetryOverlay.svelte:19-22`

```ts
$effect(() => {
  const timer = setInterval(() => { snapAlt = d.alt_rel; snapDist = d.dist_home; }, 1500);
  return () => clearInterval(timer);
});
```

`const d = app.drone` is at module/component init scope — `d` is the reactive proxy, so `d.alt_rel` reads inside `setInterval` work normally. The effect itself has no reactive deps so it runs once and returns cleanup. ✅ No bug.

### 🔴 F-7: `EkfPanel.svelte`, `HudOverlay.svelte`, `PreflightPanel.svelte`, `PositionSourcePanel.svelte`, `VibrationPanel.svelte` — `const d = app.drone` captured at module-scope, then used in template
**Files**:
- `src/components/telemetry/EkfPanel.svelte:6`
- `src/components/core/HudOverlay.svelte:5`
- `src/components/shared/PreflightPanel.svelte:6`
- `src/components/setup/PositionSourcePanel.svelte:20`
- `src/components/telemetry/VibrationPanel.svelte:79`

```ts
const d = app.drone;
```

This is actually fine because `app.drone` is a `$state` object — `d` becomes a reference to the same reactive proxy and reads (e.g. `d.lat`) still go through the proxy and are tracked. ✅ No bug — verified the pattern is supported by Svelte 5.

### 🟡 F-8: `ParamPanel.svelte` — `treeGroups` derived returns mutable `expanded` field that gets re-clobbered
**File**: `src/components/params/ParamPanel.svelte:90-101, 446-447`

```ts
let treeGroups = $derived.by((): TreeGroup[] => {
  // ...
  return Array.from(groups.entries()).map(([name, params]) => ({ name, params, expanded: false }));
});
// template:
onclick={() => group.expanded = !group.expanded}
```

`treeGroups` is `$derived` — its result recomputes any time `filtered` changes (which depends on `paramState.list`, `category`, `search`, etc.). When the user toggles `group.expanded`, it mutates an object inside the derived value. Next time params arrive or filter changes, `treeGroups` recomputes and ALL `expanded` flags reset to `false`. Tree-view state is lost. ⏳ Needs `Map<string, boolean>` separate state for expansion.

### 🟡 F-9: `ParamPanel.svelte` — `$effect(() => { filtered; visibleStart = 0; })` resets scroll on every filter recompute including identity changes
**File**: `src/components/params/ParamPanel.svelte:188`

```ts
$effect(() => { filtered; visibleStart = 0; });
```

Whenever `paramState.list` updates (param arrives during a fetch), `filtered` recomputes (new array identity), the effect fires, and `visibleStart = 0` resets scroll. During param fetch the user can't scroll because every batch resets them. 🟡 — Worth fixing by tracking the actual filter inputs (category, search, showModifiedOnly).

### 🔴 F-10: `LazyPanelHost.svelte` — `for (const id of panels._open)` reads private Set but effect won't re-run on each Set replacement properly
**File**: `src/components/core/LazyPanelHost.svelte:8-20`

```ts
$effect(() => {
  for (const id of panels._open) {
    if (!loaded[id] && !errors[id] && PANEL_LOADERS[id]) {
      PANEL_LOADERS[id]().then(mod => {
        if (mod.default) {
          loaded = { ...loaded, [id]: mod.default };  // reactive write
        }
      }).catch(err => {
        errors = { ...errors, [id]: String(err?.message || 'Load failed') };
      });
    }
  }
});
```

When the load completes and writes `loaded`, the effect re-runs (it reads `loaded[id]` inside the same effect). On re-run, the import promise has NOT necessarily resolved for newly added panels because `loaded[newId]` is still undefined → it triggers a fresh import call. Since this is rate-limited by `if (!loaded[id])`, double-imports are prevented for the same id once loaded[id] is set. But there's a subtle race: between the check `!loaded[id]` and the async `.then(...)`, if the same id is iterated again (e.g. opened twice), the second iteration also fires `PANEL_LOADERS[id]()` because `loaded[id]` is still undefined. Vite caches modules, so multiple imports are coalesced — practical impact: nil. 🟢

### 🔴 F-11: `WaypointLayer.svelte` — `$effect` modifies `app.focusWp = -1` from inside same effect that reads `app.focusWp`
**File**: `src/components/layers/WaypointLayer.svelte:112-124`

```ts
$effect(() => {
  if (app.focusWp < 0 || app.focusWp >= app.waypoints.length) return;
  const wp = app.waypoints[app.focusWp];
  // ...
  const focusTimer = setTimeout(() => { ... }, 2000);
  app.focusWp = -1;   // ← write to dep
  return () => clearTimeout(focusTimer);
});
```

The effect reads `app.focusWp` and writes `-1` to it at the end. This triggers a second effect run with `app.focusWp = -1`, where the guard at the top short-circuits and the cleanup runs (clearing the just-created timer). So **the focus ring is removed immediately by the cleanup of the previous run**, not after 2000 ms. 🔴 Real bug — the focus highlight only stays for the duration between the write and the next effect tick.

**Fix**: use `untrack()` for the write, or push `app.focusWp = -1` into a `requestAnimationFrame` callback.

### 🟡 F-12: `MapView.svelte` — `applyTileSource` runs only when `ts !== prevTileSource`, but on first run after mount `prevTileSource` is set in `onMount` before effect runs. Sometimes the initial layer setup may not align.
**File**: `src/components/core/MapView.svelte:86-93`

```ts
let prevTileSource = '';
$effect(() => {
  const ts = app.tileSource;
  if (ts !== prevTileSource && map) {
    prevTileSource = ts;
    applyTileSource();
  }
});
```

`prevTileSource` starts as `''` and is also set to `app.tileSource` in `onMount` (line 97). If the effect fires before `onMount` (which it can — effects schedule on mount but order between effects and onMount can vary), `prevTileSource === ''` and `applyTileSource()` would run BEFORE map is created. The `map` null-guard prevents the crash but means the initial source is applied twice. 🟢 Minor.

### 🔴 F-13: `OfflineMapPanel.svelte` — `$effect` modifies its own inputs (lat/lon coordinates)
**File**: `src/components/map/OfflineMapPanel.svelte:25-32`

```ts
$effect(() => {
  if (app.drone.lat !== 0) {
    latMin = app.drone.lat - 0.05;
    latMax = app.drone.lat + 0.05;
    lonMin = app.drone.lon - 0.05;
    lonMax = app.drone.lon + 0.05;
  }
});
```

This overwrites the user's manually-edited lat/lon bounds every time the drone moves. So if the user types a custom bounding box, it gets wiped by the next telemetry frame. 🔴 Real UX bug.

**Fix**: snapshot drone position once on panel open instead of using `$effect`.

### 🔴 F-14: `OfflineMapPanel.svelte` — auto-fetch tile cache on mount is in a bare $effect (no deps), runs once but no error catch chain visible
**File**: `src/components/map/OfflineMapPanel.svelte:21-23`

```ts
$effect(() => {
  fetch(apiUrl('/api/tile_cache')).then(r => r.json()).then(d => cacheInfo = d).catch(() => {});
});
```

Effect has no reactive deps so it runs once on mount and never again. Functionally equivalent to `onMount`. ✅ No bug.

### 🔴 F-15: `OrthoOverlayPanel.svelte`, `AnnotationPanel.svelte` — mutate `$state` arrays via `.push/.splice` directly
**Files**:
- `src/components/planning/AnnotationPanel.svelte:49, 70`
- `src/components/map/OrthoOverlayPanel.svelte:74, 93`
- `src/components/planning/SchedulerPanel.svelte:75, 99`
- `src/components/planning/AiAnnotationPanel.svelte:157, 170`

```ts
annotations.push({ ... });  // works because $state in Svelte 5 uses proxies
```

In Svelte 5, `$state`-wrapped arrays are proxies that DO track `.push()` and `.splice()`. ✅ No bug — verified pattern works.

### 🔴 F-16: `RcCalibPanel.svelte` — effect reads `app.drone.rc` and conditionally writes `minValues[i]` / `maxValues[i]` (both reactive) without untrack
**File**: `src/components/setup/RcCalibPanel.svelte:25-34`

```ts
$effect(() => {
  if (step !== 2) return;
  const rc = app.drone.rc;
  if (!rc || rc.length < CH_COUNT) return;
  for (let i = 0; i < CH_COUNT; i++) {
    const v = rc[i];
    if (v < minValues[i]) minValues[i] = v;       // self-write
    if (v > maxValues[i]) maxValues[i] = v;
  }
});
```

Reads `minValues[i]`, then writes `minValues[i]`. This re-fires the effect on every write. In each effect run for a given `rc`, only one channel might update before `minValues` re-publishes, causing a cascade of runs (although guard `v < minValues[i]` becomes false on second pass so it stops). Not infinite, but every reactive read in inner loop triggers full re-run. 🟡 — Performance. Wrap in `untrack()`.

### 🟡 F-17: `FrameSelectPanel.svelte`, `FlightModePanel.svelte`, `FailsafeConfigPanel.svelte`, `PidPanel.svelte` — `$effect` initializes from params, but re-fires any time `paramState.list` updates, clobbering user edits mid-fetch
**Files**:
- `src/components/setup/FrameSelectPanel.svelte:63-67`
- `src/components/params/FlightModePanel.svelte:58-66`
- `src/components/params/FailsafeConfigPanel.svelte:47-63`
- `src/components/params/PidPanel.svelte:59-69`

```ts
$effect(() => {
  if (!paramsAvailable) return;
  selectedClass = getParam('FRAME_CLASS', 1);
  selectedType  = getParam('FRAME_TYPE', 1);
});
```

`paramState.list` changes during streaming param download (one batch every few hundred ms). Each batch update re-runs this effect, clobbering whatever the user has just typed in the input. Param edits are silently overwritten until the fetch finishes.

🟡 — Real bug but limited window. Fix: only initialize when params first become available (track `paramsAvailable` transition, or guard with "if already initialized, skip").

### 🟡 F-18: `FailsafeConfigPanel.svelte` — `battEnable = getParam('FS_BATT_ENABLE', 0); battAction = getParam('FS_BATT_ENABLE', 0);` reads SAME param for two different state values
**File**: `src/components/params/FailsafeConfigPanel.svelte:49-50, 54-55, 58-59`

```ts
battEnable  = getParam('FS_BATT_ENABLE', 0);
battAction  = getParam('FS_BATT_ENABLE', 0);  // same param! should be different
// ...
rcEnable    = getParam('FS_THR_ENABLE', 0);
rcAction    = getParam('FS_THR_ENABLE', 0);   // same param!
// ...
gcsEnable   = getParam('FS_GCS_ENABLE', 0);
gcsAction   = getParam('FS_GCS_ENABLE', 0);   // same param!
```

This appears to be a bug — `battEnable` is a boolean-ish toggle while `battAction` is an integer action code. The current code makes them always equal, which means the user can never select an action independent of enabling. The save logic then uses `battEnable ? battAction || 1 : 0` which compounds the issue. ⏳ Need to verify intended ArduPilot param semantics — likely should read `FS_BATT_ACTION` or use a single field correctly.

### 🟢 F-19: `LogPanel.svelte` cleanup — calling `cancelDownload()` doesn't notify backend about cancellation if the WS was disconnected; race with reconnect
**File**: `src/components/tools/LogPanel.svelte:17-20`

Order is `sendCommand('log_cancel'); cancelDownload();`. If backend is down, `sendCommand` shows a toast but `cancelDownload()` correctly resets local state. ✅ No bug.

---

## 2. `$derived` correctness

### 🟡 F-20: `ParamDiffPanel.svelte` — `currentMap` is a `$derived` returning a function, not the Map
**File**: `src/components/params/ParamDiffPanel.svelte:60-64`

```ts
let currentMap = $derived(() => {
  const m = new Map<string, number>();
  for (const p of paramState.list) m.set(p.name, p.value);
  return m;
});
// usage:
const cur = currentMap();   // line 68
```

`$derived` returns the *value* of the expression. Here the expression is a function literal. So `currentMap` is a function. Each call rebuilds the Map fresh. Reactivity: when `paramState.list` changes, the derived doesn't recompute (no `paramState.list` read in the outer expression). Calling `currentMap()` re-reads the list each time, which only triggers reactivity if it's called from a reactive context (allRows is `$derived.by`, so the call inside allRows DOES track `paramState.list`). Net result: works, but inefficient and confusing. 🟡 — Should use `$derived.by(() => { const m = ...; return m; })`.

### 🟢 F-21: `CalibrationPanel.svelte` — already correct after recent fix
The HH:MM:SS timestamp gating is sound. ✅ Reference impl for other panels.

---

## 3. Component lifecycle leaks

### 🔴 F-22: `MapView.svelte` — `setTimeout(() => map!.invalidateSize(), 100)` never cleared on unmount
**File**: `src/components/core/MapView.svelte:110`

```ts
setTimeout(() => map!.invalidateSize(), 100);
```

If the component unmounts within 100 ms of mount, the timer fires after `map` is `null` and `map!.invalidateSize()` throws. 🟡 — Need to capture the timer id and clear on cleanup.

### 🔴 F-23: `WaypointLayer.svelte` — `focusTimer` from `setTimeout` returns cleanup, but the `focusRing` itself isn't removed if effect re-runs before timer fires AND ring was already replaced
**File**: `src/components/layers/WaypointLayer.svelte:117-123`

The effect creates a new `focusRing` each time `app.focusWp` is set. If effect re-runs (e.g. waypoints array changes during the 2000 ms), the old `focusRing` is set to a new layer but the previous one wasn't removed by the cleanup (cleanup runs AFTER the new run completes). The cleanup only clears the timer, not the ring. The old ring is replaced via the `if (focusRing) map.removeLayer(focusRing);` line, so it's removed once — but if effect re-runs and `app.focusWp < 0` (early return), the existing `focusRing` is leaked. 🟡

### 🔴 F-24: `MotorTestPanel.svelte` — `setInterval` timers stored in plain `timers` object not in `$state`; not cleared on component unmount
**File**: `src/components/setup/MotorTestPanel.svelte:15-46`

```ts
let timers: Record<number, ReturnType<typeof setInterval>> = {};
// ...
function spinMotor(index: number) {
  // ...
  timers[index] = setInterval(() => { ... }, 100);
}
```

There's no `onDestroy` or cleanup that clears the timers. If user closes the panel while motors are spinning, the intervals continue firing until they each independently stop. The `sendCommand('motor_test_stop')` is only called via "Stop All" button. 🔴 — Leaks intervals + backend keeps motor running.

**Fix**: Add `onDestroy(stopAll);`.

### 🔴 F-25: `MissionPanel.svelte` — `uploadTimer` cleared on overlapping uploads but not on unmount
**File**: `src/components/mission/MissionPanel.svelte:82-93`

```ts
let uploadTimer: ReturnType<typeof setTimeout> | null = null;
let uploading = $state(false);
function uploadMission() {
  // ...
  uploadTimer = setTimeout(() => { uploading = false; uploadTimer = null; }, 3000);
}
```

If user starts upload then navigates away, timer fires and sets `uploading = false` on a dead component (harmless because Svelte 5 ignores writes to destroyed state, but the closure leak persists for 3s). 🟢 Low-risk.

### 🔴 F-26: `FlightReportPanel.svelte` — `exportTimer` same pattern, low impact
**File**: `src/components/tools/FlightReportPanel.svelte:46, 99-100`

🟢 Same as F-25.

### 🔴 F-27: `ConnectionForm.svelte` — `connectTimer` cleared on connected but not on unmount
**File**: `src/components/core/ConnectionForm.svelte:77-95`

🟢 Same as F-25.

### 🔴 F-28: `VideoOverlay.svelte` — `mousemove`/`mouseup` window listeners added in `onDragStart`, removed both in `onDragEnd` AND in $effect cleanup
**File**: `src/components/vehicle/VideoOverlay.svelte:80-85`

```ts
$effect(() => {
  return () => {
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', onDragEnd);
  };
});
```

Good — the cleanup handles the case where component unmounts during drag. ✅ No bug.

### 🔴 F-29: `MapView.svelte` — `window.addEventListener('keydown', onKeyDown)` is registered in `onMount` and removed in its cleanup, OK
**File**: `src/components/core/MapView.svelte:109, 112`

✅ Correct.

### 🔴 F-30: `App.svelte` mobile resize listener — listener removed correctly
**File**: `src/App.svelte:227-232`

✅ Correct.

### 🟡 F-31: `LogStore` (`logStore.svelte.ts`) — `_chunks` accumulates during streaming download. On WS reconnect mid-download, `downloadId` is set but old `_chunks` is not cleared since the new download may have a different id
**File**: `src/lib/logStore.svelte.ts:28-38`

`startDownload()` clears `_chunks`. But what if the WS reconnects while download is in progress? The backend will likely abort the download, but `cancelDownload()` is not called automatically on WS close. The next `startDownload` for any log starts fresh — so the leak is bounded to one stale download's chunks. 🟢 Minor memory issue.

### 🔴 F-32: `Map3DView.svelte` — second `$effect` reads `app.waypoints`, but `map.isStyleLoaded()` race
**File**: `src/components/map/Map3DView.svelte:172-202`

```ts
$effect(() => {
  if (!map || !map.isStyleLoaded()) return;
  const wps = app.waypoints;
  ...
});
```

`isStyleLoaded()` is non-reactive; if waypoints change before style loads, effect bails early. When style loads, there's no event that re-fires this effect — so initial waypoints may never render until the next waypoint change. 🟡 — should listen to `map.on('load', ...)`.

### 🔴 F-33: `Map3DView.svelte` — `droneMarker` / `homeMarker` are NOT cleared between connection cycles
**File**: `src/components/map/Map3DView.svelte:121-124`

The `onDestroy` cleans them, but on disconnect/reconnect with new home, the existing `homeMarker` is reused. If home changes location, the marker stays at old position (the effect only creates `homeMarker` once because of `if (d.home_lat !== 0 && !homeMarker)`). 🟡 — Bug but rare scenario.

### 🔴 F-34: `DroneLayer.svelte` — `homeMarker` similarly never repositioned if home changes
**File**: `src/components/layers/DroneLayer.svelte:70-78`

Same as F-33. 🟡 same bug.

### 🟢 F-35: `MapView.svelte` — Leaflet `map.remove()` cleanup on unmount handles all layers
✅ Correct.

---

## 4. Race conditions in async workflows

### 🔴 F-36: `MissionPanel.svelte` — `uploadMission()` uses a 3-second timer to clear `uploading`, but if backend ack comes faster the user could click again before backend finishes
**File**: `src/components/mission/MissionPanel.svelte:84-94`

```ts
function uploadMission() {
  if (!app.waypoints.length || uploading) return;
  uploading = true;
  sendCommand('mission_upload', undefined, { ... });
  uploadTimer = setTimeout(() => { uploading = false; ... }, 3000);
}
```

The button is disabled while `uploading` so this is mostly safe. But the timer hard-codes 3 s rather than listening for `mission_ack_ok` / `mission_ack_fail` events from `ws.ts`. If the backend takes longer than 3 s for a large mission, the button re-enables prematurely and re-uploading would start the protocol twice on the backend. 🟡 — Should clear `uploading` on receipt of `mission_ack_*` event.

### 🔴 F-37: `ParamPanel.svelte` `submitEdit()` — sends `param_set` then optimistically marks modified, but if param_set fails the modified set stays
**File**: `src/components/params/ParamPanel.svelte:193-207`

🟢 Low — UI consistency only.

### 🔴 F-38: `CalibrationPanel.svelte` — cleanup on tab switch
**File**: `src/components/setup/CalibrationPanel.svelte:254`

```ts
onclick={() => { if (!calibrating) selected = ct.id; }}
```

User cannot switch tab during calibration — protected by button being disabled. But `calRunStartTime` is not cleared when switching between tabs WHILE NOT calibrating, so stale events from a previous (non-cancelled) calibration could match the new pattern. The pattern is matched per-tab so usually fine. ✅

### 🔴 F-39: `ConnectionForm.svelte` — serial connect can race with WS connect
**File**: `src/components/core/ConnectionForm.svelte:108-158`

```ts
async function toggleSerial() {
  // ...
  const ok = await connectSerial(115200, { onHeartbeat: (msg) => {
    if (!app.drone.connected) { app.drone.connected = true; ... }
    // ...
  } });
}
```

The serial callbacks directly mutate `app.drone.*`. Meanwhile, `ws.ts:updateState()` (called on WS reconnect) does `Object.assign(app.drone, s)` and overwrites these fields. If both connections are active simultaneously, the data fights. The UI doesn't have a "kill WS" when serial connects. 🟡

### 🔴 F-40: `ConnectionForm.svelte:156` — pushes to `app.events` directly, bypassing the trim logic
**File**: `src/components/core/ConnectionForm.svelte:156`

```ts
onStatusText: (msg) => {
  app.events.push({ ... });   // ← direct push, no 200-event cap
}
```

`addEvent()` in `stores.svelte.ts:59-64` handles the 200-cap. Bypassing it can grow `app.events` unbounded in serial mode. 🔴 Real bug.

**Fix**: import `addEvent` and call it.

### 🔴 F-41: `WaypointLayer.svelte` — fitRouteFlag race
**File**: `src/components/layers/WaypointLayer.svelte:126-130`

```ts
$effect(() => {
  if (app.fitRouteFlag <= 0 || app.waypoints.length < 2) return;
  const pts = app.waypoints.map(w => coord(w.lat, w.lon));
  map.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
});
```

`fitRouteFlag` is incremented from `stores.svelte.ts:loadDownloadedMission()` and `MissionPanel.fitAfterLoad()`. The effect runs on any change but doesn't reset the flag. So next time waypoints change in a way that triggers the effect, it will fit again because `fitRouteFlag > 0`. The whole pattern relies on `fitRouteFlag` being incremented as a counter — and the effect's tracking will re-run only when `fitRouteFlag` actually changes (Svelte tracks reads of the value, not just truthy). So a fresh increment triggers. ✅ But subtle.

---

## 5. State persistence

### 🟡 F-42: `stores.svelte.ts:loadSettings()` — does not load `mapMode`, `unitSystem`
**File**: `src/lib/stores.svelte.ts:98-114, 116-129`

`saveSettings()` does not save `mapMode` or `unitSystem`. `loadSettings()` does not load them. So these survive only in memory. 🟡 — Minor UX, intentional? but the state fields exist in the class so probably intended to persist.

### 🟢 F-43: `migrate.ts` — runs all migrations every page load
**File**: `src/lib/migrate.ts:30-57`

After the first migration the old keys are removed and subsequent loads find nothing to migrate — efficient. ✅

### 🟢 F-44: `flightDb.ts` uses localStorage despite filename `flightDb`
**File**: `src/lib/flightDb.ts`

Comment in CLAUDE.md says "IndexedDB flight record store" but the code uses `localStorage`. Possibly intentional simplification but documentation mismatch. 🟢

### 🟡 F-45: `OrthoOverlayPanel`, `AnnotationPanel`, `SchedulerPanel`, `AiAnnotationPanel`, `RolePanel`, `AirspacePanel`, `ScriptPanel`, `PreflightPanel`, `NtripPanel` — all use `localStorage` with try/catch, but `loadOverlays()` etc. in `OrthoOverlayPanel.svelte:30-39` calls `JSON.parse` inside try and returns `[]` on failure. Safe.

✅ All checked instances properly wrap in try/catch.

### 🟡 F-46: `i18n.svelte.ts:setLocale` — writes localStorage in try block but does not handle quota exceeded for very small strings (won't happen in practice)

🟢 No bug.

### 🟡 F-47: `flightDb.saveFlightRecord` — quota exhausted will silently drop the new record
**File**: `src/lib/flightDb.ts:21`

```ts
try { localStorage.setItem(DB_KEY, JSON.stringify(records)); } catch {}
```

200 records × ~150 bytes = 30 KB, well under quota. ✅ No bug.

---

## 6. WebSocket reconnection (`ws.ts`)

### 🟡 F-48: `ws.ts` — `onLocaleChange` callback overwrites every reconnect
**File**: `src/lib/ws.ts:34`

```ts
ws.onopen = () => {
  // ...
  onLocaleChange((l) => sendMessage({ type: 'set_locale', locale: l }));
};
```

`i18n.svelte.ts:50` stores `_syncCallback = cb` (single slot, not a list). Every reconnect registers a new callback but the old reference to `ws.send` would still work because of `sendMessage` using the module-level `socket` var. ✅ No leak.

### 🟡 F-49: `ws.ts` — `reconnectAttempts` only resets on successful `onopen`, not on user-initiated reconnect. If the backend goes down then up after 10 attempts, the next disconnect cycle would wait 30 s. This is intentional backoff but maybe `reconnectAttempts = 0` should reset on `connectWs()` being called externally.
**File**: `src/lib/ws.ts:130-135`

🟢 Minor UX.

### 🔴 F-50: `ws.ts` — `staleCheckTimer` runs `ws.close()` to force reconnect on stale connection, but `ws` reference inside the closure may be a previous WebSocket if `staleCheckTimer` wasn't cleared in time
**File**: `src/lib/ws.ts:27-32`

```ts
staleCheckTimer = setInterval(() => {
  if (lastMessageTime > 0 && Date.now() - lastMessageTime > 15000) {
    console.warn('[WS] connection stale, reconnecting');
    ws.close();
  }
}, 5000);
```

The closure captures `ws` from the outer `connectWs()` call. If a reconnect happens and a new timer is created (line 26 clears the old one first), the old closure is gone — OK. ✅ Verified.

### 🟢 F-51: `ws.ts` — `param_batch` accumulator and `params_complete` don't clear list on disconnect
**File**: `src/lib/ws.ts:81-86`, `src/lib/paramStore.svelte.ts`

If the user disconnects then reconnects to a different vehicle, stale params remain. `clearParams()` exists but is not called automatically. ⏳ — Should be called on `event_type: 'connected'`.

### 🟢 F-52: `ws.ts` — single-vehicle assumption
The state model maps 1:1 to a single drone. Multi-vehicle MAVLink streams update `app.drone.vehicles[]` but `app.drone` is always the primary. ✅

---

## 7. Type safety

### 🟢 F-53: `ws.ts:onmessage` — `JSON.parse` result cast to `WSMessage`, switch is exhaustive but the `default` case is silent
**File**: `src/lib/ws.ts:39-115`

If the backend adds a new `type`, the switch silently ignores it. 🟢 — Acceptable.

### 🟡 F-54: `types.ts:DroneState.vehicles[].vtype` — optional `number`, but `MultiVehiclePanel` and others read it as if always set
**File**: `src/lib/types.ts:59`

```ts
vehicles: { sysid: number; lat: number; lon: number; alt: number; hdg: number; armed?: boolean; mode?: number; vtype?: number }[];
```

Usage in `MultiVehiclePanel.svelte:79` reads `v.lat.toFixed(6)`, which is non-optional. Fine. But `v.mode` typed optional and `modeName(id: number | undefined)` handles `undefined`. ✅

### 🟢 F-55: `gamepad.svelte.ts:onConnect` reads `e.gamepad.index` — BigInt risk?
**File**: `src/lib/gamepad.svelte.ts:62-66`

Gamepad index is always a small int. ✅

### 🔴 F-56: `inspectorStore.svelte.ts` — `consoleLines.length` mutation directly via `.length = 0`
**File**: `src/components/tools/ConsolePanel.svelte:59`

```ts
function clearConsole() {
  inspectorState.consoleLines.length = 0;
}
```

In Svelte 5, setting `.length = 0` on a `$state` array proxy is supported and triggers reactivity. ✅ Works.

### 🔴 F-57: `LogStore.completeDownload` — could overflow when `maxEnd` is very large
**File**: `src/lib/logStore.svelte.ts:90-100`

```ts
let maxEnd = size;
for (const c of logState._chunks) {
  const e = c.ofs + c.bytes.length;
  if (e > maxEnd) maxEnd = e;
}
bytes = new Uint8Array(maxEnd);
```

For a 2 GB log this allocates 2 GB. Browser will throw `RangeError` or hang. 🟢 — Practical limit on log size is much smaller.

---

## 8. App.svelte / view loading

### 🔴 F-58: `App.svelte` — `$effect(() => { if (view === 'monitor' && !MonitorMods) ... })` doesn't cancel the import if user navigates away
**File**: `src/App.svelte:65-77`

If user opens monitor view, then quickly switches to params before the imports resolve, the assignments to `MonitorMods` still happen but trigger reactivity for a no-longer-displayed view. No harm. ✅

### 🟡 F-59: `App.svelte:142-146` — `checkAlerts` is called from $effect every time drone state changes (probably 10 Hz)
**File**: `src/App.svelte:142-146`

`checkAlerts` does its own internal deduplication via module-level `prev*` variables. ✅ Works but pushes a lot of work through reactive runtime.

### 🟡 F-60: `App.svelte` — title-update effect reads many drone fields, runs on every state change
**File**: `src/App.svelte:162-176`

Effect reads `mode`, `armed`, `voltage`, `gps_fix`, `remaining`, `ekf_flags`, `link_age`. Each telemetry frame triggers this effect at ~10 Hz, which sets `document.title`. Title-bar updates are cheap but this is wasteful. 🟢 — Minor.

---

## 9. Other notes

### 🔴 F-61: `audio.ts` — `prevWp = armed ? wp : 0;` — when disarmed during a mission with wp=42, prevWp goes to 0, then on re-arm with wp=42 still > 1 it will trigger "waypoint 41 reached" repeatedly
**File**: `src/lib/audio.ts:108-113`

```ts
const wp = app.drone.wp;
if (wp > prevWp && prevWp >= 1 && armed) {
  speak(t('audio.waypoint').replace('{n}', String(prevWp - 1)));
}
prevWp = armed ? wp : 0;
```

When disarmed, `prevWp = 0`. On re-arm, `prevWp = wp` (let's say 42). Then if wp increments to 43, `prevWp` was 42 — speaks "wp 41". But on the first run after disarm, `prevWp == 0`, so the speak guard `prevWp >= 1` blocks it. Then `prevWp = armed ? wp : 0` → `prevWp = 42`. Next frame wp is still 42, no trigger. Next when wp goes to 43, triggers "wp 41". Hmm, that's correct behavior (announces previous wp completion). ✅ Actually fine.

### 🟡 F-62: `audio.ts:checkAltCallouts` uses module-level `altPrev`, `altInit`, `descentNext`, `ascentIdx` — never cleared on disconnect/reconnect, but `if (!armed)` resets them. ✅

### 🔴 F-63: `audio.ts` — `prevConnected` doesn't reset on speak; the disconnect beep won't replay on multi-disconnect within same session if `prevConnected` stays false
**File**: `src/lib/audio.ts:70-74`

```ts
if (!connected && prevConnected) {
  beep(200, 1000, 3, 200);
  speak(s('飞控连接已断开', 'Vehicle connection lost'));
}
prevConnected = connected;
```

`prevConnected` is set every call. So on each fresh disconnect (after reconnect), it fires correctly. ✅

---

## Summary (re-tallied based on actual bug status in body)

Real bugs only (entries where investigation confirmed a defect, excluding "✅ No bug" entries
in the body):

🔴 **Critical** (5):
- F-1 Compass3DPanel self-dirty effect (FIXED)
- F-11 WaypointLayer focus ring removed prematurely (FIXED)
- F-13 OfflineMapPanel coordinate overwrite (FIXED)
- F-24 MotorTestPanel leaks intervals + leaves backend motor running (FIXED)
- F-40 ConnectionForm bypasses event trim cap (FIXED)

🟡 **Medium** (12):
- F-2 App.svelte summaryShown write inside dep-reading effect
- F-4 MissionPanel terrainLoading flag race with multiple in-flight fetches
- F-8 ParamPanel tree expansion state lost on re-derive
- F-9 ParamPanel scroll resets during param fetch
- F-16 RcCalibPanel min/max self-write (FIXED)
- F-17 Param-init effects clobber edits mid-fetch (FrameSelect, FlightMode, Failsafe, Pid)
- F-18 FailsafeConfigPanel reads same param for enable+action
- F-22 MapView pending invalidateSize timeout (FIXED)
- F-23 WaypointLayer focusRing leak on early effect re-run
- F-32 Map3DView waypoint source race with style load
- F-33/F-34 Home marker not repositioned when home changes
- F-36 MissionPanel upload 3 s hard-timer instead of ack listener
- F-39 ConnectionForm serial vs WS state mutation conflict
- F-42 stores.svelte didn't persist mapMode/unitSystem (FIXED)

🟢 **Low** (~10): F-3, F-12, F-19, F-20 (FIXED), F-25, F-26, F-27, F-31, F-37, F-44, F-49, F-50,
F-51 (FIXED), F-54, F-57, F-59, F-60, F-63.

Many other "F-N" entries in this document conclude "✅ No bug" — they were
investigated and dismissed (e.g. `const d = app.drone` at module scope is a
valid Svelte 5 pattern, `untrack` already present in ChartPanel/VibrationPanel,
direct `.push`/`.splice` on `$state` arrays is supported, etc.). They are kept
in the doc for reference so future audits don't redo the same investigations.

## Fixes applied in place (10 total)

Each fix is <10 lines and clearly correct. All tests still pass
(`svelte-check`: 0 errors / 0 warnings; `vitest`: 415 / 415).

1. ✅ **F-1**: `src/components/map/Compass3DPanel.svelte` — wrap sample mutation in `untrack()`
2. ✅ **F-11**: `src/components/layers/WaypointLayer.svelte` — wrap `app.focusWp = -1` in `untrack()` so the focus ring stays visible the full 2 s
3. ✅ **F-13**: `src/components/map/OfflineMapPanel.svelte` — replace `$effect` with `onMount` snapshot so user-edited bounding box isn't clobbered by every telemetry frame
4. ✅ **F-16**: `src/components/setup/RcCalibPanel.svelte` — wrap min/max updates in `untrack()` to prevent self-re-trigger cascade
5. ✅ **F-22**: `src/components/core/MapView.svelte` — capture `invalidateSize` timeout id and clear on unmount
6. ✅ **F-24**: `src/components/setup/MotorTestPanel.svelte` — add `onDestroy(stopAll)` so closing the panel stops motors and clears intervals
7. ✅ **F-40**: `src/components/core/ConnectionForm.svelte` — use `addEvent()` (which trims to 200) instead of direct `app.events.push()`
8. ✅ **F-42**: `src/lib/stores.svelte.ts` — persist `mapMode` and `unitSystem` in `saveSettings`/`loadSettings`
9. ✅ **F-51**: `src/lib/ws.ts` — call `clearParams()` on `connected` event so a new vehicle starts with a clean param list
10. ✅ **F-20**: `src/components/params/ParamDiffPanel.svelte` — convert `currentMap` from function-returning `$derived` to `$derived.by` returning the Map directly (proper memoisation)

## Follow-up needed (not auto-fixed — require >10 lines or domain decisions)

- ⏳ **F-8**: ParamPanel tree expansion state needs separate `Map<string, boolean>` keyed by group name (the current `expanded: false` inside derived gets clobbered on every recompute)
- ⏳ **F-17**: Param-initialization effects (FrameSelect, FlightMode, Failsafe, Pid) need a "load once" guard so streaming param batches don't overwrite in-progress user edits
- ⏳ **F-18**: `FailsafeConfigPanel.svelte` reads `FS_BATT_ENABLE` for both enable and action — need review of ArduPilot semantics (the correct param is likely `FS_BATT_ACTION`)
- ⏳ **F-23**: `WaypointLayer.svelte` focus ring leak path for early effect re-run
- ⏳ **F-32, F-33, F-34**: Map3DView waypoint source race + DroneLayer home marker repositioning
- ⏳ **F-36**: MissionPanel upload should listen for `mission_ack_ok`/`mission_ack_fail` events instead of a 3 s hard timer
- ⏳ **F-39**: ConnectionForm dual-transport (serial + WS) state mutation conflict
