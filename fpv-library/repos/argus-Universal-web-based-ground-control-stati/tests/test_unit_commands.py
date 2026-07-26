"""Unit tests: command builder and mission upload logic."""

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.commands import execute
from backend.drone_link import DroneLink


def make_link():
    link = DroneLink()
    link._ser = MagicMock()
    link.connected = True
    link.vehicle.sysid = 1
    return link


class TestCommandExecute:
    def test_arm_sends(self):
        link = make_link()
        execute("arm", None, link)
        assert link._ser.write.called

    def test_disarm_sends(self):
        link = make_link()
        execute("disarm", None, link)
        assert link._ser.write.called

    def test_force_disarm_sends(self):
        link = make_link()
        execute("force_disarm", None, link)
        assert link._ser.write.called

    def test_rtl_copter(self):
        link = make_link()
        link.vehicle.vtype_raw = 2
        execute("rtl", None, link)
        assert any("返航" in e["text"] for e in link.events)
        # MAVLink v2 frame: 10-byte header + payload; SET_MODE payload starts at byte 10.
        # Payload layout: mode(uint32 LE) + sysid(u8) + base_mode(u8)
        raw = link._ser.write.call_args[0][0]
        assert raw[10:14] == b"\x06\x00\x00\x00"  # mode=6 for copter RTL

    def test_rtl_plane(self):
        link = make_link()
        link.vehicle.vtype_raw = 1
        execute("rtl", None, link)
        assert any("返航" in e["text"] for e in link.events)
        # Plane RTL must use mode 11 (standard RTL), NOT mode 21 (Q-RTL/QuadPlane)
        raw = link._ser.write.call_args[0][0]
        assert raw[10:14] == b"\x0b\x00\x00\x00"  # mode=11 for plane RTL

    def test_mode_change(self):
        link = make_link()
        execute("mode", 5, link)
        assert any("模式" in e["text"] for e in link.events)

    def test_takeoff(self):
        link = make_link()
        execute("takeoff", None, link, data={"alt": 50})
        assert any("起飞" in e["text"] for e in link.events)

    def test_drop(self):
        link = make_link()
        execute("drop", None, link)
        assert any("投放" in e["text"] for e in link.events)

    def test_set_vtype_plane(self):
        link = make_link()
        execute("set_vtype", None, link, data={"vtype": "plane"})
        assert link.vehicle.force_plane is True

    def test_set_vtype_auto(self):
        link = make_link()
        execute("set_vtype", None, link, data={"vtype": "auto"})
        assert link.vehicle.force_plane is None

    def test_clear_summary(self):
        link = make_link()
        link.vehicle.flight_summary = {"duration": 100}
        execute("clear_summary", None, link)
        assert link.vehicle.flight_summary is None

    def test_drop_stop(self):
        link = make_link()
        execute("drop_stop", None, link)
        assert any("投放停止" in e["text"] for e in link.events)

    def test_mission_start_copter(self):
        link = make_link()
        link.vehicle.vtype_raw = 2  # copter
        execute("mission_start", None, link)
        assert any("任务开始" in e["text"] for e in link.events)
        assert link._ser.write.called

    def test_mission_start_plane(self):
        link = make_link()
        link.vehicle.vtype_raw = 1  # plane
        execute("mission_start", None, link)
        assert any("任务开始" in e["text"] for e in link.events)

    def test_mission_clear(self):
        link = make_link()
        execute("mission_clear", None, link)
        assert any("任务已清除" in e["text"] for e in link.events)

    def test_fence_upload_sets_pending(self):
        link = make_link()
        polygon = [
            {"lat": 34.0, "lon": 108.0},
            {"lat": 34.1, "lon": 108.0},
            {"lat": 34.1, "lon": 108.1},
        ]
        execute("fence_upload", None, link, data={"polygon": polygon})
        assert link.mission._fence_pending is True
        assert len(link.mission._fence_items) == 3
        assert any("围栏" in e["text"] for e in link.events)

    def test_fence_upload_too_few_points(self):
        link = make_link()
        result = execute(
            "fence_upload",
            None,
            link,
            data={
                "polygon": [{"lat": 34.0, "lon": 108.0}, {"lat": 34.1, "lon": 108.0}],
            },
        )
        assert result is not None and not result["ok"]
        assert "3" in result["error"]

    def test_guided_goto(self):
        link = make_link()
        link.vehicle.vtype_raw = 2  # copter
        execute(
            "guided_goto",
            None,
            link,
            data={
                "lat": 34.25800,
                "lon": 108.94200,
                "alt": 50,
            },
        )
        assert any("引导飞往" in e["text"] and "34.25800" in e["text"] for e in link.events)

    def test_cal_compass(self):
        link = make_link()
        execute("cal_compass", None, link)
        assert any("罗盘校准" in e["text"] for e in link.events)

    def test_cal_accel(self):
        link = make_link()
        execute("cal_accel", None, link)
        assert any("加速度计校准" in e["text"] for e in link.events)

    def test_cal_gyro(self):
        link = make_link()
        execute("cal_gyro", None, link)
        assert any("陀螺仪校准" in e["text"] for e in link.events)

    def test_cal_level(self):
        link = make_link()
        execute("cal_level", None, link)
        assert any("水平校准" in e["text"] for e in link.events)

    def test_cal_baro(self):
        link = make_link()
        execute("cal_baro", None, link)
        assert any("气压计校准" in e["text"] for e in link.events)

    def test_cal_cancel(self):
        link = make_link()
        execute("cal_cancel", None, link)
        assert any("取消" in e["text"] for e in link.events)

    def test_mission_download(self):
        link = make_link()
        execute("mission_download", None, link)
        assert link.mission._dl_pending is True
        assert link.mission._dl_total == 0
        assert link.mission._dl_items == []
        assert any("下载" in e["text"] for e in link.events)

    def test_param_request_all(self):
        link = make_link()
        execute("param_request_all", None, link)
        assert link.param_mgr.fetching is True

    def test_param_set(self):
        link = make_link()
        execute("param_set", None, link, data={"name": "ARMING_CHECK", "value": 0})
        assert any("ARMING_CHECK" in e["text"] for e in link.events)

    def test_param_save(self):
        link = make_link()
        link.param_mgr.params = {
            "ARMING_CHECK": {"name": "ARMING_CHECK", "value": 1.0, "type": 9, "index": 0},
        }
        result = execute("param_save", None, link)
        assert result is not None and result["ok"]
        assert result["path"].endswith(".json")
        # clean up
        import os

        if os.path.exists(result["path"]):
            os.remove(result["path"])

    def test_param_load(self):
        link = make_link()
        link.param_mgr.params = {
            "ARMING_CHECK": {"name": "ARMING_CHECK", "value": 1.0, "type": 9, "index": 0},
        }
        params_dir = Path(__file__).resolve().parent.parent / "params"
        params_dir.mkdir(exist_ok=True)
        tmp_path = params_dir / "test_load.json"
        tmp_path.write_text(json.dumps({"ARMING_CHECK": 0.0}))
        result = execute("param_load", None, link, data={"path": str(tmp_path)})
        # cmd_param_load now runs the actual load in a background thread to
        # avoid blocking the asyncio event loop with time.sleep iterations.
        assert result is not None and result["ok"] is True
        assert result.get("started") is True
        # Give the worker a moment to apply the change.
        import time as _t

        for _ in range(20):
            if link._ser.write.called:
                break
            _t.sleep(0.05)
        assert link._ser.write.called
        tmp_path.unlink()

    def test_param_load_path_traversal(self):
        link = make_link()
        result = execute("param_load", None, link, data={"path": "/etc/passwd.json"})
        assert result is not None and not result["ok"]
        assert "params directory" in result["error"]

    def test_log_list(self):
        link = make_link()
        execute("log_list", None, link)
        assert link.log_dl._log_list == []
        assert any("日志" in e["text"] for e in link.events)

    def test_log_download(self):
        link = make_link()
        link.log_dl._log_list = [{"id": 5, "size": 10240}]
        execute("log_download", None, link, data={"id": 5})
        assert link.log_dl._log_download_id == 5
        assert link.log_dl._log_download_size == 10240
        assert any("下载 #5" in e["text"] for e in link.events)

    def test_log_download_invalid_id(self):
        link = make_link()
        link.log_dl._log_list = [{"id": 5, "size": 10240}]
        result = execute("log_download", None, link, data={"id": 99})
        assert result is not None and not result["ok"]

    def test_log_cancel(self):
        link = make_link()
        link.log_dl._log_download_id = 5
        execute("log_cancel", None, link)
        assert link.log_dl._log_download_id == -1
        assert any("取消" in e["text"] for e in link.events)

    def test_rc_override(self):
        link = make_link()
        channels = [1500, 1500, 1100, 1500, 1000, 1000, 1000, 1000]
        execute("rc_override", None, link, data={"channels": channels})
        assert link._ser.write.called


class TestReboot:
    def test_reboot(self):
        link = make_link()
        execute("reboot", None, link)
        assert any("重启飞控" in e["text"] for e in link.events)
        assert link._ser.write.called

    def test_reboot_bootloader(self):
        link = make_link()
        execute("reboot_bootloader", None, link)
        assert any("引导程序" in e["text"] for e in link.events)


class TestMotorTest:
    def test_motor_test(self):
        link = make_link()
        execute("motor_test", None, link, data={"motor": 0, "throttle": 10, "duration": 2})
        assert any("电机测试" in e["text"] for e in link.events)
        assert link._ser.write.called

    def test_motor_test_stop(self):
        link = make_link()
        execute("motor_test_stop", None, link)
        assert link._ser.write.call_count >= 8


class TestGimbal:
    def test_gimbal_angle(self):
        link = make_link()
        execute("gimbal_angle", None, link, data={"pitch": -30, "yaw": 90})
        assert link._ser.write.called


class TestCamera:
    def test_camera_trigger(self):
        link = make_link()
        execute("camera_trigger", None, link)
        assert link._ser.write.called

    def test_camera_video_start(self):
        link = make_link()
        execute("camera_video_start", None, link)
        assert link._ser.write.called

    def test_camera_video_stop(self):
        link = make_link()
        execute("camera_video_stop", None, link)
        assert link._ser.write.called

    def test_camera_zoom(self):
        link = make_link()
        execute("camera_zoom", None, link, data={"zoom": 2.5})
        assert link._ser.write.called


class TestSwitchVehicle:
    def test_switch_vehicle(self):
        link = make_link()
        execute("switch_vehicle", None, link, data={"sysid": 3})
        assert link.active_sysid == 3
        assert link.vehicle.sysid == 3
        assert any("sysid=3" in e["text"] for e in link.events)


class TestInjectRtcm:
    def test_inject_rtcm(self):
        link = make_link()
        raw_data = b"\x01\x02\x03\x04\x05"
        b64 = base64.b64encode(raw_data).decode()
        execute("inject_rtcm", None, link, data={"data": b64})
        assert link._ser.write.called

    def test_inject_rtcm_large(self):
        link = make_link()
        raw_data = b"\xaa" * 250
        b64 = base64.b64encode(raw_data).decode()
        execute("inject_rtcm", None, link, data={"data": b64})
        assert link._ser.write.call_count >= 2  # 250/180 = 2 chunks

    def test_inject_rtcm_empty(self):
        link = make_link()
        execute("inject_rtcm", None, link, data={"data": ""})
        assert not link._ser.write.called


class TestRallyUpload:
    def test_rally_upload(self):
        link = make_link()
        points = [
            {"lat": 30.0, "lon": 120.0, "alt": 100},
            {"lat": 30.1, "lon": 120.1, "alt": 100},
        ]
        execute("rally_upload", None, link, data={"points": points})
        assert any("备降点" in e["text"] for e in link.events)

    def test_rally_upload_empty(self):
        link = make_link()
        execute("rally_upload", None, link, data={"points": []})
        assert not any("备降" in e["text"] for e in link.events)


class TestSerialControl:
    def test_serial_control(self):
        link = make_link()
        execute("serial_control", None, link, data={"text": "help\n"})
        assert link._ser.write.called

    def test_serial_control_empty(self):
        link = make_link()
        execute("serial_control", None, link, data={"text": ""})
        assert not link._ser.write.called


class TestDoSetRoi:
    def test_do_set_roi(self):
        link = make_link()
        execute("do_set_roi", None, link, data={"lat": 30.5, "lon": 120.3, "alt": 100})
        assert link._ser.write.called


class TestInspectorToggle:
    def test_toggle_on(self):
        link = make_link()
        assert link.inspector_enabled is False
        execute("inspector_toggle", None, link)
        assert link.inspector_enabled is True

    def test_toggle_off(self):
        link = make_link()
        link.inspector_enabled = True
        execute("inspector_toggle", None, link)
        assert link.inspector_enabled is False


class TestMissionUpload:
    def test_empty_waypoints_returns_error(self):
        link = make_link()
        result = execute("mission_upload", None, link, data={"waypoints": []})
        assert result and not result["ok"]

    def test_invalid_coords_returns_error(self):
        link = make_link()
        result = execute(
            "mission_upload",
            None,
            link,
            data={
                "waypoints": [{"lat": 0, "lon": 0, "alt": 30}],
            },
        )
        assert result and not result["ok"]

    def test_valid_mission(self):
        link = make_link()
        wps = [
            {"lat": 34.258, "lon": 108.942, "alt": 30},
            {"lat": 34.259, "lon": 108.943, "alt": 30, "drop": True},
        ]
        execute(
            "mission_upload",
            None,
            link,
            data={
                "waypoints": wps,
                "takeoff_alt": 30,
            },
        )
        assert link.mission._mission_pending
        # home(0) + takeoff(1) + wp1(2) + wp2(3) + drop(4) + RTL(5) = 6
        assert len(link.mission._mission_items) == 6
        assert any("任务" in e["text"] for e in link.events)

    def test_advcmd_servo_uploaded(self):
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 30, "cmd_servo": {"num": 9, "pwm": 1100}}]
        execute("mission_upload", None, link, data={"waypoints": wps, "takeoff_alt": 30})
        items = link.mission._mission_items
        cmds = [it["cmd"] for it in items]
        assert 183 in cmds
        servo_item = [it for it in items if it["cmd"] == 183][0]
        assert servo_item["p1"] == 9
        assert servo_item["p2"] == 1100.0

    def test_advcmd_cam_trig_uploaded(self):
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 30, "cmd_cam_trig": {"dist": 25}}]
        execute("mission_upload", None, link, data={"waypoints": wps, "takeoff_alt": 30})
        cmds = [it["cmd"] for it in link.mission._mission_items]
        assert 206 in cmds

    def test_advcmd_yaw_uploaded_with_direction(self):
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 30, "cmd_yaw": {"deg": 90, "dir": -1}}]
        execute("mission_upload", None, link, data={"waypoints": wps, "takeoff_alt": 30})
        items = link.mission._mission_items
        yaw_item = [it for it in items if it["cmd"] == 115][0]
        assert yaw_item["p1"] == 90.0
        assert yaw_item["p3"] == -1.0

    def test_advcmd_vtol_uploaded(self):
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 30, "cmd_vtol": {"mode": 3}}]
        execute("mission_upload", None, link, data={"waypoints": wps, "takeoff_alt": 30})
        cmds = [it["cmd"] for it in link.mission._mission_items]
        assert 3000 in cmds

    def test_advcmd_roi_uses_coordinates(self):
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 30, "cmd_roi": {"lat": 34.26, "lon": 108.95, "alt": 50}}]
        execute("mission_upload", None, link, data={"waypoints": wps, "takeoff_alt": 30})
        items = link.mission._mission_items
        roi_item = [it for it in items if it["cmd"] == 201][0]
        assert abs(roi_item["lat"] - 34.26) < 0.001
        assert abs(roi_item["lon"] - 108.95) < 0.001
        assert roi_item["alt"] == 50.0

    def test_advcmd_seq_to_wp_mapping(self):
        link = make_link()
        wps = [
            {"lat": 34.258, "lon": 108.942, "alt": 30, "cmd_servo": {"num": 1, "pwm": 1500}},
            {"lat": 34.259, "lon": 108.943, "alt": 30},
        ]
        execute("mission_upload", None, link, data={"waypoints": wps, "takeoff_alt": 30})
        s2w = link.mission._seq_to_wp
        assert 0 in s2w.values()
        assert 1 in s2w.values()


class TestDroneLinkLog:
    def test_start_stop_log(self):
        link = make_link()
        link._start_log()
        assert link._logfile is not None
        path = link.get_log_path()
        assert path is not None
        assert path.endswith(".csv")
        link._stop_log()
        assert link._logfile is None
        assert link.get_log_path() is None
        import os

        if os.path.exists(path):
            os.remove(path)

    def test_state_includes_log_active(self):
        link = make_link()
        assert link.get_state()["log_active"] is False
        link._start_log()
        assert link.get_state()["log_active"] is True
        link._stop_log()
        assert link.get_state()["log_active"] is False
        import glob
        import os

        for f in glob.glob(str(Path(__file__).resolve().parent.parent / "logs" / "*.csv")):
            os.remove(f)


class TestDroneLink:
    def test_is_plane_copter(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2
        assert not link.is_plane()

    def test_is_plane_plane(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 1
        assert link.is_plane()

    def test_force_plane_override(self):
        link = DroneLink()
        link.vehicle.vtype_raw = 2
        link.vehicle.force_plane = True
        assert link.is_plane()

    def test_add_event_trims(self):
        link = DroneLink()
        for i in range(150):
            link.add_event(f"event {i}")
        assert len(link.events) <= 100

    def test_get_state_structure(self):
        link = DroneLink()
        state = link.get_state()
        assert "type" in state
        assert state["type"] == "state"
        assert "connected" in state
        assert "mode" in state
        assert "lat" in state
        assert "voltage" in state
        assert "flight_summary" in state


class TestTakeoffValidation:
    def test_alt_below_min(self):
        link = make_link()
        result = execute("takeoff", None, link, data={"alt": 0.5})
        assert result is not None
        assert result["ok"] is False

    def test_alt_above_max(self):
        link = make_link()
        result = execute("takeoff", None, link, data={"alt": 1500})
        assert result is not None
        assert result["ok"] is False

    def test_valid_alt(self):
        link = make_link()
        result = execute("takeoff", None, link, data={"alt": 30})
        assert result is None


class TestMotorTestValidation:
    def test_motor_index_negative(self):
        link = make_link()
        result = execute("motor_test", None, link, data={"motor": -1, "throttle": 5, "duration": 2})
        assert result is not None
        assert result["ok"] is False

    def test_motor_index_too_high(self):
        link = make_link()
        result = execute("motor_test", None, link, data={"motor": 8, "throttle": 5, "duration": 2})
        assert result is not None
        assert result["ok"] is False

    def test_throttle_too_high(self):
        link = make_link()
        result = execute("motor_test", None, link, data={"motor": 0, "throttle": 150, "duration": 2})
        assert result is not None
        assert result["ok"] is False

    def test_duration_too_long(self):
        link = make_link()
        result = execute("motor_test", None, link, data={"motor": 0, "throttle": 5, "duration": 60})
        assert result is not None
        assert result["ok"] is False

    def test_valid_motor_test(self):
        link = make_link()
        result = execute("motor_test", None, link, data={"motor": 0, "throttle": 10, "duration": 3})
        assert result is None


class TestGimbalValidation:
    def test_pitch_out_of_range(self):
        link = make_link()
        result = execute("gimbal_angle", None, link, data={"pitch": 100, "yaw": 0})
        assert result is not None
        assert result["ok"] is False

    def test_yaw_out_of_range(self):
        link = make_link()
        result = execute("gimbal_angle", None, link, data={"pitch": 0, "yaw": 200})
        assert result is not None
        assert result["ok"] is False

    def test_valid_gimbal(self):
        link = make_link()
        result = execute("gimbal_angle", None, link, data={"pitch": -45, "yaw": 90})
        assert result is None


class TestRcOverride:
    def test_too_few_channels(self):
        link = make_link()
        result = execute("rc_override", None, link, data={"channels": [1500, 1500]})
        assert result is None

    def test_valid_8_channels(self):
        link = make_link()
        channels = [1500] * 8
        result = execute("rc_override", None, link, data={"channels": channels})
        assert result is None


class TestExecuteDispatch:
    def test_unknown_command_fails_loud(self):
        """Unknown command names must produce an error cmd_result, not
        silence — a caller with a stale command name would otherwise wait
        forever (found via sitl_verify sending a renamed command)."""
        link = make_link()
        result = execute("nonexistent_xyz", None, link)
        assert result == {"ok": False, "error": "unknown command: nonexistent_xyz"}

    def test_unsupported_autopilot_blocks_fc_commands(self):
        """A latched non-ArduPilot FC (e.g. PX4=12) must refuse FC-bound
        commands — our mode numbers and command params are ArduPilot-specific
        and would do something unintended on another stack."""
        link = make_link()
        link.vehicle.autopilot = 12  # MAV_AUTOPILOT_PX4
        for cmd in ("arm", "mode", "cal_accel", "param_set", "mission_start"):
            r = execute(cmd, 0, link)
            assert r == {"ok": False, "error": "unsupported autopilot (12): ArduPilot only"}
        assert not link._ser.write.called

    def test_unsupported_autopilot_allows_gcs_local_commands(self):
        link = make_link()
        link.vehicle.autopilot = 12
        assert execute("switch_vehicle", 2, link) is None  # dispatched, no error
        assert link.active_sysid == 2
        execute("inspector_toggle", None, link)
        assert link.inspector_enabled is True
        execute("set_vtype", None, link, data={"vtype": "plane"})
        assert link.vehicle.force_plane is True

    def test_ardupilot_and_unlatched_autopilot_pass(self):
        for ap in (0, 3):  # 0 = no heartbeat yet, 3 = ARDUPILOTMEGA
            link = make_link()
            link.vehicle.autopilot = ap
            execute("arm", None, link)
            assert link._ser.write.called

    def test_exception_caught(self):
        import backend.commands as cmd_mod

        link = make_link()

        def raise_err(_l, _p, _d):
            raise RuntimeError("test")

        cmd_mod._DISPATCH["_test_err"] = raise_err
        try:
            result = execute("_test_err", None, link)
            assert result["ok"] is False
            assert "test" in result["error"]
        finally:
            del cmd_mod._DISPATCH["_test_err"]


class TestNtripValidation:
    def test_missing_host_rejected(self):
        link = make_link()
        r = execute("ntrip_start", None, link, data={"port": 2101, "mountpoint": "M"})
        assert r and r["ok"] is False and r["error"]

    def test_bad_port_rejected(self):
        link = make_link()
        r = execute(
            "ntrip_start",
            None,
            link,
            data={
                "host": "rtk.example.com",
                "port": 99999,
                "mountpoint": "M",
            },
        )
        assert r and r["ok"] is False and r["error"]

    def test_port_not_int_rejected(self):
        link = make_link()
        r = execute(
            "ntrip_start",
            None,
            link,
            data={
                "host": "rtk.example.com",
                "port": "not-a-number",
                "mountpoint": "M",
            },
        )
        assert r and r["ok"] is False

    def test_missing_mountpoint_rejected(self):
        link = make_link()
        r = execute(
            "ntrip_start",
            None,
            link,
            data={
                "host": "rtk.example.com",
                "port": 2101,
            },
        )
        assert r and r["ok"] is False and r["error"]

    def test_crlf_injection_rejected(self):
        # Request smuggling defense: any field interpolated into the HTTP
        # request must reject CR/LF.
        link = make_link()
        r = execute(
            "ntrip_start",
            None,
            link,
            data={
                "host": "rtk.example.com",
                "port": 2101,
                "mountpoint": "A\r\nX-Injected: yes",
            },
        )
        assert r and r["ok"] is False

    def test_stop_when_idle_is_noop(self):
        link = make_link()
        assert link.ntrip_thread is None
        execute("ntrip_stop", None, link)  # must not raise
        assert link.ntrip_thread is None


class TestNtripLoop:
    """End-to-end mock of the NTRIP client thread without a real socket."""

    def _make_fake_socket(self, header: bytes, body_chunks: list[bytes]):
        """Return a mock socket that yields header then body_chunks then EOF."""
        from unittest.mock import MagicMock

        sock = MagicMock()
        chunks = iter([header, *body_chunks])

        def recv(_n):
            try:
                return next(chunks)
            except StopIteration:
                return b""

        sock.recv.side_effect = recv
        return sock

    def test_icy_response_streams_rtcm(self, monkeypatch):
        """ICY 200 OK header → body bytes get injected as GPS_RTCM_DATA."""
        import socket as socket_mod
        import threading

        from backend.commands import _ntrip

        # Fake socket: ICY header + 200 bytes of fake RTCM (one full chunk + 20).
        header = b"ICY 200 OK\r\nServer: NTRIP Foo\r\n\r\n"
        body = b"\xd3" + b"\x00" * 199  # 200 bytes starting with RTCM3 preamble
        sock = self._make_fake_socket(header, [body])
        monkeypatch.setattr(socket_mod, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        link._ser.reset_mock()

        stop_event = threading.Event()
        t = threading.Thread(
            target=_ntrip._ntrip_loop,
            args=(link, "h", 1, "M", "u", "p", stop_event),
            daemon=True,
        )
        t.start()
        t.join(timeout=3)
        assert not t.is_alive(), "ntrip loop should exit when recv returns EOF"

        # Should have sent at least one MAVLink frame containing the 0xFD prefix
        # (standard MAVLink 2 magic) or the PL-Link wrapper byte.
        assert link._ser.write.called
        # Connected + disconnected event traces.
        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_connected" in event_types
        assert "ntrip_disconnected" in event_types

    def test_bad_response_records_error(self, monkeypatch):
        import socket as socket_mod
        import threading

        from backend.commands import _ntrip

        header = b"HTTP/1.0 401 Unauthorized\r\n\r\n"
        sock = self._make_fake_socket(header, [])
        monkeypatch.setattr(socket_mod, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop_event = threading.Event()
        t = threading.Thread(
            target=_ntrip._ntrip_loop,
            args=(link, "h", 1, "M", "u", "p", stop_event),
            daemon=True,
        )
        t.start()
        t.join(timeout=3)

        event_types = [e["event_type"] for e in link.events]
        assert "ntrip_error" in event_types

    def test_stop_event_breaks_loop(self, monkeypatch):
        """stop_event.set() during streaming makes the loop exit on next recv."""
        import socket as socket_mod
        import threading
        import time

        from backend.commands import _ntrip

        header = b"ICY 200 OK\r\n\r\n"
        from unittest.mock import MagicMock

        sock = MagicMock()
        # First recv returns header; thereafter return small RTCM chunks
        # indefinitely so the loop is steady-state when stop_event fires.
        calls = {"n": 0}

        def fake_recv(_n):
            calls["n"] += 1
            return header if calls["n"] == 1 else b"\xd3" * 50

        sock.recv.side_effect = fake_recv

        monkeypatch.setattr(socket_mod, "create_connection", lambda *a, **kw: sock)

        link = make_link()
        stop_event = threading.Event()
        t = threading.Thread(
            target=_ntrip._ntrip_loop,
            args=(link, "h", 1, "M", "u", "p", stop_event),
            daemon=True,
        )
        t.start()
        time.sleep(0.1)  # let it loop a few times
        stop_event.set()
        t.join(timeout=5)
        assert not t.is_alive(), "stop_event should break the recv loop"
