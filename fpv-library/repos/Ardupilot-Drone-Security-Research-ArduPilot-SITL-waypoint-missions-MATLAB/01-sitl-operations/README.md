# 01 — SITL Operations

Six missions I ran in ArduPilot SITL using QGroundControl. The flying area used for all missions is Georgia Tech's campus (Tech Green and surrounding buildings), loaded as a satellite map in QGC.

---

## Missions

### Mission 1 — Waypoint Navigation
Set up a 6-waypoint autonomous mission starting from Tech Green, visiting Bobby Dodd Stadium, Couch Park, CRC, Van Leer, Coliseum, and Russ Chandler before returning to launch. Altitude was stepped up by 2ft at each waypoint (50ft → 62ft) then restored before landing.

Also compared NAV commands vs DO commands — NAV moves the drone to a location, DO runs an action at a waypoint without moving (like changing speed or camera trigger). The demo video shows both side by side.

**Videos:** `Task_1_Part_1.mp4`, `Task_1_NAV_vs_DO.mp4`

---

### Mission 2 — Geofencing
Tested four geofence scenarios with a polygon fence drawn around Tech Green:

- **No fence** — baseline, drone flies freely with no restrictions
- **Fence active, staying inside** — normal flight within boundary, no breach triggered
- **Fence breach** — drone intentionally flown past the boundary
- **RTL action** — fence set to trigger Return-to-Launch on breach

**Video:** `Task_2.mp4`

---

### Mission 3 — Wind Simulation
Ran the Mission 1 route twice — once with 15mph wind and once with 45mph wind — both from 315° (Northwest). Analyzed how wind affects ground speed, heading corrections, and flight path on headwind, tailwind, and crosswind legs.

At 45mph the drift is very visible. The drone has to crab sideways on crosswind legs to maintain the planned track.

Parameters used:
```
SIM_WIND_SPD = 15 / 45 mph
SIM_WIND_DIR = 315 (Northwest)
SIM_WIND_TURB = 0
WPNAV_SPEED = 30 mph
```

**Videos:** `Task_3_15mph.mp4`, `Task_3_45mph.mp4`

---

### Mission 4 — Live Telemetry Graphing
Ran the Mission 1 route while logging roll, pitch, and yaw from the live telemetry feed. Annotated the graph with specific flight events — takeoff pitch, waypoint turns showing roll spikes, yaw changes at each heading change, and the nose-down pitch on braking before waypoints.

**Video:** `Task_4.mp4`

---

### Mission 5 — Multi-Drone Operation
Launched two SITL instances at the same time using `--count 2 --auto-sysid`. Both vehicles showed up simultaneously in QGroundControl on the same UDP port. Each was given a separate 3-waypoint mission and both ran independently.

Switching between vehicles in MAVProxy:
```
vehicle 1
vehicle 2
```

**Video:** `Task_5.mp4`

---

### Mission 6 (Bonus) — Malicious Waypoint Injection
Used the Mission 1 route as a base. When the drone reached WP4 (Van Leer), a Python script injected a GUIDED mode command over MAVLink that redirected the drone 200m south to a fake coordinate. The drone abandoned its mission, flew to the injected location, landed, and disarmed — without any indication in QGC that anything went wrong.

**Videos:** `Task_6_base_mission.mp4` (normal run), `Task_6_attack.mp4` (attack run)

---

## How to Run

1. Start ArduPilot SITL:
```bash
sim_vehicle.py -v ArduCopter --console --map
```
2. Connect QGroundControl to `udp:127.0.0.1:14550`
3. Load the waypoints from the mission PDFs and fly

For Mission 5 (multi-drone):
```bash
sim_vehicle.py -v ArduCopter --count 2 --auto-sysid --console --map
```
