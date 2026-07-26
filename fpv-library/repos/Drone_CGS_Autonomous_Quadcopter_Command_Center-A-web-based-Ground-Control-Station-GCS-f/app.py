"""
AUTONOMOUS QUADCOPTER DRONE GCS (Ground Control Station)
Flask + Socket.IO Backend | MAVLink Integration + Simulation Mode
Author: Drone GCS System
"""

import threading
import time
import math
import random
import json
import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_file
from flask_socketio import SocketIO, emit
import pandas as pd
from io import BytesIO

# ─────────────────────────────────────────────────────────────────────────────
# MAVLink Import (optional – simulation fallback if not installed)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATTERY_MAX_VOLTAGE = 12.0
BATTERY_NOMINAL_VOLTAGE = 11.1
BATTERY_MIN_VOLTAGE = 10.9


def battery_percentage_from_voltage(voltage):
    if voltage is None:
        return 0
    voltage = float(voltage)
    curve = [
        (12.00, 100),
        (11.95, 95),
        (11.90, 90),
        (11.85, 82),
        (11.80, 74),
        (11.75, 66),
        (11.70, 58),
        (11.65, 50),
        (11.60, 42),
        (11.55, 35),
        (11.50, 28),
        (11.45, 22),
        (11.40, 16),
        (11.35, 11),
        (11.30, 7),
        (11.20, 4),
        (11.10, 2),
        (10.90, 0),
    ]

    if voltage >= curve[0][0]:
        return 100
    if voltage <= curve[-1][0]:
        return 0

    for (v1, p1), (v2, p2) in zip(curve, curve[1:]):
        if v1 >= voltage >= v2:
            ratio = (voltage - v2) / (v1 - v2)
            pct = p2 + ratio * (p1 - p2)
            return max(0, min(100, int(round(pct))))

    pct = (voltage - BATTERY_MIN_VOLTAGE) / (BATTERY_MAX_VOLTAGE - BATTERY_MIN_VOLTAGE) * 100
    return max(0, min(100, int(round(pct))))

# ─────────────────────────────────────────────────────────────────────────────
# App Initialization
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'drone_gcs_secret_2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─────────────────────────────────────────────────────────────────────────────
# Global Drone State
# ─────────────────────────────────────────────────────────────────────────────
drone_state = {
    "armed": False,
    "mode": "STABILIZE",
    "connected": False,
    "simulation": True,
    "lat": 18.5204,
    "lon": 73.8567,
    "alt": 0.0,
    "rel_alt": 0.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "vx": 0.0,
    "vy": 0.0,
    "vz": 0.0,
    "airspeed": 0.0,
    "groundspeed": 0.0,
    "heading": 0.0,
    "battery_voltage": BATTERY_MAX_VOLTAGE,
    "battery_current": 0.0,
    "battery_remaining": 100,
    "battery_percentage": 100,
    "battery_consumed_mah": 0.0,
    "gps_fix": 3,
    "satellites": 14,
    "hdop": 0.9,
    "throttle": 0,
    "climb_rate": 0.0,
    "mission_progress": 0,
    "total_waypoints": 0,
    "home_lat": 18.5204,
    "home_lon": 73.8567,
    "distance_to_home": 0.0,
    "flight_time": 0,
    "ekf_ok": True,
    "pre_arm_check": True,
    "vibration_x": 0.2,
    "vibration_y": 0.2,
    "vibration_z": 0.3,
    "temp_imu": 42.5,
    "temp_baro": 38.2,
    "mag_field": 520.0,
    "flow_x": 0.0,
    "flow_y": 0.0,
    "rangefinder": 0.0,
    "status_text": "System Ready",
    "wind_speed": 2.1,
    "wind_direction": 225,
    "signal_strength": 95,
    "victims_detected": 0,
    "mission_status": "IDLE",
    "autopilot_type": "ArduCopter",
    "firmware_version": "4.5.2",
    "frame_type": "X",
    "motor_status": [100, 100, 100, 100],
    "component_health": {
        "gps": "NOMINAL",
        "imu": "NOMINAL",
        "baro": "NOMINAL",
        "compass": "NOMINAL",
        "battery": "NOMINAL",
        "motors": "NOMINAL",
        "rc": "NOMINAL",
        "datalink": "NOMINAL"
    },
    "failure_mode": None,
    "failure_component": None,
    "failure_location": None,
}

# ─────────────────────────────────────────────────────────────────────────────
# Mission & Log Storage
# ─────────────────────────────────────────────────────────────────────────────
mission_log = []
flight_path = []
victims = []
system_events = []
telemetry_history = {
    "time": [],
    "altitude": [],
    "speed": [],
    "battery": [],
    "voltage": [],
    "current": [],
    "roll": [],
    "pitch": [],
    "climb_rate": [],
}

waypoints = [
    {"lat": 18.5210, "lon": 73.8575, "alt": 20, "action": "WAYPOINT", "reached": False},
    {"lat": 18.5215, "lon": 73.8590, "alt": 25, "action": "WAYPOINT", "reached": False},
    {"lat": 18.5220, "lon": 73.8585, "alt": 30, "action": "SURVEY",   "reached": False},
    {"lat": 18.5218, "lon": 73.8570, "alt": 25, "action": "WAYPOINT", "reached": False},
    {"lat": 18.5212, "lon": 73.8560, "alt": 20, "action": "WAYPOINT", "reached": False},
    {"lat": 18.5204, "lon": 73.8567, "alt": 0,  "action": "LAND",     "reached": False},
]

# ─────────────────────────────────────────────────────────────────────────────
# Simulation Engine
# ─────────────────────────────────────────────────────────────────────────────
class SimulationEngine:
    def __init__(self):
        self.t = 0
        self.wp_index = 0
        self.mission_active = False
        self.takeoff_complete = False
        self.start_time = None
        self.battery_drain_rate = 0.0015
        self.lat_velocity = 0.0
        self.lon_velocity = 0.0
        self.target_alt = 0.0
        self.current_alt = 0.0
        self.roll_noise = 0.0
        self.pitch_noise = 0.0

    def update(self):
        self.t += 0.1
        state = drone_state

        if not state["armed"]:
            self._idle_state(state)
            return

        if self.start_time is None:
            self.start_time = datetime.now()

        elapsed = (datetime.now() - self.start_time).total_seconds()
        state["flight_time"] = int(elapsed)

        # Battery drain
        if state["armed"]:
            drain = self.battery_drain_rate * (1 + state["throttle"] / 200)
            state["battery_consumed_mah"] += drain * 10
            state["battery_voltage"] = max(BATTERY_MIN_VOLTAGE, BATTERY_MAX_VOLTAGE - (state["battery_consumed_mah"] / 5000) * (BATTERY_MAX_VOLTAGE - BATTERY_MIN_VOLTAGE))
            state["battery_percentage"] = max(0, min(100, int(round((state["battery_voltage"] - BATTERY_MIN_VOLTAGE) / (BATTERY_MAX_VOLTAGE - BATTERY_MIN_VOLTAGE) * 100))))
            state["battery_remaining"] = state["battery_percentage"]
            state["battery_current"] = 8 + (state["throttle"] / 10) + random.uniform(-0.5, 0.5)
            self._check_battery_health(state)

        # Mission flight simulation
        if self.mission_active and state["mode"] == "AUTO":
            self._simulate_mission(state)
        elif state["mode"] == "STABILIZE" or state["mode"] == "LOITER":
            self._simulate_hover(state)
        elif state["mode"] == "RTL":
            self._simulate_rtl(state)

        # Sensor noise
        state["roll"] = self.roll_noise + math.sin(self.t * 0.3) * 0.5
        state["pitch"] = self.pitch_noise + math.sin(self.t * 0.2) * 0.4
        state["vibration_x"] = abs(random.gauss(0.3, 0.1))
        state["vibration_y"] = abs(random.gauss(0.3, 0.1))
        state["vibration_z"] = abs(random.gauss(0.5, 0.15))
        state["temp_imu"] = 42.5 + math.sin(self.t * 0.01) * 2
        state["wind_speed"] = max(0, state["wind_speed"] + random.uniform(-0.1, 0.1))
        state["wind_direction"] = (state["wind_direction"] + random.uniform(-1, 1)) % 360
        state["signal_strength"] = max(60, min(100, state["signal_strength"] + random.randint(-1, 1)))
        state["satellites"] = max(8, min(18, state["satellites"] + random.randint(-1, 1)))
        state["hdop"] = max(0.6, min(2.5, state["hdop"] + random.uniform(-0.05, 0.05)))
        state["mag_field"] = 520 + random.uniform(-5, 5)

        # Compute distance to home
        dlat = state["lat"] - state["home_lat"]
        dlon = state["lon"] - state["home_lon"]
        state["distance_to_home"] = math.sqrt(dlat**2 + dlon**2) * 111320

        # Groundspeed
        state["groundspeed"] = math.sqrt(state["vx"]**2 + state["vy"]**2)
        state["airspeed"] = state["groundspeed"] + random.uniform(-0.3, 0.3)
        state["climb_rate"] = state["vz"]

        # Random victim detection during survey mission
        if self.mission_active and random.random() < 0.001:
            self._detect_victim(state)

    def _idle_state(self, state):
        state["vx"] = 0
        state["vy"] = 0
        state["vz"] = 0
        state["throttle"] = 0
        if not state["armed"]:
            state["rel_alt"] = 0
        state["alt"] = state["home_lat"] * 0
        state["battery_current"] = 0.1 if not state["armed"] else 2.0

    def _simulate_hover(self, state):
        state["vx"] *= 0.95
        state["vy"] *= 0.95
        target_alt = 15.0 if state["armed"] else 0.0
        diff = target_alt - state["rel_alt"]
        state["vz"] = diff * 0.2
        state["rel_alt"] += state["vz"] * 0.1
        state["rel_alt"] = max(0, state["rel_alt"])
        state["throttle"] = 50 + int(state["vz"] * 5)

    def _simulate_mission(self, state):
        if self.wp_index >= len(waypoints):
            self.mission_active = False
            state["mission_status"] = "COMPLETED"
            state["mode"] = "LOITER"
            self._log_event("Mission completed successfully", "SUCCESS")
            return

        wp = waypoints[self.wp_index]
        target_lat = wp["lat"]
        target_lon = wp["lon"]
        target_alt = float(wp["alt"])

        # Move toward waypoint
        dlat = target_lat - state["lat"]
        dlon = target_lon - state["lon"]
        dist = math.sqrt(dlat**2 + dlon**2) * 111320

        state["mission_progress"] = int((self.wp_index / len(waypoints)) * 100)

        if dist < 1.5:  # Reached waypoint
            waypoints[self.wp_index]["reached"] = True
            self._log_event(f"Reached WP{self.wp_index+1}: {wp['action']}", "INFO")
            if wp["action"] == "LAND":
                state["mode"] = "LAND"
                self._log_event("Initiating landing sequence", "INFO")
            self.wp_index += 1
            return

        speed = 5.0  # m/s
        if dist > 0:
            state["vx"] = (dlat / dist) * 111320 * speed * 0.0001
            state["vy"] = (dlon / dist) * 111320 * speed * 0.0001

        state["lat"] += state["vx"] * 0.1
        state["lon"] += state["vy"] * 0.1

        # Altitude control
        dalt = target_alt - state["rel_alt"]
        state["vz"] = dalt * 0.3
        state["rel_alt"] += state["vz"] * 0.1
        state["rel_alt"] = max(0, state["rel_alt"])

        # Heading toward target
        state["yaw"] = math.degrees(math.atan2(dlon, dlat)) % 360
        state["heading"] = state["yaw"]
        state["throttle"] = 55 + int(state["vz"] * 3)

        # Roll/pitch reflect motion
        self.pitch_noise = -math.atan2(state["vx"], 0.1) * 2
        self.roll_noise = math.atan2(state["vy"], 0.1) * 2

        # Record path
        if len(flight_path) == 0 or math.sqrt((state["lat"] - flight_path[-1]["lat"])**2 + (state["lon"] - flight_path[-1]["lon"])**2) > 0.00005:
            flight_path.append({
                "lat": round(state["lat"], 7),
                "lon": round(state["lon"], 7),
                "alt": round(state["rel_alt"], 1),
                "time": datetime.now().isoformat()
            })

    def _simulate_rtl(self, state):
        dlat = state["home_lat"] - state["lat"]
        dlon = state["home_lon"] - state["lon"]
        dist = math.sqrt(dlat**2 + dlon**2) * 111320

        if dist < 2.0 and state["rel_alt"] < 0.5:
            state["armed"] = False
            state["rel_alt"] = 0
            state["vx"] = 0
            state["vy"] = 0
            state["vz"] = 0
            state["mode"] = "STABILIZE"
            state["mission_status"] = "RTL_COMPLETE"
            self._log_event("RTL complete. Drone disarmed.", "SUCCESS")
            return

        if state["rel_alt"] > 5:
            if dist > 3:
                speed = 4.0
                state["vx"] = (dlat / max(dist, 0.001)) * 111320 * speed * 0.0001
                state["vy"] = (dlon / max(dist, 0.001)) * 111320 * speed * 0.0001
                state["lat"] += state["vx"] * 0.1
                state["lon"] += state["vy"] * 0.1
            else:
                state["vz"] = -1.5
                state["rel_alt"] = max(0, state["rel_alt"] + state["vz"] * 0.1)
        else:
            state["vz"] = -0.5
            state["rel_alt"] = max(0, state["rel_alt"] + state["vz"] * 0.1)

        state["heading"] = math.degrees(math.atan2(dlon, dlat)) % 360
        state["yaw"] = state["heading"]

    def _check_battery_health(self, state):
        v = state["battery_voltage"]
        p = state["battery_percentage"]
        if v <= BATTERY_MIN_VOLTAGE:
            state["component_health"]["battery"] = "CRITICAL"
            state["status_text"] = "CRITICAL: Battery below operating voltage"
            state["mode"] = "RTL"
            state["failure_mode"] = "AUTO_RTL"
            state["failure_component"] = "Battery"
            self._log_event("CRITICAL: Battery below operating voltage. Auto-RTL engaged.", "CRITICAL")
        elif p < 15:
            state["component_health"]["battery"] = "WARNING"
            state["status_text"] = "WARNING: Low Battery"
            self._log_event("WARNING: Battery below 15%", "WARNING")
        elif p < 25:
            state["component_health"]["battery"] = "WARNING"
        else:
            state["component_health"]["battery"] = "NOMINAL"

    def _detect_victim(self, state):
        victim = {
            "id": len(victims) + 1,
            "lat": state["lat"] + random.uniform(-0.0002, 0.0002),
            "lon": state["lon"] + random.uniform(-0.0002, 0.0002),
            "thermal_confidence": round(random.uniform(0.72, 0.99), 2),
            "ai_confidence": round(random.uniform(0.75, 0.98), 2),
            "timestamp": datetime.now().isoformat(),
            "drone_alt": round(state["rel_alt"], 1),
            "status": "DETECTED",
        }
        victims.append(victim)
        state["victims_detected"] = len(victims)
        self._log_event(f"VICTIM DETECTED #{victim['id']} | Thermal: {victim['thermal_confidence']*100:.0f}% | AI: {victim['ai_confidence']*100:.0f}%", "VICTIM")
        socketio.emit('victim_detected', victim)

    def _log_event(self, message, level="INFO"):
        event = {
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "message": message,
            "level": level,
            "lat": drone_state.get("lat"),
            "lon": drone_state.get("lon"),
            "alt": drone_state.get("rel_alt"),
            "mode": drone_state.get("mode"),
        }
        system_events.append(event)
        mission_log.append({
            **event,
            "battery": drone_state.get("battery_remaining"),
            "voltage": drone_state.get("battery_voltage"),
            "flight_time": drone_state.get("flight_time"),
            "groundspeed": drone_state.get("groundspeed"),
        })
        socketio.emit('system_event', event)


sim_engine = SimulationEngine()

# ─────────────────────────────────────────────────────────────────────────────
# MAVLink Connection Manager (REPLACED)
# ─────────────────────────────────────────────────────────────────────────────
class MAVLinkManager:
    def __init__(self):
        self.master = None
        self.connected = False
        self.connection_string = None
        self.heartbeat_thread = None
        self.keepalive_thread = None
        self.desired_arm_state = None
        self.arm_mismatch_count = 0
        self.last_arm_command_time = 0.0
        self.last_arm_message = ""
        self.last_status_text = ""

    def connect(self, connection_string, baud=921600):
        if not MAVLINK_AVAILABLE:
            return False, "pymavlink not installed"
        try:
            self.master = mavutil.mavlink_connection(connection_string, baud=baud)
            self.master.wait_heartbeat(timeout=10)
            self.connected = True
            self.connection_string = connection_string
            drone_state["connected"] = True
            drone_state["simulation"] = False
            drone_state["autopilot_type"] = "ArduCopter (REAL)"
            self._start_heartbeat()
            self._start_keepalive()
            self.apply_test_flight_profile()
            sim_engine._log_event(f"MAVLink connected: {connection_string}", "SUCCESS")
            return True, "Connected"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.connected = False
        if self.master:
            try:
                self.master.close()
            except Exception:
                pass
        drone_state["connected"] = False
        drone_state["simulation"] = True

    def _start_heartbeat(self):
        if self.heartbeat_thread is None or not self.heartbeat_thread.is_alive():
            self.heartbeat_thread = threading.Thread(target=self._send_gcs_heartbeat, daemon=True)
            self.heartbeat_thread.start()

    def _start_keepalive(self):
        if self.keepalive_thread is None or not self.keepalive_thread.is_alive():
            self.keepalive_thread = threading.Thread(target=self._keepalive_loop, daemon=True)
            self.keepalive_thread.start()

    def _send_gcs_heartbeat(self):
        while self.connected and self.master:
            try:
                self.master.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, 0
                )
            except Exception as e:
                logger.error(f"Heartbeat send failed: {e}")
            time.sleep(0.5)

    def _keepalive_loop(self):
        counter = 0
        while self.connected and self.master:
            try:
                self.master.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, 0
                )
                if counter % 4 == 0:
                    self._request_data_streams()
                counter += 1
            except Exception as e:
                logger.error(f"Keepalive failed: {e}")
            time.sleep(0.5)

    def _request_data_streams(self):
        if not self.master:
            return
        try:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10,
                1
            )
        except Exception as e:
            logger.error(f"Request data stream failed: {e}")

    def set_parameter(self, name, value):
        if not self.connected or not self.master:
            return False, "Not connected"

        try:
            param_name = name.encode("utf-8")[:16]
            self.master.mav.param_set_send(
                self.master.target_system,
                self.master.target_component,
                param_name,
                float(value),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
            )
            return True, f"{name} set to {value}"
        except Exception as e:
            logger.error(f"Parameter set failed for {name}: {e}")
            return False, str(e)

    def apply_test_flight_profile(self):
        if not self.connected or not self.master:
            return False, "Not connected"

        results = []
        for name, value in (("FS_THR_ENABLE", 0), ("FS_GCS_ENABLE", 1)):
            ok, msg = self.set_parameter(name, value)
            results.append(msg)

        summary = " | ".join(results)
        sim_engine._log_event(f"Test flight profile applied: {summary}", "INFO")
        return True, summary

    def arm_disarm(self, arm):
        if not self.connected:
            self.last_arm_message = "Not connected"
            return False
        try:
            command = mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM
            self.desired_arm_state = arm
            self.arm_mismatch_count = 0
            self.last_arm_command_time = time.time()
            if arm:
                self.master.mav.command_long_send(
                    self.master.target_system, self.master.target_component,
                    command, 0, 1, 0, 0, 0, 0, 0, 0)
            else:
                self.master.mav.command_long_send(
                    self.master.target_system, self.master.target_component,
                    command, 0, 0, 0, 0, 0, 0, 0, 0)

            ack_seen = False
            deadline = time.time() + 8
            while time.time() < deadline:
                msg = self.master.recv_match(type=['COMMAND_ACK', 'HEARTBEAT'], blocking=True, timeout=1)
                if not msg:
                    continue

                msg_type = msg.get_type()
                if msg_type == 'COMMAND_ACK' and getattr(msg, 'command', None) == command:
                    if msg.result not in [mavutil.mavlink.MAV_RESULT_ACCEPTED, mavutil.mavlink.MAV_RESULT_IN_PROGRESS]:
                        self.last_arm_message = f"Arm rejected by Pixhawk: result={msg.result}"
                        logger.error(self.last_arm_message)
                        return False
                    ack_seen = True
                elif msg_type == 'HEARTBEAT':
                    is_armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                    drone_state["armed"] = is_armed
                    if is_armed == arm:
                        self.arm_mismatch_count = 0
                    elif arm and (time.time() - self.last_arm_command_time) < 10:
                        self.arm_mismatch_count += 1
                    else:
                        self.arm_mismatch_count = 0

                if ack_seen:
                    drone_state["armed"] = arm
                    drone_state["status_text"] = "ARMED" if arm else "DISARMED"
                    self.last_arm_message = "Arm command accepted"
                    return True

            self.last_arm_message = "Arm command timed out; check Pixhawk STATUSTEXT"
            logger.error(self.last_arm_message)
            return False
        except Exception as e:
            self.last_arm_message = str(e)
            logger.error(f"Arm/disarm failed: {e}")
            return False

    def set_mode(self, mode):
        if not self.connected:
            return False
        try:
            mode_id = self.master.mode_mapping().get(mode)
            if mode_id is not None:
                self.master.set_mode(mode_id)
            return True
        except:
            return False

    def calibrate_preflight(self, calibration_type="all"):
        if not self.connected or not self.master:
            return False, "Not connected"

        try:
            cmd = mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION
            params = {
                "gyro":    (1, 0, 0, 0, 0, 0, 0),
                "mag":     (0, 1, 0, 0, 0, 0, 0),
                "baro":    (0, 0, 1, 0, 0, 0, 0),
                "radio":   (0, 0, 0, 1, 0, 0, 0),
                "accel":   (0, 0, 0, 0, 1, 0, 0),
                "airspeed": (0, 0, 0, 0, 0, 1, 0),
                "level":   (0, 0, 0, 0, 0, 0, 1),
                "all":     (1, 1, 1, 1, 1, 0, 1),
            }
            if calibration_type not in params:
                return False, "Invalid calibration type"
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                cmd,
                0,
                *params[calibration_type]
            )
            return True, f"Calibration command sent: {calibration_type}"
        except Exception as e:
            logger.error(f"Calibration command failed: {e}")
            return False, str(e)

    def upload_mission(self, mission_items):
        if not self.connected or not self.master:
            return False, "Not connected"
        try:
            mission_count = len(mission_items)
            self.master.mav.mission_count_send(
                self.master.target_system,
                self.master.target_component,
                mission_count
            )

            deadline = time.time() + 30
            while time.time() < deadline:
                msg = self.master.recv_match(type=['MISSION_REQUEST', 'MISSION_ACK'], blocking=True, timeout=10)
                if not msg:
                    continue
                mt = msg.get_type()
                if mt == 'MISSION_REQUEST':
                    seq = msg.seq
                    if seq < 0 or seq >= mission_count:
                        return False, f"Invalid mission request seq={seq}"
                    wp = mission_items[seq]
                    command = mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
                    if wp.get('action', '').upper() == 'LAND':
                        command = mavutil.mavlink.MAV_CMD_NAV_LAND
                    self.master.mav.mission_item_int_send(
                        self.master.target_system,
                        self.master.target_component,
                        seq,
                        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                        command,
                        1 if seq == 0 else 0,
                        1,
                        0, 0, 0, 0,
                        int(wp['lat'] * 1e7),
                        int(wp['lon'] * 1e7),
                        float(wp['alt'])
                    )
                elif mt == 'MISSION_ACK':
                    if msg.type == 0:
                        return True, "Mission upload successful"
                    return False, f"Mission upload failed ACK={msg.type}"
            return False, "Mission upload timed out"
        except Exception as e:
            logger.error(f"Mission upload error: {e}")
            return False, str(e)

    def read_telemetry(self):
        if not self.connected or not self.master:
            return
        try:
            while True:
                msg = self.master.recv_match(blocking=False)
                if not msg:
                    break

                mt = msg.get_type()

                if mt == 'GLOBAL_POSITION_INT':
                    drone_state["lat"] = msg.lat / 1e7
                    drone_state["lon"] = msg.lon / 1e7
                    drone_state["alt"] = msg.alt / 1000.0
                    drone_state["rel_alt"] = msg.relative_alt / 1000.0
                    drone_state["vx"] = msg.vx / 100.0
                    drone_state["vy"] = msg.vy / 100.0
                    drone_state["vz"] = msg.vz / 100.0
                    drone_state["heading"] = msg.hdg / 100.0

                    if len(flight_path) == 0 or math.sqrt((drone_state["lat"] - flight_path[-1]["lat"])**2 + (drone_state["lon"] - flight_path[-1]["lon"])**2) > 0.00005:
                        flight_path.append({"lat": drone_state["lat"], "lon": drone_state["lon"], "alt": drone_state["rel_alt"], "time": datetime.now().isoformat()})

                elif mt == 'ATTITUDE':
                    drone_state["roll"] = math.degrees(msg.roll)
                    drone_state["pitch"] = math.degrees(msg.pitch)
                    drone_state["yaw"] = math.degrees(msg.yaw)

                elif mt == 'SYS_STATUS':
                    voltage = msg.voltage_battery / 1000.0
                    drone_state["battery_voltage"] = voltage
                    drone_state["battery_current"] = msg.current_battery / 100.0
                    drone_state["battery_percentage"] = battery_percentage_from_voltage(voltage)
                    drone_state["battery_remaining"] = drone_state["battery_percentage"]
                    drone_state["component_health"]["battery"] = "NOMINAL" if voltage > BATTERY_NOMINAL_VOLTAGE else "WARNING" if voltage > BATTERY_MIN_VOLTAGE else "CRITICAL"

                elif mt == 'GPS_RAW_INT':
                    drone_state["gps_fix"] = msg.fix_type
                    drone_state["satellites"] = msg.satellites_visible
                    drone_state["hdop"] = msg.eph / 100.0

                elif mt == 'VFR_HUD':
                    drone_state["airspeed"] = msg.airspeed
                    drone_state["groundspeed"] = msg.groundspeed
                    drone_state["throttle"] = msg.throttle
                    drone_state["climb_rate"] = msg.climb

                elif mt == 'HEARTBEAT':
                    mode = mavutil.mode_string_v10(msg)
                    is_armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                    drone_state["mode"] = mode
                    if self.desired_arm_state is None:
                        drone_state["armed"] = is_armed
                    elif is_armed == self.desired_arm_state:
                        self.arm_mismatch_count = 0
                        drone_state["armed"] = is_armed
                    else:
                        self.arm_mismatch_count += 1
                        if self.arm_mismatch_count >= 5 or (time.time() - self.last_arm_command_time) > 10:
                            drone_state["armed"] = is_armed
                            self.desired_arm_state = is_armed
                            self.arm_mismatch_count = 0

                elif mt == 'STATUSTEXT':
                    text = msg.text
                    drone_state["status_text"] = text
                    self.last_status_text = text
                    level = "CRITICAL" if "Failsafe" in text or "Error" in text else "MAVLINK"
                    sim_engine._log_event(text, level)

                elif mt == 'VIBRATION':
                    drone_state["vibration_x"] = msg.vibration_x
                    drone_state["vibration_y"] = msg.vibration_y
                    drone_state["vibration_z"] = msg.vibration_z

        except Exception as e:
            logger.error(f"MAVLink read error: {e}")

mav_manager = MAVLinkManager()

# ─────────────────────────────────────────────────────────────────────────────
# Telemetry Worker Thread (REPLACED)
# ─────────────────────────────────────────────────────────────────────────────
def telemetry_worker():
    sample_count = 0
    logger.info("Telemetry Worker Thread Started")
    while True:
        try:
            if drone_state["simulation"]:
                sim_engine.update()
            else:
                mav_manager.read_telemetry()

            sample_count += 1

            # High-resolution frequency: Update history every 1 second (10 x 100ms)
            if sample_count % 10 == 0:
                now_str = datetime.now().strftime("%H:%M:%S")
                telemetry_history["time"].append(now_str)
                telemetry_history["altitude"].append(round(drone_state["rel_alt"], 1))
                telemetry_history["speed"].append(round(drone_state["groundspeed"], 1))
                telemetry_history["battery"].append(drone_state["battery_remaining"])
                telemetry_history["voltage"].append(round(drone_state["battery_voltage"], 2))
                telemetry_history["current"].append(round(drone_state["battery_current"], 1))
                telemetry_history["roll"].append(round(drone_state["roll"], 1))
                telemetry_history["pitch"].append(round(drone_state["pitch"], 1))
                telemetry_history["climb_rate"].append(round(drone_state["climb_rate"], 2))

                # Keep buffer at 300 samples (5 minutes of data at 1Hz)
                for key in telemetry_history:
                    if len(telemetry_history[key]) > 300:
                        telemetry_history[key].pop(0)

            # Emit live telemetry to web dashboard at 10Hz
            socketio.emit('telemetry', build_telemetry_packet())

        except Exception as e:
            logger.error(f"Telemetry worker error: {e}")

        time.sleep(0.1)


def build_telemetry_packet():
    return {
        **drone_state,
        "waypoints": waypoints,
        "flight_path_tail": flight_path[-50:] if len(flight_path) > 50 else flight_path,
        "victims": victims,
        "history": {k: telemetry_history[k][-60:] for k in telemetry_history},
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# REST API Routes
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    return jsonify({
        "simulation": drone_state["simulation"],
        "connected": drone_state["connected"],
        "mavlink_available": MAVLINK_AVAILABLE,
        "mode": drone_state["mode"],
        "armed": drone_state["armed"],
    })


@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json or {}
    port = data.get('port', 'COM3')
    baud = data.get('baud', 921600)
    conn_str = f"{port}"
    success, msg = mav_manager.connect(conn_str, baud=baud)
    return jsonify({"success": success, "message": msg})


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    mav_manager.disconnect()
    drone_state["simulation"] = True
    drone_state["connected"] = False
    return jsonify({"success": True})


@app.route('/api/arm', methods=['POST'])
def api_arm():
    data = request.json or {}
    arm = data.get('arm', True)
    if drone_state["simulation"]:
        drone_state["armed"] = arm
        drone_state["status_text"] = "ARMED" if arm else "DISARMED"
        sim_engine.start_time = None if not arm else sim_engine.start_time
        if arm:
            drone_state["battery_remaining"] = 100
            drone_state["battery_voltage"] = BATTERY_MAX_VOLTAGE
            drone_state["battery_percentage"] = 100
            drone_state["battery_consumed_mah"] = 0
        sim_engine._log_event(f"Drone {'ARMED' if arm else 'DISARMED'}", "INFO")
        return jsonify({"success": True, "armed": drone_state["armed"], "simulation": True, "message": drone_state["status_text"]})
    else:
        ok = mav_manager.arm_disarm(arm)
        message = mav_manager.last_arm_message or drone_state.get("status_text", "")
        return jsonify({"success": ok, "armed": drone_state["armed"], "simulation": False, "message": message})


@app.route('/api/mode', methods=['POST'])
def api_mode():
    data = request.json or {}
    mode = data.get('mode', 'STABILIZE')
    valid_modes = ["STABILIZE", "LOITER", "AUTO", "RTL", "GUIDED", "LAND", "ALT_HOLD", "ACRO", "POSHOLD"]
    if mode not in valid_modes:
        return jsonify({"success": False, "error": "Invalid mode"})
    drone_state["mode"] = mode
    sim_engine._log_event(f"Mode changed to {mode}", "INFO")
    if drone_state["simulation"]:
        return jsonify({"success": True})
    else:
        ok = mav_manager.set_mode(mode)
        return jsonify({"success": ok})


@app.route('/api/start_mission', methods=['POST'])
def api_start_mission():
    if not drone_state["armed"]:
        return jsonify({"success": False, "error": "Drone must be armed first"})
    for wp in waypoints:
        wp["reached"] = False
    drone_state["total_waypoints"] = len(waypoints)
    if not drone_state["simulation"] and mav_manager.connected:
        ok, msg = mav_manager.upload_mission(waypoints)
        if not ok:
            return jsonify({"success": False, "error": msg})
        if not mav_manager.set_mode("AUTO"):
            return jsonify({"success": False, "error": "Failed to set AUTO mode"})
        drone_state["mode"] = "AUTO"
        drone_state["mission_status"] = "ACTIVE"
        sim_engine._log_event("Mission uploaded and AUTO mode engaged", "INFO")
        return jsonify({"success": True, "message": "Mission uploaded to Pixhawk"})
    sim_engine.wp_index = 0
    sim_engine.mission_active = True
    drone_state["mode"] = "AUTO"
    drone_state["mission_status"] = "ACTIVE"
    sim_engine._log_event("Mission started — AUTO mode engaged", "INFO")
    return jsonify({"success": True})


@app.route('/api/rtl', methods=['POST'])
def api_rtl():
    drone_state["mode"] = "RTL"
    sim_engine.mission_active = False
    drone_state["mission_status"] = "RTL"
    sim_engine._log_event("Return-to-Launch initiated", "WARNING")
    if not drone_state["simulation"]:
        mav_manager.set_mode("RTL")
    return jsonify({"success": True})


@app.route('/api/abort', methods=['POST'])
def api_abort():
    drone_state["mode"] = "LOITER"
    sim_engine.mission_active = False
    drone_state["mission_status"] = "ABORTED"
    sim_engine._log_event("MISSION ABORTED — Entering LOITER", "CRITICAL")
    if not drone_state["simulation"]:
        mav_manager.set_mode("LOITER")
    return jsonify({"success": True})


@app.route('/api/calibrate', methods=['POST'])
def api_calibrate():
    data = request.json or {}
    calibration_type = data.get('type', 'all')

    if drone_state["simulation"]:
        sim_engine._log_event(f"Simulation calibration requested: {calibration_type}", "INFO")
        return jsonify({"success": True, "message": f"Simulation calibration noted: {calibration_type}"})

    ok, msg = mav_manager.calibrate_preflight(calibration_type)
    return jsonify({"success": ok, "message": msg})


@app.route('/api/test_profile', methods=['POST'])
def api_test_profile():
    if drone_state["simulation"]:
        sim_engine._log_event("Simulation test profile requested", "INFO")
        return jsonify({"success": True, "message": "Simulation test profile noted"})

    ok, msg = mav_manager.apply_test_flight_profile()
    return jsonify({"success": ok, "message": msg})


@app.route('/api/update_waypoints', methods=['POST'])
def api_update_waypoints():
    global waypoints
    data = request.json or {}
    new_wps = data.get('waypoints', [])
    if new_wps:
        waypoints = new_wps
        if not drone_state["simulation"] and mav_manager.connected:
            ok, msg = mav_manager.upload_mission(waypoints)
            if not ok:
                return jsonify({"success": False, "error": msg})
    return jsonify({"success": True, "count": len(waypoints)})


@app.route('/api/add_waypoint', methods=['POST'])
def api_add_waypoint():
    data = request.json or {}
    lat = data.get('lat')
    lon = data.get('lon')
    alt = data.get('alt', 20)
    if lat is None or lon is None:
        return jsonify({"success": False, "error": "lat and lon are required"})
    waypoint = {"lat": float(lat), "lon": float(lon), "alt": float(alt), "action": "WAYPOINT", "reached": False}
    waypoints.append(waypoint)
    if not drone_state["simulation"] and mav_manager.connected:
        ok, msg = mav_manager.upload_mission(waypoints)
        if not ok:
            return jsonify({"success": False, "error": msg})
    return jsonify({"success": True, "waypoint": waypoint, "count": len(waypoints)})


@app.route('/api/upload_mission', methods=['POST'])
def api_upload_mission():
    data = request.json or {}
    mission_items = data.get('waypoints', waypoints)
    if not mav_manager.connected or drone_state["simulation"]:
        return jsonify({"success": False, "error": "Pixhawk not connected"})
    ok, msg = mav_manager.upload_mission(mission_items)
    return jsonify({"success": ok, "message": msg})


@app.route('/api/clear_mission', methods=['POST'])
def api_clear_mission():
    for wp in waypoints:
        wp["reached"] = False
    victims.clear()
    drone_state["victims_detected"] = 0
    drone_state["mission_status"] = "IDLE"
    sim_engine.wp_index = 0
    sim_engine._log_event("Mission cleared", "INFO")
    return jsonify({"success": True})


@app.route('/api/telemetry_snapshot')
def api_telemetry_snapshot():
    return jsonify(build_telemetry_packet())


@app.route('/api/flight_log')
def api_flight_log():
    return jsonify(mission_log[-200:])


@app.route('/api/victims')
def api_victims():
    return jsonify(victims)


# ─────────────────────────────────────────────────────────────────────────────
# Excel Export
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/export_excel')
def export_excel():
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:

            # Sheet 1 — Mission Summary
            summary_data = {
                "Parameter": [
                    "Mission Date", "Drone Mode", "Armed Status",
                    "Total Flight Time (s)", "Total Distance (m)",
                    "Victims Detected", "Mission Status",
                    "Battery Consumed (mAh)", "Battery Remaining (%)",
                    "Min Voltage (V)", "Max Altitude (m)", "Max Speed (m/s)",
                    "GPS Fix Type", "Satellites", "Failure Mode",
                    "Failure Component", "Firmware Version", "Frame Type",
                    "Autopilot", "Total Waypoints", "Waypoints Reached",
                ],
                "Value": [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    drone_state["mode"], str(drone_state["armed"]),
                    drone_state["flight_time"],
                    round(drone_state["distance_to_home"], 1),
                    drone_state["victims_detected"],
                    drone_state["mission_status"],
                    round(drone_state["battery_consumed_mah"], 1),
                    drone_state["battery_remaining"],
                    round(drone_state["battery_voltage"], 2),
                    round(max(telemetry_history["altitude"] or [0]), 1),
                    round(max(telemetry_history["speed"] or [0]), 1),
                    drone_state["gps_fix"], drone_state["satellites"],
                    drone_state.get("failure_mode", "None"),
                    drone_state.get("failure_component", "None"),
                    drone_state["firmware_version"], drone_state["frame_type"],
                    drone_state["autopilot_type"],
                    len(waypoints), sum(1 for w in waypoints if w["reached"]),
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="Mission Summary", index=False)

            # Sheet 2 — Telemetry Timeline
            if telemetry_history["time"]:
                telem_df = pd.DataFrame({
                    "Time": telemetry_history["time"],
                    "Altitude_m": telemetry_history["altitude"],
                    "Speed_ms": telemetry_history["speed"],
                    "Battery_%": telemetry_history["battery"],
                    "Voltage_V": telemetry_history["voltage"],
                    "Current_A": telemetry_history["current"],
                    "Roll_deg": telemetry_history["roll"],
                    "Pitch_deg": telemetry_history["pitch"],
                    "ClimbRate_ms": telemetry_history["climb_rate"],
                })
                telem_df.to_excel(writer, sheet_name="Telemetry Timeline", index=False)

            # Sheet 3 — System Events Log
            if mission_log:
                log_df = pd.DataFrame(mission_log)
                log_df.to_excel(writer, sheet_name="System Events Log", index=False)

            # Sheet 4 — Flight Path (GPS Coordinates)
            if flight_path:
                path_df = pd.DataFrame(flight_path)
                path_df.to_excel(writer, sheet_name="GPS Flight Path", index=False)

            # Sheet 5 — Victims Detected
            if victims:
                vict_df = pd.DataFrame(victims)
                vict_df.to_excel(writer, sheet_name="Victims Detected", index=False)
            else:
                pd.DataFrame({"Status": ["No victims detected in this mission"]}).to_excel(
                    writer, sheet_name="Victims Detected", index=False)

            # Sheet 6 — Waypoints
            wp_data = []
            for i, wp in enumerate(waypoints):
                wp_data.append({
                    "WP_Index": i + 1,
                    "Latitude": wp["lat"],
                    "Longitude": wp["lon"],
                    "Altitude_m": wp["alt"],
                    "Action": wp["action"],
                    "Reached": wp["reached"],
                })
            pd.DataFrame(wp_data).to_excel(writer, sheet_name="Waypoints", index=False)

            # Sheet 7 — Component Health
            health_df = pd.DataFrame([
                {"Component": k, "Status": v}
                for k, v in drone_state["component_health"].items()
            ])
            health_df.to_excel(writer, sheet_name="Component Health", index=False)

            # Sheet 8 — Failure Analysis
            fail_data = {
                "Field": [
                    "Failure Mode", "Failure Component",
                    "Failure Location (Lat)", "Failure Location (Lon)",
                    "Failure Time", "Battery at Failure (%)",
                    "Altitude at Failure (m)", "Last Status Text"
                ],
                "Value": [
                    drone_state.get("failure_mode", "None"),
                    drone_state.get("failure_component", "None"),
                    drone_state.get("lat", "N/A"),
                    drone_state.get("lon", "N/A"),
                    datetime.now().isoformat() if drone_state.get("failure_mode") else "N/A",
                    drone_state["battery_remaining"],
                    round(drone_state["rel_alt"], 1),
                    drone_state["status_text"]
                ]
            }
            pd.DataFrame(fail_data).to_excel(writer, sheet_name="Failure Analysis", index=False)

        output.seek(0)
        filename = f"drone_mission_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Excel export error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Socket.IO Events
# ─────────────────────────────────────────────────────────────────────────────
@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    emit('telemetry', build_telemetry_packet())
    emit('system_event', {
        "time": datetime.now().strftime("%H:%M:%S"),
        "message": "GCS Client connected",
        "level": "INFO"
    })


@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")


@socketio.on('request_telemetry')
def handle_request_telemetry():
    emit('telemetry', build_telemetry_packet())


# ─────────────────────────────────────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    telem_thread = threading.Thread(target=telemetry_worker, daemon=True)
    telem_thread.start()
    logger.info("=" * 60)
    logger.info("  DRONE GCS SERVER STARTING")
    logger.info("  Open http://localhost:5000 in your browser")
    logger.info("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)