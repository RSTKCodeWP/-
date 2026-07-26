"""Contract tests for MAVLink session recording (.tlog) and offline replay.

The invariant under test: a byte stream recorded from a live link, replayed
through backend/replay.py, must drive DroneLink to the exact same state a
live session would have produced — that is what makes recorded hardware
sessions usable as offline regression fixtures.
"""

import struct
import time

import pytest
from frame_builders import SESSION, attitude, global_position, heartbeat, write_tlog

from backend.config import cfg
from backend.connection import ReplayWrapper, _parse_replay_port, open_port
from backend.crc_extras import CRC_EXTRA
from backend.drone_link import DroneLink
from backend.pllink_proto import bm, ple
from backend.replay import read_tlog, replay_into


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "LOG_DIR", tmp_path)
    return tmp_path


class FakeSer:
    def __init__(self):
        self.written = b""

    def read(self, n):
        return b""

    def write(self, data):
        self.written += data

    def close(self):
        pass


# ── recording ────────────────────────────────────────────────────────────


class TestTlogRecording:
    def test_rx_frame_recorded_byte_exact(self, log_dir):
        link = DroneLink()
        link._start_log()
        frame = heartbeat()
        before = int(time.time() * 1e6)
        link._process(frame)
        link._stop_log()
        after = int(time.time() * 1e6)

        tlogs = list(log_dir.glob("*.tlog"))
        assert len(tlogs) == 1
        raw = tlogs[0].read_bytes()
        (ts,) = struct.unpack_from(">Q", raw, 0)
        assert before <= ts <= after
        assert raw[8:] == frame

    def test_tx_frame_recorded(self, log_dir):
        link = DroneLink()
        link._start_log()
        link._ser = FakeSer()
        frame = bm(0, b"\x00" * 9, 0, CRC_EXTRA[0])  # GCS heartbeat, sysid 255
        link.send(frame)
        link._stop_log()
        raw = next(iter(log_dir.glob("*.tlog"))).read_bytes()
        assert raw[8:] == frame

    def test_tx_recorded_unwrapped_in_pllink_mode(self, log_dir):
        """tlog must stay pure MAVLink: pllink transport framing (XOR wrap)
        is stripped, matching what _process records on the RX side."""
        link = DroneLink()
        link._start_log()
        link._ser = FakeSer()
        link._protocol = "pllink"
        frame = bm(0, b"\x00" * 9, 0, CRC_EXTRA[0])
        link.send(frame)
        link._stop_log()
        assert link._ser.written == ple(frame, 0)  # wire got wrapped
        raw = next(iter(log_dir.glob("*.tlog"))).read_bytes()
        assert raw[8:] == frame  # log got the inner frame

    def test_record_without_start_is_noop(self, log_dir):
        link = DroneLink()
        link._process(heartbeat())
        assert list(log_dir.glob("*.tlog")) == []

    def test_stop_then_process_does_not_crash_or_write(self, log_dir):
        link = DroneLink()
        link._start_log()
        link._stop_log()
        size = next(iter(log_dir.glob("*.tlog"))).stat().st_size
        link._process(heartbeat())
        assert next(iter(log_dir.glob("*.tlog"))).stat().st_size == size


# ── tlog parsing ─────────────────────────────────────────────────────────


class TestReadTlog:
    def test_round_trip_byte_exact(self, tmp_path):
        frames = [heartbeat(seq=0), attitude(seq=1), global_position(seq=2)]
        path = tmp_path / "s.tlog"
        write_tlog(path, frames, t0_usec=42, spacing_usec=7)
        records = read_tlog(str(path), include_gcs=True)
        assert [f for _, f in records] == frames
        assert [t for t, _ in records] == [42, 49, 56]

    def test_gcs_frames_filtered_by_default(self, tmp_path):
        gcs_hb = bm(0, b"\x00" * 9, 0, CRC_EXTRA[0])  # sysid 255
        path = tmp_path / "s.tlog"
        write_tlog(path, [gcs_hb, heartbeat()])
        records = read_tlog(str(path))
        assert len(records) == 1
        assert records[0][1][5] == 1  # only the FC frame survives

    def test_signed_frame_length_honored(self, tmp_path):
        # MAVLink v2 incompat flag 0x01 appends a 13-byte signature after the
        # CRC — same framing DroneLink._parse_mavlink_frame consumes.
        frame = bytearray(heartbeat())
        frame[2] |= 0x01
        signed = bytes(frame) + b"\xaa" * 13
        path = tmp_path / "s.tlog"
        write_tlog(path, [signed, heartbeat()])
        records = read_tlog(str(path))
        assert [f for _, f in records] == [signed, heartbeat()]

    def test_bad_magic_raises_with_offset(self, tmp_path):
        path = tmp_path / "s.tlog"
        path.write_bytes(struct.pack(">Q", 1) + b"\x55" + b"\x00" * 20)
        with pytest.raises(ValueError, match="byte 8"):
            read_tlog(str(path))

    def test_truncated_frame_raises(self, tmp_path):
        path = tmp_path / "s.tlog"
        path.write_bytes(struct.pack(">Q", 1) + heartbeat()[:10])
        with pytest.raises(ValueError, match="truncated"):
            read_tlog(str(path))

    @pytest.mark.parametrize("keep", [9, 10])
    def test_truncation_inside_header_raises_valueerror_not_indexerror(self, tmp_path, keep):
        """Reviewer finding: a record cut at exactly ts+magic (9 B) or
        ts+magic+len (10 B) — a disk-full short write — used to raise a bare
        IndexError that escaped every OSError handler upstream, killing the
        WS session (connect path) or the link thread (auto-reconnect path)."""
        path = tmp_path / "s.tlog"
        path.write_bytes((struct.pack(">Q", 1) + heartbeat())[:keep])
        with pytest.raises(ValueError, match="truncated"):
            read_tlog(str(path))

    def test_empty_file_ok(self, tmp_path):
        path = tmp_path / "s.tlog"
        path.write_bytes(b"")
        assert read_tlog(str(path)) == []


# ── replay into state ────────────────────────────────────────────────────


class TestReplayInto:
    def test_recorded_session_reproduces_live_state(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION)
        link = DroneLink()
        assert replay_into(link, str(path)) == 3
        st = link.get_state()
        assert st["connected"] is True
        assert st["mode_id"] == 4
        assert st["armed"] is True
        assert st["lat"] == pytest.approx(31.2304, abs=1e-6)
        assert st["lon"] == pytest.approx(121.4737, abs=1e-6)
        assert st["alt_rel"] == pytest.approx(5.0)
        assert st["roll"] == pytest.approx(5.7, abs=0.1)  # 0.1 rad
        assert st["frames"] == 3

    def test_gcs_only_session_produces_no_state(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, [bm(0, b"\x00" * 9, i, CRC_EXTRA[0]) for i in range(3)])
        link = DroneLink()
        assert replay_into(link, str(path)) == 0
        assert link.get_state()["connected"] is False

    def test_replay_equals_bulk_feed_equals_dribble(self, tmp_path):
        """Fragmentation invariance: per-frame replay, one bulk feed, and a
        byte-at-a-time dribble must all land on identical state."""
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION)
        blob = b"".join(SESSION)

        replayed = DroneLink()
        replay_into(replayed, str(path))
        bulk = DroneLink()
        bulk.feed(blob)
        dribble = DroneLink()
        for i in range(len(blob)):
            dribble.feed(blob[i : i + 1])

        keys = ("connected", "mode_id", "armed", "lat", "lon", "alt_rel", "roll", "frames")
        s_r, s_b, s_d = (x.get_state() for x in (replayed, bulk, dribble))
        for k in keys:
            assert s_r[k] == s_b[k] == s_d[k], k


# ── replay transport ─────────────────────────────────────────────────────


class TestReplayWrapper:
    def test_streams_all_fc_frames_in_order(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION, spacing_usec=1)  # effectively instant
        w = ReplayWrapper(str(path))
        got = b""
        deadline = time.monotonic() + 2
        while len(got) < len(b"".join(SESSION)) and time.monotonic() < deadline:
            got += w.read(1024)
        assert got == b"".join(SESSION)
        assert w.read(1024) == b""  # EOF

    def test_read_never_splits_a_frame(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION, spacing_usec=1)
        w = ReplayWrapper(str(path))
        chunk = b""
        deadline = time.monotonic() + 2
        while not chunk and time.monotonic() < deadline:
            chunk = w.read(16)  # smaller than any frame
        assert chunk == SESSION[0]  # one whole frame, not 16 bytes of it

    def test_pacing_defers_future_frames(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION, spacing_usec=30_000_000)  # 30 s apart
        w = ReplayWrapper(str(path))
        got = b""
        deadline = time.monotonic() + 2
        while not got and time.monotonic() < deadline:
            got += w.read(1024)
        assert got == SESSION[0]
        assert w.read(1024) == b""  # frame 2 is 30 s away — not due

    def test_silence_gap_clamped_so_replay_crosses_it(self, tmp_path, monkeypatch):
        """Reviewer finding: an in-log silence gap longer than
        LINK_LOST_TIMEOUT tripped the auto-reconnect, which reopened the
        replay from the top — the session looped over its prefix forever.
        Gaps must be clamped so the replay always makes progress."""
        monkeypatch.setattr(ReplayWrapper, "GAP_CLAMP_WALL", 0.05)
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION[:2], spacing_usec=30_000_000)  # 30 s gap
        w = ReplayWrapper(str(path))
        got = b""
        deadline = time.monotonic() + 2
        while len(got) < len(b"".join(SESSION[:2])) and time.monotonic() < deadline:
            got += w.read(1024)
        assert got == b"".join(SESSION[:2])  # crossed the gap within 2 s wall

    def test_speed_factor_accelerates(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION, spacing_usec=1_000_000)  # 1 s apart
        w = ReplayWrapper(str(path), speed=1000.0)
        got = b""
        deadline = time.monotonic() + 2
        while len(got) < len(b"".join(SESSION)) and time.monotonic() < deadline:
            got += w.read(1024)
        assert got == b"".join(SESSION)

    def test_write_discarded_close_idempotent(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION)
        w = ReplayWrapper(str(path))
        w.write(b"\xfd" * 20)
        w.close()
        w.close()

    def test_missing_file_raises_oserror(self, tmp_path):
        with pytest.raises(OSError):
            ReplayWrapper(str(tmp_path / "nope.tlog"))

    def test_corrupt_file_raises_oserror(self, tmp_path):
        path = tmp_path / "bad.tlog"
        path.write_bytes(b"\x00" * 30)
        with pytest.raises(OSError):
            ReplayWrapper(str(path))

    def test_gcs_only_file_raises_oserror(self, tmp_path):
        path = tmp_path / "gcs.tlog"
        write_tlog(path, [bm(0, b"\x00" * 9, 0, CRC_EXTRA[0])])
        with pytest.raises(OSError):
            ReplayWrapper(str(path))

    def test_port_spec_parsing(self):
        assert _parse_replay_port("replay:logs/a.tlog") == ("logs/a.tlog", 1.0)
        assert _parse_replay_port("replay:logs/a.tlog@10") == ("logs/a.tlog", 10.0)
        assert _parse_replay_port("replay:logs/a.tlog@2.5") == ("logs/a.tlog", 2.5)
        assert _parse_replay_port("replay:we@ird.tlog") == ("we@ird.tlog", 1.0)

    def test_open_port_routes_replay_scheme(self, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION)
        w = open_port("replay:%s" % path, 57600)
        assert isinstance(w, ReplayWrapper)


# ── end to end through connect() ─────────────────────────────────────────


class TestReplayEndToEnd:
    def test_connect_replay_port_drives_state_without_hardware(self, log_dir, tmp_path):
        path = tmp_path / "s.tlog"
        write_tlog(path, SESSION, spacing_usec=1000)
        link = DroneLink()
        assert link.connect("replay:%s@1000" % path, 57600) is True
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not link.connected:
                time.sleep(0.05)
            st = link.get_state()
            assert st["connected"] is True
            assert st["mode_id"] == 4
            assert st["lat"] == pytest.approx(31.2304, abs=1e-6)
        finally:
            link.disconnect()

    def test_connect_replay_port_does_not_record_new_logs(self, log_dir, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        path = src / "s.tlog"
        write_tlog(path, SESSION)
        link = DroneLink()
        assert link.connect("replay:%s" % path, 57600) is True
        link.disconnect()
        assert list(log_dir.glob("*.csv")) == [] and list(log_dir.glob("*.tlog")) == []
