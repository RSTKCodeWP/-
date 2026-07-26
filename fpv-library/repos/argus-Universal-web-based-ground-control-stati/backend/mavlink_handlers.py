from __future__ import annotations

import math
import struct
import time
from typing import TYPE_CHECKING

from . import mavlink_dispatch
from .crc_extras import CRC_EXTRA
from .locale_text import lt
from .statustext_filter import filter_statustext

if TYPE_CHECKING:
    from .drone_link import DroneLink


def _pad(p: bytes, n: int) -> bytes:
    """Return p zero-padded to at least n bytes.

    MAVLink 2 senders may zero-trim trailing zero bytes from a payload to save
    bandwidth; receivers are required to treat the trimmed bytes as zero. Our
    handlers read named fields by offset and would either crash on a short
    buffer or return early on a strict `pl < N` check. Calling `_pad` before
    unpacking lets each handler read at any offset up to n without worrying
    about the wire-level truncation. `pl` still reflects the original size, so
    conditional reads on extension fields remain correct.
    """
    return p if len(p) >= n else p + b"\x00" * (n - len(p))


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:3166 — GCS_MAVLINK::send_heartbeat
def handle_heartbeat(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 9)
    v = link.vehicle
    v.mode = p[0] | (p[1] << 8) | (p[2] << 16) | (p[3] << 24)
    old_vtype = v.vtype_raw
    v.vtype_raw = p[4]
    # HEARTBEAT.autopilot byte (offset 5). The FC advertises its autopilot
    # stack once at boot and the value is stable afterwards. We filter out:
    #   - 0 (GENERIC, uninitialized — keep our default of 0)
    #   - 8 (INVALID — GCS components and pure data-link relays send this;
    #        latching on it would corrupt the FC's value if a GCS heartbeat
    #        arrives after the FC's)
    # Any other non-zero value is treated as an FC identifier and latched.
    # See CLAUDE.md ## PX4 Status for why the rest of the codebase still
    # assumes ArduPilot regardless. MAV_AUTOPILOT enum: 3=ArduPilot, 12=PX4.
    ap = p[5]
    if ap > 0 and ap != 8 and ap != v.autopilot:
        v.autopilot = ap
        # Fail loud: everything downstream (mode names, command enums,
        # calibration handshakes) is ArduPilot-specific, and commands.execute()
        # refuses FC-bound commands while this value is latched. Warn once per
        # session (flag reset on connect/reconnect): on a mixed AP+PX4 link the
        # shared VehicleState flaps last-heartbeat-wins, and a per-change event
        # would fire every second forever.
        if ap != 3 and not getattr(link, "_unsupported_fc_warned", False):
            link._unsupported_fc_warned = True
            name = "PX4" if ap == 12 else "autopilot=%d" % ap
            link.add_event(lt("unsupported_fc", link.locale) % name, "unsupported_fc")
    if old_vtype != v.vtype_raw and v.vtype_raw > 0:
        link.add_event(lt("vehicle_type", link.locale) % link._get_vehicle_info()[2], "vehicle_type")
    new_armed = bool(p[6] & 0x80)
    if new_armed != v.armed:
        link.add_event(
            lt("armed", link.locale) if new_armed else lt("disarmed", link.locale), "armed" if new_armed else "disarmed"
        )
        if new_armed:
            v.flight_summary = None  # clear previous record so ws.ts guard fires on next disarm
            v.armed_time = time.time()
            v.max_alt = v.max_speed = v.total_dist = 0
            link.attitude._prev_pos = None
            link.battery._bat_history = []
            link.battery._bat_start_pct = link.battery.remaining
        else:
            dur = int(time.time() - v.armed_time) if v.armed_time else 0
            bat = link.battery
            bat_used = (bat._bat_start_pct - bat.remaining) if bat._bat_start_pct >= 0 and bat.remaining >= 0 else -1
            v.flight_summary = {
                "duration": dur,
                "max_alt": round(v.max_alt, 1),
                "max_speed": round(v.max_speed, 1),
                "total_dist": round(v.total_dist),
                "bat_used": bat_used,
            }
            bat.bat_time_remaining = -1
    v.armed = new_armed
    v.sysid = link._raw_sysid
    if not link.connected:
        link.connected = True
        link.add_event(lt("connected", link.locale) % v.sysid, "connected")


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:6082 — GCS_MAVLINK::send_attitude
def handle_attitude(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 16)
    a = link.attitude
    a.roll = struct.unpack_from("<f", p, 4)[0] * 57.2958
    a.pitch = struct.unpack_from("<f", p, 8)[0] * 57.2958
    a.yaw = struct.unpack_from("<f", p, 12)[0] * 57.2958
    if a.yaw < 0:
        a.yaw += 360


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:6138 — GCS_MAVLINK::send_global_position_int
def handle_global_position_int(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 28)
    a = link.attitude
    a.lat = struct.unpack_from("<i", p, 4)[0] / 1e7
    a.lon = struct.unpack_from("<i", p, 8)[0] / 1e7
    a.alt_msl = struct.unpack_from("<i", p, 12)[0] / 1000.0
    a.alt_rel = struct.unpack_from("<i", p, 16)[0] / 1000.0
    if pl >= 22:
        a.vx = struct.unpack_from("<h", p, 20)[0] / 100.0
    if pl >= 24:
        a.vy = struct.unpack_from("<h", p, 22)[0] / 100.0
    if pl >= 26:
        a.vz = struct.unpack_from("<h", p, 24)[0] / 100.0
    a.gs = (a.vx**2 + a.vy**2) ** 0.5
    if pl >= 28:
        a.hdg = struct.unpack_from("<H", p, 26)[0] / 100.0
    # Only auto-infer home on first valid fix. We require a non-trivial fix
    # (>~111 m from null island) to avoid latching the (0,0) startup placeholder
    # the FC emits before GPS lock. An equator-based real home is fine because
    # the FC will also emit HOME_POSITION (242) once home is set, which sets
    # _home_set unconditionally.
    if not a._home_set and (abs(a.lat) > 0.001 or abs(a.lon) > 0.001):
        a.home_lat = a.lat
        a.home_lon = a.lon
        a._home_set = True
        link.add_event(lt("home_set", link.locale) % (a.lat, a.lon), "home_set")
    if a._home_set:
        dlat = (a.lat - a.home_lat) * 111320
        dlon = (a.lon - a.home_lon) * 111320 * math.cos(math.radians(a.lat))
        a.dist_home = (dlat**2 + dlon**2) ** 0.5
    v = link.vehicle
    if v.armed:
        if a.alt_rel > v.max_alt:
            v.max_alt = a.alt_rel
        if a.gs > v.max_speed:
            v.max_speed = a.gs
        if a._prev_pos:
            dp = ((a.lat - a._prev_pos[0]) * 111320) ** 2 + (
                (a.lon - a._prev_pos[1]) * 111320 * math.cos(math.radians(a.lat))
            ) ** 2
            v.total_dist += dp**0.5
        a._prev_pos = (a.lat, a.lon)


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:6005 — GCS_MAVLINK::send_sys_status
def handle_sys_status(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 31)
    bat = link.battery
    bat.voltage = (p[14] | (p[15] << 8)) / 1000.0
    if pl >= 18:
        bat.current = struct.unpack_from("<h", p, 16)[0] / 100.0
    if pl > 30:
        bat.remaining = struct.unpack_from("<b", p, 30)[0]
    if bat.remaining >= 0 and link.vehicle.armed:
        now = time.time()
        bat._bat_history.append((now, bat.remaining))
        bat._bat_history = [(t, r) for t, r in bat._bat_history if now - t < 120]
        if len(bat._bat_history) >= 2:
            dt = bat._bat_history[-1][0] - bat._bat_history[0][0]
            dr = bat._bat_history[0][1] - bat._bat_history[-1][1]
            if dt > 10 and dr > 0:
                bat.bat_time_remaining = int(bat.remaining / (dr / dt))


# ArduPilot: libraries/AP_GPS/AP_GPS.cpp:1375 — AP_GPS::send_mavlink_gps_raw
def handle_gps_raw_int(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 30)
    link.gps.gps_fix = p[28]
    link.gps.gps_sats = p[29]


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:716 — GCS_MAVLINK::send_mission_current
def handle_mission_current(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 2)
    link.mission.wp_seq = p[0] | (p[1] << 8)


def handle_home_position(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 20)
    hlat = struct.unpack_from("<i", p, 0)[0] / 1e7
    hlon = struct.unpack_from("<i", p, 4)[0] / 1e7
    # FC only sends HOME_POSITION when home is actually set
    # (GCS_Common.cpp:3064 `if (!AP::ahrs().home_is_set()) return`),
    # so trust it even for equator coordinates.
    link.attitude.home_lat = hlat
    link.attitude.home_lon = hlon
    link.attitude._home_set = True


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:5956 — try_send_message(MSG_MISSION_ITEM_REACHED)
def handle_mission_item_reached(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 2)
    seq = p[0] | (p[1] << 8)
    link.add_event(lt("wp_reached", link.locale) % seq, "wp_reached")


_CMD_NAMES_ZH = {
    22: "起飞",
    176: "模式",
    181: "继电器",
    241: "校准",
    300: "任务开始",
    400: "解锁/锁定",
    410: "引导",
    42424: "罗盘校准",
    42425: "接受罗盘校准",
    42426: "取消罗盘校准",
}
_CMD_NAMES_EN = {
    22: "Takeoff",
    176: "Mode",
    181: "Relay",
    241: "Calibration",
    300: "Mission Start",
    400: "Arm/Disarm",
    410: "Guided",
    42424: "Compass Cal",
    42425: "Accept Compass Cal",
    42426: "Cancel Compass Cal",
}
_ACK_RESULTS_ZH = {0: "成功", 1: "暂时拒绝", 2: "拒绝", 3: "不支持", 4: "进行中", 5: "已取消"}
_ACK_RESULTS_EN = {
    0: "success",
    1: "temporarily rejected",
    2: "denied",
    3: "unsupported",
    4: "in progress",
    5: "cancelled",
}


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:1446 — GCS_MAVLINK_InProgress::send_ack
def handle_command_ack(p: bytes, pl: int, link: DroneLink) -> None:
    # Min check 2: command at 0-1. result (offset 2) reads 0 (ACCEPTED) when
    # the byte was trimmed.
    if pl < 2:
        return
    p = _pad(p, 3)
    cmd_id = struct.unpack_from("<H", p, 0)[0]
    result = p[2]
    en = link.locale == "en"
    cmd_name = (_CMD_NAMES_EN if en else _CMD_NAMES_ZH).get(cmd_id, str(cmd_id))
    result_text = (_ACK_RESULTS_EN if en else _ACK_RESULTS_ZH).get(
        result, "unknown(%d)" % result if en else "未知(%d)" % result
    )
    if result == 4:
        return
    if result == 0 and cmd_id in (241, 42424, 42425, 42426):
        return
    etype = "cmd_ack_ok" if result == 0 else "cmd_ack_fail"
    link.add_event(lt("cmd_ack", link.locale) % (cmd_name, result_text), etype)


# ArduPilot: libraries/AP_Compass/AP_Compass_Calibration.cpp:270 — Compass::send_mag_cal_progress
def handle_mag_cal_progress(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 17)
    if getattr(link, "_mag_cal_done", False):
        return
    pct = p[16]
    prev = getattr(link, "_mag_cal_pct", -1)
    if pct > prev:
        link._mag_cal_pct = pct
        if (pct // 5) != (prev // 5):
            link.add_event(lt("mag_cal_pct", link.locale) % pct, "cal_compass")


# ArduPilot: libraries/AP_Compass/AP_Compass_Calibration.cpp:309 — Compass::send_mag_cal_report
def handle_mag_cal_report(p: bytes, pl: int, link: DroneLink) -> None:
    # cal_status at offset 42. autosaved (43) and the orientation extension
    # fields commonly trim down to pl=43 when autosaved=0.
    if pl < 43:
        return
    p = _pad(p, 44)
    if getattr(link, "_mag_cal_done", False):
        return
    cal_status = p[42]
    link._mag_cal_done = True
    link._mag_cal_pct = -1
    if cal_status == 4:
        link.add_event(lt("mag_cal_done", link.locale), "cal_compass")
        link.add_event(lt("mag_cal_reboot", link.locale), "cal_compass")
    else:
        link.add_event(lt("mag_cal_fail", link.locale), "cal_compass")


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:2684 — GCS_MAVLINK::service_statustext
def handle_statustext(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 2:
        return
    text = bytes(p[1:51]).split(b"\x00")[0].decode("ascii", "replace").strip()
    if not text:
        return
    if text.startswith("PreArm:") or text.startswith("Arm:"):
        msg = text.split(":", 1)[1].strip()
        # PreArm checks run every ~5s and re-emit the same warnings until the
        # condition is fixed. Dedup against _prearm_messages so the event log
        # gets one entry per distinct cause, not one every cycle.
        if msg in link._prearm_messages:
            return
        link._prearm_messages.append(msg)
        if len(link._prearm_messages) > 20:
            link._prearm_messages = link._prearm_messages[-10:]
    text = filter_statustext(text, link.locale)
    link.add_event(("%s: %s" % ("FC" if link.locale == "en" else "飞控", text)), "statustext")


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:3394 — GCS_MAVLINK::send_servo_output_raw
def handle_servo_output(p: bytes, pl: int, link: DroneLink) -> None:
    # Min check 6 (servo1 last byte). Trim could drop port (offset 20) and the
    # extension servo9-16 if those values are all zero.
    if pl < 6:
        return
    p = _pad(p, 37)
    rc = link.rc_servo
    rc.servo_out = [struct.unpack_from("<H", p, 4 + i * 2)[0] for i in range(8)]
    if pl >= 37:
        rc.servo_out += [struct.unpack_from("<H", p, 21 + i * 2)[0] for i in range(8)]
    else:
        rc.servo_out += [0] * 8


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:2168 — GCS_MAVLINK::send_rc_channels
def handle_rc_channels(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 6:
        return
    p = _pad(p, 42)
    link.rc_servo.rc_channels = [struct.unpack_from("<H", p, 4 + i * 2)[0] for i in range(16)]
    link.rc_servo.rc_rssi = p[41]


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:2237 — GCS_MAVLINK::send_raw_imu
# (mag = compass.get_field(0), milligauss). Layout: time_usec u64 @0,
# acc i16 @8/10/12, gyro i16 @14/16/18, xmag/ymag/zmag i16 @20/22/24.
def handle_raw_imu(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 26)
    d = link.diagnostic
    d.mag_x = struct.unpack_from("<h", p, 20)[0]
    d.mag_y = struct.unpack_from("<h", p, 22)[0]
    d.mag_z = struct.unpack_from("<h", p, 24)[0]


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:3073 — GCS_MAVLINK::send_vibration
def handle_vibration(p: bytes, pl: int, link: DroneLink) -> None:
    # Min check 12: vibration_x first useful field. Trim can drop trailing
    # clipping counters when they're zero.
    if pl < 12:
        return
    p = _pad(p, 32)
    d = link.diagnostic
    d.vibe_x = struct.unpack_from("<f", p, 8)[0]
    d.vibe_y = struct.unpack_from("<f", p, 12)[0]
    d.vibe_z = struct.unpack_from("<f", p, 16)[0]
    d.vibe_clip0 = struct.unpack_from("<I", p, 20)[0]
    d.vibe_clip1 = struct.unpack_from("<I", p, 24)[0]
    d.vibe_clip2 = struct.unpack_from("<I", p, 28)[0]


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:3492 — GCS_MAVLINK::send_vfr_hud
def handle_vfr_hud(p: bytes, pl: int, link: DroneLink) -> None:
    # Min check 4 (airspeed): MAVLink 2 zero-trim can shrink this from the
    # nominal 20 bytes down to as little as 4 when throttle/heading/climb are
    # zero.
    if pl < 4:
        return
    p = _pad(p, 20)
    airspeed, gs, alt, climb, heading, throttle = struct.unpack_from("<ffffhH", p)
    a = link.attitude
    a.airspeed = airspeed
    a.throttle = throttle
    a.climb = climb


# ArduPilot: libraries/AP_NavEKF3/AP_NavEKF3_Outputs.cpp:348 — NavEKF3_core::send_status_report
def handle_ekf_status(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 22)
    vel, pos_h, pos_v, comp, terr, flags = struct.unpack_from("<fffffH", p)
    d = link.diagnostic
    d.ekf_vel_var = vel
    d.ekf_pos_h_var = pos_h
    d.ekf_pos_v_var = pos_v
    d.ekf_compass_var = comp
    d.ekf_terrain_var = terr
    d.ekf_flags = flags


def handle_mount_status(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 12)
    pitch_cdeg, _roll_cdeg, yaw_cdeg = struct.unpack_from("<iii", p)
    d = link.diagnostic
    d.gimbal_pitch = pitch_cdeg / 100.0
    d.gimbal_yaw = yaw_cdeg / 100.0


# ArduPilot: libraries/AP_Mount/AP_Mount.cpp — GCS_MAVLink::send_gimbal_device_attitude_status
def handle_gimbal_device_attitude_status(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 20:
        return
    p = _pad(p, 36)
    # Wire layout (MAVLink 2, sorted by size): time_boot_ms (u32, 0..3),
    # q[4] (float×4, 4..19), angular_velocity_{x,y,z} (float, 20..31),
    # failure_flags (u32, 32..35), flags (u16, 36..37).
    w, x, y, z = struct.unpack_from("<4f", p, 4)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    d = link.diagnostic
    d.gimbal_pitch = math.degrees(pitch)
    d.gimbal_yaw = math.degrees(yaw)


# ArduPilot: libraries/AP_Terrain/TerrainGCS.cpp:229 — AP_Terrain::send_terrain_report
def handle_terrain_report(p: bytes, pl: int, link: DroneLink) -> None:
    # TERRAIN_REPORT (136) wire layout (MAVLink 2, sorted by size):
    #   lat (i32, 0..3), lon (i32, 4..7), terrain_height (float, 8..11),
    #   current_height (float, 12..15), spacing (u16, 16..17),
    #   pending (u16, 18..19), loaded (u16, 20..21).
    # We want terrain_height (ground elevation) for "terrain altitude" display,
    # not current_height (vehicle altitude above the ground).
    if pl < 1:
        return
    p = _pad(p, 16)
    link.diagnostic.terrain_alt = struct.unpack_from("<f", p, 8)[0]


# ArduPilot: libraries/AP_WindVane/AP_WindVane.cpp:427 — AP_WindVane::send_wind
def handle_wind(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 12)
    direction, speed, _ = struct.unpack_from("<fff", p)
    link.diagnostic.wind_dir = direction % 360
    link.diagnostic.wind_speed = speed


# ArduPilot: libraries/GCS_MAVLink/GCS_Param.cpp:332 — GCS_MAVLINK::send_parameter_value
def handle_param_value(p: bytes, pl: int, link: DroneLink) -> None:
    link.param_mgr.handle_param_value(p, pl)


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:2980 — GCS_MAVLINK::send_autopilot_version
def handle_autopilot_version(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 44)
    fw_ver = struct.unpack_from("<I", p, 16)[0]
    major = (fw_ver >> 24) & 0xFF
    minor = (fw_ver >> 16) & 0xFF
    patch = (fw_ver >> 8) & 0xFF
    board = struct.unpack_from("<I", p, 28)[0]
    git_bytes = bytes(p[36:44])
    git = "".join("%02x" % b for b in git_bytes if b != 0)[:8]
    v = link.vehicle
    v.fw_version = "v%d.%d.%d" % (major, minor, patch)
    v.fw_git = git
    v.board_id = board
    link.add_event(lt("fw_info", link.locale) % (v.fw_version, v.fw_git), "fw_info")


# ArduPilot: libraries/GCS_MAVLink/MissionItemProtocol.cpp:135 — handle_mission_request_list
def handle_mission_count(p: bytes, pl: int, link: DroneLink) -> None:
    m = link.mission
    if pl < 1 or not m._dl_pending:
        return
    p = _pad(p, 3)
    count = struct.unpack_from("<H", p, 0)[0]
    m._dl_total = count
    m._dl_items = [None] * count
    if count > 0:
        _request_dl_item(link, 0)
        link.add_event(lt("mission_dl_n", link.locale) % count, "mission_dl_n")
    else:
        m._dl_pending = False
        link.add_event(lt("mission_dl_none", link.locale), "mission_dl_none")


def handle_mission_item_int(p: bytes, pl: int, link: DroneLink) -> None:
    m = link.mission
    if pl < 1 or not m._dl_pending:
        return
    p = _pad(p, 37)
    # MISSION_ITEM_INT (73) wire layout (sorted by size):
    #   0..3   p1 (float), 4..7   p2 (float)
    #   8..11  p3 (float), 12..15 p4 (float)
    #   16..19 x=lat*1e7 (i32), 20..23 y=lon*1e7 (i32)
    #   24..27 z=alt (float)
    #   28..29 seq (u16), 30..31 cmd (u16)
    #   32 target_system, 33 target_component, 34 frame
    #   35 current, 36 autocontinue
    #   ext: 37 mission_type
    p1 = struct.unpack_from("<f", p, 0)[0]
    p2 = struct.unpack_from("<f", p, 4)[0]
    p3 = struct.unpack_from("<f", p, 8)[0]
    p4 = struct.unpack_from("<f", p, 12)[0]
    lat = struct.unpack_from("<i", p, 16)[0] / 1e7
    lon = struct.unpack_from("<i", p, 20)[0] / 1e7
    alt = struct.unpack_from("<f", p, 24)[0]
    seq = struct.unpack_from("<H", p, 28)[0]
    cmd = struct.unpack_from("<H", p, 30)[0]
    frame = p[34]
    current = p[35]
    autocontinue = p[36]
    if seq < m._dl_total:
        m._dl_items[seq] = {
            "seq": seq,
            "cmd": cmd,
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "p1": p1,
            "p2": p2,
            "p3": p3,
            "p4": p4,
            "frame": frame,
            "current": current,
            "autocontinue": autocontinue,
        }
    # Finalize only when EVERY slot is filled — not merely when the highest
    # seq arrives. A duplicated or out-of-order final MISSION_ITEM_INT
    # (seq == _dl_total-1) would otherwise trigger the else-branch while gaps
    # remain, and the `[i for i in _dl_items if i is not None]` collapse below
    # would silently drop the still-missing items → a truncated mission on
    # read-back (re-uploading it then loses those waypoints). Requesting the
    # lowest still-missing seq is idempotent — AP_Mission tolerates a repeated
    # MISSION_REQUEST_INT — and the _dl watchdog still fails loud if the FC
    # never supplies it.
    next_missing = next((i for i, item in enumerate(m._dl_items) if item is None), None)
    if next_missing is not None:
        m._dl_start_time = time.time()
        _request_dl_item(link, next_missing)
    else:
        m._dl_pending = False
        items = [i for i in m._dl_items if i is not None]
        wps = []
        pending_speed = 0.0
        for item in items:
            if item["cmd"] == 178:
                pending_speed = item.get("p2", 0)
            elif item["cmd"] in (16, 18, 19, 82) and item["seq"] > 0:
                wtype = (
                    "loiter_turns"
                    if item["cmd"] == 18
                    else ("loiter_time" if item["cmd"] == 19 else ("spline" if item["cmd"] == 82 else "wp"))
                )
                wps.append(
                    {
                        "lat": item["lat"],
                        "lon": item["lon"],
                        "alt": item["alt"],
                        "drop": False,
                        "delay": item["p1"] if item["cmd"] == 16 else 0,
                        "speed": pending_speed,
                        "type": wtype,
                        "loiter_param": item["p1"] if item["cmd"] in (18, 19) else 0,
                        # Preserve fields the previous round-trip dropped.
                        # AP_Mission stores these per-item; re-uploading
                        # without them changes plane acceptance radius /
                        # loiter radius / yaw constraints.
                        "p3": item.get("p3", 0),
                        "p4": item.get("p4", 0),
                        "frame": item.get("frame", 3),
                        "autocontinue": item.get("autocontinue", 1),
                    }
                )
                pending_speed = 0.0
            elif item["cmd"] == 181 and wps:
                wps[-1]["drop"] = True
        m._dl_messages.append({"type": "mission_downloaded", "waypoints": wps})
        if len(m._dl_messages) > 500:
            m._dl_messages = m._dl_messages[-200:]
        link.add_event(lt("mission_dl_done", link.locale) % len(wps), "mission_dl_done")
        from .pllink_proto import bm

        link.send(bm(47, struct.pack("<BBB", link.vehicle.sysid, 1, 0), link.sq, CRC_EXTRA[47]))


def _request_dl_item(link: DroneLink, seq: int) -> None:
    from .pllink_proto import bm

    link.send(bm(51, struct.pack("<HBBB", seq, link.vehicle.sysid, 1, 0), link.sq, CRC_EXTRA[51]))


# ArduPilot: libraries/GCS_MAVLink/MissionItemProtocol.cpp:357 — MissionItemProtocol::queued_request_send
def handle_mission_request(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 5)
    seq = p[0] | (p[1] << 8)
    mission_type = p[4]
    m = link.mission
    from . import commands as cmd_mod

    if mission_type == 1 and m._fence_pending:
        if seq < len(m._fence_items):
            cmd_mod.send_fence_item_int(link, m._fence_items[seq])
            m._fence_ul_start_time = time.time()  # FC is making progress
    elif mission_type == 2 and m._rally_pending:
        if seq < len(m._rally_items):
            cmd_mod.send_rally_item_int(link, m._rally_items[seq])
            m._rally_ul_start_time = time.time()
    elif mission_type == 0 and m._mission_pending:
        if seq < len(m._mission_items):
            cmd_mod.send_mission_item_int(link, m._mission_items[seq])
            m._mission_ul_start_time = time.time()


# ArduPilot: libraries/GCS_MAVLink/MissionItemProtocol.cpp:341 — MissionItemProtocol::send_mission_ack
def handle_mission_ack(p: bytes, pl: int, link: DroneLink) -> None:
    # Min check 1: target_system. type (offset 2) reads 0=ACCEPTED from
    # zero-padded buffer if trimmed.
    if pl < 1:
        return
    p = _pad(p, 4)
    mtype = p[2]
    mission_type = p[3]
    m = link.mission
    if mission_type == 1 and m._fence_pending:
        m._fence_pending = False
        m._fence_ul_start_time = 0.0
        link.add_event(
            (lt("fence_ack_ok", link.locale) if mtype == 0 else lt("fence_ack_fail", link.locale) % mtype),
            "fence_ack_ok" if mtype == 0 else "fence_ack_fail",
        )
    elif mission_type == 2 and m._rally_pending:
        m._rally_pending = False
        m._rally_ul_start_time = 0.0
        # No fence_ack_ok/fail-equivalent for rally; reuse mission text.
        link.add_event(
            (lt("mission_ack_ok", link.locale) if mtype == 0 else lt("mission_ack_fail", link.locale) % mtype),
            "mission_ack_ok" if mtype == 0 else "mission_ack_fail",
        )
    elif mission_type == 0 and m._mission_pending:
        m._mission_pending = False
        m._mission_ul_start_time = 0.0
        link.add_event(
            (lt("mission_ack_ok", link.locale) if mtype == 0 else lt("mission_ack_fail", link.locale) % mtype),
            "mission_ack_ok" if mtype == 0 else "mission_ack_fail",
        )


# ArduPilot: libraries/AP_Logger/AP_Logger_MAVLinkLogTransfer.cpp:259 — AP_Logger::handle_log_send_listing
def handle_log_entry(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 14)
    time_utc, size, log_id, num_logs, last_log_num = struct.unpack_from("<IIHHH", p, 0)
    lg = link.log_dl
    lg._log_list.append({"id": log_id, "size": size, "time_utc": time_utc})
    if log_id == last_log_num:
        lg._log_messages.append({"type": "log_list", "logs": list(lg._log_list)})
        link.add_event(lt("log_list_n", link.locale) % len(lg._log_list), "log_list_n")


# ArduPilot: libraries/GCS_MAVLink/GCS_Common.cpp:304 — GCS_MAVLINK::send_battery_status
def handle_battery_status(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 10:
        return
    p = _pad(p, 36)
    cells = []
    for i in range(10):
        v = struct.unpack_from("<H", p, 10 + i * 2)[0]
        if v == 0xFFFF:
            break
        cells.append(v / 1000.0)
    link.battery.battery_cells = cells


# ArduPilot: libraries/AP_ADSB/AP_ADSB.cpp:620 — AP_ADSB::send_adsb_vehicle
def handle_adsb_vehicle(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 1:
        return
    p = _pad(p, 38)
    icao = struct.unpack_from("<I", p, 0)[0]
    lat = struct.unpack_from("<i", p, 4)[0] / 1e7
    lon = struct.unpack_from("<i", p, 8)[0] / 1e7
    alt = struct.unpack_from("<i", p, 12)[0] / 1000.0
    hdg = struct.unpack_from("<H", p, 16)[0] / 100.0
    hor_vel = struct.unpack_from("<H", p, 18)[0] / 100.0
    ver_vel = struct.unpack_from("<h", p, 20)[0] / 100.0
    callsign = bytes(p[27:36]).split(b"\x00")[0].decode("ascii", "replace").strip()
    tr = link.traffic
    tr._adsb_vehicles[icao] = {
        "icao": icao,
        "lat": round(lat, 7),
        "lon": round(lon, 7),
        "alt": round(alt, 0),
        "hdg": round(hdg, 0),
        "speed": round(hor_vel, 1),
        "vs": round(ver_vel, 1),
        "callsign": callsign,
        "t": time.time(),
    }
    if len(tr._adsb_vehicles) > 200:
        oldest = min(tr._adsb_vehicles, key=lambda k: tr._adsb_vehicles[k]["t"])
        del tr._adsb_vehicles[oldest]


# ArduPilot: libraries/GCS_MAVLink/GCS_serial_control.cpp:192 — GCS_MAVLINK::handle_serial_control
def handle_serial_control(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 9:
        return
    p = _pad(p, 79)
    count = p[8]
    if count > 0 and count <= 70:
        text = bytes(p[9 : 9 + count]).decode("ascii", "replace")
        link._console_buf.append(text)
        if len(link._console_buf) > 500:
            link._console_buf = link._console_buf[-250:]


_LOG_STREAM_CHUNK_SIZE = 65536  # 64KB chunks pushed to the frontend during download


def _mark_received(intervals: list[tuple[int, int]], start: int, end: int) -> None:
    """Merge the byte range [start, end) into a sorted, disjoint coverage
    list (twin of transport.ts _markReceived). A raw byte SUM would over-count
    duplicates — after a stall re-request, a late-buffered tail of the old
    burst can legitimately overlap the new burst, and the inflated sum would
    mask a real hole elsewhere in the file. In-order bursts extend the tail
    interval in O(1)."""
    if intervals:
        s, e = intervals[-1]
        if s <= start <= e:
            if end > e:
                intervals[-1] = (s, end)
            return
    intervals.append((start, end))
    intervals.sort()
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    intervals[:] = merged


def _covered_bytes(intervals: list[tuple[int, int]]) -> int:
    return sum(e - s for s, e in intervals)


def _next_log_gap(lg) -> tuple[int, int] | None:
    """First uncovered byte range of the download, or None when coverage is
    complete. With whole-log streaming this doubles as the resume point: no
    holes means the first gap starts exactly at the high-water mark."""
    prev_end = 0
    for s, e in lg._log_recv_intervals:
        if s > prev_end:
            return (prev_end, s)
        prev_end = max(prev_end, e)
    if prev_end < lg._log_download_size:
        return (prev_end, lg._log_download_size)
    return None


def _request_next_log_gap(lg, link) -> bool:
    """Request the first uncovered byte range in one LOG_REQUEST_DATA.

    This is the MAVProxy pattern ArduPilot explicitly tolerates
    (AP_Logger_MAVLinkLogTransfer.cpp:112-113 names it): stream big ranges,
    then fill the holes. AP anchors the transfer to our ofs and caps count to
    the remaining log size (:144-152), so requesting an entire gap is always
    in-spec. Returns False when coverage is complete (nothing left to ask)."""
    gap = _next_log_gap(lg)
    if gap is None:
        return False
    from .pllink_proto import bm

    start, gap_end = gap
    lg._log_window_end = gap_end
    link.send(
        bm(
            119,
            struct.pack("<IIHBB", start, gap_end - start, lg._log_download_id, link.vehicle.sysid, 1),
            link.sq,
            CRC_EXTRA[119],
        )
    )
    return True


def _contiguous_prefix(lg) -> int:
    """Bytes received without a hole from offset 0 — the only data safe to
    stream to the frontend as chunks (a hole may still be gap-filled later,
    but an already-emitted chunk can never be amended)."""
    iv = lg._log_recv_intervals
    return iv[0][1] if iv and iv[0][0] == 0 else 0


def _emit_log_chunks(lg, log_id: int) -> None:
    """Emit any complete log_chunk messages whose contents are now
    fully present in lg._log_download_data (between lg._log_emit_ofs and the
    contiguous prefix). Each chunk goes out as a small base64 message
    rather than buffering the whole log for a single end-of-download blob."""
    import base64

    while _contiguous_prefix(lg) - lg._log_emit_ofs >= _LOG_STREAM_CHUNK_SIZE:
        start = lg._log_emit_ofs
        endc = start + _LOG_STREAM_CHUNK_SIZE
        b64 = base64.b64encode(bytes(lg._log_download_data[start:endc])).decode("ascii")
        lg._log_messages.append({"type": "log_chunk", "id": log_id, "ofs": start, "data": b64})
        lg._log_emit_ofs = endc


def _finalize_log_download(lg, log_id: int, truncated: bool, link: DroneLink) -> None:
    """Emit any trailing partial chunk, then a final log_complete message
    (no data — the frontend has been accumulating chunks). Free the bytearray."""
    import base64

    final_size = lg._log_download_ofs
    # Mid-window frame loss leaves zero-filled holes that the window cadence
    # never revisits. Coverage intervals make the check exact — duplicates
    # and re-request overlaps never inflate it — so covered < final_size is
    # a definite loss: flag the file rather than shipping silent zeros.
    missing = final_size - _covered_bytes(lg._log_recv_intervals)
    if not truncated and missing > 0:
        truncated = True
        link.add_event(lt("log_dl_holes", link.locale) % missing, "log_dl_holes")
    if lg._log_emit_ofs < final_size:
        b64 = base64.b64encode(bytes(lg._log_download_data[lg._log_emit_ofs : final_size])).decode("ascii")
        lg._log_messages.append({"type": "log_chunk", "id": log_id, "ofs": lg._log_emit_ofs, "data": b64})
        lg._log_emit_ofs = final_size
    lg._log_messages.append(
        {
            "type": "log_complete",
            "id": log_id,
            "size": final_size,
            "truncated": truncated,
        }
    )
    # A truncated finalize (count==0 EOF, stall give-up, detected holes) must
    # not announce "complete" right after a failure event — say what it is.
    done_key = "log_dl_done_part" if truncated else "log_dl_done"
    link.add_event(lt(done_key, link.locale) % (log_id, final_size // 1024), done_key)
    lg._log_download_id = -1
    lg._log_download_data = bytearray()
    lg._log_emit_ofs = 0
    lg._log_recv_intervals = []
    lg._log_last_data_time = 0.0
    lg._log_stall_retries = 0
    # NO trim here: the ws drain is a cursor over this list with no ack —
    # dropping entries loses log_chunk payload the frontend can never
    # recover (a whole-log stream outruns the drain; the old [-200:] trim
    # ate 60% of a 28 MB SITL download). The queue is cleared at the START
    # of the next download / cancel / disconnect instead.
    #
    # Memory cost (honest accounting): during a download the peak is the
    # pre-allocated _log_download_data (1× the log) PLUS the base64 chunk
    # queue (~1.35×) = ~2.35×; after completion ~1.35× stays resident until
    # the next download clears it. Fine for typical logs (<50 MB). A very
    # large log on the backend-serial path (e.g. 260 MB → ~610 MB peak)
    # would want real backpressure — trim entries below the slowest ws
    # client's cursor — but that needs per-client cursor coordination in
    # ws_manager and is deferred: the user's real download path is WebSerial
    # (transport.ts, browser-side assembly), which never touches this queue.


# ArduPilot: libraries/AP_Logger/AP_Logger_MAVLinkLogTransfer.cpp:296 — AP_Logger::handle_log_send_data
def handle_log_data(p: bytes, pl: int, link: DroneLink) -> None:
    if pl < 7:
        return
    p = _pad(p, 97)
    lg = link.log_dl
    ofs, log_id, count = struct.unpack_from("<IHB", p, 0)
    if log_id != lg._log_download_id:
        return
    # Any accepted frame is progress — re-arm the stall watchdog
    # (check_log_dl_stall) and forget past retries.
    lg._log_last_data_time = time.time()
    lg._log_stall_retries = 0
    # FC documents count=0 as EOF / error per MAVLink common.xml: previously
    # this fell through to `end = ofs + 0 = ofs`; with end < size we re-
    # requested forever in a tight loop (LOG_REQUEST_DATA never receives data
    # because the source log is gone or unreadable).
    if count == 0:
        _finalize_log_download(lg, log_id, truncated=True, link=link)
        return
    # The LOG_DATA data field is uint8_t[90] (MAVLink common.xml) but count is
    # a free u8 — a corrupt frame that passes CRC could advertise up to 255.
    # Unclamped, the slice below would come up short and the bytearray slice
    # assignment would SHRINK the buffer, shifting every later byte left.
    count = min(count, 90)
    end = ofs + count
    # ofs shares count's threat model: every LOG_REQUEST_DATA we send is
    # capped to the remaining bytes, so an out-of-range frame is never
    # legitimate. Unguarded, a garbage ofs would push the high-water mark
    # past the size and finalize would report a bogus length (the frontend
    # sizes its assembly buffer from it — up to 4 GB for a u32 ofs).
    if end > lg._log_download_size:
        return
    _mark_received(lg._log_recv_intervals, ofs, end)
    data = p[7 : 7 + count]
    lg._log_download_data[ofs:end] = data
    # High-water mark: only used as the delivered-file size when a truncated
    # finalize ships a partial download. Progress/completion run on coverage.
    lg._log_download_ofs = max(lg._log_download_ofs, end)
    covered = _covered_bytes(lg._log_recv_intervals)
    # Stream out fully-received 64KB chunks. Avoids the 5× memory peak that
    # would happen if we kept the whole log in memory and base64-encoded it
    # in one shot at the end (auditor finding P1).
    _emit_log_chunks(lg, log_id)
    # Time-throttled progress: a whole-log stream delivers thousands of
    # frames per second — a per-N-frames cadence floods the ws queue.
    now = time.time()
    if now - lg._log_last_progress_time >= 0.25 and covered < lg._log_download_size:
        lg._log_last_progress_time = now
        lg._log_messages.append(
            {
                "type": "log_progress",
                "received": covered,
                "total": lg._log_download_size,
            }
        )
    if covered >= lg._log_download_size:
        _finalize_log_download(lg, log_id, truncated=False, link=link)
    elif end >= lg._log_window_end or count < 90:
        # AP's burst for our current request just ended — either this frame
        # reached the end of the requested range, or AP sent a short frame
        # (a short read ends its transfer too, AP_Logger_MAVLinkLogTransfer
        # .cpp:339-341). AP SILENTLY DROPS requests that arrive mid-burst
        # (:111-120), so this boundary is the only safe moment to ask for
        # more. Ask for the first uncovered gap: during the main whole-log
        # stream that's simply the resume point; after it, it fills holes
        # left by lost frames (end-of-transfer gap-fill, MAVProxy-style).
        _request_next_log_gap(lg, link)


LOG_DL_STALL_TIMEOUT = 5.0  # seconds; matches the transport.ts 5s watchdog
LOG_DL_STALL_RETRIES = 3  # matches transport.ts LOG_DL_STALL_RETRIES


def check_log_dl_stall(link: DroneLink) -> None:
    """Stall watchdog for the log download — twin of transport.ts _onDlStall.

    Called from the link thread's main loop alongside the param/mission
    checkers. The next LOG_REQUEST_DATA is only ever sent from
    handle_log_data, so losing the last frame of a burst means no LOG_DATA
    ever arrives again and nothing would re-request — a permanent silent
    hang.

    Re-requesting the first uncovered gap is safe: AP already ended its
    burst when it sent the (lost) final frame (AP_Logger_MAVLinkLogTransfer
    .cpp:337-341, end_log_transfer() at remaining==0), and the :111-120
    guard only drops requests that arrive while a transfer is actively
    sending — so an idle AP honors the retry, and a still-bursting AP (e.g.
    paused on txspace :300-302 or GCS-heartbeat starvation :304-307)
    harmlessly drops it.
    """
    lg = link.log_dl
    if lg._log_download_id == -1 or lg._log_last_data_time <= 0:
        return
    if time.time() - lg._log_last_data_time <= LOG_DL_STALL_TIMEOUT:
        return
    log_id = lg._log_download_id
    if lg._log_stall_retries >= LOG_DL_STALL_RETRIES:
        # Deliver what we have (zero-filled, flagged truncated) instead of
        # dropping a nearly-complete multi-MB download on the floor.
        link.add_event(lt("log_dl_stall_fail", link.locale), "log_dl_stall_fail")
        _finalize_log_download(lg, log_id, truncated=True, link=link)
        return
    lg._log_stall_retries += 1
    lg._log_last_data_time = time.time()
    if not _request_next_log_gap(lg, link):
        # Coverage complete but the finalize never ran — should be unreachable
        # (handle_log_data finalizes on covered >= size); close out cleanly.
        _finalize_log_download(lg, log_id, truncated=False, link=link)
        return
    link.add_event(lt("log_dl_stall", link.locale) % (lg._log_download_ofs // 1024), "log_dl_stall")


def init_handlers() -> None:
    mavlink_dispatch.register(0, handle_heartbeat)
    mavlink_dispatch.register(30, handle_attitude)
    mavlink_dispatch.register(33, handle_global_position_int)
    mavlink_dispatch.register(1, handle_sys_status)
    mavlink_dispatch.register(24, handle_gps_raw_int)
    mavlink_dispatch.register(42, handle_mission_current)
    mavlink_dispatch.register(242, handle_home_position)
    mavlink_dispatch.register(46, handle_mission_item_reached)
    mavlink_dispatch.register(77, handle_command_ack)
    mavlink_dispatch.register(253, handle_statustext)
    mavlink_dispatch.register(36, handle_servo_output)
    mavlink_dispatch.register(65, handle_rc_channels)
    mavlink_dispatch.register(27, handle_raw_imu)
    mavlink_dispatch.register(241, handle_vibration)
    mavlink_dispatch.register(74, handle_vfr_hud)
    mavlink_dispatch.register(193, handle_ekf_status)
    mavlink_dispatch.register(158, handle_mount_status)
    mavlink_dispatch.register(285, handle_gimbal_device_attitude_status)
    mavlink_dispatch.register(136, handle_terrain_report)
    mavlink_dispatch.register(168, handle_wind)
    mavlink_dispatch.register(22, handle_param_value)
    mavlink_dispatch.register(148, handle_autopilot_version)
    mavlink_dispatch.register(44, handle_mission_count)
    mavlink_dispatch.register(73, handle_mission_item_int)
    mavlink_dispatch.register(40, handle_mission_request)
    mavlink_dispatch.register(51, handle_mission_request)
    mavlink_dispatch.register(47, handle_mission_ack)
    mavlink_dispatch.register(118, handle_log_entry)
    mavlink_dispatch.register(120, handle_log_data)
    mavlink_dispatch.register(126, handle_serial_control)
    mavlink_dispatch.register(246, handle_adsb_vehicle)
    mavlink_dispatch.register(191, handle_mag_cal_progress)
    mavlink_dispatch.register(192, handle_mag_cal_report)
    mavlink_dispatch.register(147, handle_battery_status)
