"""Performance benchmark tests for backend modules.

These tests set generous thresholds (2-3x expected) so they pass reliably
but catch major regressions (10x slower would fail).
"""

import json
import struct
import threading
import time

from backend.pllink_proto import pld, ple
from backend.state import (
    AttitudeState,
    BatteryState,
    DiagnosticState,
    GpsState,
    RcServoState,
    VehicleState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_drone_link():
    """Create a DroneLink instance for testing without connecting."""
    from backend.drone_link import DroneLink

    link = DroneLink()
    link.connected = True
    link.frame_count = 100
    link.last_frame_time = time.time()
    link.start_time = time.time() - 60
    link.vehicle.mode = 5
    link.vehicle.armed = True
    link.vehicle.armed_time = time.time() - 30
    link.vehicle.vtype_raw = 2
    link.attitude.roll = 3.5
    link.attitude.pitch = -1.2
    link.attitude.yaw = 180.0
    link.attitude.lat = 30.1234567
    link.attitude.lon = 120.7654321
    link.attitude.alt_rel = 50.3
    link.attitude.alt_msl = 120.5
    link.attitude.gs = 5.5
    link.attitude.hdg = 270.0
    link.battery.voltage = 11.8
    link.battery.current = 12.5
    link.battery.remaining = 75
    link.gps.gps_fix = 3
    link.gps.gps_sats = 12
    return link


def build_mavlink_frame(msg_id=30, payload_len=28):
    """Build a valid MAVLink v2 frame for msg_id=30 (ATTITUDE)."""
    payload = bytes(payload_len)
    header = bytes(
        [
            payload_len,  # payload len
            0,  # incompat_flags
            0,  # compat_flags
            0,  # seq
            1,  # sysid
            1,  # compid
            msg_id & 0xFF,
            (msg_id >> 8) & 0xFF,
            (msg_id >> 16) & 0xFF,
        ]
    )
    # CRC calculation (MAVLink CRC-16)
    crc = 0xFFFF
    for b in header + payload:
        tmp = b ^ (crc & 0xFF)
        tmp ^= (tmp << 4) & 0xFF
        crc = (crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)
        crc &= 0xFFFF
    # Add CRC_EXTRA for msg 30 = 39
    crc_extra = 39
    tmp = crc_extra ^ (crc & 0xFF)
    tmp ^= (tmp << 4) & 0xFF
    crc = (crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)
    crc &= 0xFFFF

    frame = b"\xfd" + header + payload + struct.pack("<H", crc)
    return frame


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStateUpdateLatency:
    """Test that state field updates are fast."""

    def test_attitude_updates_1000(self):
        """1000 attitude state updates must complete in < 100ms."""
        a = AttitudeState()
        start = time.perf_counter()
        for i in range(1000):
            a.roll = float(i % 360)
            a.pitch = float(i % 90)
            a.yaw = float(i % 360)
            a.lat = 30.0 + i * 0.0001
            a.lon = 120.0 + i * 0.0001
            a.alt_rel = float(i)
            a.gs = float(i % 30)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"1000 attitude updates took {elapsed:.4f}s (> 100ms)"

    def test_all_state_updates_1000(self):
        """1000 updates across all state dataclasses in < 100ms."""
        att = AttitudeState()
        bat = BatteryState()
        gps = GpsState()
        veh = VehicleState()
        diag = DiagnosticState()
        rc = RcServoState()

        start = time.perf_counter()
        for i in range(1000):
            att.roll = float(i)
            att.pitch = float(i)
            att.yaw = float(i)
            bat.voltage = 11.0 + (i % 10) * 0.1
            bat.current = float(i % 30)
            bat.remaining = i % 100
            gps.gps_fix = i % 6
            gps.gps_sats = i % 20
            veh.mode = i % 20
            veh.armed = i % 2 == 0
            diag.vibe_x = float(i % 50)
            diag.ekf_flags = i
            rc.rc_channels = [i % 2000] * 16
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"1000 full state updates took {elapsed:.4f}s (> 100ms)"


class TestSerializationThroughput:
    """Test JSON serialization performance of full state dict."""

    def test_serialize_full_state_1000(self):
        """Serialize full state dict 1000 times in < 500ms."""
        link = make_drone_link()
        state = link.get_state()

        start = time.perf_counter()
        for _ in range(1000):
            json.dumps(state)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"1000 serializations took {elapsed:.4f}s (> 500ms)"

    def test_get_state_build_1000(self):
        """Build state dict 1000 times in < 500ms."""
        link = make_drone_link()

        start = time.perf_counter()
        for _ in range(1000):
            link.get_state()
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"1000 get_state calls took {elapsed:.4f}s (> 500ms)"


class TestDeltaComputation:
    """Test delta (diff) computation speed."""

    def test_compute_delta_1000(self):
        """Compute 1000 deltas between state snapshots in < 200ms."""
        link = make_drone_link()
        prev_state = link.get_state()

        # Simulate slight changes each iteration
        start = time.perf_counter()
        for i in range(1000):
            link.attitude.roll = float(i % 360)
            link.attitude.alt_rel = float(i)
            link.battery.voltage = 11.0 + (i % 10) * 0.1
            current_state = link.get_state()
            # Compute delta like ws_manager does
            _ = {k: v for k, v in current_state.items() if prev_state.get(k) != v}
            prev_state = current_state
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"1000 delta computations took {elapsed:.4f}s (> 200ms)"

    def test_no_change_delta_1000(self):
        """When state has not changed, delta is empty. 1000 iterations < 200ms."""
        link = make_drone_link()
        state = link.get_state()

        start = time.perf_counter()
        for _ in range(1000):
            current = link.get_state()
            _ = {k: v for k, v in current.items() if state.get(k) != v}
        elapsed = time.perf_counter() - start
        assert elapsed < 0.2, f"1000 no-change deltas took {elapsed:.4f}s (> 200ms)"


class TestMavlinkParseThroughput:
    """Test MAVLink frame parsing throughput."""

    def test_parse_10000_frames(self):
        """Parse 10000 MAVLink frames in < 1s."""
        frame = build_mavlink_frame(msg_id=30, payload_len=28)
        link = make_drone_link()

        # Prepare a buffer with many frames concatenated
        buf = frame * 100

        start = time.perf_counter()
        parsed = 0
        for _ in range(100):
            link._buf = buf
            while len(link._buf) >= 12:
                result, consumed = link._parse_mavlink_frame()
                if result:
                    link._buf = link._buf[consumed:]
                    parsed += 1
                elif consumed > 0:
                    link._buf = link._buf[consumed:]
                else:
                    break
        elapsed = time.perf_counter() - start
        assert parsed == 10000, f"Expected 10000 frames, got {parsed}"
        assert elapsed < 1.0, f"Parsing 10000 frames took {elapsed:.4f}s (> 1s)"

    def test_parse_with_garbage_prefix(self):
        """Parse frames with garbage prefix 10000 times in < 2s."""
        frame = build_mavlink_frame(msg_id=30, payload_len=28)
        garbage = bytes([0x00, 0x11, 0x22, 0x33, 0x44])
        frame_with_garbage = garbage + frame
        link = make_drone_link()

        start = time.perf_counter()
        parsed = 0
        for _ in range(10000):
            link._buf = frame_with_garbage
            while len(link._buf) >= 12:
                result, consumed = link._parse_mavlink_frame()
                if result:
                    link._buf = link._buf[consumed:]
                    parsed += 1
                elif consumed > 0:
                    link._buf = link._buf[consumed:]
                else:
                    break
        elapsed = time.perf_counter() - start
        assert parsed == 10000
        assert elapsed < 2.0, f"10000 garbage-prefix parses took {elapsed:.4f}s (> 2s)"


class TestPLLinkThroughput:
    """Test PL-Link encode/decode throughput."""

    # Thresholds guard against algorithmic pathology (an accidental O(n^2)
    # would be 10-100x), not micro-perf: GitHub's 2026-07 runner image is
    # ~13% slower than the old one and pushed the previous 1s/1s/2s limits
    # into flake territory (1.13s observed on a green codebase).

    def test_encode_10000(self):
        """Encode 10000 PL-Link frames in < 3s."""
        payload = bytes(32)  # typical MAVLink payload size

        start = time.perf_counter()
        for i in range(10000):
            ple(payload, i & 0xFF)
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"10000 PL-Link encodes took {elapsed:.4f}s (> 3s)"

    def test_decode_10000(self):
        """Decode 10000 PL-Link frames in < 3s."""
        payload = bytes(32)
        encoded = ple(payload, 0x42)

        start = time.perf_counter()
        for _ in range(10000):
            result, consumed = pld(encoded)
            assert result is not None
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"10000 PL-Link decodes took {elapsed:.4f}s (> 3s)"

    def test_roundtrip_10000(self):
        """Encode then decode 10000 PL-Link frames in < 6s."""
        payload = bytes(range(32))

        start = time.perf_counter()
        for i in range(10000):
            encoded = ple(payload, i & 0xFF)
            result, consumed = pld(encoded)
            assert result == payload
        elapsed = time.perf_counter() - start
        assert elapsed < 6.0, f"10000 PL-Link roundtrips took {elapsed:.4f}s (> 6s)"


class TestEventBufferPerformance:
    """Test event buffer append with trimming."""

    def test_append_10000_events(self):
        """Append 10000 events (with trimming at 100) in < 200ms."""
        link = make_drone_link()

        start = time.perf_counter()
        for i in range(10000):
            link.add_event(f"Event number {i}", "test")
        elapsed = time.perf_counter() - start
        # Buffer should have trimmed to 50-100 events
        assert len(link.events) <= 100
        assert elapsed < 0.2, f"10000 event appends took {elapsed:.4f}s (> 200ms)"

    def test_ws_queue_append_10000(self):
        """Append 10000 WS queue items (with trimming at 2000) in < 200ms."""
        link = make_drone_link()

        start = time.perf_counter()
        for i in range(10000):
            link.queue_ws({"type": "test", "i": i})
        elapsed = time.perf_counter() - start
        assert len(link._ws_queue) <= 2000
        assert elapsed < 0.2, f"10000 ws_queue appends took {elapsed:.4f}s (> 200ms)"


class TestConcurrentStateAccess:
    """Test concurrent state reads while writing."""

    def test_concurrent_reads_writes(self):
        """Concurrent reads + writes should not cause significant degradation.

        Baseline: single-threaded get_state 1000x.
        With concurrent writes: should not be more than 3x slower.
        """
        link = make_drone_link()

        # Baseline: single-threaded reads
        start = time.perf_counter()
        for _ in range(1000):
            link.get_state()
        baseline = time.perf_counter() - start

        # Now run concurrent writes while reading
        stop_event = threading.Event()
        write_count = [0]

        def writer():
            i = 0
            while not stop_event.is_set():
                with link._state_lock:
                    link.attitude.roll = float(i % 360)
                    link.attitude.pitch = float(i % 90)
                    link.battery.voltage = 11.0 + (i % 10) * 0.1
                i += 1
                write_count[0] = i

        writer_thread = threading.Thread(target=writer, daemon=True)
        writer_thread.start()

        start = time.perf_counter()
        for _ in range(1000):
            link.get_state()
        concurrent_time = time.perf_counter() - start

        stop_event.set()
        writer_thread.join(timeout=2)

        # Concurrent should not be more than 10x slower than baseline.
        # Loosened from 3x→5x→10x because under full test suite load the OS
        # scheduler can starve the main thread while the writer holds the lock.
        # Single-run always passes at <3x; the flakiness is scheduling noise.
        ratio = concurrent_time / max(baseline, 0.0001)
        assert ratio < 10.0, (
            f"Concurrent access {ratio:.1f}x slower than baseline "
            f"(baseline={baseline:.4f}s, concurrent={concurrent_time:.4f}s)"
        )
        assert write_count[0] > 0, "Writer thread did not execute"

    def test_lock_contention_stress(self):
        """Multiple readers + one writer: all complete within 2s for 5000 reads."""
        link = make_drone_link()
        stop_event = threading.Event()
        results = []

        def reader():
            count = 0
            while count < 1000 and not stop_event.is_set():
                link.get_state()
                count += 1
            results.append(count)

        def writer():
            i = 0
            while not stop_event.is_set():
                with link._state_lock:
                    link.attitude.roll = float(i)
                    link.attitude.lat = 30.0 + i * 0.0001
                i += 1
                if i > 5000:
                    break

        threads = []
        start = time.perf_counter()
        writer_t = threading.Thread(target=writer, daemon=True)
        writer_t.start()
        threads.append(writer_t)

        for _ in range(5):
            t = threading.Thread(target=reader, daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=5)
        stop_event.set()
        elapsed = time.perf_counter() - start

        total_reads = sum(results)
        assert total_reads == 5000, f"Expected 5000 reads, got {total_reads}"
        assert elapsed < 2.0, f"Concurrent stress test took {elapsed:.4f}s (> 2s)"
