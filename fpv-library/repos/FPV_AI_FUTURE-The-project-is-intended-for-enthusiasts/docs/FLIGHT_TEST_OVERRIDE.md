# Flight test with manual backup — MSP_OVERRIDE toggle

Fly the interceptor **manually** on your normal transmitter, and let the **seeker system** take the
sticks only while **you hold a toggle switch**. Flip the toggle down (or lose the Pi) and Betaflight
instantly returns control to your receiver. This is the safe way to observe the real system in the
air, and it also removes the arming blocker — **arming stays on your receiver; the Pi never arms.**

```
toggle DOWN  ->  Betaflight uses the RECEIVER    ->  you fly            (safety layer, always there)
toggle UP    ->  Betaflight uses the Pi's MSP RC ->  the system flies   (masked axes only)
flip DOWN / Pi dies / MSP stream stops           ->  receiver again     (FC failsafe, not the Pi)
```

Two safety properties come from **Betaflight**, so they hold even if the Pi crashes: arming is on the
RX, and MSP-override times out to the RX if the stream stops. The Pi script (`fpv_ai/msp_override_flight.py`)
only computes channels, hard-caps throttle, and is default-DENY (no target / not engaged → neutral).

---

## 1. Betaflight setup (Configurator, **props OFF**)

Keep your **real receiver as the RX** — do **NOT** set MSP as the serialrx provider.

**CLI tab:**
```
feature MSP_OVERRIDE
set msp_override_channels_mask = 15      # bits 0..3 = roll,pitch,yaw,throttle. The toggle AUX is NOT masked.
save
```
- `15` = all four flight axes (your choice: full contour). For a first flight you may prefer `7`
  (roll+pitch+yaw, throttle stays yours) — then run the bridge with `--axes rpy`.

**Modes tab:**
- Add a range for **MSP OVERRIDE**, assign it to the AUX channel of your toggle, set the active band
  (e.g. 1600–2100). Apply the same threshold to the bridge with `--switch-threshold-us 1600`.

**Ports tab:** the UART you wired to the Pi must have **MSP** enabled (you already did this on UART2).
Match the baud on both sides.

---

## 2. Identify the toggle channel (props OFF)

On the Pi:
```
cd ~/seeker   # wherever the repo is
PYTHONPATH=.:fpv python3 -m fpv_ai.msp_override_flight scan --port /dev/ttyAMA0 --baud 115200
```
Flip the toggle and watch which index jumps ~1000↔~2000. That index is your `--switch-index`
(AUX1 is usually index 4). Also confirm the stick channels move as you expect.

---

## 3. Bring-up ladder — do these IN ORDER, props off until step 4

1. **Props OFF — verify handover.** Run `live` (below). In Configurator's Receiver tab, flip the
   toggle UP and confirm roll/pitch/yaw/throttle follow the Pi's values; flip DOWN and confirm they
   snap back to your sticks. Confirm instant manual reclaim.
2. **Props OFF — verify default-DENY.** With no target in the camera, toggle UP → the bridge holds
   **level + gentle throttle** (it does not command the flight axes off a lost target). Point the
   camera at a warm target → the guidance values appear.
3. **DRY in the air.** Fly manually, run `dry` (sends nothing), point the nose at a target, and watch
   the log / console for what the system **would** command. Sanity-check direction and magnitude.
4. **LIVE, tethered or low + ready to flip down.** Hover manually, flip UP for a second, observe,
   flip DOWN. Increase exposure gradually. **Keep your thumb on the toggle.**

**Set the throttle ceiling for YOUR aircraft** with `--throttle-max-us` (default 1700). This is the
runaway guard; your ultimate throttle safety is flipping the toggle down.

---

## 4. Running the bridge

```
# DRY — observe only, transmits NOTHING (do this in the air first):
PYTHONPATH=.:fpv python3 -m fpv_ai.msp_override_flight dry  \
    --port /dev/ttyAMA0 --baud 115200 --device /dev/video0 --up-camera \
    --switch-index 4 --log ~/seeker/logs/override_dry.csv

# LIVE — system flies the masked axes while the toggle is UP:
PYTHONPATH=.:fpv python3 -m fpv_ai.msp_override_flight live \
    --port /dev/ttyAMA0 --baud 115200 --device /dev/video0 --up-camera \
    --switch-index 4 --switch-threshold-us 1600 \
    --axes rpyt --throttle-max-us 1700 --lostlock-throttle-us 1450 \
    --log ~/seeker/logs/override_live.csv
```

### Camera geometry — `--up-camera`
This airframe's camera looks **straight up** (intercept from below). Pass `--up-camera` so the guidance
maps correctly: horizontal LOS-rate → **roll + pitch** (translate under the target), **throttle → climb**
into it, **yaw ≈ 0** (yawing a fixed up-camera only spins the pixel frame). Tune the closing climb with
`--climb-throttle` (default 0.62 = above hover). Without `--up-camera` the guidance uses the
forward-camera map (`elevation → throttle`, `pitch = forward march`) — **wrong for this aircraft.**
The gimbal "point-when-engaged / return-to-0-when-disengaged" behaviour is **not yet wired** — first
flights are effectively strapdown (camera fixed up).

Key flags: `--axes` (subset of `r p y t`), `--throttle-max-us` (hard cap), `--designate CX CY`
(acquire a target near a pixel; default = frame centre — point the nose at the target and engage),
`--hz` (RC stream rate, default 50), `--duration`.

The CSV logs every tick: `t, engaged, switch_us, state, locked, have_cmd, sent, roll/pitch/yaw/throttle`
— your post-flight record of exactly what the system saw and commanded.

---

## What this does NOT do

- It does not arm — you arm manually on the RX.
- It does not close the *fully autonomous* “launch-and-forget” loop — you are the engage authority via
  the toggle, and you hold manual backup. This is the honest first real-world step: observe the seeker
  driving the airframe, on live thermal, with a hardware manual override underneath.
- Gyro ego-compensation is **off** (needs S0 gyro-scale calibration); perception runs detection/track
  without ego de-rotation. Fine for observation; note it when reading terminal behaviour.
