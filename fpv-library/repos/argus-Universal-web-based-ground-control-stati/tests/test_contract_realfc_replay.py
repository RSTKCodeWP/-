"""Real-hardware session regression via a recorded bench tlog.

tests/fixtures/realfc_bench.tlog is a genuine bench session against a
Plkj-FPV-rocket board (ArduPilot Copter v4.6.3, QUAD/X, USB link, backend
serial path) recorded 2026-07-16: connect + stream setup (SET_MESSAGE_INTERVAL
x14), mode Loiter -> Stabilize, disarm, LOG_REQUEST_LIST (1 entry on the FC),
empty-mission download, and a full 1034-parameter fetch. Identifying data was
rewritten by scripts/scrub_tlog.py (coordinates shifted onto the SITL CMAC
default home, banner serial digits and AUTOPILOT_VERSION uid2 zeroed); every
other frame is byte-exact from the wire.

Unlike the synthetic frames in frame_builders.py and the SITL calibration
fixtures, this is the one fixture whose byte stream a real flight controller
actually produced — MAVLink2 zero-trim as the FC trims it, real stream mix,
real ACK ordering. Two layers, same structure as
test_contract_calibration_replay.py:

  wire   — the fixture still contains the session's GCS TX commands and the
           FC responses (guards against silently regenerating a broken or
           unscrubbed fixture);
  replay — feeding the FC side through the production parse path lands
           DroneLink.get_state() on the exact values the live session showed.
"""

import re
from collections import Counter
from pathlib import Path

import pytest
from pymavlink.dialects.v20 import ardupilotmega as mavlink

from backend.drone_link import DroneLink
from backend.replay import read_tlog, replay_into

FIXTURE = str(Path(__file__).parent / "fixtures" / "realfc_bench.tlog")

GCS_SYSID = 255
CMAC_LAT, CMAC_LON = -35.363261, 149.165230  # scrub anchor (SITL default home)
# Board-UID banner shape: three 8-char UPPERCASE-HEX groups
# (libraries/AP_HAL_ChibiOS/Util.cpp:346). Assert on the SHAPE only — a real
# UID must never appear as a literal in this repo (it cannot be rotated).
_SERIAL_GROUPS = re.compile(r"\b[0-9A-F]{8} [0-9A-F]{8} [0-9A-F]{8}\b")


def _decode_all() -> list:
    mav = mavlink.MAVLink(None)
    mav.robust_parsing = True
    return [mav.decode(bytearray(frame)) for _, frame in read_tlog(FIXTURE, include_gcs=True)]


@pytest.fixture(scope="module")
def msgs() -> list:
    return _decode_all()


class TestFixtureWire:
    def test_session_shape(self, msgs):
        tx = [m for m in msgs if m.get_srcSystem() == GCS_SYSID]
        rx = [m for m in msgs if m.get_srcSystem() != GCS_SYSID]
        assert len(tx) == 148 and len(rx) == 5515
        rx_counts = Counter(m.get_type() for m in rx)
        assert rx_counts["PARAM_VALUE"] == 1038  # 1034 params + retries
        assert rx_counts["GLOBAL_POSITION_INT"] == 754
        assert rx_counts["HOME_POSITION"] == 1
        assert rx_counts["AUTOPILOT_VERSION"] == 1

    def test_gcs_commands_present(self, msgs):
        tx = [m for m in msgs if m.get_srcSystem() == GCS_SYSID]
        set_modes = [m.custom_mode for m in tx if m.get_type() == "SET_MODE"]
        # Copter LOITER=5, STABILIZE=0 — ArduCopter/mode.h:83 / :78.
        assert set_modes == [5, 0]
        longs = [m for m in tx if m.get_type() == "COMMAND_LONG"]
        disarms = [m for m in longs if m.command == 400]
        assert len(disarms) == 1 and disarms[0].param1 == 0
        assert sum(1 for m in longs if m.command == 511) >= 8  # stream setup
        for t in ("LOG_REQUEST_LIST", "MISSION_REQUEST_LIST", "PARAM_REQUEST_LIST"):
            assert any(m.get_type() == t for m in tx), t

    def test_fc_responses_present(self, msgs):
        rx = [m for m in msgs if m.get_srcSystem() != GCS_SYSID]
        acks = {(m.command, m.result) for m in rx if m.get_type() == "COMMAND_ACK"}
        assert (400, 0) in acks  # disarm accepted
        logs = [m for m in rx if m.get_type() == "LOG_ENTRY"]
        assert len(logs) == 1 and logs[0].num_logs == 1
        counts = [m for m in rx if m.get_type() == "MISSION_COUNT"]
        assert len(counts) == 1 and counts[0].count == 0  # FC had no mission

    def test_fixture_is_scrubbed(self, msgs):
        """Regeneration guard: a re-recorded fixture must go through
        scripts/scrub_tlog.py before landing here."""
        for m in msgs:
            t = m.get_type()
            if t in ("GPS_RAW_INT", "GLOBAL_POSITION_INT", "TERRAIN_REPORT"):
                assert abs(m.lat / 1e7 - CMAC_LAT) < 0.2, t
                assert abs(m.lon / 1e7 - CMAC_LON) < 0.2, t
                if t == "GPS_RAW_INT":
                    assert m.alt_ellipsoid == 0  # geoid-undulation side-channel
            elif t == "AHRS2":
                assert abs(m.lat / 1e7 - CMAC_LAT) < 0.2
                assert abs(m.lng / 1e7 - CMAC_LON) < 0.2
            elif t == "HOME_POSITION":
                assert abs(m.latitude / 1e7 - CMAC_LAT) < 0.2
                assert abs(m.longitude / 1e7 - CMAC_LON) < 0.2
            elif t == "AUTOPILOT_VERSION":
                assert m.uid == 0 and all(b == 0 for b in m.uid2)
            elif t == "PARAM_VALUE" and m.param_id == "COMPASS_DEC":
                assert m.param_value == 0.0  # world-magnetic-model side-channel
            elif t == "STATUSTEXT":
                # Any UID-shaped hex triple must be all zeros, and the field
                # elevation figure must be zeroed. Shape-only assertions —
                # no real value belongs in this file.
                for grp in _SERIAL_GROUPS.findall(m.text):
                    assert set(grp) == {"0", " "}, "board serial not zeroed"
                el = re.search(r"Field Elevation Set: (\d+)m", m.text)
                if el:
                    assert int(el.group(1)) == 0


class TestReplay:
    @pytest.fixture(scope="class")
    def link(self) -> DroneLink:
        link = DroneLink()
        link.locale = "en"
        fed = replay_into(link, FIXTURE)
        assert fed == 5515
        return link

    def test_state_matches_live_session(self, link):
        st = link.get_state()
        assert st["connected"] is True
        assert st["frames"] == 5515
        # Every frame a live session recorded must replay cleanly — the tlog
        # only ever contains frames that passed the CRC_EXTRA gate.
        assert st["parse_errors"] == 0
        assert st["autopilot"] == 3 and st["vtype_raw"] == 2
        assert st["mode_id"] == 0 and st["mode"] == "Stabilize"
        assert st["armed"] is False
        assert st["fw_version"] == "v4.6.3" and st["board_id"] == 3801088
        assert st["gps_fix_raw"] == 3 and st["gps_sats"] == 5
        assert st["rc_rssi"] == 255 and len(st["rc"]) == 16
        assert st["vibe"] == [0.1, 0.1, 0.1] and len(st["mag"]) == 3

    def test_param_fetch_completed(self, link):
        st = link.get_state()
        assert st["param_count"] == 1034
        assert st["param_total"] == 1034
        assert st["param_fetching"] is False

    def test_positions_landed_on_scrub_anchor(self, link):
        st = link.get_state()
        assert st["home_lat"] == pytest.approx(CMAC_LAT, abs=1e-6)
        assert st["home_lon"] == pytest.approx(CMAC_LON, abs=1e-6)
        assert st["lat"] == pytest.approx(CMAC_LAT, abs=0.01)
        assert st["lon"] == pytest.approx(CMAC_LON, abs=0.01)

    def test_session_events_replayed(self, link):
        by_type: dict[str, list[str]] = {}
        for e in link.events:
            by_type.setdefault(e["event_type"], []).append(e["text"])
        assert "connected" in by_type
        assert any("v4.6.3" in t for t in by_type.get("fw_info", []))
        assert any("1" in t for t in by_type.get("log_list_n", []))
        assert len(by_type.get("cmd_ack_ok", [])) >= 9  # 8+ stream setup + disarm
        assert any("1034" in t for t in by_type.get("param_done", []))
        # The scrubbed banner flows through to the UI event feed: the
        # UID-shaped triple is present and is all zeros.
        joined = " ".join(t for ts in by_type.values() for t in ts)
        groups = _SERIAL_GROUPS.findall(joined)
        assert groups, "board banner missing from event feed"
        assert all(set(g) == {"0", " "} for g in groups)
