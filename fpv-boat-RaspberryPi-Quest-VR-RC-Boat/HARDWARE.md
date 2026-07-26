# FPV Boat — Hardware Wiring

Raspberry Pi Zero 2 W → **L298N dual H-bridge → two motors** (differential
thrust, no rudder / no steering servo).

## L298N wiring

| Function                 | L298N pin | BCM    | Physical pin |
| ------------------------ | --------- | ------ | ------------ |
| Left motor speed (PWM)   | ENA       | GPIO12 | **32** (PWM0) |
| Left motor direction     | IN1       | GPIO5  | **29**       |
| Left motor direction     | IN2       | GPIO6  | **31**       |
| Right motor speed (PWM)  | ENB       | GPIO13 | **33** (PWM1) |
| Right motor direction    | IN3       | GPIO20 | **38**       |
| Right motor direction    | IN4       | GPIO21 | **40**       |
| Common ground            | GND       | GND    | **34** (and 39) |

Motor outputs: **OUT1/OUT2 → left motor**, **OUT3/OUT4 → right motor**. If a
motor spins the wrong way, swap its two output leads (or its IN pins).

ENA/ENB are on GPIO12/GPIO13 because those are the Pi's two hardware-PWM
channels (PWM0/PWM1) — smoothest speed control. IN1..IN4 are plain GPIO. Pins
are defined in `motor_control.py` (`LEFT_EN`/`LEFT_IN1`… etc.) — change them
there if you rewire.

## Power — read before connecting

- **Motor supply (Vs / +12V terminal):** from the motor battery (LiPo, through
  the buck converter per your power plan) — **not** from the Pi's 5V.
- **Grounds must be common:** tie the L298N GND, the battery ground, and the
  Pi ground (physical pin 34) together.
- **Do not backfeed** the L298N's onboard 5V regulator output into the Pi's 5V
  rail. Run only the six control lines (ENA/ENB/IN1-4) + ground between the
  L298N and the Pi.
- **DPDT failsafe switch:** install before any *water* testing (a wiring task,
  not code). Bench testing the L298N over GPIO does not require it.
- **Driver rating:** this L298N is ~2A/channel continuous — fine for stock toy
  motors. If you move to bigger motors (e.g. 380-size) you must also upgrade the
  driver (BTS7960 or dual DRV8871). Don't put a big motor on this driver.

## Differential thrust

Steering is done by driving the two motors at different speeds:

```
left_motor  = throttle + steer
right_motor = throttle - steer      # each clamped to -1.0 .. 1.0
```

Negative values reverse a motor (full H-bridge), so the viewer's reverse toggle
just sends a negative throttle. This math lives in `motor_control.py`.

## Safety watchdog

`MotorController` zeroes both motors if `set_drive()` isn't called within 0.5 s
(`WATCHDOG_S`). The viewer feeds control at ~20 Hz, so a dropped link or a
stalled client stops the boat rather than letting it run away. The server also
calls `motors.stop()` when the control websocket closes.

## Pulse quality

On Raspberry Pi OS **Bookworm**, `gpiozero` uses the **lgpio** pin factory by
default (installed by `setup.sh` / `pip install lgpio`), which drives the
motor/lights PWM cleanly — just run `python3 webrtc_stream.py`.

**Do not** set `GPIOZERO_PIN_FACTORY=pigpio`: `pigpio` is no longer packaged on
Bookworm (`apt install pigpio` fails), and forcing that factory makes gpiozero
raise on init — which drops motors *and* lights into no-op mode (you'll see
`[motor]/[lights] hardware disabled (No module named 'pigpio')`). If you hit that,
just launch without the env var.

If the GPIO libraries are missing entirely, `motor_control.py` prints
`[motor] hardware disabled ...` and the server still runs streaming + recording
in software-only mode.

## Bench testing

Test the driver on its own, motors **off** the boat, before wiring to the web
server:

```sh
python3 motor_control.py
```

This ramps both motors ahead, spins in place each way, then astern — confirming
direction, speed response, and channel independence.

## Thermal safety (auto-shutdown)

The Pi Zero 2 W is thermally marginal under video encoding. The server runs a
background monitor: if CPU temperature stays at/above `CPU_OVERHEAT_C` (default
**80 °C**) for a few seconds, it stops the motors and **shuts the Pi down** to
protect the hardware. The HUD temp readout is color-coded: **white** = OK,
**yellow** = caution (≥70 °C), **red** = overheating (≥80 °C, shutdown imminent).

For the shutdown to work, the server's user needs **passwordless `sudo shutdown`**.
Add a sudoers drop-in once:

```sh
echo "$USER ALL=(ALL) NOPASSWD: /sbin/shutdown" | sudo tee /etc/sudoers.d/thermal-shutdown
sudo chmod 440 /etc/sudoers.d/thermal-shutdown
```

Without it, the monitor logs `shutdown failed … is passwordless sudo set up?`
and the Pi keeps running (relying on the firmware's own ~85 °C hardware
throttle/shutdown as the last line of defense). Tune the threshold with the
`CPU_OVERHEAT_C` env var.

The same passwordless-`sudo shutdown` rule also powers the **in-headset
shutdown combo** (both grips + B → confirm popup → `/system/shutdown`), which
takes the identical safe-poweroff path (stop motors/lights, close any active
recording, then `sudo shutdown`). One sudoers drop-in covers both. The combo is
**live** — confirming Yes calls `/system/shutdown` and the HUD shows a
`SHUTTING DOWN…` overlay until the Pi powers off.

## Running lights (ShareGoo 8-LED kit)

Two LED groups (4 white front, 4 red rear), each switched by its own NPN
transistor — GPIO can't safely source the LEDs' combined current, so it just
drives the transistor base. **Lights auto-turn-on with recording** (on at
`/record/start`, off at `/record/stop` and on thermal shutdown) **and can be
toggled manually** (single-tap Y → `/lights/toggle`); both groups switch
together. Code: `lights_control.py` (`python3 lights_control.py` to bench-blink).
No-op without `gpiozero`.

A third channel drives rear **reverse ("backup") lights** that come on
automatically whenever the boat is in reverse (the server calls
`lights.reverse()` off the control websocket's reverse flag). These LEDs aren't
installed yet — the pin is already claimed so wiring is drop-in, and it stays a
no-op until then. Wire it like the other groups (GPIO → 1k → transistor base).

| Function          | BCM    | Physical pin |
| ----------------- | ------ | ------------ |
| White front group | GPIO17 | **11**       |
| Red rear group    | GPIO27 | **13**       |
| Reverse lights    | GPIO22 | **15** (future install) |

Per group:
```
GPIO pin --[1k]--> transistor base
transistor collector <-- LED group negative
transistor emitter ----> GND (shared with Pi / buck converter)
LED group positive -----> 5V rail (buck converter output)
```

Change the pins in `lights_control.py` (`FRONT_PIN` / `REAR_PIN`) if you rewire.

## Battery telemetry (INA219)

Pack voltage + current come from an **INA219** breakout over I2C (the Pi has no
native ADC). Wire it **high-side, in series** on the battery line so it sees the
full pack:

| INA219 pin | Connect to |
| ---------- | ---------- |
| VCC        | Pi 3V3 (pin 1) |
| GND        | Pi GND (shared) |
| SDA        | GPIO2 / pin 3 |
| SCL        | GPIO3 / pin 5 |
| Vin+       | Battery **+** (pack positive) |
| Vin−       | Downstream load (→ buck converter input) |

Enable I2C once (`sudo raspi-config` → Interface → I2C) and install the lib:
`pip3 install pi-ina219`. Confirm the sensor shows at `0x40` with
`i2cdetect -y 1`. Then `python3 battery_control.py` prints live reads.

**Shunt/current caveat:** the standard breakout has a 0.1 Ω shunt rated ~3.2 A.
The motors + Pi can peak past that, which clips the *current* reading (voltage is
unaffected). For accurate current at full throttle, use an INA226 or swap in a
lower-value shunt and set `BATTERY_SHUNT_OHMS` / `BATTERY_MAX_AMPS`. Voltage —
the safety-critical number — is fine on the stock board.

`BATTERY_CELLS` defaults to **2** (2S) — set it if your pack differs — so the
voltage→charge-% curve is right (2S: ~8.4 V full, ~6.5 V empty). Below
`BATTERY_WARN_PCT` (default 25%) the HUD flashes **LOW BATTERY**; at ≤10% it
flashes **BATTERY CRITICAL**.

## Camera pan/tilt head-tracking (PCA9685 + 2× SG90)

The camera follows where the pilot looks: the viewer streams head yaw/pitch over
the control websocket, and the server maps it to two servo angles. A **PCA9685**
(16-channel PWM over I2C) drives the servos — the Pi's two hardware-PWM channels
are already taken by the L298N, and software PWM jitters servos.

| PCA9685 pin | Connect to |
| ----------- | ---------- |
| VCC         | Pi 3V3 (pin 1) — logic power |
| GND         | Pi GND (shared) |
| SDA         | GPIO2 / pin 3 |
| SCL         | GPIO3 / pin 5 |
| V+          | **5 V servo rail from the buck converter** (NOT the Pi 5 V) |
| Ch 0 signal | Pan servo |
| Ch 1 signal | Tilt servo |

Servos pull current spikes that can brown out the Pi — power them from the buck
converter's 5 V rail into the PCA9685 **V+**, with a common ground. Install:
`pip3 install adafruit-circuitpython-servokit`; bench with
`python3 pan_tilt_control.py` (sweeps both servos).

⚠️ **I2C address collision:** the PCA9685 **and** the INA219 both default to
**0x40**. Run both and one won't answer. Fix by moving one: bridge the PCA9685's
**A0** solder jumper (→ 0x41) and set `PAN_TILT_I2C_ADDR=0x41`, or move the
INA219 with `BATTERY_I2C_ADDR`. Confirm with `i2cdetect -y 1` (you should see
two distinct addresses).

Tuning env vars: `PAN_CHANNEL` / `TILT_CHANNEL` (default 0/1), `PAN_RANGE_DEG` /
`TILT_RANGE_DEG` (head degrees that map to full servo travel, default 90/45),
`PAN_SIGN` / `TILT_SIGN` (set to `-1` to flip a servo that tracks backwards), and
`PAN_CENTER` / `TILT_CENTER` (neutral servo angle = camera straight/level,
default 90 — raise/lower if the mount points the camera off-center at 90, e.g.
`TILT_CENTER=115` to level a camera that aims down).
Tilt travel is clamped to 45–135° so the camera can't crank into the hull. The
servo channels are set in `pan_tilt_control.py` — change them there if you rewire.

## Control mapping (from the headset)

| Input                          | Action                                  |
| ------------------------------ | --------------------------------------- |
| Left trigger                   | Throttle (squeeze to go)                |
| Right thumbstick X             | Steer                                   |
| A — double-tap                 | Start recording                         |
| A — single-tap                 | Stop recording                          |
| X — double-tap                 | Toggle cruise; while cruising, hold = slower  |
| Y — single-tap                 | Toggle running lights (also auto-on with recording) |
| Y — double-tap                 | Toggle reverse; while cruising, hold = faster |
| Both grips                     | Recenter head-tracking (camera holds current aim as neutral) |
| Both grips + B                 | Open the shutdown-confirm popup (stick to choose, A to select) |
| Right trigger, left thumbstick | Reserved / unused                       |

> Note: this mapping follows the current build. `ROADMAP.md` Track A describes an
> earlier scheme (A = record toggle, B = reverse). The code above is canonical;
> reconcile the roadmap when convenient.
