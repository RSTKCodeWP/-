# 04 — Geofence Lua Alert Script

An ArduPilot Lua script that runs directly on the flight controller and watches the drone's position against the configured geofence. When the drone gets close to the boundary it sends a warning to the GCS. When it actually crosses, it sends an emergency alert.

This is different from ArduPilot's built-in geofence action (which just triggers RTL or land). This script gives you early warnings and keeps a breach count, which is useful if you want to log violations or trigger custom behavior.

---

## How It Works

The script reads three ArduPilot parameters on load:
- `FENCE_ENABLE` — only runs if this is 1
- `FENCE_RADIUS` — the horizontal boundary in meters
- `FENCE_ALT_MAX` — the altitude ceiling in meters

Every second it checks the current position against both limits. There are two alert levels:

- **Warning** — sent when the drone is past 80% of the limit but hasn't breached yet. Shown as a yellow message in QGC.
- **Breach** — sent when the limit is exceeded. Shown as a red emergency message in QGC.

Once the drone comes back inside, a "back inside" message is sent and the alert state resets. It won't spam the same alert repeatedly — state is tracked between checks.

---

## Installing on ArduPilot

1. Copy `geofence_alert.lua` to the `APM/scripts/` folder on the flight controller's SD card

2. Enable Lua scripting in ArduPilot parameters:
```
SCR_ENABLE = 1
```

3. Reboot the flight controller. You should see this in the GCS messages:
```
GeoFence script loaded
```

4. Set your fence parameters:
```
FENCE_ENABLE  = 1
FENCE_RADIUS  = 100   (meters from home)
FENCE_ALT_MAX = 50    (meters above home)
```

For SITL testing:
```bash
sim_vehicle.py -v ArduCopter --console --map --scripting
```

Then set the parameters above in MAVProxy or QGC and fly toward the boundary.

---

## Tuning

Two values at the top of the script you can change:

```lua
local CHECK_INTERVAL_MS = 1000   -- how often to check (ms)
local WARNING_FRACTION  = 0.80   -- warn at this fraction of the limit
```

Set `WARNING_FRACTION = 0.90` if you want less warning time, or `0.70` for earlier warnings.

---

## Files

- `geofence_alert.lua` — the script
