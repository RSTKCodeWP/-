# 02 — MATLAB Fallback Controller

A fallback flight controller written in MATLAB that takes over from ArduPilot when the main autopilot gets compromised. It connects to ArduPilot SITL through the JSON physics interface, so it runs as a custom physics backend — not as a GCS sending commands, but as an actual replacement for the flight controller itself.

---

## What It Does

The scenario is: at t=40s into the flight, an attacker injects a forced 60-degree roll into the drone's attitude and DCM. ArduPilot can't recover from this because its own attitude reference has been corrupted.

The fallback controller detects this (roll > 45 degrees) and takes over:
1. Overrides the PWM outputs going to the motors
2. Runs a PD loop to drive roll and pitch back to zero
3. Holds altitude at whatever it was when the fallback triggered
4. Hands back control once attitude is stable (roll and pitch both under 10 degrees)

---

## The Controller

It's a PD controller. No integral term — the goal is recovery, not precision hovering.

**Gains:**
```
Kp_roll  = 350    Kd_roll  = 70
Kp_pitch = 350    Kd_pitch = 70
Kp_alt   = 60     Kd_alt   = 45
```

**Motor mixing** (X-frame, NED convention, proven from physics):
```
ch1 FR (X+, Y+):  PWM_hover + alt_corr + roll_corr - pitch_corr
ch4 RR (X+, Y-):  PWM_hover + alt_corr + roll_corr + pitch_corr
ch2 RL (X-, Y-):  PWM_hover + alt_corr - roll_corr + pitch_corr
ch3 FL (X-, Y+):  PWM_hover + alt_corr - roll_corr - pitch_corr
```

Hover PWM is 1531, calculated from the motor parameters of the simulated Hexsoon 450 airframe (2kg mass, 4 motors, 53.9% throttle at hover).

There's also a 1.5-second settling ramp when the fallback first kicks in — corrections scale from 20% to 100% over that window to avoid a sudden jerk on takeover.

---

## How to Run

You need MATLAB R2021b+ and the ArduPilot SITL JSON interface files.

1. Clone ArduPilot and navigate to the JSON MATLAB examples:
```
ardupilot/libraries/SITL/examples/JSON/MATLAB/Copter/
```

2. Copy `fallback_controller.m` into that folder alongside `Copter.m` and `SITL_connector.m`

3. Start ArduPilot SITL with the JSON backend:
```bash
sim_vehicle.py -v ArduCopter --model JSON --console --map
```

4. Run in MATLAB:
```matlab
run('fallback_controller.m')
```

5. Arm the drone in QGroundControl and take off. At t=40s the attack triggers. Watch the terminal output — you'll see `[FALLBACK] *** TRIGGERED ***` when it kicks in and `[FALLBACK] *** RECOVERED ***` when it hands back.

---

## Terminal Output Example

```
[MAIN CTRL]       t= 38.0s | Alt= 12.4m | Roll= +0.3deg | Pitch= +1.1deg

================================================
[FALLBACK] *** TRIGGERED at t = 40.02 s ***
[FALLBACK] Roll  = +60.0 deg  (limit: +/-45 deg)
[FALLBACK] Altitude hold target: 12.41 m
[FALLBACK] Main controller OVERRIDDEN
================================================

[FALLBACK ACTIVE] t= 41.0s | Alt= 11.8m (tgt=12.4m) | Roll= +28.4deg | Pitch= +2.1deg
[FALLBACK ACTIVE] t= 43.0s | Alt= 12.1m (tgt=12.4m) | Roll=  +6.2deg | Pitch= +0.8deg

================================================
[FALLBACK] *** RECOVERED at t = 44.38 s ***
[FALLBACK] Attitude stable — returning to main controller
================================================
```

---

## Files

- `fallback_controller.m` — the full controller
