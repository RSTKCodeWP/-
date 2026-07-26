# 03 — MAVLink Traffic Analysis

Captured and analyzed the full MAVLink communication between QGroundControl and ArduPilot SITL during a standard mission — arm, takeoff to 30m, fly, land, disarm. Used Wireshark with the MAVLink dissector plugin to decode the packets.

---

## What Was Captured

The `.tlog` file contains the full telemetry log from the session. Wireshark screenshots are in the `wireshark-screenshots/` folder covering:

- Protocol hierarchy (how much of the traffic is MAVLink vs raw UDP/TCP)
- TCP and UDP conversation stats
- IPv4 endpoint mapping
- Individual decoded MAVLink messages: arm/disarm, takeoff, mode change, land
- Specific message IDs and their field values

---

## Key Findings

**Protocol breakdown:**
MAVLink runs over both UDP (port 14550 for GCS) and TCP (port 5760 for MAVProxy). The bulk of traffic is telemetry flowing from the drone to the GCS — attitude, GPS, battery, RC inputs — at around 4Hz per message type.

**No authentication:**
Default SITL has no MAVLink message signing (SIGNATURE field is absent in all captured packets). Any device on the same network that knows the system ID can send commands and the autopilot will accept them. This is what makes the DoS attack in module 05 possible.

**System ID:**
The autopilot's SYSID is 1 (default). The GCS (QGroundControl) identifies as SYSID 255. This is visible in every packet header.

**Key messages observed:**

| Message | ID | Direction | Notes |
|---------|-----|-----------|-------|
| HEARTBEAT | 0 | Both | Every 1s from both sides |
| COMMAND_LONG | 76 | GCS → Drone | ARM, TAKEOFF, mode changes |
| COMMAND_ACK | 77 | Drone → GCS | Acknowledgement with result code |
| SET_MODE | 11 | GCS → Drone | Mode change (GUIDED, AUTO, LAND) |
| GLOBAL_POSITION_INT | 33 | Drone → GCS | GPS position at ~4Hz |
| ATTITUDE | 30 | Drone → GCS | Roll/pitch/yaw at ~10Hz |

---

## How to Replay the Tlog

You can open `flight.tlog` in QGroundControl directly (File → Open Telemetry Log) to replay the flight. Or use pymavlink:

```python
from pymavlink import mavutil

mav = mavutil.mavlink_connection('flight.tlog')
while True:
    msg = mav.recv_match(blocking=True)
    if msg is None:
        break
    print(msg)
```

To open in Wireshark, you need the MAVLink Wireshark plugin:
https://github.com/ArduPilot/pymavlink/tree/master/generator/C/include_v2.0

---

## Files

- `flight.tlog` — raw telemetry log from the session
- `wireshark-screenshots/` — annotated screenshots of the Wireshark analysis
