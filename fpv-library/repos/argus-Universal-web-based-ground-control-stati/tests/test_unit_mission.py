"""Unit tests for backend/commands/_mission.py — mission/fence/rally upload,
download, timeout watchdogs, and waypoint type variants."""

import time
from unittest.mock import MagicMock, patch

from backend.commands._mission import (
    _upload_mission,
    check_mission_dl_timeout,
    cmd_mission_set_current,
    cmd_mission_start,
    cmd_mission_upload,
)
from backend.drone_link import DroneLink


def make_link():
    link = DroneLink()
    link._ser = MagicMock()
    link.connected = True
    link.vehicle.sysid = 1
    return link


# ---------------------------------------------------------------------------
# cmd_mission_start — delayed send_cmd OSError (lines 29-30)
# ---------------------------------------------------------------------------
class TestMissionStartDelayedError:
    def test_delayed_send_cmd_oserror_is_caught(self):
        """When the delayed send_cmd raises OSError, the error is caught and
        an event is added instead of crashing (lines 29-30)."""
        link = make_link()
        link.vehicle.vtype_raw = 2  # copter

        with patch("backend.commands._mission.send_cmd", side_effect=OSError("write failed")):
            cmd_mission_start(link, None, {})
            # The timer fires asynchronously — give it time
            import backend.commands._mission as m

            with m._timer_lock:
                timer = m._mission_timer
            if timer:
                timer.join(timeout=2)

        # Should have the mission_start event + the failure event
        event_types = [e.get("event_type") for e in link.events]
        assert "mission_start" in event_types
        assert "cmd_ack_fail" in event_types


# ---------------------------------------------------------------------------
# cmd_mission_upload — plane spline rejection (line 57)
# ---------------------------------------------------------------------------
class TestMissionUploadPlaneSpline:
    def test_plane_rejects_spline_waypoints(self):
        """ArduPlane does not support spline waypoints (line 57)."""
        link = make_link()
        link.vehicle.vtype_raw = 1  # plane
        wps = [
            {"lat": 34.258, "lon": 108.942, "alt": 30, "type": "spline"},
        ]
        result = cmd_mission_upload(link, None, {"waypoints": wps})
        assert result is not None
        assert result["ok"] is False
        assert result["error"]  # non-empty error message (locale-dependent)


# ---------------------------------------------------------------------------
# cmd_mission_upload — coordinate validation edge cases (lines 61-70)
# ---------------------------------------------------------------------------
class TestMissionUploadCoordValidation:
    def test_non_numeric_lat_rejected(self):
        """Non-numeric lat string triggers TypeError/ValueError path (lines 61-62)."""
        link = make_link()
        result = cmd_mission_upload(
            link,
            None,
            {
                "waypoints": [{"lat": "abc", "lon": 108.0, "alt": 30}],
            },
        )
        assert result is not None
        assert result["ok"] is False

    def test_non_numeric_alt_rejected(self):
        """Non-numeric alt triggers TypeError/ValueError path (lines 67-68)."""
        link = make_link()
        result = cmd_mission_upload(
            link,
            None,
            {
                "waypoints": [{"lat": 34.258, "lon": 108.942, "alt": "high"}],
            },
        )
        assert result is not None
        assert result["ok"] is False

    def test_alt_out_of_range_rejected(self):
        """Alt outside -500..100000 is rejected (line 69-70)."""
        link = make_link()
        result = cmd_mission_upload(
            link,
            None,
            {
                "waypoints": [{"lat": 34.258, "lon": 108.942, "alt": 200000}],
            },
        )
        assert result is not None
        assert result["ok"] is False

    def test_alt_below_min_rejected(self):
        link = make_link()
        result = cmd_mission_upload(
            link,
            None,
            {
                "waypoints": [{"lat": 34.258, "lon": 108.942, "alt": -600}],
            },
        )
        assert result is not None
        assert result["ok"] is False

    def test_none_lat_rejected(self):
        """None lat triggers TypeError path (lines 61-62)."""
        link = make_link()
        result = cmd_mission_upload(
            link,
            None,
            {
                "waypoints": [{"lat": None, "lon": 108.0, "alt": 30}],
            },
        )
        assert result is not None
        assert result["ok"] is False

    def test_too_many_waypoints_rejected(self):
        """More than 500 waypoints is rejected (line 51)."""
        link = make_link()
        wps = [{"lat": 34.0 + i * 0.001, "lon": 108.0, "alt": 30} for i in range(501)]
        result = cmd_mission_upload(link, None, {"waypoints": wps})
        assert result is not None
        assert result["ok"] is False
        assert "500" in result["error"]


# ---------------------------------------------------------------------------
# check_mission_dl_timeout — all four watchdog branches (lines 105-122)
# ---------------------------------------------------------------------------
class TestMissionDlTimeout:
    def test_dl_timeout_clears_pending(self):
        """Download timeout fires when elapsed > MISSION_DL_TIMEOUT (lines 105-108)."""
        link = make_link()
        link.mission._dl_pending = True
        link.mission._dl_start_time = time.time() - 999  # well past timeout
        check_mission_dl_timeout(link)
        assert link.mission._dl_pending is False
        assert link.mission._dl_start_time == 0.0
        assert any("mission_dl_timeout" in e.get("event_type", "") for e in link.events)

    def test_dl_not_timed_out_stays_pending(self):
        """Download within timeout window stays pending."""
        link = make_link()
        link.mission._dl_pending = True
        link.mission._dl_start_time = time.time()  # just started
        check_mission_dl_timeout(link)
        assert link.mission._dl_pending is True

    def test_mission_upload_timeout_clears(self):
        """Mission upload watchdog fires (lines 111-114)."""
        link = make_link()
        link.mission._mission_pending = True
        link.mission._mission_ul_start_time = time.time() - 999
        check_mission_dl_timeout(link)
        assert link.mission._mission_pending is False
        assert link.mission._mission_ul_start_time == 0.0
        assert any("mission_ack_fail" in e.get("event_type", "") for e in link.events)

    def test_fence_upload_timeout_clears(self):
        """Fence upload watchdog fires (lines 116-118)."""
        link = make_link()
        link.mission._fence_pending = True
        link.mission._fence_ul_start_time = time.time() - 999
        check_mission_dl_timeout(link)
        assert link.mission._fence_pending is False
        assert link.mission._fence_ul_start_time == 0.0
        assert any("fence_ack_fail" in e.get("event_type", "") for e in link.events)

    def test_rally_upload_timeout_clears(self):
        """Rally upload watchdog fires (lines 120-122)."""
        link = make_link()
        link.mission._rally_pending = True
        link.mission._rally_ul_start_time = time.time() - 999
        check_mission_dl_timeout(link)
        assert link.mission._rally_pending is False
        assert link.mission._rally_ul_start_time == 0.0
        assert any("mission_ack_fail" in e.get("event_type", "") for e in link.events)

    def test_multiple_timeouts_fire_simultaneously(self):
        """All four watchdogs can fire in a single check_mission_dl_timeout call."""
        link = make_link()
        past = time.time() - 999
        link.mission._dl_pending = True
        link.mission._dl_start_time = past
        link.mission._mission_pending = True
        link.mission._mission_ul_start_time = past
        link.mission._fence_pending = True
        link.mission._fence_ul_start_time = past
        link.mission._rally_pending = True
        link.mission._rally_ul_start_time = past

        check_mission_dl_timeout(link)

        assert not link.mission._dl_pending
        assert not link.mission._mission_pending
        assert not link.mission._fence_pending
        assert not link.mission._rally_pending


# ---------------------------------------------------------------------------
# _upload_mission — waypoint type variants (lines 139-150, 194)
# ---------------------------------------------------------------------------
class TestUploadMissionWaypointTypes:
    def test_loiter_turns_waypoint(self):
        """type=loiter_turns -> nav_cmd=18 (lines 143-144)."""
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 50, "type": "loiter_turns", "loiter_param": 5}]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        nav_items = [it for it in items if it["cmd"] == 18]
        assert len(nav_items) == 1
        assert nav_items[0]["p1"] == 5.0

    def test_loiter_time_waypoint(self):
        """type=loiter_time -> nav_cmd=19 (lines 146-147)."""
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 50, "type": "loiter_time", "loiter_param": 20}]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        nav_items = [it for it in items if it["cmd"] == 19]
        assert len(nav_items) == 1
        assert nav_items[0]["p1"] == 20.0

    def test_spline_waypoint(self):
        """type=spline -> nav_cmd=82 (lines 149-150)."""
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 50, "type": "spline", "delay": 3}]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        nav_items = [it for it in items if it["cmd"] == 82]
        assert len(nav_items) == 1
        assert nav_items[0]["p1"] == 3.0

    def test_speed_command_inserted(self):
        """Waypoint with speed > 0 inserts DO_CHANGE_SPEED (cmd 178) (lines 139-140)."""
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 50, "speed": 5}]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        speed_items = [it for it in items if it["cmd"] == 178]
        assert len(speed_items) == 1
        assert speed_items[0]["p1"] == 1  # speed type = airspeed
        assert speed_items[0]["p2"] == 5.0

    def test_seq_to_wp_with_speed_waypoints(self):
        """seq_to_wp mapping accounts for speed command insertion (line 194)."""
        link = make_link()
        wps = [
            {"lat": 34.258, "lon": 108.942, "alt": 50, "speed": 5},
            {"lat": 34.259, "lon": 108.943, "alt": 50},
        ]
        _upload_mission(link, wps, 50.0)
        s2w = link.mission._seq_to_wp
        # wp0 has speed cmd before it: home(0), takeoff(1), speed(2), wp0(3), wp1(4), RTL(5)
        assert s2w[3] == 0
        assert s2w[4] == 1

    def test_default_waypoint_type(self):
        """No type specified defaults to nav_cmd=16 (NAV_WAYPOINT)."""
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 50}]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        # home(cmd=16), takeoff(cmd=22), wp(cmd=16), RTL(cmd=20)
        wp_items = [it for it in items if it["cmd"] == 16 and it["seq"] > 0]
        assert len(wp_items) == 1

    def test_delay_on_regular_waypoint(self):
        """Regular waypoint with delay sets p1 (line 153)."""
        link = make_link()
        wps = [{"lat": 34.258, "lon": 108.942, "alt": 50, "delay": 7}]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        wp_item = [it for it in items if it["cmd"] == 16 and it["seq"] > 0][0]
        assert wp_item["p1"] == 7.0

    def test_multiple_advanced_commands_on_single_wp(self):
        """A waypoint with servo + roi + cam_trig + yaw + vtol + drop
        generates all auxiliary items and correct seq_to_wp mapping."""
        link = make_link()
        wps = [
            {
                "lat": 34.258,
                "lon": 108.942,
                "alt": 50,
                "cmd_servo": {"num": 9, "pwm": 1100},
                "cmd_roi": {"lat": 34.26, "lon": 108.95, "alt": 50},
                "cmd_cam_trig": {"dist": 25},
                "cmd_yaw": {"deg": 90, "dir": 1},
                "cmd_vtol": {"mode": 4},
                "drop": True,
            }
        ]
        _upload_mission(link, wps, 50.0)
        items = link.mission._mission_items
        cmds = [it["cmd"] for it in items]
        # Should include: 16(home), 22(takeoff), 16(wp), 183(servo), 201(roi),
        # 206(cam), 115(yaw), 3000(vtol), 181(drop), 20(RTL)
        assert 183 in cmds
        assert 201 in cmds
        assert 206 in cmds
        assert 115 in cmds
        assert 3000 in cmds
        assert 181 in cmds
        # seq_to_wp should map the nav waypoint seq to wp index 0
        assert 0 in link.mission._seq_to_wp.values()


# ---------------------------------------------------------------------------
# cmd_mission_set_current — jump to waypoint during flight (msg 41)
# ---------------------------------------------------------------------------
class TestMissionSetCurrent:
    def test_sends_msg_41_with_correct_seq(self):
        """Sends MISSION_SET_CURRENT (msg 41) with wp_index resolved to seq."""
        link = make_link()
        # Simulate a prior upload that mapped seq 5 -> wp_index 2
        link.mission._seq_to_wp = {2: 0, 3: 1, 5: 2}
        cmd_mission_set_current(link, None, {"wp_index": 2})

        # Should have sent a frame with msg 41
        assert link._ser.write.called
        frame = link._ser.write.call_args[0][0]
        assert frame[7] == 41  # msg ID at offset 7 in MAVLink v2 frame
        # seq should be 5 (from _seq_to_wp reverse lookup)
        import struct

        payload_start = 10  # MAVLink v2: 10 bytes header
        seq = struct.unpack_from("<H", frame, payload_start)[0]
        assert seq == 5

    def test_fallback_seq_when_no_mapping(self):
        """Falls back to wp_index + 2 when _seq_to_wp has no match."""
        link = make_link()
        link.mission._seq_to_wp = {}
        cmd_mission_set_current(link, None, {"wp_index": 3})

        frame = link._ser.write.call_args[0][0]
        import struct

        payload_start = 10
        seq = struct.unpack_from("<H", frame, payload_start)[0]
        assert seq == 5  # 3 + 2

    def test_event_logged(self):
        """An event is added for the jump command."""
        link = make_link()
        link.mission._seq_to_wp = {4: 1}
        cmd_mission_set_current(link, None, {"wp_index": 1})
        assert any(e.get("event_type") == "mission_set_current" for e in link.events)

    def test_param_fallback(self):
        """When wp_index is not in data, falls back to param argument."""
        link = make_link()
        link.mission._seq_to_wp = {}
        cmd_mission_set_current(link, 7, {})

        frame = link._ser.write.call_args[0][0]
        import struct

        payload_start = 10
        seq = struct.unpack_from("<H", frame, payload_start)[0]
        assert seq == 9  # 7 + 2
