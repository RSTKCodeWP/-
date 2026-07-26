"""Link-layer fault injection — offline, through the real ingest path.

The transport between GCS and FC is a lossy serial line: noise bursts, torn
frames, CRC hits, duplicated packets, and mid-transfer disconnects all
happen on real hardware. Every test here drives DroneLink.feed() — the same
code the live link thread runs — and asserts the link recovers to a correct
state instead of wedging, crashing, or double-counting.
"""

import struct

from frame_builders import SESSION, fc_frame, global_position, heartbeat, param_value

from backend.crc_extras import CRC_EXTRA
from backend.drone_link import DroneLink
from backend.pllink_proto import bm, ple


class TestNoiseRecovery:
    def test_garbage_prefix_then_valid_frame(self):
        link = DroneLink()
        assert link.feed(b"\x00\x37\xa5" * 40 + heartbeat()) == 1
        assert link.connected is True

    def test_noise_between_every_frame(self):
        """A full session still lands on correct state with noise bursts
        injected between every frame."""
        link = DroneLink()
        noisy = b""
        for f in SESSION:
            noisy += b"\xa5\x00\x13\x37\xee" + f
        link.feed(noisy)
        st = link.get_state()
        assert st["connected"] is True
        assert st["mode_id"] == 4
        assert st["frames"] == len(SESSION)

    def test_embedded_magic_in_torn_frame_resyncs_bounded(self):
        """A corrupted frame whose payload contains 0xFD makes the parser
        chase a phantom frame whose bogus length field can swallow up to
        ~280 bytes of real traffic (payload_len max 255 + signature) — a
        stream parser cannot distinguish it from a real partial frame.
        The contract is BOUNDED loss: once enough bytes arrive, the phantom
        fails CRC and subsequent real frames parse again."""
        link = DroneLink()
        torn = bytearray(global_position())
        torn[-1] ^= 0xFF  # kill the CRC
        torn[15] = 0xFD  # plant a fake magic inside the payload
        followup = [heartbeat(seq=i) for i in range(20)]  # 420 bytes > 280
        link.feed(bytes(torn) + b"".join(followup))
        assert link.connected is True
        assert link.frame_count >= 10

    def test_all_noise_no_frames(self):
        link = DroneLink()
        assert link.feed(bytes(range(1, 250)) * 4) == 0
        assert link.connected is False


class TestTornFrames:
    def test_frame_split_at_every_boundary(self):
        """Serial reads tear frames at arbitrary offsets; every split point
        must yield exactly one parsed frame once the tail arrives."""
        frame = heartbeat()
        for cut in range(1, len(frame)):
            link = DroneLink()
            assert link.feed(frame[:cut]) == 0
            assert link.feed(frame[cut:]) == 1, "cut at %d" % cut
            assert link.connected is True

    def test_incomplete_frame_never_processed(self):
        link = DroneLink()
        link.feed(heartbeat()[:-1])
        assert link.frame_count == 0
        assert link.connected is False


class TestCorruption:
    def test_crc_hit_dropped_next_frame_survives(self):
        link = DroneLink()
        bad = bytearray(heartbeat())
        bad[-1] ^= 0xFF
        assert link.feed(bytes(bad) + global_position() + heartbeat()) == 2
        assert link.connected is True

    def test_corrupted_payload_does_not_poison_state(self):
        """CRC guards payload integrity: a flipped bit inside the payload
        must drop the frame entirely, not deliver wrong values."""
        link = DroneLink()
        bad = bytearray(global_position(lat=31.0, lon=121.0))
        bad[12] ^= 0x40  # flip a bit inside the lat field
        link.feed(bytes(bad))
        assert link.attitude.lat == 0.0
        assert link.frame_count == 0

    def test_unknown_msg_id_flood_bounded(self):
        """256-id cap on the unknown-id ledger: a noisy line synthesizing
        random ids can't grow memory unboundedly, but drops stay counted."""
        link = DroneLink()
        for mid in range(60000, 60300):
            assert mid not in CRC_EXTRA
            hdr = bytes([2, 0, 0, 0, 1, 1, mid & 0xFF, (mid >> 8) & 0xFF, (mid >> 16) & 0xFF])
            link.feed(b"\xfd" + hdr + b"\x00\x00" + b"\x00\x00")
        assert len(link._unknown_msg_ids) <= 256
        assert link._parse_errors >= 300

    def test_buffer_flood_trimmed_then_recovers(self):
        link = DroneLink()
        link.feed(b"\x11" * 100_000)
        assert len(link._buf) <= 65536
        link.feed(heartbeat())
        assert link.connected is True


class TestDuplicateDelivery:
    def test_duplicate_param_value_not_double_counted(self):
        link = DroneLink()
        link.param_mgr.fetching = True
        frame = param_value(b"RTL_ALT", 300.0, count=2, index=0)
        link.feed(frame + frame + frame)
        assert link.param_mgr.received_count == 1
        assert link.param_mgr.params["RTL_ALT"]["value"] == 300.0

    def test_duplicate_armed_heartbeat_single_transition(self):
        """A duplicated armed heartbeat must not re-trigger the arm
        transition (which would reset armed_time / flight statistics)."""
        link = DroneLink()
        link.feed(heartbeat(armed=True, seq=0))
        first_armed_time = link.vehicle.armed_time
        link.vehicle.max_alt = 42.0  # accumulate some flight stats
        link.feed(heartbeat(armed=True, seq=1))
        assert link.vehicle.armed_time == first_armed_time
        assert link.vehicle.max_alt == 42.0
        arm_events = [e for e in link.events if e["event_type"] == "armed"]
        assert len(arm_events) == 1


class TestTruncatedPayloads:
    def test_zero_truncated_payload_handled(self):
        """MAVLink v2 truncates trailing zero payload bytes on the wire
        (mavlink docs: payload truncation) — handlers must _pad and cope."""
        link = DroneLink()
        # GLOBAL_POSITION_INT with everything after time_boot_ms zeroed →
        # v2 sender may ship as few as 1 byte. Build a 4-byte variant.
        link.feed(fc_frame(33, b"\x01\x00\x00\x00"))
        assert link.frame_count == 1
        assert link.attitude.lat == 0.0
        assert link._parse_errors == 0


class TestDisconnectMidTransfer:
    def test_link_drop_clears_param_fetch(self):
        """FC drop mid PARAM_REQUEST_LIST: the fetching flag must not stay
        latched forever (it gates the UI's param progress spinner)."""
        link = DroneLink()
        link.param_mgr.fetching = True
        link.param_mgr._fetch_start = 123.0
        link._reset_session_state()
        assert link.param_mgr.fetching is False

    def test_link_drop_clears_mission_download(self):
        link = DroneLink()
        link.mission._dl_pending = True
        link.mission._mission_pending = True
        link._reset_session_state()
        assert link.mission._dl_pending is False
        assert link.mission._mission_pending is False

    def test_link_drop_resets_stream_request_gate(self):
        """frame_count must return to 0 so request_streams() re-fires — the
        FC's stream subscriptions lapse across a transport reset."""
        link = DroneLink()
        link.feed(heartbeat() + global_position())
        assert link.frame_count > 0
        link._reset_session_state()
        assert link.frame_count == 0
        assert link.connected is False


class TestPllinkFaults:
    def test_corrupt_pllink_frame_dropped_next_survives(self):
        link = DroneLink()
        link._protocol = "pllink"
        good = ple(heartbeat(), 0)
        bad = bytearray(ple(global_position(), 1))
        bad[-1] ^= 0xFF  # kill the pllink CRC
        assert link.feed(bytes(bad) + good) == 1
        assert link.connected is True

    def test_pllink_wrapping_garbage_inner_no_crash(self):
        """A pllink frame that decodes to non-MAVLink bytes (XOR key drift,
        firmware bug) must be discarded by _process without raising."""
        link = DroneLink()
        link._protocol = "pllink"
        link.feed(ple(b"\x00" * 24, 0))
        assert link.connected is False

    def test_auto_detect_locks_pllink_despite_leading_noise(self):
        """Auditor W7 regression: noise before the first magic must not
        permanently lock the wrong protocol."""
        link = DroneLink()
        link.feed(b"\x99\x88\x77" + ple(heartbeat(), 0))
        assert link._protocol == "pllink"
        assert link.connected is True

    def test_auto_detect_locks_standard_despite_leading_noise(self):
        link = DroneLink()
        link.feed(b"\x99\x88\x77" + heartbeat())
        assert link._protocol == "standard"
        assert link.connected is True


class TestMultiVehicleInterleave:
    def test_interleaved_sysids_tracked_separately(self):
        link = DroneLink()
        hb2 = bm(0, struct.pack("<IBBBBB", 0, 2, 3, 0x10, 4, 3), 0, CRC_EXTRA[0], sysid=2)
        link.feed(heartbeat() + hb2)
        assert set(link._vehicles) == {1, 2}


class TestUnsupportedFcSessionLifecycle:
    """The unsupported-FC warning and command gate are per-session: a
    reconnect may be a different vehicle, so both must re-arm (fresh-eyes
    review F2: stale autopilot silently gated the next session, and a spent
    warning flag hid the event on a same-FC reconnect)."""

    def test_warns_once_per_session_then_rearms_on_reset(self):
        from backend.commands import execute

        link = DroneLink()
        link.feed(heartbeat(autopilot=12))
        assert link.vehicle.autopilot == 12
        warns = lambda: sum(1 for e in link.events if e["event_type"] == "unsupported_fc")  # noqa: E731
        assert warns() == 1
        link.feed(heartbeat(autopilot=12, seq=1))
        assert warns() == 1  # no per-heartbeat spam

        r = execute("arm", None, link)
        assert r == {"ok": False, "error": "unsupported autopilot (12): ArduPilot only"}

        # Silent in-loop reconnect path: latch cleared, gate open until the
        # next heartbeat, warning re-armed for the new session.
        link._reset_session_state()
        assert link.vehicle.autopilot == 0
        link.feed(heartbeat(autopilot=12, seq=2))
        assert warns() == 2

    def test_px4_to_ardupilot_reconnect_ungates(self):
        from backend.commands import execute

        link = DroneLink()
        link.feed(heartbeat(autopilot=12))
        link._reset_session_state()
        # New session is an ArduPilot vehicle — commands must flow again
        # immediately (a stale 12 would refuse them until who-knows-when).
        link.feed(heartbeat(autopilot=3, seq=1))
        from unittest.mock import MagicMock

        link._ser = MagicMock()
        execute("arm", None, link)
        assert link._ser.write.called
        # only the pre-reset PX4 session warned; the AP session must not
        assert sum(1 for e in link.events if e["event_type"] == "unsupported_fc") == 1
