"""RTL co-simulation: bt656_rx.v recovers a Y frame from a valid BT.656 byte stream (M0 ingest).

A Python BT.656 encoder wraps a known monochrome Y frame (SAV/EAV preambles + 4:2:2 mux with
neutral chroma), the Verilog receiver unwraps it via iverilog, and the recovered frame must equal
the original byte-for-byte -- proving the embedded-sync parse, the active-video gating and the
chroma/luma demux.  Skips cleanly if iverilog is not installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _xy(f: int, v: int, h: int) -> int:
    """BT.656 XY status byte: bit7=1, bit6=F, bit5=V, bit4=H (protection bits left 0; RX ignores)."""
    return 0x80 | (f << 6) | (v << 5) | (h << 4)


def _encode_bt656(frame: list[list[int]], *, blank_lines: int = 2) -> list[int]:
    """Wrap a Y frame (rows of luma in [1,254], even width) into a BT.656 byte stream."""
    out: list[int] = []
    sav = lambda f, v: [0xFF, 0x00, 0x00, _xy(f, v, 0)]
    eav = lambda f, v: [0xFF, 0x00, 0x00, _xy(f, v, 1)]

    for _ in range(blank_lines):                       # vertical blanking (V=1) before the field
        out += sav(0, 1) + [0x80, 0x10] * 4 + eav(0, 1)
    for row in frame:                                  # active lines (V=0)
        out += sav(0, 0)
        for i in range(0, len(row), 2):                # 4:2:2 -> Cb Y0 Cr Y1 ...
            out += [0x80, row[i], 0x80, row[i + 1]]
        out += eav(0, 0)
    out += sav(0, 1) + [0x80] + eav(0, 1)              # trailing blanking
    return out


def _make_frame(h: int, w: int) -> list[list[int]]:
    return [[1 + ((r * w + c) % 254) for c in range(w)] for r in range(h)]


def _run_rx(stream: list[int], tmp_path: Path) -> list[list[int]]:
    stim = tmp_path / "stim.txt"
    stim.write_text("".join(f"{b}\n" for b in stream))

    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "bt656_rx.v"), str(_RTL_DIR / "tb_bt656_rx.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim), f"+stim={stim}"],
                          check=True, capture_output=True, text=True)

    frames: list[list[list[int]]] = []
    lines: list[list[int]] = []
    cur: list[int] | None = None
    for line in proc.stdout.splitlines():
        if line == "SOF":
            if lines:
                frames.append(lines)
            lines = []
            cur = None
        elif line == "SOL":
            cur = []
            lines.append(cur)
        elif line.startswith("Y "):
            assert cur is not None, "Y sample before any SOL"
            cur.append(int(line.split()[1]))
    if lines:
        frames.append(lines)
    assert len(frames) == 1, f"expected exactly one frame, got {len(frames)}"
    return frames[0]


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_bt656_rx_recovers_the_frame(tmp_path):
    """The receiver recovers the exact Y frame from the encoded BT.656 stream."""
    frame = _make_frame(h=8, w=8)
    recovered = _run_rx(_encode_bt656(frame), tmp_path)
    assert recovered == frame, f"recovered frame != original\n  got={recovered}\n  exp={frame}"
    print(f"\n[bt656_rx] recovered {len(frame)}x{len(frame[0])} Y frame byte-exact from BT.656 stream")


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
def test_bt656_rx_wider_frame(tmp_path):
    """A wider line still demuxes correctly (chroma/luma phase holds across the line)."""
    frame = _make_frame(h=4, w=16)
    assert _run_rx(_encode_bt656(frame), tmp_path) == frame
