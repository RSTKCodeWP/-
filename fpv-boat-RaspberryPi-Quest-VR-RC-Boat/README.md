# FPV RC Boat

An FPV RC boat you pilot from a Meta Quest headset: a Raspberry Pi Zero 2 W
streams live camera video over WebRTC into a head-locked WebXR viewer with a
telemetry HUD, records H.264 to the Pi while streaming, and takes throttle/steer
input from the Quest controllers over a websocket to drive the motors.

## Features

- **Live FPV video** — WebRTC (`aiortc` + `picamera2`), 1280×720, head-locked
  video plane rendered in immersive VR.
- **Telemetry HUD** — link quality + ping, recording status, storage, battery
  (voltage + charge %, via an INA219), and live throttle/steer gauges (with a
  REV badge and L/R steer markers).
- **Simultaneous recording** — H.264 to `~/recordings/`, runs alongside the
  live stream; start/stop from the controller.
- **Controller input** — Quest controllers read via WebXR `inputSources`;
  steer/throttle/record/reverse mapped as below.
- **Differential-thrust motor control** — `motor_control.py` drives an L298N
  H-bridge (software-only no-op until the driver is wired). See `HARDWARE.md`.

## Controls

Full Quest controller mapping (read via WebXR `inputSources` in the immersive
session):

- **Left trigger** — throttle (squeeze to go; 0 → full)
- **Right thumbstick (X axis)** — steer
- **A — double-tap** — start recording
- **A — single-tap** — stop recording
- **X — double-tap** — toggle cruise (holds the current throttle)
- **X — hold (while cruising)** — slow the cruise set-speed down
- **Y — single-tap** — toggle running lights (manual; also auto-on with recording)
- **Y — double-tap** — toggle reverse (inverts throttle direction)
- **Y — hold (while cruising)** — speed the cruise set-speed up
- **Both grips** — recenter head-tracking: the camera holds its current aim and that becomes "straight ahead" (aim it level first, then squeeze)
- **Both grips + B** — open the graceful-shutdown confirm popup
- **Shutdown popup: right stick ← / →** — move highlight between Yes / No
- **Shutdown popup: A** — select the highlighted option
- **Right trigger, left thumbstick** — reserved / unused

**Head-tracking:** the on-boat camera follows where you look — the viewer streams
your headset's yaw/pitch to the Pi, which aims two servos (pan/tilt) via a
PCA9685. **Squeeze both grips to recenter:** the camera *holds its current aim*
and that becomes the new straight-ahead (a "CAMERA CENTERED" flash confirms). So
to level a camera whose mount sits off-center, just tilt your head until the feed
is level, then squeeze both grips — no angle config needed. See `HARDWARE.md`.

Rear **reverse ("backup") lights** — future install — come on automatically
whenever reverse is engaged; the server drives them off the reverse flag, so
they have no button of their own.

**Cruise:** double-tap X to lock the current throttle; while cruising, hold Y to
speed up and hold X to slow down (reverse is locked out). Squeezing the trigger
past ~50% instantly disengages cruise.

A **headlight telltale** (the car-style lamp-with-rays symbol) sits inside the
top of the throttle gauge — blue when the running lights are on, dimmed when
off — so you can tell at a glance whether the lights are lit.

**Graceful shutdown:** hold both grips + B to open a confirm popup (defaults to
**No**); the right stick moves the highlight, A selects, and it auto-cancels
after 5 s of no input. Confirming **Yes** calls `/system/shutdown`, which stops
the motors/lights, closes any recording cleanly, and powers the Pi down so a
hard power cut can't corrupt the SD card — the HUD shows a **SHUTTING DOWN…**
overlay until the page dies with the Pi. The physical master switch stays the
true cutoff, flipped only after this completes.

Steering is **differential thrust** (no rudder): `left = throttle + steer`,
`right = throttle - steer`.

## Fresh Pi setup / recovery

On a newly-imaged Pi (or after an SD reflash), clone the repo and run the
provisioning script — it enables I2C, installs all the system + Python deps,
generates the TLS cert, and adds the passwordless-shutdown sudoers rule:

```sh
git clone https://github.com/AlexSchrader/fpv-boat.git ~/fpv-boat && cd ~/fpv-boat
bash setup.sh
```

`setup.sh` is idempotent (safe to re-run). Python deps are also in
`requirements.txt` (`pip3 install --break-system-packages -r requirements.txt`);
note **picamera2 comes from apt** (`python3-picamera2`), not pip. On Bookworm
gpiozero uses the **lgpio** pin factory by default — `pigpio` is no longer
packaged and isn't needed.

## Running (on the Pi)

```sh
# WebXR needs HTTPS — generate a self-signed cert once (VR won't start over plain HTTP)
# (setup.sh already does this; run it manually only if you skipped setup)
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout ~/key.pem -out ~/cert.pem -subj "/CN=fpv-boat"

python3 webrtc_stream.py          # serves HTTPS on :5000 when the cert is present
```

Then in the Quest browser open **`https://<pi-ip>:5000/viewer`**, accept the
self-signed cert warning, and hit **Enter VR**. (Pi is `FPV-boat`, currently
`10.0.0.26` — see `NETWORKING.md` for keeping the IP stable and avoiding SSH
drops.)

Just run `python3 webrtc_stream.py` — on Bookworm gpiozero uses the **lgpio**
pin factory automatically, which is fine for the motor/lights PWM. (Don't set
`GPIOZERO_PIN_FACTORY=pigpio`: `pigpio` isn't packaged on Bookworm, and forcing
it makes gpiozero fail to init and silently drop motors/lights into no-op.)

The server runs streaming + recording even without the GPIO libs — it just logs
`hardware disabled` and skips motor output.

## Tuning (env vars)

Set these before launching `webrtc_stream.py` — defaults keep current behavior:

| Var | Default | Purpose |
| --- | ------- | ------- |
| `RECORD_WIDTH` / `RECORD_HEIGHT` | `1280` / `720` | Recorded (main) resolution — hardware-encoded |
| `STREAM_WIDTH` / `STREAM_HEIGHT` | `960` / `540` | Streamed (lores) resolution — must be ≤ record size |
| `RECORD_BITRATE` | `0` (encoder default) | H.264 record bitrate, bits/sec |
| `CPU_OVERHEAT_C` | `80` | CPU temp that triggers auto-shutdown |
| `RECORDINGS_MIN_FREE_GB` | `2.0` | Free-space floor before auto-deleting oldest clips (`0` disables) |
| `BATTERY_CELLS` | `2` | LiPo cell count in series (sets the voltage→% curve) |
| `BATTERY_SHUNT_OHMS` | `0.1` | INA219 shunt resistance |
| `BATTERY_MAX_AMPS` | _(auto)_ | Expected max current (tunes INA219 gain) |
| `BATTERY_WARN_PCT` | `25` | Charge % at which the HUD flashes LOW BATTERY (≤10% = CRITICAL) |
| `BATTERY_I2C_ADDR` | `0x40` | INA219 I2C address (move it if it collides with the PCA9685) |
| `PAN_CHANNEL` / `TILT_CHANNEL` | `0` / `1` | PCA9685 channels for the pan / tilt servos |
| `PAN_RANGE_DEG` / `TILT_RANGE_DEG` | `90` / `45` | Head degrees that map to full servo travel |
| `PAN_SIGN` / `TILT_SIGN` | `1` / `1` | Set to `-1` to flip a servo that tracks backwards |
| `PAN_CENTER` / `TILT_CENTER` | `90` / `90` | Neutral servo angle = camera straight/level (raise/lower to level a mount that sits off-center) |
| `PAN_TILT_I2C_ADDR` | `0x40` | PCA9685 I2C address (default collides with the INA219 — move one) |

The **stream (lores) is software-encoded by aiortc**, so its resolution is the
main driver of CPU load/heat — the default is 960×540 to keep temps down.
Recording (main) stays 720p because it uses the hardware encoder. Bump the
stream while watching `htop` / the HUD CPU temp:

```sh
STREAM_WIDTH=1280 STREAM_HEIGHT=720 python3 webrtc_stream.py   # sharper, hotter
```

## Endpoints

| Route              | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| `/viewer`          | WebXR viewer page                                  |
| `/clips`           | Recordings manager page (list / download / delete) |
| `/watch`           | Flat spectator page — live feed + telemetry (no VR) |
| `/offer`           | WebRTC signaling (POST)                            |
| `/ws/control`      | Websocket: `{throttle, steer, reverse}` → motors   |
| `/control_status`  | Last received control values (JSON)                |
| `/lights/toggle`   | Toggle the running lights (manual; single-tap Y)   |
| `/system/shutdown` | Graceful power-off (stops motors/lights/recording, then `sudo shutdown`) |
| `/record/start` `/record/stop` | Recording control (start auto-frees space) |
| `/telemetry`       | Recording, storage, CPU temp/load, armed state (JSON) |
| `/recordings`      | List clips — name, size, timestamp (JSON)          |
| `/recordings/download?file=NAME` | Download a clip over HTTP             |
| `/recordings/delete?file=NAME`   | Delete a clip (not the active one)   |
| `/three.module.js` | Vendored Three.js                                  |

## Files

| File | Purpose |
| ---- | ------- |
| `webrtc_stream.py` | Main server: WebRTC video, recording, telemetry, control websocket, optional HTTPS |
| `motor_control.py` | L298N differential-thrust driver with a 0.5 s safety watchdog (bench-test: `python3 motor_control.py`) |
| `lights_control.py` | Front/rear LED lights, GPIO-switched, auto-on with recording (bench-test: `python3 lights_control.py`) |
| `battery_control.py` | LiPo telemetry via INA219 (voltage/current/charge %); no-op without the sensor (bench-test: `python3 battery_control.py`) |
| `pan_tilt_control.py` | Camera pan/tilt head-tracking via PCA9685 + 2 servos; no-op without the board (bench-test: `python3 pan_tilt_control.py`) |
| `webxr_viewer.html` | Three.js WebXR viewer + HUD + controller input |
| `clips.html` | Recordings manager page (served at `/clips`) |
| `watch.html` | Flat spectator page — video + telemetry (served at `/watch`) |
| `three.module.js` | Vendored Three.js (served locally, no CDN) |
| `HARDWARE.md` | Wiring, power safety, pin map, watchdog notes |
| `NETWORKING.md` | Keeping the Pi's IP stable + WiFi power-save fix |
| `ROADMAP.md` | Project tracks and current-state snapshot |

## Bench-testing the motors

With the motors **off** the boat and the L298N wired per `HARDWARE.md`:

```sh
python3 motor_control.py    # ramps ahead, spins each way, then astern
```

## Development

CI (`.github/workflows/ci.yml`) byte-compiles the Python (syntax only — no
Pi-only deps needed) and syntax-checks the viewer's ES module on every PR and
push to `main`.

**Repo hygiene:** on the Pi, the project shares the home directory, so always
`git add <specific files>` — never `git add -A` / `git add .`.

See `ROADMAP.md` for planned work (battery telemetry, recording management,
pan/tilt head-tracking, cruise control, and more).
