# FPV RC Boat — Project Roadmap

**How to use this doc:** Each track below is written to be picked up independently — you don't need to finish Track A before starting Track C. Dependencies are called out explicitly where they exist (mostly hardware arrival, not code order). Hand any single track to Claude Code and it should have enough context to work without needing the others done first.

---

## Current State Snapshot (as of this doc)

**Hardware in hand and wired:** Raspberry Pi Zero 2 W (`FPV-boat` hostname), Arducam Camera Module 3 Wide (IMX708, CSI-connected), heatsink installed, 128GB microSD as boot/storage drive.

**Hardware in hand, not yet wired:** L298N dual H-bridge motor driver (BOJACK), DPDT failsafe switch (Nilight 6-pin ON/OFF/ON, waterproof boots), MP1584EN buck converters (3-pack), ShareGoo 8-LED kit (4 white front / 4 red rear), SG90 micro servos (4ct), PG7 cable glands, IP65 junction boxes, BrosTrend AC5L USB WiFi adapter (+ micro-USB OTG). **→ Track B (motor control) is fully unblocked.**

**Still needed:** PCA9685 16-ch PWM servo driver (for pan/tilt head-tracking — servos alone aren't enough), LiPo battery, INA219 (battery/current sensing). Water sensor **not** needed — will tap the boat's existing stock hull sensor.

**Software running today, confirmed working:**
- `webrtc_stream.py` — aiohttp server on the Pi, HTTPS (self-signed cert), serves:
  - `/offer` — WebRTC signaling endpoint, streams live camera video via `aiortc` + `picamera2`
  - `/record/start`, `/record/stop`, `/record/status` — H.264 recording to `~/recordings/`, runs simultaneously with the live stream
  - `/telemetry` — JSON with recording state + disk space
  - `/viewer` — serves the WebXR HTML page
  - `/three.module.js` — locally hosted Three.js (no CDN dependency)
  - `/ws/control` — websocket endpoint, receives `{throttle, steer, reverse}` JSON and drives `motor_control.py` (differential thrust). No-op until the L298N is wired, but the software path is complete.
- `webxr_viewer.html` — Three.js WebXR page:
  - Head-locked video plane + HUD plane (canvas-texture based), rendered in immersive VR
  - HUD shows: link quality (bars + ping), battery (placeholder, no sensor), recording status + storage bar, throttle/steer gauges
  - Gamepad polling via `navigator.getGamepads()` — **currently broken for buttons, see Track A**
  - Debug overlay drawn onto the HUD canvas itself (necessary since HTML overlays aren't visible inside an active VR session)
- `three.module.js` — vendored Three.js r0.160, served locally to avoid CDN dependency issues in the Quest browser
- ~~`stream.py`~~ — removed; the legacy MJPEG server was superseded by `webrtc_stream.py` (WebRTC confirmed working in-headset)

**~~Known active bug~~ (RESOLVED):** Gamepad button presses weren't registering via `navigator.getGamepads()` on the Quest. Fixed by reading `session.inputSources` directly (Track A). Controller input is now confirmed working in-headset. See the current mapping in `README.md` / `HARDWARE.md`.

**Repo:** `github.com/AlexSchrader/fpv-boat`, SSH-auth push access set up on the Pi. `.gitignore` in place excluding `.ssh/`, `.cache/`, `recordings/`, and other non-project files after an earlier incident where a private key was briefly staged (rotated afterward, not actually exposed). **Always `git add` explicit filenames on this repo, never `git add -A` or `git add .`, since the Pi's home directory contains far more than just the project.**

**Networking notes:** Pi's IP is DHCP-assigned and has changed at least once mid-project (was `10.0.0.20`, moved to `10.0.0.26`). If the viewer says "unreachable," check `hostname -I` on the Pi first before assuming a code problem. WiFi power management was disabled (`iwconfig wlan0 power off`) to fix intermittent SSH disconnects — this fix is only applied for the current boot; needs `/etc/rc.local` persistence confirmed if it hasn't been already.

---

## Track A — Fix Controller Input (WebXR inputSources) — ✅ DONE

> Completed: migrated to `session.inputSources`, mapped right stick → steer,
> left stick → throttle, A double-tap/tap → record start/stop, X → reverse
> toggle (B/Y/triggers reserved), streaming to `/ws/control`. Confirmed live in
> the headset. Note the final button scheme differs from the original text
> below (A was "record toggle", B was "reverse") — the mapping in `README.md`
> is canonical.

**Goal:** Get real throttle/steer/button data flowing reliably from the Quest controllers to the Pi.

**Independent of:** Everything else. This is pure browser JS work against the existing `webxr_viewer.html` and doesn't need motor hardware to test — you can verify it's working by watching values change at `/control_status` or on the HUD gauges.

**What's broken:** `navigator.getGamepads()` button arrays aren't returning presses in the Quest browser during an immersive session, even though axes (thumbstick position) appear to work.

**What to do:**
1. Replace `navigator.getGamepads()` polling with the WebXR-native approach: inside the `renderer.setAnimationLoop` callback, access `session.inputSources` (available via `renderer.xr.getSession()`), iterate each `XRInputSource`, and read `.gamepad.axes` / `.gamepad.buttons` from there instead. This is the spec-correct path and should be far more reliable than the generic Gamepad API during an XR session.
2. Use `inputSource.handedness` (`'left'` / `'right'`) instead of guessing from `gamepad.hand` or array index.
3. Keep the existing debug-overlay-on-HUD-canvas pattern for testing — HTML overlays aren't visible once inside VR, so any debug output must be drawn onto `hudCanvas` via `hctx`, not the DOM `#debug` div.
4. Once button events are confirmed working, re-wire: A → `/record/start`/`/record/stop` toggle, B → reverse mode toggle, X/Y → logged only (reserved for cruise control later, see Track H).
5. Verify end-to-end by checking `/control_status` on the Pi updates live while moving sticks/pressing buttons, before considering this done.

**Files touched:** `webxr_viewer.html` only.

---

## Track B — Motor Control (L298N + Differential Thrust)

**Goal:** Get the Pi actually driving the two boat motors via GPIO, using differential thrust (no rudder).

**Independent of:** Controller input fully working (can bench-test with hardcoded throttle/steer values first), video/HUD state.

**~~Blocked on~~ UNBLOCKED:** L298N and DPDT failsafe switch are both in hand. The differential-thrust driver + watchdog software (`motor_control.py`) is already written and bench-testable (`python3 motor_control.py`). Remaining work is hardware: wire the L298N per `HARDWARE.md`, bench-test with motors off the boat, then wire the DPDT failsafe before any water testing.

**Design already locked in:**
```
left_motor  = throttle + steer
right_motor = throttle - steer
# clamp each to -1.0 .. 1.0
```
- Throttle comes from an exponential curve on the trigger/stick input: `throttle = sign(x) * x**2` (already implemented client-side in the viewer for display; needs to be the actual value sent, or applied server-side — decide one place to own this transform, not both, to avoid double-curving).
- L298N gives two independent H-bridge channels — one per motor, each independently forward/reverse/PWM-speed capable.
- **Current L298N is rated ~2A per channel continuously.** Stock toy motors are fine. If you upgrade to bigger motors later (e.g. 380-size), you MUST also upgrade the driver (BTS7960 or dual DRV8871) — don't put a bigger motor on this driver.

**What to do:**
1. Wire L298N to Pi GPIO (standard 4-pin control: IN1-4 for direction, ENA/ENB for PWM speed — Pi Zero 2 W has hardware PWM on limited pins, check which GPIO you're using support it or use software PWM via a library like `RPi.GPIO` or `gpiozero`).
2. Write a small standalone Python module (e.g. `motor_control.py`) with a class exposing `set_drive(throttle: float, steer: float)` that does the differential thrust math and writes to GPIO. Keep this decoupled from the web server so it can be bench-tested independently with a simple script before wiring to the websocket.
3. Bench-test on a breadboard with the motors OFF the boat first — confirm direction, speed response, and that both channels are independent.
4. Wire the `/ws/control` handler in `webrtc_stream.py` (the `latest_control` dict already receives `{throttle, steer, reverse}`) to call into this new motor module on every message.
5. Add the software watchdog: if no control message received in ~500ms, force throttle to 0. This is critical since there's no radio fallback when the Pi is in control.
6. DPDT failsafe switch installation is a physical/wiring task, not code — do this before any water testing, not before bench testing.

**Files touched:** New `motor_control.py`, edits to `webrtc_stream.py`'s `control_ws` handler.

---

## Track C — Video Pipeline Quality & Performance

**Goal:** Improve video quality/smoothness without regressing the stability that's already been hard-won.

**Independent of:** Everything else — this is purely `webrtc_stream.py` + camera config.

**Current state:** 1280x720, software H.264 encoding via `aiortc`'s default `libx264` path (no Pi GPU hardware encoding wired up — an earlier attempt to patch `aiortc`'s codec module to use `h264_v4l2m2m` was written but never confirmed successful; worth verifying whether it's actually active). Occasional ASW/reprojection glitches in VR mode, believed tied to frame timing rather than a hard bug (largely resolved after removing a duplicate animation loop — see Track A history).

**What to try, roughly in order of effort:**
1. **Confirm/verify hardware encoding is actually active.** Check the `aiortc` `h264.py` codec file on the Pi for the `h264_v4l2m2m` patch and confirm no "falling back to libx264" warning appears in server logs when a client connects.
2. **Resolution/bitrate tuning** — 1280x720 is the known-good baseline. Any increase (tried 1080p30 earlier, caused visible degradation from CPU/encoder overload) should be tested incrementally, watching Pi CPU usage (`htop`) live while streaming, not just eyeballing the result.
3. ~~Consider exposing resolution/bitrate as environment variables~~ ✅ **DONE** — `RECORD_WIDTH/HEIGHT`, `STREAM_WIDTH/HEIGHT`, `RECORD_BITRATE` env vars. Stream default lowered to **960×540** to cut CPU heat (aiortc software-encodes the stream); recording stays 720p on the hardware encoder. See `README.md` → Tuning.

> Update from the code: item 1 is **answered** — the WebRTC path captures raw `lores` frames and lets **aiortc software-encode** them, so the stream is *not* hardware-encoded. True hardware WebRTC encoding would mean feeding the Pi's H.264 encoder output into aiortc (a real rework, not a config flag). Also added: **thermal auto-shutdown** (`CPU_OVERHEAT_C`, default 80 °C) and CPU temp/load + video-FPS on the HUD.

**Files touched:** `webrtc_stream.py`, possibly the installed `aiortc` package files directly (document any such patches clearly since they don't survive a `pip install --upgrade`).

---

## Track D — HUD: Real Battery Telemetry — ✅ SOFTWARE DONE (pending INA219)

> Shipped: `battery_control.py` reads an **INA219** (voltage + current over I2C)
> and estimates charge % from a LiPo curve (`percent_from_voltage()`, pure +
> unit-tested; `BATTERY_CELLS` sets the series count). `/telemetry` now carries
> `battery_voltage / current_ma / percent / cells / warn_pct`, and the HUD BAT
> column shows `BAT <V>` + a color-coded `<pct>%` (white / orange ≤warn / red
> ≤10%). Full no-op without the sensor (shows `--%`). **Remaining is hardware:**
> wire the INA219 per `HARDWARE.md` and `pip3 install pi-ina219`. Chose the
> INA219 over a bare voltage divider because it gives current too (feeds J.5).

**Original plan (for reference):**
1. Add a `/telemetry` field for `battery_voltage` and `battery_percent`.
2. Update `drawHud()` to render the real value instead of the ghosted placeholder.

---

## Track E — Recording Management — ✅ DONE

> Completed: `/record/start` calls `enforce_storage_limit()`, which deletes the
> oldest clips until `RECORDINGS_MIN_FREE_GB` (default 2, set 0 to disable) is
> free, never touching the active file. Added `GET /recordings` (name/size/
> timestamp, newest first) and `GET /recordings/download?file=NAME` (with a
> basename traversal guard). Time-based expiry could still be layered on later.

**Goal:** Prevent the SD card from silently filling up, and make old recordings easy to manage.

**Independent of:** Everything else. Recording itself already works.

**What to do:**
1. Add a simple cleanup policy — e.g. delete recordings older than N days, or cap total recordings folder size, triggered either on `/record/start` or via a cron job.
2. Consider adding a `/recordings` listing endpoint (filenames + sizes + timestamps) so a future UI could show/download/delete clips without SSHing in.
3. The storage bar on the HUD already shows free space live — no changes needed there unless the above listing endpoint gets a UI counterpart.

**Files touched:** `webrtc_stream.py`.

---

## Track F — Networking Reliability

**Goal:** Stop losing time to "unreachable" / SSH drops / changed IPs.

**Independent of:** Everything else.

**What to do:**
1. **Set a DHCP reservation** for the Pi's MAC address on your router (or a static IP directly on the Pi via `dhcpcd.conf`), so the IP stops changing between sessions. This alone would have saved real time earlier in the project.
2. **Confirm `iwconfig wlan0 power off` survives reboot** — check whether the earlier `/etc/rc.local` edit actually took effect (test with an actual reboot, not just trusting it was saved correctly).
3. Consider documenting the current IP/hostname prominently (e.g. in this repo's README) so it's not re-discovered via trial and error each session.

**Files touched:** Pi system config only (`/etc/dhcpcd.conf` or router admin panel, `/etc/rc.local`), no project code.

---

## Track G — Repo Hygiene

**Goal:** Keep the GitHub repo clean and safe going forward.

**Independent of:** Everything else. Already in a good state, this is about not regressing.

**Rules already established:**
- Always `git add <specific filenames>`, never `git add -A` / `git add .` in the Pi's home directory.
- `.gitignore` already excludes `.ssh/`, `.cache/`, `.config/`, `.local/`, `recordings/`, and other non-project files.
- SSH key auth is set up for pushing — no tokens/passwords needed.

**Possible follow-ups:**
1. Add a proper `README.md` to the repo summarizing the project (this roadmap doc could partially serve that purpose or be linked from it).
2. Consider moving `~/recordings/` off the Pi periodically (rsync/scp to a computer) rather than only relying on the `.gitignore` exclusion, since it's not backed up anywhere as-is.

**Files touched:** `.gitignore`, new `README.md`.

---

## Track H — Post-MVP / Future Work

**Goal:** Everything explicitly deferred until the core FPV + motor control loop is proven on water.

**Independent of:** All other tracks — these are intentionally last.

1. **Pan/tilt camera + head tracking** — ✅ **SOFTWARE DONE (pending PCA9685).** `pan_tilt_control.py` maps head yaw/pitch → servo angles via a PCA9685 (pure, unit-tested `head_to_servo()`, tilt clamped to a safe cone; no-op without `adafruit_servokit`). The viewer reads the XR head quaternion each frame, takes yaw/pitch relative to the VR-entry heading, and streams degrees over `/ws/control`; the server calls `pan_tilt.set_head()` and centers on link drop. `/telemetry` exposes `pan_angle`/`tilt_angle`. **Remaining is hardware:** wire the PCA9685 + 2 SG90s per `HARDWARE.md`, `pip3 install adafruit-circuitpython-servokit`, and mind the I2C 0x40 collision with the INA219.
2. ~~**Cruise control**~~ ✅ **DONE** — Y double-tap toggles throttle-hold (captures current throttle); while cruising, hold Y to speed up / hold X to slow down, steer stays live, reverse is locked out. A fresh trigger squeeze past ~50% disengages (safety). CRUISE badge on the throttle gauge (green when active). Client-side in `webxr_viewer.html`.
3. ~~**In-headset graceful shutdown**~~ ✅ **DONE (live).** Both grips + B open a confirm popup (right stick chooses Yes/No, A selects, defaults to No, auto-cancels after 5 s); the boat's drive is frozen while it's open. Confirming Yes calls `/system/shutdown`, which takes the shared `_safe_poweroff()` path (stop motors/lights, close recording, `sudo shutdown`) so a hard power cut can't corrupt the SD card, with the physical master switch as the true cutoff. The HUD shows a `SHUTTING DOWN…` overlay until the page dies with the Pi.
4. **Obstacle avoidance** — HC-SR04 ultrasonic sensor, auto-stop/steer-away logic.
5. **Motor/driver upgrade** — 380-size motor + BTS7960 or dual DRV8871 driver, only after the stock-motor + L298N version is proven reliable.
6. **Raspberry Pi AI Camera (IMX500)** — drop-in swap for the current camera module (same CSI mount), enables on-sensor AI inference without taxing the Pi's CPU.
7. **Native Android/OpenXR app** — a genuine platform migration away from the browser-based WebXR approach, mentioned as the right move specifically when AI features get added, since it opens up more direct hardware/performance access than a browser page can offer. Not a small task — treat as its own project phase, not a "track" alongside the others.
8. **Vision-based navigation / follow-me mode** — depends on #6 above being done first.

---

## Track I — Lights, Sensors, Spectator Page, Tests

**Goal:** A batch of independent, additive features — none of these block each other or anything already built. Pick any one and go.

### I.1 — Running Lights — ✅ DONE (v1, simpler scheme)

> Shipped: `lights_control.py` (`LightController.on()/off()/toggle()`, no-op
> without gpiozero) switches both LED groups **together**, auto-triggered by
> recording (on at `/record/start`, off at `/record/stop` + thermal shutdown)
> **and manually via single-tap Y** (`/lights/toggle`). A separate
> reverse-linked rear channel (`lights.reverse()`, GPIO22) is wired into the
> control websocket so rear "backup" lights auto-on in reverse — **pin claimed,
> LEDs pending install**. Pins in `HARDWARE.md`. Still unimplemented from the
> original plan below: the B-hold **strobe** mode.

**Original plan — Running Lights (dual-group, reverse-linked):**

**Hardware:** ShareGoo 8-LED kit (4 white "headlight" LEDs, 4 red "taillight" LEDs, individual leads, resistors pre-wired into the kit). Wire as **two independently switched groups**, not one:
- White group → one logic-level MOSFET (e.g. IRLZ44N) or small relay, gate/coil driven by a GPIO output pin. Power comes from the LiPo/buck-converter rail, not directly from the GPIO pin.
- Red group → a second MOSFET/relay on its own GPIO pin.

**Control mapping:**
- **B tap** (currently unused) → toggle white front lights on/off
- **B hold (~0.5s)** → cycle white lights: steady → strobe → off
- **Red rear lights are NOT manually controlled** — wire their GPIO output to mirror the existing `reverse` boolean already tracked in the control state. They light up automatically whenever reverse is toggled, functioning like real reverse/brake lights. No new input needed for this half.

**Software:** New `lights_control.py`, mirroring the structure of `motor_control.py` — a small class/module exposing `set_front(mode)` and `set_rear(bool)`, called from the same place `webrtc_stream.py` already handles `/ws/control` messages (rear from `reverse`, front from a new field the viewer sends on B press).

**HUD:** Add a small `LIGHTS` badge next to the existing `REC`/`REV` badges showing front-light state (off / steady / strobe). Rear lights don't need a badge since they're just a mirror of the existing REV badge.

### I.2 — Water-Sensor-Aware Auto-Record

**Goal:** Recording starts on throttle, stops on **either** idle timeout **or** the boat coming out of the water — whichever happens first.

**Hardware:** A basic digital immersion/water sensor module (~$2-3, three pins: VCC, GND, digital OUT — reads HIGH/LOW based on whether its exposed contacts are wet). Wire OUT to a spare GPIO input pin.

**Software:**
1. Poll the sensor GPIO alongside the existing telemetry loop.
2. Debounce it — require a couple continuous seconds of "dry" reading before treating it as "out of water," so a wave or splash doesn't falsely trigger a stop.
3. Auto-stop logic becomes: stop recording if `(idle_seconds > IDLE_TIMEOUT) OR (dry_seconds > DRY_TIMEOUT)`.
4. Expose the raw sensor state on `/telemetry` too (`in_water: bool`) — useful for debugging and could eventually feed a HUD indicator.

**Files touched:** `webrtc_stream.py` (new sensor poll + auto-record logic).

### I.3 — Real Battery Telemetry via INA219 — ✅ SOFTWARE DONE (pending sensor)

> Same work as Track D above — see there. `battery_control.py` reads the INA219
> (voltage + `current_ma`), estimates SoC from a proper LiPo curve (not a naive
> linear map), and drives the HUD BAT column + LOW BATTERY / BATTERY CRITICAL
> alerts. `pip3 install pi-ina219` + wire per `HARDWARE.md` to light it up. The
> `current_ma` field also gives J.5 (motor current) for free once wired.

### I.4 — Heading via QMC5883L Magnetometer

**Goal:** A real compass heading, since it pairs naturally with the speed/heading placeholders already sketched into the original HUD mockup.

**Hardware:** Search **"GY-271 QMC5883L compass module"** — commonly ~$6-9, I2C interface, can share the Pi's I2C bus alongside the INA219 (different I2C addresses, no conflict).

**Software:**
1. Add `heading_deg` to `/telemetry`.
2. HUD: small compass readout or rotating needle graphic — this is a good candidate to finally light up the "HEADING — planned" ghost placeholder that's been sitting dimmed in the HUD since the original mockup.

**Files touched:** `webrtc_stream.py`, `webxr_viewer.html`.

### I.5 — Spectator Page — ✅ DONE (v1)

> Shipped: `watch.html` served at `/watch` — a self-contained flat page with the same WebRTC video connection and a clean telemetry overlay (ARMED/FAILSAFE, ping/fps, CPU temp, REC, storage). Built standalone (DOM overlay, no changes to `webxr_viewer.html`) to stay safe without a headset to re-test the VR viewer. **Future:** factor the canvas HUD-draw code into a shared module both pages import, for a pixel-identical HUD — deferred until it can be headset-tested.

**Goal:** Let a friend watch the live feed + HUD from a phone browser without needing the Quest-cast workflow.

**What to do:**
1. New route `/watch` serving a stripped-down variant of the viewer: same WebRTC video connection and HUD canvas drawing logic as `webxr_viewer.html`, but with the WebXR session code (`Enter VR` button, `inputSources` polling, head-lock plane logic) removed — just a flat 2D page showing the video + HUD.
2. Reuse as much of the existing HUD-drawing code as reasonably possible rather than duplicating it — consider whether the HUD draw function could be factored into a shared JS file both pages import, instead of copy-pasting it into a second HTML file.

**Files touched:** New `watch.html` (or similar), new route in `webrtc_stream.py`, possible refactor of shared HUD code out of `webxr_viewer.html`.

### I.6 — Unit Tests for Motor Math — ✅ DONE

> Shipped: `test_motor_control.py` (differential-thrust mix + clamp edge cases,
> armed-state transitions, watchdog trip) and `test_lights_control.py`
> (running-lights on/off/toggle, the reverse channel's idempotency + truthiness
> coercion, channel independence, pin-collision guards) — 26 tests total, run in
> CI via `python -m unittest discover -p 'test_*.py'`. Both suites exercise the
> software (no-GPIO) path, so they need no Pi-only deps. **Not covered:** the
> exponential throttle curve (there isn't one — the trigger maps linearly) and
> anything living in `webrtc_stream.py` (it imports picamera2/aiortc, so it isn't
> importable in CI); the deterministic pieces there are already factored into the
> two testable modules.

**Original plan:**
1. Test the differential-thrust calculation directly: `left = throttle + steer`, `right = throttle - steer`, both clamped to `[-1, 1]`. Cover edge cases — full throttle + full steer (should clamp), zero throttle with steer (pivot turn), negative throttle (reverse).
2. Test the exponential throttle curve function in isolation.
3. Wire into the existing CI workflow (`.github/workflows/ci.yml`) so these run on every push/PR alongside the current syntax checks.

---

## Track J — Additional HUD Telemetry

**Goal:** Surface data that's already being collected (or nearly free to collect) but isn't shown on the HUD yet, plus a couple of genuinely important safety-visibility additions.

**Independent of:** Everything else — these are additive HUD elements, and several depend only on data the server already has.

### J.1 — CPU Temperature Readout — ✅ DONE

> Shipped: `/telemetry` exposes `cpu_temp_c` / `cpu_load` / `cpu_load_frac`, and the HUD shows a color-coded CPU readout (white / yellow ≥70 °C / red ≥80 °C) plus a load bar, next to the auto-shutdown at `CPU_OVERHEAT_C`. Original intent below.

The server already tracks CPU temp for the auto-shutdown safety feature (`CPU_OVERHEAT_C` env var), but it's never surfaced to the pilot. Add it to `/telemetry` (`cpu_temp_c`) and render a small readout on the HUD — ideally the number turns amber/red as it approaches the shutdown threshold, so an unexpected shutdown mid-run doesn't come as a total surprise.

**Files touched:** `webrtc_stream.py` (`/telemetry`), `webxr_viewer.html` (`drawHud`).

### J.2 — Low-Storage Warning Badge — ✅ DONE

> Shipped: `/telemetry` exposes `recordings_min_free_gb`; the HUD flashes an amber **LOW STORAGE** badge below the top card once free space drops below that auto-cleanup floor.

Storage-remaining is already shown as a bar. Add a flashing/highlighted "LOW STORAGE" badge that appears once free space crosses the same threshold that triggers auto-cleanup, so the pilot gets a heads-up rather than just watching a bar quietly shrink.

**Files touched:** `webxr_viewer.html` (`drawHud`).

### J.3 — Low-Battery Visual Alert — ✅ DONE

> Shipped: below the top card the HUD flashes an amber **LOW BATTERY** badge once
> charge drops to `battery_warn_pct` (default 25%, env `BATTERY_WARN_PCT`) and a
> red **BATTERY CRITICAL** at ≤10%; the BAT % readout also recolors white →
> orange → red. Badges stack with LOW STORAGE when both are live. Goes live with
> the INA219 (Track D/I.3); reads null and stays hidden without it.

### J.4 — In-Water / Beached Badge

Since the stock hull water sensor is already being tapped for auto-record (Track I.2), showing its live state on the HUD is nearly free — a small "IN WATER" / "BEACHED" badge doubles as a sanity check independent of the auto-record logic itself.

**Files touched:** `webrtc_stream.py` (`/telemetry` already gains `in_water` from I.2), `webxr_viewer.html` (`drawHud`).

### J.5 — Motor Current Draw

Once the INA219 is wired in (Track I.3) it reports current draw in addition to voltage. Show this separately from battery % — a live spike in current draw is an early warning for a fouled prop, something jammed, or the boat running aground, independent of how much charge is left.

**Files touched:** `webrtc_stream.py` (`/telemetry`), `webxr_viewer.html` (`drawHud`), depends on Track I.3.

### J.6 — Lights Status Badge

Once Track I.1 (lights) exists, show current front-light mode (off/steady/strobe) on the HUD in the same visual style as the existing REC/REV badges, for consistency.

**Files touched:** `webxr_viewer.html` (`drawHud`), depends on Track I.1.

### J.7 — Speed & Distance-from-Launch (once GPS exists)

Once the GPS module is wired in (see the M10-25Q module covering both compass and GPS), two more HUD elements become meaningful:
- **Speed over ground** — finally lights up the "SPEED — planned" ghost placeholder that's been dimmed in the HUD since the original mockup.
- **Distance from launch point** — compute from the GPS fix at recording-start vs. current position. Pairs naturally with the link-quality bars: together they answer "how worried should I be right now" at range.

**Files touched:** `webrtc_stream.py` (`/telemetry`), `webxr_viewer.html` (`drawHud`), depends on GPS wiring (UART, separate from the I2C compass half of the same module).

### J.8 — ARMED / FAILSAFE Watchdog Indicator (priority — safety-relevant) — ✅ DONE

> Shipped: `motor_control.py` tracks an `armed` flag (True on `set_drive`, False when the watchdog trips or on `stop()`), exposed via `/telemetry` (`armed`). The HUD shows a prominent top-center **ARMED** (cyan, steady) / **FAILSAFE** (red, flashing) pill. Covered by unit tests.

**This is the one to prioritize over the rest of this track.** Right now the HUD shows link quality (ping/bars), but there's a meaningful difference between "signal's a little slow" and "the watchdog is about to zero the throttle from lost connection" — and that distinction isn't visible at a glance.

Add a clear, hard-to-miss state indicator:
- **ARMED** (green/cyan, steady) — control messages arriving normally, motors responsive.
- **FAILSAFE** (red, flashing) — no control message received within the watchdog window (~500ms, per the existing motor_control watchdog), throttle has been forced to zero.

This should be driven by the same watchdog state already implemented in `motor_control.py` for Track B — expose it via `/telemetry` (`armed: bool`) rather than inferring it client-side from ping alone, since the actual watchdog trip is a server-side fact, not something the browser should guess at.

**Files touched:** `motor_control.py` / `webrtc_stream.py` (expose watchdog state), `webxr_viewer.html` (prominent HUD indicator — this one should be sized/positioned to be genuinely hard to miss, not tucked into a corner like the other badges).

### J.9 — Control Latency (priority — splits two problems apart) — ✅ DONE

> Shipped: the viewer stamps each `/ws/control` message with `ts`; the server echoes `{ack: ts}`; the client computes a smoothed round-trip and shows `ctl <n>ms` (color-coded) in the HUD LINK cell — separate from video ping. Viewer-only (spectators don't drive).

Right now the HUD shows general ping, but that doesn't distinguish between two genuinely different problems: the video feed lagging vs. the actual control loop lagging. Add a specific measurement of round-trip time from "trigger/steer input sent" to "motor command acknowledged" on the server, separate from whatever ping/link-quality number is already shown.

**Why this one's worth prioritizing:** if the boat ever feels sluggish or unresponsive, this is the number that tells you whether it's a WiFi problem, a video decode problem, or the boat's own control loop — three very different things to debug, currently indistinguishable from the HUD alone.

**Files touched:** `webxr_viewer.html` (timestamp control messages, measure round trip), `webrtc_stream.py` (`/ws/control` echo timestamp back). *(Software-only — doable now.)*

### J.10 — WiFi Signal Strength (RSSI) — ✅ DONE

> Shipped: `/telemetry` exposes `wifi_rssi_dbm` (from `/proc/net/wireless`); shown on the VR HUD (LINK cell, color-coded) and the `/watch` page.

Free — the Pi's network stack already exposes actual signal strength in dB. Show this as a precise number alongside (or instead of) the abstracted link-quality bars already on the HUD.

**Files touched:** `webrtc_stream.py` (`/telemetry`, read RSSI via `iwconfig` or `/proc/net/wireless`), `webxr_viewer.html` (`drawHud`). *(Software-only — doable now.)*

### J.11 — Session / Recording Elapsed Time — ✅ DONE

> Shipped: `/telemetry` exposes `rec_elapsed_s`; the REC readout shows `ON AIR m:ss` on the HUD and `/watch`.

A simple running clock since recording started. Standard on any camera HUD, trivial to add since recording start time is already tracked server-side.

**Files touched:** `webrtc_stream.py` (`/telemetry`), `webxr_viewer.html` (`drawHud`). *(Software-only — doable now.)*

### J.12 — CPU Load % — ✅ mostly DONE

> `/telemetry` already exposes `cpu_load` / `cpu_load_frac` and the HUD shows a CPU **load bar** next to the temp (cyan→orange→red). Remaining nicety: a numeric `%` readout if wanted.

Separate from CPU temperature (J.1) — a load spike here would explain a stutter in the stream or delayed control response in a way temperature alone doesn't capture.

**Files touched:** `webrtc_stream.py` (`/telemetry`, read via `psutil` or `/proc/loadavg`), `webxr_viewer.html` (`drawHud`).

### J.13 — Free RAM (diagnostic, low priority) — ✅ DONE

> Shipped: `/telemetry` exposes `mem_free_mb` (from `/proc/meminfo`); shown on the `/watch` page.

Mostly useful for debugging a crash after the fact rather than something the pilot needs mid-flight, but trivial to add alongside CPU load if already touching that code.

**Files touched:** `webrtc_stream.py` (`/telemetry`), `webxr_viewer.html` (`drawHud`). *(Software-only — doable now.)*

### Noted for later — Gyro / IMU (not free, requires a purchase)

A gyro/IMU (e.g. MPU6050, ~$3-5) would enable a genuinely useful boat orientation/tilt indicator — detecting a capsize or a bad-angle wave hit — but unlike everything else in this track, it requires buying a small sensor rather than just software. Not blocking anything; worth keeping on the radar for a future hardware order rather than treating as a free HUD addition.

---

## Quick Reference — File Map

| File | Purpose | Status |
|---|---|---|
| `webrtc_stream.py` | Main server: WebRTC video, recording, telemetry, control websocket, optional HTTPS | Active, working |
| `webxr_viewer.html` | Client: Three.js WebXR viewer + HUD + controller input | Active, working |
| `README.md` | Project overview, setup, controls | Active |
| `HARDWARE.md` | L298N wiring, power, watchdog, pin map | Active |
| `.github/workflows/ci.yml` | CI: byte-compile Python + JS syntax check | Active |
| `three.module.js` | Vendored Three.js | Static, no changes expected |
| `NETWORKING.md` | Stable-IP + WiFi power-save notes | Active |
| `motor_control.py` | Motor GPIO driver (L298N differential thrust + watchdog) | Created; awaiting L298N hardware to go live |
| `.gitignore` | Repo hygiene | In place |
