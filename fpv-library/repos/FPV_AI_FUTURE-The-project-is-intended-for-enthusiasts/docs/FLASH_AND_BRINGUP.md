<!-- The single runbook that takes the chosen configuration from code to a first bench/flight. -->

# Block-3 — flash & bring-up runbook (FT640 on our gimbal, up-camera)

This is the ordered procedure to bring the **chosen configuration** to first power and first flight. Owner
decisions locked in (2026-07-19):

| decision | choice |
|---|---|
| seeker + stabilisation | **FT640 on our 2-axis gimbal** (`fpv/gimbal/` + full pipeline) — the 10/10 sim config |
| engagement geometry | **intercept from below, camera up** (up-camera command mapping) |
| flight controller | re-flash SpeedyBee F405 V4 with the interceptor CLI config |
| kill path | **independent RP2040/Pico kill-MCU + Betaflight failsafe** (two domains) |

**Props stay OFF until the V&V gate (`firmware/V_AND_V.md`) passes.** Every step below is bench work first.

---

## What the code side already provides (done, tested)

| piece | module | what it is |
|---|---|---|
| flight brain | `fpv_ai/flight_head.py` `GimbalFlightHead` | FT640→pipeline(up-camera, **full-ego forced ON**)→guidance + gimbal-tracks-centroid. Contract-tested. |
| flight loop | `fpv_ai/flight_gimbal.py` `FlightGimbalController` | routes guidance→FC (toggle-gated, throttle-capped) + setpoints→servos. Routing tested. |
| FC config | `firmware/betaflight-fork/INTERCEPTOR_CLI.md` | the CLI diff: MSP override + mask 15 + kill/failsafe + payload GPIO removed |
| kill-MCU | `firmware/hwkill-mcu/hwkill_mcu.ino` | default-deny gate, HW watchdog, now with a **stuck-clock detector** |
| Pi-5 I/O | `seeker_core/pi5_io.py` | FT640 grabber, I2C head IMU, PCA9685 servos, calibration |

The closed-loop performance evidence is `test_a_real_gimbal_closes_the_intercept` (10/10, CPA 1.23 m). It is a
sim; the point of this runbook is to move past sim.

---

## Step 1 — Flash the flight controller

1. Betaflight Configurator → CLI. Optionally back up first: `diff all` → save the text.
2. Paste the config from `firmware/betaflight-fork/INTERCEPTOR_CLI.md`, section by section. **Confirm the
   `[CONFIRM]` items against your transmitter's physical switches first** (the MSP-override toggle channel,
   and that the stray AUX3 ARM and AUX4 payload GPIO removals are what you want).
3. `save`. After reboot: `diff` → verify `aux 4 50 1 ...` (MSP_OVERRIDE) is present and
   `msp_override_channels_mask = 15`.
4. **Bench safety check, props OFF, battery in, on the RX only:** confirm ARM only arms from your AUX5 switch
   and that the Pi is not connected yet.

## Step 2 — Flash the independent kill-MCU

1. Open `firmware/hwkill-mcu/hwkill_mcu.ino` (target: RP2040/Pico). Set the pin defines for your wiring
   (`PIN_POWER_GATE`, `PIN_BEACON_RX/TX`, `PIN_RESET_LATCH`).
2. Flash. On boot the gate defaults to **CUT** — verify with a meter that motor power is OFF with no beacon.
3. Bench the safety contract (props OFF, motors on a current-limited supply or disconnected):
   - no beacon → power CUT;
   - stream a valid permit beacon → power enabled;
   - stop the beacon → power CUT within `BEACON_TIMEOUT_MS` (500 ms);
   - send a KILL frame → power CUT and **latched** (only the physical reset button clears it).
   See `firmware/hwkill-mcu/README.md` for the frame format.

## Step 3 — Wire and verify the head (props OFF)

Per `firmware/WIRING.md` (three independent domains: flight power / kill / radio — do not cross-power):
- FT640 → CVBS→USB grabber → Pi `/dev/video0`.
- Head IMU → Pi I2C.
- 2 gimbal servos → PCA9685 → Pi I2C. **Only the gimbal servos on this bus — never the motors.**
- FC → Pi USB (MSP over `/dev/ttyACM0`).

Calibrate the head IMU axes/signs and the servo rad→pulse mapping (`seeker_core/pi5_io.py` has the
calibration; `seeker_core/calibrate_gimbal.py` is the routine). Get this right — a wrong IMU sign makes the
gimbal drive the target OUT of frame, and a wrong servo sign does the same.

## Step 4 — Dry run on the Pi (props OFF)

```bash
# handover only: toggle -> override, no perception, no gimbal motion
python3 -m fpv_ai.msp_override_flight no-camera

# the full gimbal loop, LOGGING what it would command -- does NOT stream to the FC
python3 -m fpv_ai.flight_gimbal --dry
```

Watch for: the gimbal servos slew to keep a warm object centred; the logged FC channels stay neutral until
you hold the toggle; throttle never exceeds `--throttle-max-us`. **This is the cheapest place to catch a real
vs. sim gap** (AGC, clutter, IMU/vibration) before anything spins.

## Step 5 — Static-stand HIL (props OFF, GAP 2)

Mount the head on the gimbal bench (`fpv/gimbal/bench_runner.py`). Move a warm target by hand; confirm the
gimbal holds it and the guidance command tracks in the right direction. This closes the loop on the REAL
seeker for the first time — the biggest unknown in `REMAINING_WORK.md`.

## Step 6 — First flight (GAP 3, field, pilot on the backup)

Follow `docs/FLIGHT_TEST_OVERRIDE.md`. Fly manually; hold the toggle to hand the sticks to the seeker in a
bounded envelope (slow, overhead, well-cued target); release or lose the Pi and the FC returns your sticks.
The independent kill-MCU is the last-resort power cut. Nothing in the "proven-in-sim" list is real until this
step produces data.

---

## The safety chain, in one place (why a first flight is recoverable)

1. **Arming** stays on your RX switch. The Pi's MSP mask (15) covers only the 4 sticks, so the Pi **cannot
   arm** — enforced by Betaflight.
2. **Override is momentary**: it applies only while you hold the toggle. Let go → your sticks.
3. **Pi/USB/loop dies** → the MSP RC stream stops → Betaflight drops the override within a few hundred ms →
   your sticks. Enforced by Betaflight, not by our code.
4. **RC link lost** → `failsafe_procedure = DROP` cuts motors.
5. **Last resort** → the independent kill-MCU cuts motor POWER on its own clock and its own radio, latched.

Five layers, and layers 1–4 hold even if the Pi is wrong or dead.
