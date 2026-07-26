# 05 — MAVLink DoS Proof of Concept

A script that demonstrates what happens when someone gets access to the MAVLink network and starts sending commands. It floods ArduPilot with spoofed mode-change and disarm commands at 100Hz, overriding whatever the real GCS is trying to do.

**This only works against SITL. Do not use against real systems.**

---

## The Vulnerability

Default ArduPilot (and most real deployments) don't use MAVLink message signing. This means the autopilot can't tell the difference between a command from the legitimate GCS and a command from an attacker on the same network. Whoever sends commands faster wins.

ArduPilot does have signing support (`SYSID_MYGCS`, `MAV_AUTH_KEY`) but it's off by default and not commonly enabled in the field.

---

## What the Script Does

1. Connects to SITL's secondary MAVLink port (TCP 5762)
2. Uses a spoofed system ID (255) which looks like a GCS
3. Sends two commands in a tight loop at ~100Hz:
   - Force mode change to LAND
   - Disarm (with the force-disarm-while-flying magic code 21196)

The autopilot accepts both because it has no way to verify who sent them. The drone immediately starts landing and can't be stopped by the real GCS because the attack commands are coming in faster.

---

## How to Run (SITL only)

Start SITL with two MAVLink outputs:
```bash
sim_vehicle.py -v ArduCopter --console --map --out tcp:127.0.0.1:5762
```

Arm the drone and get it airborne in QGC. Then in a separate terminal:
```bash
pip install pymavlink
python3 mavlink_dos.py
```

You'll see the drone immediately switch to LAND mode and begin descending. The real GCS can't override it while the script is running.

Press `Ctrl+C` to stop the attack.

---

## Defense

The fix is straightforward — enable MAVLink message signing:

```
MAV_AUTH_KEY = your_secret_key
```

With signing enabled, the autopilot rejects any unsigned or incorrectly signed message. The attack script would need the same key to work, which an attacker on the network wouldn't have.

Other mitigations:
- Network isolation (keep the MAVLink network separate from anything untrusted)
- Firewall rules to restrict which IPs can reach port 5760/5762
- `SYSID_MYGCS` parameter to only accept commands from a specific system ID

---

## Files

- `mavlink_dos.py` — the PoC script
