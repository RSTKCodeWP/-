"""RTL co-simulation: centroid_dp.v vs the Python fixed-point reference (M0, real hardware brick).

Drives REAL detected blobs from the golden scenes through the Verilog centroid datapath (iverilog)
and asserts the RTL output matches the bit-exact Python reference (fpga/ref_model/fixed_point) to
the LSB.  This is the first synthesised-logic-shaped block of the FPGA port, verified against the
same golden vectors that gate the software detector.

Skips cleanly if iverilog is not installed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from fpv.seeker.detect import ThresholdState, detect_frame
from fpv.seeker.thermal_sim import ThermalSimulator

from fpga.ref_model.golden_vectors import GOLDEN_SCENES
from fpga.ref_model.fixed_point import reconstruct_blob_inputs, weighted_centroid

_F = 8                                   # fractional bits (must match tb_centroid_dp.v localparam F)
_RTL_DIR = Path(__file__).parent
_IVERILOG = shutil.which("iverilog")
_VVP = shutil.which("vvp")


def _collect_blobs(scene, max_blobs: int = 8):
    """Return a list of (pixels, q_x, q_y, den) from real detected blobs of the scene.

    pixels: list of (x, y, w) integer triples (component pixels, background-subtracted weights).
    q_x/q_y: the exact fixed-point centroid numerators floor((num<<F)/den) the RTL must reproduce.
    """
    sim = ThermalSimulator(scene.cfg)
    frames = sim.generate(scene.n_frames)
    ts = ThresholdState()
    out = []
    for frame_u16, gt in frames:
        blobs, ts = detect_frame(
            frame_u16, cam_temp_c=gt.cam_temp_c, ffc_state=gt.ffc_state,
            threshold_state=ts, frame_id=gt.frame_id,
            min_snr=scene.min_snr, min_area_px=scene.min_area_px)
        if gt.ffc_state != "READY" or not gt.is_target_visible or not blobs:
            continue
        rec = reconstruct_blob_inputs(frame_u16, ts.threshold_counts, blobs[0].bbox)
        if rec is None:
            continue
        raw_patch, comp_mask, x0, y0 = rec
        res = weighted_centroid(raw_patch, comp_mask, x0, y0, frac_bits=None)
        if res.degenerate or res.den <= 0:
            continue

        patch = raw_patch.astype(np.int64)
        local_bg = int(patch[comp_mask].min())
        bg_sub = np.maximum(patch - local_bg, 0)
        h, w = patch.shape
        pixels = [(x0 + c, y0 + r, int(bg_sub[r, c]))
                  for r in range(h) for c in range(w) if comp_mask[r, c]]

        q_x = (res.num_x << _F) // res.den
        q_y = (res.num_y << _F) // res.den
        out.append((pixels, int(q_x), int(q_y), int(res.den)))
        if len(out) >= max_blobs:
            break
    return out


def _run_rtl(blobs, tmp_path: Path):
    """Compile centroid_dp + tb with iverilog, stream the blobs, return list of (cx, cy, den)."""
    stim = tmp_path / "stim.txt"
    with stim.open("w") as f:
        for pixels, _qx, _qy, _den in blobs:
            n = len(pixels)
            for i, (x, y, w) in enumerate(pixels):
                f.write(f"{x} {y} {w} {1 if i == n - 1 else 0}\n")

    sim = tmp_path / "sim.vvp"
    subprocess.run(
        [_IVERILOG, "-g2012", "-o", str(sim),
         str(_RTL_DIR / "centroid_dp.v"), str(_RTL_DIR / "tb_centroid_dp.v")],
        check=True, capture_output=True, text=True)
    proc = subprocess.run([_VVP, str(sim), f"+stim={stim}"],
                          check=True, capture_output=True, text=True)

    results = []
    for line in proc.stdout.splitlines():
        if line.startswith("RES "):
            _, cx, cy, den = line.split()
            results.append((int(cx), int(cy), int(den)))
    return results


@pytest.mark.skipif(_IVERILOG is None or _VVP is None, reason="iverilog/vvp not installed")
@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_centroid_dp_matches_python_reference(scene, tmp_path):
    """The Verilog centroid datapath reproduces the Python fixed-point centroid bit-for-bit."""
    blobs = _collect_blobs(scene)
    assert len(blobs) >= 4, f"{scene.name}: only {len(blobs)} usable blobs"

    results = _run_rtl(blobs, tmp_path)
    assert len(results) == len(blobs), (
        f"{scene.name}: RTL emitted {len(results)} centroids for {len(blobs)} blobs")

    for i, ((_, q_x, q_y, den), (cx, cy, den_rtl)) in enumerate(zip(blobs, results)):
        assert den_rtl == den, f"{scene.name} blob {i}: RTL den {den_rtl} != {den}"
        assert cx == q_x, f"{scene.name} blob {i}: RTL cx_fixed {cx} != {q_x} (px {cx/2**_F:.4f})"
        assert cy == q_y, f"{scene.name} blob {i}: RTL cy_fixed {cy} != {q_y} (px {cy/2**_F:.4f})"
    print(f"\n[{scene.name}] centroid_dp.v == Python fixed-point ref on {len(blobs)} real blobs "
          f"(cx/cy/den bit-exact, F={_F})")
