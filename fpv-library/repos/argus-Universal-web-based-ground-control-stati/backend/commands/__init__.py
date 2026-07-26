from __future__ import annotations

from typing import TYPE_CHECKING

from ._flight import (
    cmd_arm,
    cmd_disarm,
    cmd_drop,
    cmd_drop_stop,
    cmd_force_disarm,
    cmd_mode,
    cmd_rtl,
    cmd_takeoff,
)
from ._hardware import (
    cmd_camera_trigger,
    cmd_camera_video_start,
    cmd_camera_video_stop,
    cmd_camera_zoom,
    cmd_clear_summary,
    cmd_do_set_roi,
    cmd_gimbal_angle,
    cmd_gimbal_pitchyaw,
    cmd_guided_goto,
    cmd_inject_rtcm,
    cmd_inspector_toggle,
    cmd_motor_test,
    cmd_motor_test_stop,
    cmd_rc_override,
    cmd_reboot,
    cmd_reboot_bootloader,
    cmd_serial_control,
    cmd_set_vtype,
    cmd_switch_vehicle,
)
from ._helpers import request_streams as request_streams
from ._helpers import send_fence_item_int as send_fence_item_int
from ._helpers import send_heartbeat as send_heartbeat
from ._helpers import send_mission_item_int as send_mission_item_int
from ._helpers import send_rally_item_int as send_rally_item_int
from ._mission import (
    cmd_fence_upload,
    cmd_mission_clear,
    cmd_mission_download,
    cmd_mission_set_current,
    cmd_mission_start,
    cmd_mission_upload,
    cmd_rally_upload,
)
from ._ntrip import cmd_ntrip_start, cmd_ntrip_stop
from ._setup import (
    cmd_cal_accel,
    cmd_cal_accel_next,
    cmd_cal_baro,
    cmd_cal_cancel,
    cmd_cal_compass,
    cmd_cal_compass_accept,
    cmd_cal_gyro,
    cmd_cal_level,
    cmd_log_cancel,
    cmd_log_download,
    cmd_log_list,
    cmd_param_load,
    cmd_param_request_all,
    cmd_param_save,
    cmd_param_save_to_flash,
    cmd_param_set,
)

if TYPE_CHECKING:
    from ..drone_link import DroneLink


_DISPATCH = {
    "arm": cmd_arm,
    "disarm": cmd_disarm,
    "force_disarm": cmd_force_disarm,
    "rtl": cmd_rtl,
    "mode": cmd_mode,
    "takeoff": cmd_takeoff,
    "drop": cmd_drop,
    "drop_stop": cmd_drop_stop,
    "mission_start": cmd_mission_start,
    "mission_clear": cmd_mission_clear,
    "mission_upload": cmd_mission_upload,
    "fence_upload": cmd_fence_upload,
    "mission_download": cmd_mission_download,
    "rally_upload": cmd_rally_upload,
    "mission_set_current": cmd_mission_set_current,
    "set_vtype": cmd_set_vtype,
    "guided_goto": cmd_guided_goto,
    "switch_vehicle": cmd_switch_vehicle,
    "clear_summary": cmd_clear_summary,
    "cal_compass": cmd_cal_compass,
    "cal_compass_accept": cmd_cal_compass_accept,
    "cal_accel": cmd_cal_accel,
    "cal_accel_next": cmd_cal_accel_next,
    "cal_gyro": cmd_cal_gyro,
    "cal_level": cmd_cal_level,
    "cal_baro": cmd_cal_baro,
    "cal_cancel": cmd_cal_cancel,
    "param_request_all": cmd_param_request_all,
    "param_set": cmd_param_set,
    "param_save": cmd_param_save,
    "param_save_to_flash": cmd_param_save_to_flash,
    "param_load": cmd_param_load,
    "log_list": cmd_log_list,
    "log_download": cmd_log_download,
    "log_cancel": cmd_log_cancel,
    "reboot": cmd_reboot,
    "reboot_bootloader": cmd_reboot_bootloader,
    "inspector_toggle": cmd_inspector_toggle,
    "serial_control": cmd_serial_control,
    "inject_rtcm": cmd_inject_rtcm,
    "ntrip_start": cmd_ntrip_start,
    "ntrip_stop": cmd_ntrip_stop,
    "rc_override": cmd_rc_override,
    "motor_test": cmd_motor_test,
    "motor_test_stop": cmd_motor_test_stop,
    "gimbal_angle": cmd_gimbal_angle,
    "gimbal_pitchyaw": cmd_gimbal_pitchyaw,
    "camera_trigger": cmd_camera_trigger,
    "camera_video_start": cmd_camera_video_start,
    "camera_video_stop": cmd_camera_video_stop,
    "camera_zoom": cmd_camera_zoom,
    "do_set_roi": cmd_do_set_roi,
}


# Commands that never send anything to the FC — still allowed when an
# unsupported autopilot is latched (ntrip_stop tears down the GCS-side
# client; the others only mutate GCS display/selection state).
_GCS_LOCAL = {"switch_vehicle", "set_vtype", "clear_summary", "inspector_toggle", "ntrip_stop"}


def execute(cmd: str, param, link: DroneLink, data: dict | None = None) -> dict | None:
    data = data or {}
    handler = _DISPATCH.get(cmd)
    if not handler:
        # Fail loud: an unregistered command name (client/backend version skew,
        # typo in a driving script) used to vanish without any reply, leaving
        # the caller waiting on a cmd_result forever. Found when sitl_verify.py
        # sent a stale command name and silently got nothing back.
        import logging

        logging.getLogger(__name__).warning("Unknown command %r dropped", cmd)
        return {"ok": False, "error": "unknown command: %s" % cmd}
    # 0 = no FC heartbeat latched yet, 3 = MAV_AUTOPILOT_ARDUPILOTMEGA
    # (common.xml; 8 = INVALID never latches — see handle_heartbeat). Any other
    # value is a known non-ArduPilot FC: our mode numbers, command params and
    # calibration handshakes are ArduPilot-specific (CLAUDE.md ## PX4 Status),
    # so sending them would do something unintended on the vehicle.
    ap = link.vehicle.autopilot
    if ap not in (0, 3) and cmd not in _GCS_LOCAL:
        return {"ok": False, "error": "unsupported autopilot (%s): ArduPilot only" % ap}
    try:
        return handler(link, param, data)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("Command '%s' failed", cmd)
        return {"ok": False, "error": str(exc)[:200]}
