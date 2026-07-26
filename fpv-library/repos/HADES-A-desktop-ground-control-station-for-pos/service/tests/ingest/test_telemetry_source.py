"""Tests for TelemetrySource + SrtFileSource (Task 1.4)."""

from pathlib import Path

import pytest

from hades.ingest.srt_file_source import SrtFileSource
from hades.ingest.telemetry_source import TelemetrySource

FIXTURES = Path(__file__).parent.parent / "fixtures"
SRT = FIXTURES / "clip_2s.srt"


def test_srt_source_is_a_telemetry_source():
    assert issubclass(SrtFileSource, TelemetrySource)


def test_telemetry_source_is_abstract():
    with pytest.raises(TypeError):
        TelemetrySource()


def test_parses_all_blocks_from_fixture():
    poses = list(SrtFileSource(SRT))
    assert len(poses) == 20  # fixture has 20 subtitle blocks


def test_first_pose_fields_match_fixture_line():
    pose = next(iter(SrtFileSource(SRT)))
    # Fixture block 1: lat 35.123456, lon -80.654321, rel_alt 50.000
    assert pose.lat == pytest.approx(35.123456)
    assert pose.lon == pytest.approx(-80.654321)
    assert pose.alt == pytest.approx(50.000)


def test_negative_longitude_sign_preserved():
    pose = next(iter(SrtFileSource(SRT)))
    assert pose.lon < 0  # western hemisphere — sign must survive parsing


def test_alt_is_rel_alt_tagged_rel_takeoff():
    pose = next(iter(SrtFileSource(SRT)))
    assert pose.alt == pytest.approx(50.000)  # rel_alt, not abs_alt
    assert pose.alt_datum == "REL_TAKEOFF"


def test_pose_from_srt_is_position_only_attitude_none():
    # Real DJI O4 .srt has no attitude/gimbal fields — heading-limited.
    pose = next(iter(SrtFileSource(SRT)))
    assert pose.roll is None
    assert pose.pitch is None
    assert pose.yaw is None


def test_seq_is_framecnt_minus_one_zero_based():
    seqs = [p.seq for p in SrtFileSource(SRT)]
    assert seqs == list(range(20))  # FrameCnt 1..20 -> seq 0..19


def test_timestamps_monotonic_from_zero():
    ts = [p.t for p in SrtFileSource(SRT)]
    assert ts[0] == pytest.approx(0.0)
    assert all(b > a for a, b in zip(ts, ts[1:]))


def test_lat_lon_step_every_five_frames():
    # Fixture steps lat/lon every 5 frames (GPS oversampled into frames).
    poses = list(SrtFileSource(SRT))
    assert poses[0].lat == pytest.approx(poses[4].lat)  # same fix held
    assert poses[5].lat > poses[4].lat  # stepped at frame 5


def test_bad_abs_alt_flagged_but_rel_alt_kept():
    # Fixture frame index 7 carries abs_alt -32.309 (firmware glitch).
    poses = list(SrtFileSource(SRT))
    bad = poses[7]
    assert bad.alt == pytest.approx(50.000)  # rel_alt still trustworthy
    assert bad.abs_alt_valid is False
    # Neighboring frames have a sane abs_alt.
    assert poses[6].abs_alt_valid is True


def test_abs_alt_regex_not_fooled_by_prefixed_token(tmp_path):
    # A vendor token whose name ends in abs_alt must not be grabbed instead of
    # the real [rel_alt: X abs_alt: Y] value (un-anchored regex trap).
    srt = tmp_path / "prefixed.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,100\n"
        '<font size="28">FrameCnt: 1, DiffTime: 33ms\n'
        "2026-06-24 14:30:00.000\n"
        "[gb_abs_alt: 999.0] [latitude: 35.0] [longitude: -80.0] "
        "[rel_alt: 50.000 abs_alt: 168.026] </font>\n"
    )
    pose = next(iter(SrtFileSource(srt)))
    assert pose.abs_alt == pytest.approx(168.026)  # not 999.0


def test_block_without_gps_flagged_not_dropped(tmp_path):
    # GPS cold-start: a block with no lat/lon must yield a flagged pose,
    # preserving frame alignment (count unchanged), never plot 0,0.
    srt = tmp_path / "nogps.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:00,100\n"
        '<font size="28">FrameCnt: 1, DiffTime: 33ms\n'
        "2026-06-24 14:30:00.000\n"
        "[iso: 100] [rel_alt: 0.000 abs_alt: 0.000] </font>\n"
    )
    poses = list(SrtFileSource(srt))
    assert len(poses) == 1  # not dropped
    assert poses[0].gps_valid is False
    assert poses[0].lat is None and poses[0].lon is None


def test_empty_srt_raises(tmp_path):
    srt = tmp_path / "empty.srt"
    srt.write_text("")
    with pytest.raises(ValueError):
        list(SrtFileSource(srt))


def test_nonempty_but_no_parseable_blocks_raises(tmp_path):
    # A non-empty but corrupt/truncated .srt with no valid telemetry blocks must
    # raise (not silently look like missing telemetry) — validation must not run blind.
    srt = tmp_path / "garbage.srt"
    srt.write_text("not a subtitle\n\nstill not a subtitle\n\njust noise\n")
    with pytest.raises(ValueError):
        list(SrtFileSource(srt))
