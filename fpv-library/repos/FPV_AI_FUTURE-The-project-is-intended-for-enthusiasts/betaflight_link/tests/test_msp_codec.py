"""Tests for the MSP v2 wire codec (Block-3 S4 command/telemetry path).

Safety-critical path (RPi -> Betaflight). The CRC is pinned to hand-verified
DVB-S2 known-answer vectors; the RC mapping and channel order are asserted exactly
because a swap here would invert control surfaces on a real aircraft.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from fpv_ai.betaflight_link import msp_codec as mc
from fpv_ai.betaflight_link.msp_codec import (
    MSP_RAW_IMU,
    MSP_SET_RAW_RC,
    Attitude,
    ImuRaw,
    MspDecoder,
    TransportFrameError,
    crc8_dvb_s2,
    decode_attitude,
    decode_msp_v2,
    decode_raw_imu,
    decode_rc,
    encode_msp_v2,
    encode_set_raw_rc,
)


# ── CRC8 / DVB-S2: hand-verified known answers ──────────────────────────────────
def test_crc8_known_answers():
    assert crc8_dvb_s2(b"") == 0x00
    assert crc8_dvb_s2(b"\x00") == 0x00
    # crc=1 -> seven left-shifts to 0x80 -> (0x80<<1)^0xD5 & 0xFF = 0xD5
    assert crc8_dvb_s2(b"\x01") == 0xD5


def test_crc8_accumulates_left_to_right():
    # feeding in two chunks with carried crc == feeding the whole buffer
    data = bytes(range(20))
    one_shot = crc8_dvb_s2(data)
    carried = crc8_dvb_s2(data[10:], crc8_dvb_s2(data[:10]))
    assert one_shot == carried


# ── Frame structure + round-trip ────────────────────────────────────────────────
def test_encode_frame_structure():
    frame = encode_msp_v2(MSP_SET_RAW_RC, b"\x01\x02\x03\x04")
    assert frame[0:2] == b"$X"
    assert frame[2] == ord("<")            # direction to FC
    assert frame[3] == 0                   # flag
    assert int.from_bytes(frame[4:6], "little") == MSP_SET_RAW_RC
    assert int.from_bytes(frame[6:8], "little") == 4   # payload size
    assert frame[8:12] == b"\x01\x02\x03\x04"
    # full length = 8 header + size + 1 crc
    assert len(frame) == 8 + 4 + 1


def test_encode_decode_round_trip():
    for payload in (b"", b"\x00", b"\xff" * 32, bytes(range(64))):
        frame = encode_msp_v2(108, payload, direction=mc.DIR_FROM_FC, flag=7)
        decoded = decode_msp_v2(frame)
        assert decoded.function == 108
        assert decoded.payload == payload
        assert decoded.flag == 7
        assert decoded.direction == mc.DIR_FROM_FC


def test_decode_rejects_bad_preamble():
    frame = bytearray(encode_msp_v2(MSP_SET_RAW_RC, b"\x01\x02"))
    frame[1] = ord("M")  # MSP v1 preamble, not v2
    with pytest.raises(TransportFrameError):
        decode_msp_v2(bytes(frame))


def test_decode_catches_crc_corruption():
    frame = bytearray(encode_msp_v2(MSP_SET_RAW_RC, b"\x10\x20\x30\x40"))
    frame[-1] ^= 0xFF  # flip CRC
    with pytest.raises(TransportFrameError):
        decode_msp_v2(bytes(frame))
    frame2 = bytearray(encode_msp_v2(MSP_SET_RAW_RC, b"\x10\x20\x30\x40"))
    frame2[9] ^= 0x01  # flip a payload bit -> CRC must catch it
    with pytest.raises(TransportFrameError):
        decode_msp_v2(bytes(frame2))


def test_decode_rejects_wrong_length():
    frame = encode_msp_v2(MSP_SET_RAW_RC, b"\x01\x02\x03\x04")
    with pytest.raises(TransportFrameError):
        decode_msp_v2(frame[:-1])      # truncated
    with pytest.raises(TransportFrameError):
        decode_msp_v2(frame + b"\x00")  # trailing junk


# ── RC value mapping (safety: exact) ────────────────────────────────────────────
def test_symmetric_mapping_and_clamp():
    assert mc.symmetric_to_us(0.0) == 1500
    assert mc.symmetric_to_us(1.0) == 2000
    assert mc.symmetric_to_us(-1.0) == 1000
    assert mc.symmetric_to_us(5.0) == 2000     # clamp high
    assert mc.symmetric_to_us(-5.0) == 1000    # clamp low


def test_throttle_mapping_and_clamp():
    assert mc.throttle_to_us(0.0) == 1000
    assert mc.throttle_to_us(0.5) == 1500
    assert mc.throttle_to_us(1.0) == 2000
    assert mc.throttle_to_us(-0.3) == 1000     # clamp
    assert mc.throttle_to_us(2.0) == 2000


def test_value_mapping_handles_non_finite():
    # NaN/inf from a degenerate tracker must degrade safely, never raise, never high throttle
    nan, inf = float("nan"), float("inf")
    # ANY non-finite -> neutral/idle (safest: never slam a stick to an extreme on garbage)
    assert mc.symmetric_to_us(nan) == 1500
    assert mc.symmetric_to_us(inf) == 1500
    assert mc.symmetric_to_us(-inf) == 1500
    assert mc.throttle_to_us(nan) == 1000
    assert mc.throttle_to_us(inf) == 1000
    assert mc.throttle_to_us(-inf) == 1000


@dataclass
class _FakeCmd:
    roll_cmd: float
    pitch_cmd: float
    yaw_rate_cmd: float
    throttle_cmd: float


def test_ai_command_to_channels():
    cmd = _FakeCmd(roll_cmd=1.0, pitch_cmd=0.0, yaw_rate_cmd=-1.0, throttle_cmd=0.0)
    ch = mc.ai_command_to_channels(cmd)
    assert ch["roll"] == 2000
    assert ch["pitch"] == 1500
    assert ch["yaw"] == 1000
    assert ch["throttle"] == 1000
    # AUX defaults LOW (disarmed)
    assert ch["aux1"] == 1000 and ch["aux2"] == 1000


def test_channel_order_is_explicit_and_complete():
    # order matters: a wrong order swaps control axes on the real aircraft
    assert mc.RC_CHANNEL_ORDER[:4] == ("roll", "pitch", "yaw", "throttle")
    ch = {name: 1500 for name in mc.RC_CHANNEL_ORDER}
    lst = mc.channels_to_list(ch)
    assert lst == [1500] * len(mc.RC_CHANNEL_ORDER)
    # a missing channel must raise, never silently default
    del ch["throttle"]
    with pytest.raises(TransportFrameError):
        mc.channels_to_list(ch)


def test_set_raw_rc_round_trip():
    channels = [1500, 1600, 1400, 1000, 1000, 2000, 1000, 1000]
    frame = encode_set_raw_rc(channels)
    decoded = decode_msp_v2(frame)
    assert decoded.function == MSP_SET_RAW_RC
    assert decode_rc(decoded.payload) == channels


def test_set_raw_rc_clamps_out_of_range():
    frame = encode_set_raw_rc([2500, 500, 1500, 1500])
    decoded = decode_rc(decode_msp_v2(frame).payload)
    assert decoded == [2000, 1000, 1500, 1500]


# ── IMU / attitude decode (gyro path for ego-motion) ────────────────────────────
def _pack_int16(values):
    out = bytearray()
    for v in values:
        out.extend(int(v).to_bytes(2, "little", signed=True))
    return bytes(out)


def test_decode_raw_imu_round_trip():
    raw = _pack_int16([10, -20, 30, 40, -50, 60, -70, 80, -90])
    imu = decode_raw_imu(raw)
    assert imu == ImuRaw(acc=(10, -20, 30), gyro=(40, -50, 60), mag=(-70, 80, -90))


def test_decode_raw_imu_rejects_short():
    with pytest.raises(TransportFrameError):
        decode_raw_imu(b"\x00" * 10)


def test_gyro_raw_to_radps_scale():
    # 1000 lsb * 0.07 deg/s/lsb = 70 deg/s -> ~1.2217 rad/s
    out = mc.gyro_raw_to_radps((1000, 0, -1000), deg_per_s_per_lsb=0.07)
    assert out[0] == pytest.approx(70.0 * 0.017453292519943295, rel=1e-9)
    assert out[1] == 0.0
    assert out[2] == pytest.approx(-out[0], rel=1e-9)


def test_decode_attitude():
    payload = _pack_int16([450, -100, 90])  # roll 45.0 deg, pitch -10.0 deg, yaw 90 deg
    att = decode_attitude(payload)
    assert isinstance(att, Attitude)
    assert att.roll_rad == pytest.approx(45.0 * 0.017453292519943295, rel=1e-9)
    assert att.pitch_rad == pytest.approx(-10.0 * 0.017453292519943295, rel=1e-9)
    assert att.yaw_rad == pytest.approx(90.0 * 0.017453292519943295, rel=1e-9)


# ── Streaming decoder over a noisy UART ──────────────────────────────────────────
def test_stream_single_frame():
    dec = MspDecoder()
    frame = encode_set_raw_rc([1500, 1500, 1500, 1000])
    frames = dec.feed(frame)
    assert len(frames) == 1
    assert frames[0].function == MSP_SET_RAW_RC


def test_stream_resyncs_past_garbage():
    dec = MspDecoder()
    frame = encode_set_raw_rc([1500, 1500, 1500, 1000])
    frames = dec.feed(b"\x00\xab garbage \x24noise" + frame)
    assert len(frames) == 1
    assert decode_rc(frames[0].payload) == [1500, 1500, 1500, 1000]


def test_stream_partial_then_complete():
    dec = MspDecoder()
    frame = encode_set_raw_rc([1100, 1200, 1300, 1400])
    assert dec.feed(frame[:5]) == []          # header incomplete
    assert dec.feed(frame[5:-1]) == []         # payload incomplete (missing crc)
    out = dec.feed(frame[-1:])                 # final crc byte completes it
    assert len(out) == 1
    assert decode_rc(out[0].payload) == [1100, 1200, 1300, 1400]


def test_stream_two_concatenated_frames():
    dec = MspDecoder()
    f1 = encode_set_raw_rc([1500, 1500, 1500, 1000])
    f2 = encode_msp_v2(MSP_RAW_IMU, _pack_int16([1, 2, 3, 4, 5, 6, 7, 8, 9]), direction=mc.DIR_FROM_FC)
    out = dec.feed(f1 + f2)
    assert [f.function for f in out] == [MSP_SET_RAW_RC, MSP_RAW_IMU]


def test_stream_skips_crc_corrupt_frame_then_recovers():
    dec = MspDecoder()
    bad = bytearray(encode_set_raw_rc([1500, 1500, 1500, 1000]))
    bad[-1] ^= 0xFF  # corrupt CRC
    good = encode_msp_v2(MSP_RAW_IMU, _pack_int16([0] * 9), direction=mc.DIR_FROM_FC)
    out = dec.feed(bytes(bad) + good)
    # the corrupt frame is dropped; the good one is recovered
    assert [f.function for f in out] == [MSP_RAW_IMU]
