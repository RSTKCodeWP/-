"""Regenerate the committed video/telemetry test fixtures (Phase 1).

These fixtures are tiny, deterministic, and committed so ingestion tests stay
offline (DESIGN.md §4). Run from the service dir:

    uv run python tests/fixtures/make_fixtures.py

Produces:
  - clip_2s.mp4      happy-path H.264 clip (64x48, 10 fps, 20 frames)
  - clip_2s.srt      DJI O4-format telemetry sidecar matching clip_2s.mp4
  - res_change.ts    MPEG-TS with a mid-stream resolution change (64x48 -> 96x64)
  - clip_corrupt.h264 raw annexb stream with two damaged slice NALs (decodes
                      most frames, raises on the corrupt ones)

The H.264-in-MP4 happy path is what real footage exercises; the .ts and raw
.h264 reproduce the drop/resize failure modes (Task 1.3). Generator approach is
verified against PyAV 17.x (research note, Phase 1 session).
"""

from __future__ import annotations

import re
from pathlib import Path

import av
import numpy as np
from av.bitstream import BitStreamFilterContext

FIXTURES = Path(__file__).parent


def _gradient(w: int, h: int, i: int) -> np.ndarray:
    """A per-frame-shifting gradient so consecutive frames differ."""
    col = np.linspace(0, 255, w, dtype=np.int32)[None, :]
    row = np.linspace(0, 255, h, dtype=np.int32)[:, None]
    arr = np.empty((h, w, 3), np.uint8)
    arr[:, :, 0] = ((col + i * 8) % 256).astype(np.uint8)
    arr[:, :, 1] = (row % 256).astype(np.uint8)
    arr[:, :, 2] = np.uint8((i * 12) % 256)
    return arr


def make_mp4(path: Path, w: int = 64, h: int = 48, fps: int = 10, n: int = 20) -> None:
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height = w, h
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "30", "preset": "ultrafast", "g": "5"}
        for i in range(n):
            frame = av.VideoFrame.from_ndarray(_gradient(w, h, i), format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):  # flush — mandatory or frames are lost
            container.mux(packet)


def make_offset_mp4(
    path: Path, w: int = 64, h: int = 48, fps: int = 10, n: int = 5, offset_s: float = 100.0
) -> None:
    """An mp4 whose first decoded frame's PTS is NOT zero.

    Real MP4/MOV containers carry a nonzero start_time / edit-list offset, so the
    first frame's presentation time is often not 0 — but the `.srt` timecode always
    starts at 0. FileFrameSource must zero-base the video clock or every frame
    mis-aligns to telemetry. This fixture exercises that.
    """
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=fps)
        stream.width, stream.height = w, h
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "30", "preset": "ultrafast", "g": "5"}
        pts_offset = round(offset_s * fps * 1024)  # default time_base is 1/(fps*1024)
        packets = []
        for i in range(n):
            frame = av.VideoFrame.from_ndarray(_gradient(w, h, i), format="rgb24")
            for p in stream.encode(frame):
                if p.pts is not None:
                    p.pts += pts_offset
                packets.append(p)
        for p in stream.encode(None):
            if p.pts is not None:
                p.pts += pts_offset
            packets.append(p)
        for p in packets:
            container.mux(p)


def make_res_change_ts(path: Path, fps: int = 10) -> None:
    """Two segments of different resolution muxed into one MPEG-TS track.

    MPEG-TS carries SPS in-band per keyframe, so a single decoded track reports a
    changed width/height partway through (which MP4's single-entry stsd cannot).
    """
    seg_a, seg_b = FIXTURES / "_seg_a.mp4", FIXTURES / "_seg_b.mp4"
    make_mp4(seg_a, w=64, h=48, fps=fps, n=10)
    make_mp4(seg_b, w=96, h=64, fps=fps, n=10)
    try:
        with av.open(str(path), "w", format="mpegts") as out:
            out_stream = None
            offset = 0
            for seg in (seg_a, seg_b):
                with av.open(str(seg)) as inp:
                    ist = inp.streams.video[0]
                    if out_stream is None:
                        out_stream = out.add_stream_from_template(ist)
                    bsf = BitStreamFilterContext("h264_mp4toannexb", in_stream=ist)
                    end = 0
                    for p in inp.demux(ist):
                        if p.dts is None:
                            continue
                        for fp in bsf.filter(p):
                            fp.stream = out_stream
                            if fp.pts is not None:
                                fp.pts += offset
                            fp.dts += offset
                            end = max(end, (fp.pts or fp.dts) + (fp.duration or 0))
                            out.mux(fp)
                    offset = end
    finally:
        seg_a.unlink(missing_ok=True)
        seg_b.unlink(missing_ok=True)


def make_corrupt_h264(path: Path, w: int = 64, h: int = 48, fps: int = 10, n: int = 30) -> None:
    """Raw annexb .h264 with two damaged slice NALs in the second half.

    MP4 corruption is either concealed (no raise) or breaks av.open(); a raw
    annexb stream lets one frame raise InvalidDataError while the rest decode.
    """
    with av.open(str(path), "w", format="h264") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        s.options = {"crf": "30", "preset": "ultrafast", "g": "3"}
        for i in range(n):
            frame = av.VideoFrame.from_ndarray(_gradient(w, h, i), format="rgb24")
            for p in s.encode(frame):
                c.mux(p)
        for p in s.encode(None):
            c.mux(p)

    raw = bytearray(path.read_bytes())
    hit = 0
    for m in re.finditer(b"\x00\x00\x01", bytes(raw)):
        pos = m.start()
        if (raw[pos + 3] & 0x1F) in (1, 5) and pos > len(raw) // 2:
            raw[pos + 3] |= 0x80  # set forbidden_zero_bit
            for k in range(pos + 4, min(pos + 80, len(raw))):
                raw[k] ^= 0xAA  # trash payload
            hit += 1
            if hit >= 2:
                break
    path.write_bytes(raw)


# DJI O4-generation .srt: modern bracket format, combined [rel_alt: X abs_alt: Y],
# NO attitude/gimbal fields (faithful to real O4 output). lat/lon held constant
# across several frames then stepped, to exercise GPS oversampling. One block
# carries a broken abs_alt (firmware bug) so the untrustworthy-abs_alt path is real.
SRT_BLOCK = (
    "{idx}\n"
    "{t0} --> {t1}\n"
    '<font size="28">FrameCnt: {fc}, DiffTime: 33ms\n'
    "2026-06-24 14:30:{sec:06.3f}\n"
    "[iso: 100] [shutter: 1/1000.0] [fnum: 2.8] [ev: 0] [ct: 5500] "
    "[color_md: default] [focal_len: 24.00] "
    "[latitude: {lat:.6f}] [longitude: {lon:.6f}] "
    "[rel_alt: {rel:.3f} abs_alt: {abs:.3f}] </font>\n"
)


def _tc(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(path: Path, n: int = 20, fps: int = 10) -> None:
    dt = 1.0 / fps
    base_lat, base_lon, rel = 35.123456, -80.654321, 50.000
    blocks = []
    for i in range(n):
        # Step lat/lon every 5 frames (GPS ~oversampled into frames).
        step = i // 5
        lat = base_lat + step * 0.000100
        lon = base_lon + step * 0.000100
        abs_alt = 168.026 if i != 7 else -32.309  # frame 7: known-bad abs_alt
        blocks.append(
            SRT_BLOCK.format(
                idx=i + 1,
                t0=_tc(i * dt),
                t1=_tc((i + 1) * dt),
                fc=i + 1,
                sec=i * dt,
                lat=lat,
                lon=lon,
                rel=rel,
                abs=abs_alt,
            )
        )
    path.write_text("\n".join(blocks) + "\n")


def main() -> None:
    make_mp4(FIXTURES / "clip_2s.mp4")
    make_srt(FIXTURES / "clip_2s.srt")
    make_res_change_ts(FIXTURES / "res_change.ts")
    make_corrupt_h264(FIXTURES / "clip_corrupt.h264")
    make_offset_mp4(FIXTURES / "clip_offset.mp4")
    for f in (
        "clip_2s.mp4",
        "clip_2s.srt",
        "res_change.ts",
        "clip_corrupt.h264",
        "clip_offset.mp4",
    ):
        p = FIXTURES / f
        print(f"{f}: {p.stat().st_size} bytes")


if __name__ == "__main__":
    main()
