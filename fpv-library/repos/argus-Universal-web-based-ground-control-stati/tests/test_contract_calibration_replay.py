"""Calibration-handshake regression via recorded real-firmware fixtures.

tests/fixtures/{magcal,accelcal}_sitl.tlog are real ArduPilot SITL sessions
recorded by tests/sitl_calibrate.py: the backend's own command path drove a
full onboard compass calibration (accept included) and a full 6-position
accelerometer calibration against the SITL 'calibration' vehicle model.

Two layers of assertions:
  wire   — the fixtures themselves contain the exact GCS TX bytes and FC
           responses of a SUCCESSFUL handshake (guards against silently
           regenerating a broken fixture);
  replay — feeding the FC side back through DroneLink.feed() reproduces the
           calibration state machine and events our UI is built on. This is
           the offline regression for the last FC-coupled logic that had no
           coverage without hardware.
"""

import struct
from pathlib import Path

from backend.drone_link import DroneLink
from backend.replay import read_tlog, replay_into

FIXTURES = Path(__file__).parent / "fixtures"
MAGCAL = str(FIXTURES / "magcal_sitl.tlog")
ACCELCAL = str(FIXTURES / "accelcal_sitl.tlog")

GCS_SYSID = 255


def _replay_capturing_events(path: str):
    """Replay a fixture and capture EVERY event emitted along the way.

    link.events is a display buffer trimmed to the last 50 past 100 entries;
    a full session replay overflows it. Live WS clients see every event via
    the queue cursor, so tests observe the same stream by tapping add_event.
    """
    link = DroneLink()
    captured: list[dict] = []
    orig = link.add_event

    def tap(text: str, event_type: str = "") -> None:
        captured.append({"text": text, "event_type": event_type})
        orig(text, event_type)

    link.add_event = tap
    fed = replay_into(link, path)
    return link, captured, fed


def _mid(frame: bytes) -> int:
    return frame[7] | (frame[8] << 8) | (frame[9] << 16)


def _payload(frame: bytes, n: int) -> bytes:
    """Payload zero-padded to n (MAVLink2 senders zero-trim trailing zeros)."""
    p = frame[10 : 10 + frame[1]]
    return p if len(p) >= n else p + b"\x00" * (n - len(p))


def _gcs_frames(path: str) -> list[bytes]:
    return [f for _, f in read_tlog(path, include_gcs=True) if f[5] == GCS_SYSID]


def _fc_frames(path: str) -> list[bytes]:
    return [f for _, f in read_tlog(path)]


def _command_longs(frames: list[bytes]) -> list[bytes]:
    # COMMAND_LONG (76): param1-7 f32 @0..27, command u16 @28,
    # target_system u8 @30, target_component u8 @31, confirmation u8 @32
    return [_payload(f, 33) for f in frames if _mid(f) == 76]


def _statustexts(frames: list[bytes]) -> list[str]:
    # STATUSTEXT (253): severity u8 @0, text char[50] @1
    return [
        _payload(f, 51)[1:51].split(b"\x00", 1)[0].decode(errors="replace")
        for f in frames
        if _mid(f) == 253
    ]


class TestMagcalFixtureWire:
    def test_gcs_sent_start_and_accept(self):
        cmds = _command_longs(_gcs_frames(MAGCAL))
        ids = {struct.unpack_from("<H", p, 28)[0] for p in cmds}
        # MAV_CMD_DO_START_MAG_CAL / MAV_CMD_DO_ACCEPT_MAG_CAL — the two
        # halves of the GCS-side handshake (backend/commands/_setup.py)
        assert 42424 in ids
        assert 42425 in ids
        start = next(p for p in cmds if struct.unpack_from("<H", p, 28)[0] == 42424)
        # cmd_cal_compass contract: mask=0 (all), retry=0, autosave=0, delay=0
        assert struct.unpack_from("<ffff", start, 0) == (0.0, 0.0, 0.0, 0.0)

    def test_fc_streamed_progress_then_report(self):
        mids = [_mid(f) for f in _fc_frames(MAGCAL)]
        assert 191 in mids  # MAG_CAL_PROGRESS
        assert 192 in mids  # MAG_CAL_REPORT
        assert mids.index(191) < mids.index(192)

    def test_fixture_recorded_a_success(self):
        """cal_status @42 == 4 (MAG_CAL_SUCCESS) — same offset our handler
        reads (ArduPilot: libraries/AP_Compass/AP_Compass_Calibration.cpp:309,
        Compass::send_mag_cal_report). A regenerated fixture that recorded a
        failed cal must not pass silently."""
        reports = [_payload(f, 44) for f in _fc_frames(MAGCAL) if _mid(f) == 192]
        assert reports
        assert any(p[42] == 4 for p in reports)


class TestMagcalReplay:
    def test_replay_reproduces_progress_and_done_state(self):
        link, events, fed = _replay_capturing_events(MAGCAL)
        assert fed > 0
        assert link._mag_cal_done is True
        assert link._mag_cal_pct == -1  # reset by handle_mag_cal_report
        texts = [e["text"] for e in events if e["event_type"] == "cal_compass"]
        assert any("%" in t for t in texts), "no progress events surfaced"
        assert any(("完成" in t) or ("complete" in t) for t in texts), texts[-3:]
        assert not any(("失败" in t) or ("FAILED" in t) for t in texts)

    def test_progress_events_monotonic(self):
        _, events, _ = _replay_capturing_events(MAGCAL)
        pcts = [
            int(e["text"].split()[-1].rstrip("%"))
            for e in events
            if e["event_type"] == "cal_compass" and "%" in e["text"]
        ]
        assert pcts, "expected at least one percentage event"
        assert pcts == sorted(pcts)


class TestAccelcalFixtureWire:
    def test_gcs_started_accel_cal(self):
        cmds = _command_longs(_gcs_frames(ACCELCAL))
        # MAV_CMD_PREFLIGHT_CALIBRATION (241) with param5=1 = accel cal
        starts = [p for p in cmds if struct.unpack_from("<H", p, 28)[0] == 241]
        assert starts
        assert any(struct.unpack_from("<f", p, 16)[0] == 1.0 for p in starts)

    def test_gcs_sent_position_acks(self):
        """cal_accel_next sends COMMAND_ACK(command=0, result=1) — the QGC
        dialect of AP_AccelCal::handle_command_ack (backend/commands/_setup.py
        cites the surprising semantics). Six positions -> at least six ACKs."""
        acks = [
            _payload(f, 3)
            for f in _gcs_frames(ACCELCAL)
            if _mid(f) == 77
        ]
        matching = [p for p in acks if struct.unpack_from("<HB", p, 0) == (0, 1)]
        assert len(matching) >= 6

    def test_fc_prompted_all_six_positions_in_order(self):
        texts = [t for t in _statustexts(_fc_frames(ACCELCAL)) if "Place vehicle" in t]
        assert len(texts) >= 6
        # AP_AccelCal prompt order (vehicle_test_suite.py:AccelCal expects
        # exactly these, in this order)
        expected = ["level", "LEFT", "RIGHT", "nose DOWN", "nose UP", "BACK"]
        missing = [key for key in expected if not any(key in t for t in texts)]
        assert not missing, f"prompts never seen: {missing} in {texts}"
        firsts = [min(i for i, t in enumerate(texts) if key in t) for key in expected]
        assert firsts == sorted(firsts), f"prompt order wrong: {texts}"

    def test_fc_reported_success(self):
        assert any("Calibration successful" in t for t in _statustexts(_fc_frames(ACCELCAL)))


class TestAccelcalReplay:
    def test_replay_surfaces_prompts_and_success_as_events(self):
        """The frontend calibration panel keys off statustext events — real
        AP prompt strings must survive parse -> statustext filter -> event."""
        link, events, fed = _replay_capturing_events(ACCELCAL)
        assert fed > 0
        st = [e["text"] for e in events if e["event_type"] == "statustext"]
        prompts = [t for t in st if "Place vehicle" in t]
        assert len(prompts) >= 6
        for key in ("level", "LEFT", "RIGHT", "nose DOWN", "nose UP", "BACK"):
            assert any(key in t for t in prompts), f"missing {key} prompt: {prompts}"
        assert any("Calibration successful" in t for t in st)
