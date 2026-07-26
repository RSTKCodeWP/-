from __future__ import annotations

import base64
import math
import struct
from typing import TYPE_CHECKING

from ..crc_extras import CRC_EXTRA
from ..locale_text import lt
from ..pllink_proto import bm
from ._helpers import send_cmd, send_cmd_int, send_serial_control

if TYPE_CHECKING:
    from ..drone_link import DroneLink


# --- Vehicle ---


def cmd_set_vtype(link: DroneLink, param, data: dict):
    v = data.get("vtype", "auto")
    link.vehicle.force_plane = True if v == "plane" else (False if v == "copter" else None)
    vname = lt("vtype_plane" if v == "plane" else "vtype_copter" if v == "copter" else "vtype_auto", link.locale)
    link.add_event(lt("vtype_set", link.locale) % vname, "vtype_set")


def cmd_guided_goto(link: DroneLink, param, data: dict):
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))
    alt = float(data.get("alt", 30))
    if abs(lat) < 0.001 and abs(lon) < 0.001:
        return {"ok": False, "error": lt("err_bad_coord", link.locale)}
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180) or not (-500 <= alt <= 100000):
        return {"ok": False, "error": lt("err_bad_coord", link.locale)}
    lat7 = int(lat * 1e7)
    lon7 = int(lon * 1e7)
    gm = 15 if link.is_plane() else 4
    from ._helpers import send_set_mode

    send_set_mode(link, gm)
    link.add_event(lt("guided", link.locale) % (lat7 / 1e7, lon7 / 1e7, alt), "guided")
    p = struct.pack("<IiifffffffffHBBB", 0, lat7, lon7, alt, 0, 0, 0, 0, 0, 0, 0, 0, 0x0FF8, link.vehicle.sysid, 1, 6)
    link.send(bm(86, p, link.sq, CRC_EXTRA[86]))


def cmd_switch_vehicle(link: DroneLink, param, data: dict):
    new_sysid = int(param) if param is not None else int(data.get("sysid", 1))
    link.active_sysid = new_sysid
    link.vehicle.sysid = new_sysid
    link.add_event(lt("vehicle_switch", link.locale) % new_sysid, "vehicle_switch")


def cmd_clear_summary(link: DroneLink, param, data: dict):
    link.vehicle.flight_summary = None


# --- System ---


def cmd_reboot(link: DroneLink, param, data: dict):
    link.add_event(lt("reboot", link.locale), "reboot")
    send_cmd(link, 246, p1=1)


def cmd_reboot_bootloader(link: DroneLink, param, data: dict):
    link.add_event(lt("reboot_bl", link.locale), "reboot_bl")
    send_cmd(link, 246, p1=3)


def cmd_inspector_toggle(link: DroneLink, param, data: dict):
    link.inspector_enabled = not link.inspector_enabled


def cmd_serial_control(link: DroneLink, param, data: dict):
    text = data.get("text", "")
    if text:
        send_serial_control(link, text)


def cmd_inject_rtcm(link: DroneLink, param, data: dict):
    rtcm_data = data.get("data", "")
    if not rtcm_data:
        return
    raw = base64.b64decode(rtcm_data)
    for i in range(0, len(raw), 180):
        chunk = raw[i : i + 180]
        flags = 0x01
        if i == 0:
            flags |= 0x04
        if i + 180 >= len(raw):
            flags |= 0x08
        p = struct.pack("<BB", flags, len(chunk))
        p += chunk + b"\x00" * (180 - len(chunk))
        link.send(bm(233, p, link.sq, CRC_EXTRA[233]))


# --- RC / Motor ---


def cmd_rc_override(link: DroneLink, param, data: dict):
    channels = data.get("channels", [])
    if not isinstance(channels, list) or len(channels) < 8:
        return None
    try:
        p = b""
        for i in range(8):
            p += struct.pack("<H", max(0, min(65535, int(channels[i]))))
        p += struct.pack("<BB", link.vehicle.sysid, 1)
        link.send(bm(70, p, link.sq, CRC_EXTRA[70]))
    except (TypeError, ValueError):
        return {"ok": False, "error": lt("err_channel_data", link.locale)}


def cmd_motor_test(link: DroneLink, param, data: dict):
    # UI sends `motor` as a 0-based index (matching its 0..7 loop), but
    # ArduPilot's MOTOR_TEST handler (GCS_MAVLink_Copter.cpp:702) requires
    # param1 to be the **1-based** motor sequence number — motor 0 is rejected
    # as invalid. Convert here.
    motor = int(data.get("motor", 0))
    if not 0 <= motor <= 7:
        return {"ok": False, "error": lt("err_motor_index", link.locale)}
    throttle = float(data.get("throttle", 5))
    if not 0 <= throttle <= 100:
        return {"ok": False, "error": lt("err_throttle_range", link.locale)}
    duration = float(data.get("duration", 2))
    if not 0 < duration <= 30:
        return {"ok": False, "error": lt("err_motor_duration", link.locale)}
    link.add_event(lt("motor_test", link.locale) % (motor + 1, throttle), "motor_test")
    send_cmd(link, 209, p1=float(motor + 1), p2=0, p3=throttle, p4=duration, p5=1)


def cmd_motor_test_stop(link: DroneLink, param, data: dict):
    # 1-based motor sequence numbers, see cmd_motor_test.
    for i in range(1, 9):
        send_cmd(link, 209, p1=float(i), p2=0, p3=0, p4=0, p5=1)


# --- Camera / Gimbal ---


def cmd_gimbal_angle(link: DroneLink, param, data: dict):
    pitch = float(data.get("pitch", 0))
    yaw = float(data.get("yaw", 0))
    if not -90 <= pitch <= 90 or not -180 <= yaw <= 180:
        return {"ok": False, "error": lt("err_gimbal_angle", link.locale)}
    send_cmd(link, 205, p1=pitch, p3=yaw, p7=2)


# Replaces the broken gimbal_rate path removed in the 2026-05 audit (msg 282
# encoded as 27 bytes vs the required 35). The handler is
# AP_Mount::handle_command_do_gimbal_manager_pitchyaw at
# libraries/AP_Mount/AP_Mount.cpp:363-417 and branches in this exact order:
#   (a) if isnan(pitch_angle) && isnan(yaw_angle) is FALSE  → set_angle_target
#   (b) else if isnan(pitch_rate) && isnan(yaw_rate) is FALSE → set_rate_target
#   (c) else if all four NaN → set_yaw_lock(YAW_LOCK_flag)
# packet.x (int32 slot in COMMAND_INT) is read as uint32 flags
# (RETRACT=1, NEUTRAL=2, YAW_LOCK=16); packet.z (float slot) is cast to
# uint8 instance number (0 = primary gimbal).
_GIMBAL_FLAG_RETRACT = 1
_GIMBAL_FLAG_NEUTRAL = 2
_GIMBAL_FLAG_YAW_LOCK = 16


def cmd_gimbal_pitchyaw(link: DroneLink, param, data: dict):
    def _f(key: str) -> float:
        v = data.get(key)
        if v is None:
            return float("nan")
        try:
            return float(v)
        except (TypeError, ValueError):
            return float("nan")

    pitch = _f("pitch")
    yaw = _f("yaw")
    pitch_rate = _f("pitch_rate")
    yaw_rate = _f("yaw_rate")

    for name, v, lo, hi in (
        ("pitch", pitch, -90.0, 90.0),
        ("yaw", yaw, -180.0, 180.0),
        ("pitch_rate", pitch_rate, -180.0, 180.0),
        ("yaw_rate", yaw_rate, -180.0, 180.0),
    ):
        if not math.isnan(v) and not (lo <= v <= hi):
            return {"ok": False, "error": f"{name} out of range"}

    flags = int(data.get("flags", 0))
    if not -0x80000000 <= flags <= 0x7FFFFFFF:
        return {"ok": False, "error": "flags must fit in int32"}
    instance = int(data.get("instance", 0))
    if not 0 <= instance <= 6:
        return {"ok": False, "error": lt("err_gimbal_instance", link.locale)}

    send_cmd_int(link, 1000, p1=pitch, p2=yaw, p3=pitch_rate, p4=yaw_rate, x=flags, y=0, z=float(instance), frame=0)


def cmd_camera_trigger(link: DroneLink, param, data: dict):
    # MAV_CMD_DO_DIGICAM_CONTROL (203): param5 = shoot command (1 = trigger).
    # Sending all zeros is a no-op — AP_Camera ignores it. See AP_Camera.cpp's
    # MAV_CMD_DO_DIGICAM_CONTROL case for the param decoding.
    send_cmd(link, 203, p5=1)


def cmd_camera_video_start(link: DroneLink, param, data: dict):
    send_cmd(link, 2500, p1=0, p2=0, p3=1)


def cmd_camera_video_stop(link: DroneLink, param, data: dict):
    send_cmd(link, 2501)


def cmd_camera_zoom(link: DroneLink, param, data: dict):
    zoom_val = float(data.get("zoom", 1))
    if not 0.1 <= zoom_val <= 100:
        return {"ok": False, "error": lt("err_zoom_range", link.locale)}
    send_cmd(link, 531, p1=1, p2=zoom_val)


def cmd_do_set_roi(link: DroneLink, param, data: dict):
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))
    alt = float(data.get("alt", 0))
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return {"ok": False, "error": lt("err_bad_coord", link.locale)}
    send_cmd(link, 201, p1=3, p5=lat, p6=lon, p7=alt)
