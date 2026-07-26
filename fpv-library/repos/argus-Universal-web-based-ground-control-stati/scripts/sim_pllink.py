#!/usr/bin/env python3
"""
Argus 飞控模拟器 — GCS 仿真测试

用法:
    python3 sim_pllink.py [端口]       (默认 5770)

GCS 连接:
    端口栏填 tcp:localhost:5770 → 点"连接"

模拟行为:
    - 启动后自动发送遥测 (姿态/GPS/电池/航向)
    - 支持解锁/锁定、模式切换、任务上传
    - AUTO 模式自动沿航点飞行，到达后推进下一航点
    - RTL 模式返回起飞点并降落
    - 电池缓慢消耗，<20% 触发 STATUSTEXT 告警
    - 定期发送 ArduPilot 风格 STATUSTEXT 测试过滤器
"""

import math
import random
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.pllink_proto import bm as _bm
from backend.pllink_proto import pld, ple


def bm(mid, p, s, ce):
    return _bm(mid, p, s, ce, sysid=1)


COPTER_MODES = {0: "STABILIZE", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND"}


class Simulator:
    def __init__(self):
        self.armed = False
        self.mode = 5
        self.vtype = 2
        self.sysid = 1

        self.lat = 34.258330
        self.lon = 108.942500
        self.alt = 0.0
        self.home_lat = self.lat
        self.home_lon = self.lon

        self.roll = self.pitch = 0.0
        self.yaw = 45.0
        self.vx = self.vy = self.vz = 0.0

        self.voltage = 25.2
        self.current = 0.0
        self.remaining = 95

        self.gps_fix = 3
        self.sats = 14

        self.mission = []
        self.mission_seq = 0
        self.target_idx = -1

        self.fence = []

        self.params = {
            "BATT_CAPACITY": 5000.0,
            "BATT_MONITOR": 4.0,
            "ARMING_CHECK": 1.0,
            "ARMING_REQUIRE": 1.0,
            "FS_THR_ENABLE": 1.0,
            "FS_THR_VALUE": 975.0,
            "FS_GCS_ENABLE": 1.0,
            "FS_BATT_ENABLE": 2.0,
            "FS_BATT_MAH": 0.0,
            "FS_BATT_VOLTAGE": 10.5,
            "ATC_RAT_RLL_P": 0.135,
            "ATC_RAT_RLL_I": 0.135,
            "ATC_RAT_RLL_D": 0.0036,
            "ATC_RAT_PIT_P": 0.135,
            "ATC_RAT_PIT_I": 0.135,
            "ATC_RAT_PIT_D": 0.0036,
            "ATC_RAT_YAW_P": 0.18,
            "ATC_RAT_YAW_I": 0.018,
            "ATC_RAT_YAW_D": 0.0,
            "INS_GYRO_FILTER": 20.0,
            "INS_ACCEL_FILTER": 20.0,
            "INS_LOG_BAT_MASK": 3.0,
            "LOG_BITMASK": 65535.0,
            "LOG_BACKEND_TYPE": 1.0,
            "RC1_MAX": 2000.0,
            "RC1_MIN": 1000.0,
            "RC1_TRIM": 1500.0,
            "RC2_MAX": 2000.0,
            "RC2_MIN": 1000.0,
            "RC2_TRIM": 1500.0,
            "WPNAV_SPEED": 500.0,
            "WPNAV_SPEED_UP": 250.0,
            "WPNAV_SPEED_DN": 150.0,
            "RTL_ALT": 1500.0,
            "RTL_SPEED": 0.0,
            "FLTMODE1": 5.0,
            "FLTMODE2": 5.0,
            "FLTMODE3": 6.0,
            "FLTMODE4": 3.0,
            "FLTMODE5": 0.0,
            "FLTMODE6": 9.0,
        }
        self._param_names = sorted(self.params.keys())

        self._fake_logs = [
            {"id": 1, "size": 2048, "time_utc": 1748000000},
            {"id": 2, "size": 5120, "time_utc": 1748100000},
            {"id": 3, "size": 900, "time_utc": 1748200000},
        ]
        self._log_send_active = False
        self._log_send_id = -1

        self.sq = 0
        self.t = 0.0
        self.takeoff_alt = 30.0
        self._status_queue = []
        self._last_bat_warn = 0
        self._startup_msgs = [
            (1.0, "Initialising"),
            (2.0, "Calibrating barometer"),
            (3.0, "Barometer not healthy"),
            (4.0, "EKF3 IMU0 is using GPS"),
            (5.0, "Ready to fly"),
        ]

    def tick(self, dt):
        self.t += dt

        self.roll = 2.0 * math.sin(self.t * 0.5) + random.uniform(-0.3, 0.3)
        self.pitch = 1.5 * math.cos(self.t * 0.7) + random.uniform(-0.3, 0.3)

        for msg_t, msg in self._startup_msgs:
            if self.t >= msg_t and self.t < msg_t + dt:
                self._status_queue.append(msg)
        if self._startup_msgs and self.t > self._startup_msgs[-1][0]:
            self._startup_msgs = []

        if self.armed:
            self.current = 12.0 + random.uniform(-1, 3)
            self.voltage = 25.2 - (100 - self.remaining) * 0.06
            self.remaining = max(0, self.remaining - 0.008 * dt)

            if self.remaining < 20 and self.t - self._last_bat_warn > 30:
                self._status_queue.append("Low Battery")
                self._last_bat_warn = self.t

            if self.mode == 3 and self.mission and self.target_idx >= 0:
                self._fly_mission(dt)
            elif self.mode == 6:
                self._fly_to(self.home_lat, self.home_lon, 0, dt, land=True)
            elif self.mode == 9:
                if self.alt > 0.3:
                    self.vz = -1.5
                    self.alt = max(0, self.alt + self.vz * dt)
                else:
                    self.alt = self.vz = 0
                    self.armed = False
                    self._status_queue.append("Crash: Disarming")
        else:
            self.current = 0
            self.vx = self.vy = self.vz = 0

    def _fly_mission(self, dt):
        if self.target_idx >= len(self.mission):
            return
        wp = self.mission[self.target_idx]
        if wp is None:
            return
        if wp["cmd"] == 16 and wp["seq"] == 0:
            self.target_idx += 1
            self.mission_seq = self.mission[self.target_idx]["seq"] if self.target_idx < len(self.mission) else 0
            return
        if wp["cmd"] == 22:
            if self.alt < wp["alt"] - 0.5:
                self.vz = 2.5
                self.alt += self.vz * dt
                self.vx = self.vy = 0
            else:
                self.alt = wp["alt"]
                self.vz = 0
                self._advance_wp()
        elif wp["cmd"] == 16:
            arrived = self._fly_to(wp["lat"], wp["lon"], wp["alt"], dt)
            if arrived:
                self._advance_wp()
        elif wp["cmd"] == 20:
            arrived = self._fly_to(self.home_lat, self.home_lon, 0, dt, land=True)
            if arrived and self.alt < 0.5:
                self.armed = False
                print("  [SIM] 任务完成, 已锁定")
        elif wp["cmd"] == 181:
            print("  [SIM] 投放执行 (seq %d)" % wp["seq"])
            self._advance_wp()
        else:
            self._advance_wp()

    def _advance_wp(self):
        self.target_idx += 1
        if self.target_idx < len(self.mission):
            wp = self.mission[self.target_idx]
            self.mission_seq = wp["seq"]
            print("  [SIM] -> 航点 seq=%d cmd=%d" % (wp["seq"], wp["cmd"]))
        else:
            print("  [SIM] 任务完成")

    def _fly_to(self, tlat, tlon, talt, dt, land=False):
        dlat = (tlat - self.lat) * 111320
        dlon = (tlon - self.lon) * 111320 * math.cos(math.radians(self.lat))
        dist = math.sqrt(dlat * dlat + dlon * dlon)

        speed = 5.0
        arrived = False
        if dist > 1.5:
            ratio = min(speed * dt / dist, 1.0)
            self.lat += (tlat - self.lat) * ratio
            self.lon += (tlon - self.lon) * ratio
            self.vx = dlat / dist * speed
            self.vy = dlon / dist * speed
            self.yaw = math.degrees(math.atan2(dlon, dlat)) % 360
        else:
            self.vx = self.vy = 0
            arrived = True

        if talt > 0 and abs(self.alt - talt) > 0.5:
            self.vz = 2.0 if talt > self.alt else -2.0
            self.alt += self.vz * dt
        elif land:
            if self.alt > 0.3:
                self.vz = -1.5
                self.alt = max(0, self.alt + self.vz * dt)
            else:
                self.alt = self.vz = 0
        else:
            self.vz = 0

        return arrived

    # --- MAVLink frame builders ---

    def msg_heartbeat(self):
        base = 0x80 if self.armed else 0
        p = struct.pack("<IBBBBB", self.mode, self.vtype, 3, base, 0, 3)
        return bm(0, p, self.sq, 50)

    def msg_attitude(self):
        p = struct.pack(
            "<Iffffff",
            int(self.t * 1000),
            math.radians(self.roll),
            math.radians(self.pitch),
            math.radians(self.yaw),
            0,
            0,
            0,
        )
        return bm(30, p, self.sq, 39)

    def msg_global_pos(self):
        p = struct.pack(
            "<IiiiihhhH",
            int(self.t * 1000),
            int(self.lat * 1e7),
            int(self.lon * 1e7),
            int((self.alt + 400) * 1000),
            int(self.alt * 1000),
            int(self.vx * 100),
            int(self.vy * 100),
            int(self.vz * 100),
            int(self.yaw * 100),
        )
        return bm(33, p, self.sq, 104)

    def msg_gps_raw(self):
        gs = math.sqrt(self.vx**2 + self.vy**2)
        cog = int(self.yaw * 100) if gs > 0.5 else 0
        p = struct.pack(
            "<QiiiHHHHBB",
            int(self.t * 1e6),
            int(self.lat * 1e7),
            int(self.lon * 1e7),
            int((self.alt + 400) * 1000),
            150,
            200,
            int(gs * 100),
            cog,
            self.gps_fix,
            self.sats,
        )
        return bm(24, p, self.sq, 24)

    def msg_sys_status(self):
        p = struct.pack(
            "<IIIHHhHHHHHHb",
            0xFFFFFFFF,
            0xFFFFFFFF,
            0xFFFFFFFF,
            500,
            int(self.voltage * 1000),
            int(self.current * 100),
            0,
            0,
            0,
            0,
            0,
            0,
            max(0, min(100, int(self.remaining))),
        )
        return bm(1, p, self.sq, 124)

    def msg_rc_channels(self):
        ch = [1500] * 18
        ch[0] = 1500 + int(50 * math.sin(self.t * 0.3))
        ch[1] = 1500 + int(50 * math.cos(self.t * 0.4))
        ch[2] = 1200 + int(300 * (1 + math.sin(self.t * 0.1)) / 2) if self.armed else 1000
        ch[3] = 1500 + int(30 * math.sin(self.t * 0.2))
        ch[4] = 1800 if self.armed else 1000
        # Wire-sorted RC_CHANNELS layout: time_boot_ms(u32) at 0-3, chan1..chan18
        # (u16 x 18) at 4-39, chancount(u8) at 40, rssi(u8) at 41 = 42 bytes.
        # Previous code put chancount right after time, shifting all channels by
        # one byte and producing junk values when the backend (correctly) read
        # chan1 at offset 4.
        p = struct.pack("<I", int(self.t * 1000))
        for c in ch:
            p += struct.pack("<H", c)
        p += struct.pack("<BB", 16, 255)
        return bm(65, p, self.sq, 118)

    def msg_servo_output(self):
        servos = [1500] * 16
        if self.armed:
            servos[0] = 1500 + int(100 * math.sin(self.t * 0.5))
            servos[1] = 1500 + int(100 * math.cos(self.t * 0.6))
            servos[2] = 1200 + int(300 * (1 + math.sin(self.t * 0.1)) / 2)
            servos[3] = 1500 + int(50 * math.sin(self.t * 0.3))
        else:
            servos = [1000] * 4 + [1500] * 12
        p = struct.pack("<I", int(self.t * 1e6))
        for s in servos[:8]:
            p += struct.pack("<H", s)
        p += struct.pack("<B", 0)
        for s in servos[8:]:
            p += struct.pack("<H", s)
        return bm(36, p, self.sq, 222)

    def msg_vibration(self):
        vx = 5.0 + random.uniform(-2, 2) + (15.0 if self.armed else 0)
        vy = 4.0 + random.uniform(-2, 2) + (12.0 if self.armed else 0)
        vz = 8.0 + random.uniform(-3, 3) + (20.0 if self.armed else 0)
        p = struct.pack("<Qfff", int(self.t * 1e6), vx, vy, vz)
        p += struct.pack("<III", 0, 0, 0)
        return bm(241, p, self.sq, 90)

    def msg_ekf_status(self):
        vel = 0.02 + random.uniform(-0.005, 0.005)
        pos_h = 0.03 + random.uniform(-0.005, 0.005)
        pos_v = 0.05 + random.uniform(-0.01, 0.01)
        comp = 0.01 + random.uniform(-0.003, 0.003)
        terr = 0.0
        flags = 0x01FF  # attitude + velocity + position all OK
        p = struct.pack("<fffffH", vel, pos_h, pos_v, comp, terr, flags)
        # EKF_STATUS_REPORT is msg_id 193, not 74 (VFR_HUD). Previous code
        # used 74, so the backend's handle_vfr_hud read EKF variances as
        # airspeed/climb (telemetry overlay garbage) AND handle_ekf_status
        # at msg_id 193 was never invoked (EKF panel showed no data).
        return bm(193, p, self.sq, 71)

    def msg_wind(self):
        direction = 225.0 + random.uniform(-10, 10)
        speed = 3.5 + random.uniform(-0.5, 0.5)
        speed_z = 0.1 + random.uniform(-0.05, 0.05)
        p = struct.pack("<fff", direction, speed, speed_z)
        # WIND (id 168) crc_extra is 1 per MAVLink common.xml. Previous value
        # 231 was wrong — frames were accepted only because PL-Link framing
        # doesn't validate the inner MAVLink CRC. On a raw-MAVLink link the
        # frame would be dropped silently.
        return bm(168, p, self.sq, 1)

    def msg_vfr_hud(self):
        gs = math.sqrt(self.vx**2 + self.vy**2)
        airspeed = gs + random.uniform(-0.2, 0.2)
        climb = -self.vz if self.vz else 0.0
        throttle = max(0, min(100, int(50 + (self.alt / 1.0) if self.armed else 0)))
        # VFR_HUD wire-sorted layout: airspeed(f), groundspeed(f), alt(f),
        # climb(f), heading(i16), throttle(u16) = 20 bytes
        p = struct.pack("<ffffhH", airspeed, gs, self.alt, climb, int(self.yaw) % 360, throttle)
        return bm(74, p, self.sq, 20)

    def msg_terrain_report(self):
        terrain_msl = 400.0 + random.uniform(-2, 2)
        # `self.alt` is alt-above-home (we publish it as relative_alt in
        # msg_global_pos), and there is no separate self.alt_rel attribute.
        # The previous reference raised AttributeError if anyone wired this
        # message into the broadcast loop.
        current_height = max(0, self.alt + random.uniform(-0.5, 0.5))
        p = struct.pack("<iiffHHH", int(self.lat * 1e7), int(self.lon * 1e7), terrain_msl, current_height, 100, 0, 100)
        return bm(136, p, self.sq, 1)

    def msg_mission_current(self):
        p = struct.pack("<H", self.mission_seq)
        return bm(42, p, self.sq, 28)

    def msg_home_position(self):
        p = struct.pack("<iii", int(self.home_lat * 1e7), int(self.home_lon * 1e7), 400000)
        p += bytes(52 - len(p))
        return bm(242, p, self.sq, 104)

    def msg_statustext(self, text, severity=6):
        tb = text.encode("ascii", "replace")[:50]
        p = struct.pack("<B", severity) + tb + bytes(50 - len(tb))
        return bm(253, p, self.sq, 83)

    def msg_command_ack(self, cmd, result):
        p = struct.pack("<HB", cmd, result)
        return bm(77, p, self.sq, 143)

    def msg_mission_ack(self, mtype, mission_type=0):
        p = struct.pack("<BBBB", 255, 190, mtype, mission_type)
        return bm(47, p, self.sq, 153)

    def msg_mission_request(self, seq, mission_type=0):
        p = struct.pack("<HBBB", seq, 255, 190, mission_type)
        return bm(51, p, self.sq, 196)

    def msg_wp_reached(self, seq):
        p = struct.pack("<H", seq)
        return bm(46, p, self.sq, 11)

    def msg_autopilot_version(self):
        fw_ver = (4 << 24) | (5 << 16) | (7 << 8) | 255
        git_hash = b"a1b2c3d4"
        # MAVLink 2 wire-sorted layout (largest first):
        #   capabilities(Q @0), uid(Q @8), flight_sw(I @16), middleware_sw(I @20),
        #   os_sw(I @24), board_version(I @28), vendor_id(H @32), product_id(H @34),
        #   flight_custom_version[8] (@36), middleware_custom_version[8] (@44),
        #   os_custom_version[8] (@52). Total 60 bytes (no extensions sent).
        # Previous code placed flight_sw_version at offset 8 (UID slot) so the
        # backend (which correctly reads offset 16) saw "0" and reported
        # firmware v0.0.0 in sim mode.
        p = struct.pack("<Q", 0xFFFF)  # 0-7   capabilities
        p += struct.pack("<Q", 0x1234567890ABCDEF)  # 8-15  uid
        p += struct.pack("<IIII", fw_ver, 0, 0, 56)  # 16-31 flight/middle/os/board
        p += struct.pack("<HH", 0, 0)  # 32-35 vendor, product
        p += git_hash + bytes(8) + bytes(8)  # 36-59 3x 8-byte custom_version
        return bm(148, p, self.sq, 178)

    def msg_mission_item_int(self, wp):
        frame = 3 if wp["cmd"] in (16, 18, 19, 21, 22) else 2
        lat7 = int(wp.get("lat", 0) * 1e7)
        lon7 = int(wp.get("lon", 0) * 1e7)
        p = struct.pack(
            "<ffffiifHHBBBBBB",
            float(wp.get("p1", 0)),
            float(wp.get("p2", 0)),
            0.0,
            0.0,
            lat7,
            lon7,
            float(wp.get("alt", 0)),
            wp["seq"],
            wp["cmd"],
            255,
            190,
            frame,
            1 if wp["seq"] == 0 else 0,
            1,
            0,
        )
        return bm(73, p, self.sq, 38)

    def msg_param_value(self, name, value, index, total):
        name_bytes = name.encode("ascii")[:16].ljust(16, b"\x00")
        p = struct.pack("<f", value) + struct.pack("<HH", total, index) + name_bytes + struct.pack("<B", 9)
        return bm(22, p, self.sq, 220)

    def msg_log_entry(self, log_id, size, time_utc, num_logs, last_log_num):
        p = struct.pack("<IIHHH", time_utc, size, log_id, num_logs, last_log_num)
        return bm(118, p, self.sq, 56)

    def msg_log_data(self, log_id, ofs, data_bytes):
        count = len(data_bytes)
        padded = data_bytes + bytes(90 - count)
        p = struct.pack("<IHB", ofs, log_id, count) + padded
        return bm(120, p, self.sq, 134)

    # --- Command handlers ---

    def handle_mavlink(self, payload):
        if len(payload) < 12 or payload[0] != 0xFD:
            return []
        mid = payload[7] | (payload[8] << 8) | (payload[9] << 16)
        p = payload[10 : 10 + payload[1]]
        resp = []

        if mid == 0:
            pass
        elif mid == 43 and len(p) >= 2:
            count = len(self.mission)
            resp.append(bm(44, struct.pack("<HBBB", count, 255, 190, 0), self.sq, 221))
            print("  [SIM] 任务下载请求: %d 项" % count)
        elif mid == 51 and len(p) >= 4:
            seq = struct.unpack_from("<H", p, 0)[0]
            if seq < len(self.mission) and self.mission[seq] is not None:
                resp.append(self.msg_mission_item_int(self.mission[seq]))
        elif mid == 21 and len(p) >= 2:
            total = len(self._param_names)
            for i, name in enumerate(self._param_names):
                resp.append(self.msg_param_value(name, self.params[name], i, total))
            print("  [SIM] 参数列表请求: 发送 %d 个" % total)
        elif mid == 23 and len(p) >= 23:
            value = struct.unpack_from("<f", p, 0)[0]
            name = bytes(p[6:22]).split(b"\x00")[0].decode("ascii", "replace")
            if name in self.params:
                self.params[name] = value
                idx = self._param_names.index(name)
                resp.append(self.msg_param_value(name, value, idx, len(self._param_names)))
                print("  [SIM] 参数设置: %s = %.4g" % (name, value))
        elif mid == 76 and len(p) >= 29:
            params = struct.unpack_from("<fffffff", p, 0)
            cmd = struct.unpack_from("<H", p, 28)[0]
            resp = self._handle_cmd(cmd, params)
        elif mid == 11 and len(p) >= 5:
            mode = struct.unpack_from("<I", p, 0)[0]
            self.mode = mode
            mn = COPTER_MODES.get(mode, "?")
            print("  [SIM] 模式 -> %s (%d)" % (mn, mode))
        elif mid == 44 and len(p) >= 3:
            count = struct.unpack_from("<H", p, 0)[0]
            mission_type = p[4] if len(p) >= 5 else 0
            if mission_type == 1:
                self.fence = [None] * count
                print("  [SIM] 围栏接收: 预计 %d 项" % count)
                if count > 0:
                    resp.append(self.msg_mission_request(0, mission_type=1))
            else:
                self.mission = [None] * count
                self.target_idx = -1
                self.mission_seq = 0
                print("  [SIM] 任务接收: 预计 %d 项" % count)
                if count > 0:
                    resp.append(self.msg_mission_request(0))
        elif mid == 73 and len(p) >= 35:
            mission_type = p[37] if len(p) >= 38 else 0
            if mission_type == 1:
                resp = self._handle_fence_item(p)
            else:
                resp = self._handle_mission_item(p)
        elif mid == 45:
            self.mission = []
            self.target_idx = -1
            self.mission_seq = 0
            print("  [SIM] 任务已清除")
            resp.append(self.msg_mission_ack(0))
        elif mid == 84:
            pass
        elif mid == 117 and len(p) >= 6:
            num = len(self._fake_logs)
            last_id = self._fake_logs[-1]["id"] if self._fake_logs else 0
            for lg in self._fake_logs:
                resp.append(self.msg_log_entry(lg["id"], lg["size"], lg["time_utc"], num, last_id))
            print("  [SIM] 日志列表请求: 发送 %d 条" % num)
        elif mid == 119 and len(p) >= 12:
            ofs = struct.unpack_from("<I", p, 0)[0]
            count = struct.unpack_from("<I", p, 4)[0]
            log_id = struct.unpack_from("<H", p, 8)[0]
            lg = next((l for l in self._fake_logs if l["id"] == log_id), None)
            if lg:
                self._log_send_active = True
                self._log_send_id = log_id
                total_size = lg["size"]
                cur = ofs
                end = min(ofs + count, total_size)
                while cur < end:
                    chunk = min(90, end - cur)
                    data_bytes = bytes([(cur + i) & 0xFF for i in range(chunk)])
                    resp.append(self.msg_log_data(log_id, cur, data_bytes))
                    cur += chunk
                print("  [SIM] 日志数据: id=%d ofs=%d count=%d" % (log_id, ofs, count))
        elif mid == 122:
            # LOG_REQUEST_END = 122 (per MAVLink common.xml). The backend's
            # cmd_log_cancel sends 122; using 126 here (SERIAL_CONTROL) meant
            # the sim never actually saw a cancel.
            self._log_send_active = False
            self._log_send_id = -1
            print("  [SIM] 日志传输取消")
        else:
            pass

        return resp

    def _handle_cmd(self, cmd, params):
        resp = []
        if cmd == 400:
            if params[0] > 0.5:
                if self.gps_fix >= 3:
                    self.armed = True
                    self.home_lat = self.lat
                    self.home_lon = self.lon
                    print("  [SIM] 已解锁")
                    resp.append(self.msg_command_ack(400, 0))
                    resp.append(self.msg_statustext("Ready to FLY"))
                else:
                    print("  [SIM] 解锁拒绝: GPS 不足")
                    resp.append(self.msg_command_ack(400, 4))
                    resp.append(self.msg_statustext("PreArm: Need 3D Fix"))
            else:
                force = params[1] > 21000
                self.armed = False
                print("  [SIM] 已锁定%s" % (" (强制)" if force else ""))
                resp.append(self.msg_command_ack(400, 0))
        elif cmd == 22:
            alt = params[6]
            self.takeoff_alt = alt if alt > 0 else 30
            print("  [SIM] 起飞: %.0fm" % self.takeoff_alt)
            resp.append(self.msg_command_ack(22, 0))
        elif cmd == 300:
            if self.mission:
                self.target_idx = 0
                self.mission_seq = 0
                print("  [SIM] 任务开始 (%d 项)" % len(self.mission))
            resp.append(self.msg_command_ack(300, 0))
        elif cmd == 511:
            resp.append(self.msg_command_ack(511, 0))
        elif cmd == 512:
            msg_id = int(params[0])
            if msg_id == 148:
                resp.append(self.msg_autopilot_version())
            resp.append(self.msg_command_ack(512, 0))
        elif cmd == 181:
            state = "ON" if params[1] > 0.5 else "OFF"
            print("  [SIM] 继电器 %s" % state)
            resp.append(self.msg_command_ack(181, 0))
        elif cmd == 42424:
            print("  [SIM] 罗盘校准 (onboard)")
            resp.append(self.msg_command_ack(42424, 0))
            self._status_queue.append("Compass calibration started")
            self._status_queue.append("Rotate vehicle...")
            self._status_queue.append("Compass calibration complete")
        elif cmd == 42425:
            print("  [SIM] 接受罗盘校准")
            resp.append(self.msg_command_ack(42425, 0))
        elif cmd == 42426:
            print("  [SIM] 取消罗盘校准")
            resp.append(self.msg_command_ack(42426, 0))
        elif cmd == 241:
            p1, _, p3, _, p5 = params[0], params[1], params[2], params[3], params[4]
            if p1 > 0.5:
                print("  [SIM] 陀螺仪校准")
                resp.append(self.msg_command_ack(241, 0))
                self._status_queue.append("Gyro calibration started")
                self._status_queue.append("Gyro calibration complete")
            elif p3 > 0.5:
                print("  [SIM] 气压计校准")
                resp.append(self.msg_command_ack(241, 0))
                self._status_queue.append("Barometer calibration complete")
            elif abs(p5 - 1) < 0.1:
                print("  [SIM] 加速度计校准")
                resp.append(self.msg_command_ack(241, 0))
                self._status_queue.append("Accel calibration started")
                self._status_queue.append("Place vehicle level and press any key")
                self._status_queue.append("Accel calibration complete")
            elif abs(p5 - 4) < 0.1:
                print("  [SIM] 水平校准")
                resp.append(self.msg_command_ack(241, 0))
                self._status_queue.append("Level calibration complete")
            else:
                print("  [SIM] 校准取消")
                resp.append(self.msg_command_ack(241, 0))
        else:
            resp.append(self.msg_command_ack(cmd, 3))
        return resp

    def _handle_fence_item(self, p):
        p1 = struct.unpack_from("<f", p, 0)[0]
        lat = struct.unpack_from("<i", p, 16)[0] / 1e7
        lon = struct.unpack_from("<i", p, 20)[0] / 1e7
        seq = struct.unpack_from("<H", p, 28)[0]
        cmd = struct.unpack_from("<H", p, 30)[0]

        if seq < len(self.fence):
            self.fence[seq] = {"seq": seq, "cmd": cmd, "lat": lat, "lon": lon, "vertex_count": p1}
            print("  [SIM] 围栏顶点 %d: cmd=%d (%.5f, %.5f) count=%.0f" % (seq, cmd, lat, lon, p1))

        if seq + 1 < len(self.fence):
            return [self.msg_mission_request(seq + 1, mission_type=1)]
        else:
            self.fence = [f for f in self.fence if f is not None]
            print("  [SIM] 围栏接收完成: %d 顶点" % len(self.fence))
            return [self.msg_mission_ack(0, mission_type=1)]

    def _handle_mission_item(self, p):
        p1 = struct.unpack_from("<f", p, 0)[0]
        p2 = struct.unpack_from("<f", p, 4)[0]
        lat = struct.unpack_from("<i", p, 16)[0] / 1e7
        lon = struct.unpack_from("<i", p, 20)[0] / 1e7
        alt = struct.unpack_from("<f", p, 24)[0]
        seq = struct.unpack_from("<H", p, 28)[0]
        cmd = struct.unpack_from("<H", p, 30)[0]

        if seq < len(self.mission):
            self.mission[seq] = {"seq": seq, "cmd": cmd, "lat": lat, "lon": lon, "alt": alt, "p1": p1, "p2": p2}
            print("  [SIM] 航点 %d: cmd=%d (%.5f, %.5f) %.0fm p1=%.1f p2=%.1f" % (seq, cmd, lat, lon, alt, p1, p2))

        if seq + 1 < len(self.mission):
            return [self.msg_mission_request(seq + 1)]
        else:
            self.mission = [m for m in self.mission if m is not None]
            print("  [SIM] 任务接收完成: %d 项" % len(self.mission))
            return [self.msg_mission_ack(0)]


def serve(port):
    sim = Simulator()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(1)
    print("=" * 50)
    print("  Argus 飞控模拟器")
    print("  监听: tcp://0.0.0.0:%d" % port)
    print("  GCS 端口栏填: tcp:localhost:%d" % port)
    print("  Ctrl+C 停止")
    print("=" * 50)

    while True:
        print("\n等待 GCS 连接...")
        conn, addr = srv.accept()
        conn.settimeout(0.05)
        print("已连接: %s:%d" % addr)

        sim.__init__()
        buf = b""
        sq = 0
        last_hb = last_att = last_gps = last_sys = last_wp = last_rc = last_ekf = 0
        # Auto-detect peer protocol from the first parsed frame so we can speak
        # the same dialect back. Previously the sim only emitted PL-Link
        # XOR-framed messages, which broke any GCS that connected over TCP with
        # protocol=auto (the backend forces TCP+auto → standard, so it never
        # parsed our reply). Detecting on first inbound frame keeps both modes
        # working from a single sim binary.
        client_proto = None

        def tx(frame):
            nonlocal sq
            try:
                if client_proto == "standard":
                    conn.sendall(frame)
                else:
                    conn.sendall(ple(frame, sq & 0xFF))
                sq += 1
            except Exception:
                raise ConnectionError

        def parse_standard_frame(b):
            if len(b) < 12 or b[0] != 0xFD:
                # Skip leading garbage byte
                idx = b.find(b"\xfd")
                if idx < 0:
                    return None, len(b)
                if idx > 0:
                    return None, idx
                return None, 0
            plen = b[1]
            frame_len = 12 + plen
            if len(b) < frame_len:
                return None, 0
            return bytes(b[:frame_len]), frame_len

        try:
            while True:
                now = time.time()

                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    buf += data
                except TimeoutError:
                    pass

                # Detect protocol from the first 1-2 bytes of received traffic
                if client_proto is None and len(buf) >= 2:
                    if buf[0] == 0x50 and buf[1] == 0x4C:
                        client_proto = "pllink"
                    elif buf[0] == 0xFD:
                        client_proto = "standard"

                while len(buf) >= (7 if client_proto != "standard" else 12):
                    if client_proto == "standard":
                        payload, consumed = parse_standard_frame(buf)
                    else:
                        payload, consumed = pld(buf)
                    if payload:
                        buf = buf[consumed:]
                        for resp in sim.handle_mavlink(payload):
                            tx(resp)
                    elif consumed > 0:
                        buf = buf[consumed:]
                    else:
                        break

                sim.tick(0.05)

                while sim._status_queue:
                    tx(sim.msg_statustext(sim._status_queue.pop(0)))

                if now - last_hb >= 1.0:
                    tx(sim.msg_heartbeat())
                    tx(sim.msg_home_position())
                    last_hb = now

                if now - last_att >= 0.25:
                    tx(sim.msg_attitude())
                    last_att = now

                if now - last_gps >= 0.25:
                    tx(sim.msg_global_pos())
                    tx(sim.msg_gps_raw())
                    last_gps = now

                if now - last_sys >= 1.0:
                    tx(sim.msg_sys_status())
                    last_sys = now

                if now - last_ekf >= 1.0:
                    tx(sim.msg_ekf_status())
                    tx(sim.msg_wind())
                    tx(sim.msg_vfr_hud())
                    last_ekf = now

                if now - last_wp >= 1.0:
                    tx(sim.msg_mission_current())
                    last_wp = now

                if now - last_rc >= 0.5:
                    tx(sim.msg_rc_channels())
                    tx(sim.msg_vibration())
                    tx(sim.msg_servo_output())
                    last_rc = now

                time.sleep(0.05)

        except (BrokenPipeError, ConnectionResetError, ConnectionError, OSError) as e:
            print("断开: %s" % e)
        finally:
            conn.close()
            print("连接已关闭")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5770
    try:
        serve(port)
    except KeyboardInterrupt:
        print("\n已停止")
