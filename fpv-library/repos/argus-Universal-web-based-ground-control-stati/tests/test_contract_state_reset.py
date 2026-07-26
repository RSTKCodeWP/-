"""Contract test: _reset_session_state() resets all expected session fields.

Verifies:
1. After _reset_session_state(), the specific fields listed in the reset
   method are at their cleared values.
2. The state dataclass defaults match what _reset_session_state sets (so future
   field additions don't silently diverge).
3. When drone is armed and flight_summary is set, a re-arm event (via
   handle_heartbeat) clears flight_summary.
"""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

import pytest

from backend.drone_link import DroneLink
from backend.mavlink_handlers import handle_heartbeat
from backend.state import (
    AttitudeState,
    LogState,
    MissionState,
    VehicleState,
)


@pytest.fixture()
def link(tmp_path, monkeypatch):
    """Create a DroneLink with mocked serial + log dir."""
    import backend.drone_link as _dl_module

    fake_backend = tmp_path / "backend"
    fake_backend.mkdir()
    fake_drone_link = fake_backend / "drone_link.py"
    fake_drone_link.touch()
    monkeypatch.setattr(_dl_module, "__file__", str(fake_drone_link))

    dl = DroneLink()
    dl._ser = MagicMock()
    return dl


class TestResetSessionState:
    def test_connected_is_false_after_reset(self, link):
        link.connected = True
        link._reset_session_state()
        assert link.connected is False

    def test_vtype_raw_zeroed_after_reset(self, link):
        link.vehicle.vtype_raw = 6
        link._reset_session_state()
        assert link.vehicle.vtype_raw == 0

    def test_force_plane_none_after_reset(self, link):
        link.vehicle.force_plane = True
        link._reset_session_state()
        assert link.vehicle.force_plane is None

    def test_home_set_false_after_reset(self, link):
        link.attitude._home_set = True
        link._reset_session_state()
        assert link.attitude._home_set is False

    def test_frame_count_zeroed_after_reset(self, link):
        link.frame_count = 999
        link._reset_session_state()
        assert link.frame_count == 0

    def test_last_frame_time_zeroed_after_reset(self, link):
        link.last_frame_time = 12345.6
        link._reset_session_state()
        assert link.last_frame_time == 0.0

    def test_mission_pending_cleared_after_reset(self, link):
        link.mission._mission_pending = True
        link.mission._fence_pending = True
        link.mission._rally_pending = True
        link.mission._dl_pending = True
        link._reset_session_state()
        assert link.mission._mission_pending is False
        assert link.mission._fence_pending is False
        assert link.mission._rally_pending is False
        assert link.mission._dl_pending is False

    def test_log_dl_reset_after_reset(self, link):
        link.log_dl._log_download_id = 42
        link.log_dl._log_download_data = bytearray(b"data")
        link._reset_session_state()
        assert link.log_dl._log_download_id == -1
        assert link.log_dl._log_download_data == bytearray()

    def test_prearm_messages_cleared_after_reset(self, link):
        link._prearm_messages = ["err1", "err2"]
        link._reset_session_state()
        assert link._prearm_messages == []

    def test_flight_summary_cleared_after_reset(self, link):
        """Regression: flight_summary was not cleared on reconnect — stale
        summary from a previous session would appear as if from the new one."""
        link.vehicle.flight_summary = {"duration": 100, "max_alt": 50.0}
        link._reset_session_state()
        assert link.vehicle.flight_summary is None


class TestResetMatchesDataclassDefaults:
    """Ensure _reset_session_state values align with dataclass defaults.

    For each field that _reset_session_state explicitly sets, the value it
    sets should equal the dataclass field default (so a fresh DroneLink and
    a reset DroneLink both yield the same initial state). This catches cases
    where someone adds a field with a non-zero default but forgets to add it
    to the reset method.
    """

    def test_vehicle_reset_fields_match_defaults(self, link):
        link._reset_session_state()
        # Fields that _reset_session_state explicitly sets on vehicle:
        assert link.vehicle.vtype_raw == VehicleState.vtype_raw  # 0
        assert link.vehicle.force_plane == VehicleState.force_plane  # None
        assert link.vehicle.flight_summary == VehicleState.flight_summary  # None

    def test_attitude_reset_fields_match_defaults(self, link):
        link._reset_session_state()
        # _home_set is explicitly reset to False (matches dataclass default)
        assert link.attitude._home_set == AttitudeState._home_set  # False
        # _prev_pos is reset to None (matches dataclass default)
        assert link.attitude._prev_pos == AttitudeState._prev_pos  # None

    def test_mission_reset_fields_match_defaults(self, link):
        link._reset_session_state()
        assert link.mission._mission_pending == MissionState._mission_pending  # False
        assert link.mission._fence_pending == MissionState._fence_pending  # False
        assert link.mission._rally_pending == MissionState._rally_pending  # False
        assert link.mission._dl_pending == MissionState._dl_pending  # False
        assert link.mission._dl_start_time == MissionState._dl_start_time  # 0.0
        assert link.mission._mission_ul_start_time == MissionState._mission_ul_start_time  # 0.0
        assert link.mission._fence_ul_start_time == MissionState._fence_ul_start_time  # 0.0
        assert link.mission._rally_ul_start_time == MissionState._rally_ul_start_time  # 0.0

    def test_log_reset_fields_match_defaults(self, link):
        link._reset_session_state()
        assert link.log_dl._log_download_id == LogState._log_download_id  # -1
        assert link.log_dl._log_download_size == LogState._log_download_size  # 0
        assert link.log_dl._log_download_ofs == LogState._log_download_ofs  # 0
        assert link.log_dl._log_emit_ofs == LogState._log_emit_ofs  # 0
        # _log_download_data: factory default is bytearray()
        assert link.log_dl._log_download_data == bytearray()


class TestFlightSummaryClearedOnArm:
    """Test that re-arming clears the previous flight_summary."""

    def _build_heartbeat_payload(self, mode=0, vtype=2, armed=False):
        base_mode = 0x80 if armed else 0x00
        return struct.pack("<IBBBBB", mode, vtype, 0, base_mode, 0, 3)

    def test_flight_summary_cleared_when_new_arm_fires(self, link):
        """When drone is armed (new arm event via heartbeat), flight_summary is cleared."""
        # Set up as if the drone just disarmed and produced a summary
        link.vehicle.armed = False
        link.vehicle.flight_summary = {"duration": 100, "max_alt": 50.0}

        # Simulate a heartbeat with armed=True (new arm event)
        payload = self._build_heartbeat_payload(vtype=2, armed=True)
        handle_heartbeat(payload, len(payload), link)

        assert link.vehicle.flight_summary is None, (
            "flight_summary should be cleared when the vehicle arms (start of new flight)"
        )

    def test_flight_summary_set_on_disarm(self, link):
        """When drone disarms, flight_summary is populated with the session stats."""
        # Set up as if the drone is armed
        link.vehicle.armed = True
        link.vehicle.armed_time = 0.0  # will produce duration ~0
        link.vehicle.flight_summary = None

        # Simulate a heartbeat with armed=False (disarm event)
        payload = self._build_heartbeat_payload(vtype=2, armed=False)
        handle_heartbeat(payload, len(payload), link)

        assert link.vehicle.flight_summary is not None
        assert "duration" in link.vehicle.flight_summary
        assert "max_alt" in link.vehicle.flight_summary
        assert "max_speed" in link.vehicle.flight_summary
        assert "total_dist" in link.vehicle.flight_summary
        assert "bat_used" in link.vehicle.flight_summary
