# ArduPilot Drone Security Research

A collection of work I did covering drone operations, flight controller internals, MAVLink protocol analysis, and UAV security. Everything here runs on ArduPilot SITL — no real hardware needed to try any of it.

The work is split into five areas, each building on the previous one:

---

## What's Inside

### [01 — SITL Operations](./01-sitl-operations/)
Basic through intermediate drone operations using QGroundControl and ArduPilot SITL. Covers waypoint missions, geofencing, wind effects on flight path, live telemetry, multi-drone setups, and a waypoint injection attack demo.

### [02 — MATLAB Fallback Controller](./02-fallback-controller/)
A physics-based PD fallback controller written in MATLAB that hooks into ArduPilot's SITL JSON interface. When the main autopilot gets compromised (simulated by a forced 60-degree roll at t=40s), the fallback kicks in, levels the drone, and holds altitude until it's safe to hand back control.

### [03 — MAVLink Traffic Analysis](./03-mavlink-traffic-analysis/)
Captured and analyzed real MAVLink traffic between QGroundControl and ArduPilot SITL using Wireshark. Breaks down the protocol structure, identifies specific command messages (arm, takeoff, mode change, land), and maps out the full TCP/UDP conversation flow.

### [04 — Geofence Lua Script](./04-geofence-lua/)
An ArduPilot Lua script that runs on the flight controller itself and monitors position against the configured geofence. Sends warning messages to the GCS at 80% of the limit, and emergency alerts on actual breach. Works with ArduPilot's native FENCE parameters — no external software needed.

### [05 — MAVLink DoS PoC](./05-mavlink-dos-poc/)
A proof-of-concept script showing what happens when an attacker gets access to the MAVLink network. Floods the autopilot with spoofed mode-change and disarm commands at 100Hz. Works because default ArduPilot SITL has no message signing enabled. **SITL only.**

---

## Setup

You need ArduPilot SITL running for everything here. The quickest way:

```bash
# Clone ArduPilot
git clone https://github.com/ArduPilot/ardupilot.git
cd ardupilot
git submodule update --init --recursive

# Install dependencies
./Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile

# Launch a copter SITL
cd ArduCopter
sim_vehicle.py -v ArduCopter --console --map
```

Then connect QGroundControl to `udp:127.0.0.1:14550`.

For the MATLAB fallback controller, you also need MATLAB R2021b+ with the ArduPilot SITL JSON connector.

---

## Tools Used

- ArduPilot SITL
- QGroundControl
- MAVProxy
- pymavlink
- MATLAB (for the fallback controller)
- Wireshark (for traffic analysis)

---

## Note

Everything here was done in simulation for research purposes. The attack scripts (DoS, waypoint injection) only work against SITL and are included to show how these vulnerabilities work, not to be used against real systems.
