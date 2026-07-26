"""Fixed-point closeout for the REST of the detect front-end (top-hat, threshold, CC) -- M0.

Together with ``fixed_point.py`` (centroid datapath) this completes the fixed-point budget of the S1
detect front-end that the PL IP must reproduce.  The finding this module establishes:

  * MORPHOLOGY IS INTEGER-EXACT.  The white top-hat is ``f - opening(f)`` and a flat-SE opening is
    erode(min) then dilate(max); on integer counts min/max are exact, so the top-hat residual is
    integer-valued.  No quantisation, no error budget -- the PL only needs the SE line buffers.
  * CONNECTED COMPONENTS IS INTEGER-EXACT.  Labelling a binary mask is combinational integer logic.
  * THE THRESHOLD is the only stats stage.  Its inputs (percentile, MAD) are medians of integer
    top-hat values -> exact via a histogram; the only fixed-point ops are the constant multiplies
    (k=2.5 * MAD is exact in 1 fractional bit; sigma_clip=3.0 is integer).  So the threshold rounds
    to <= ~1 count.  This module MEASURES whether that <=1-count rounding moves the LOS: it perturbs
    the threshold by +/-1, +/-2 counts and reports the resulting target-centroid shift.

Conclusion (pinned by the tests): the whole detect front-end maps to fixed-point with the centroid
divide (fixed_point.py: <=4-8 fractional bits) as the ONLY non-trivial quantiser; morphology and CC
are exact and the threshold rounding is negligible for the LOS.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from fpv.seeker.detect import (
    _CC_HEIGHT,
    _CC_LEFT,
    _CC_TOP,
    _CC_WIDTH,
    _STRUCT_ELEM,
    _compute_threshold,
    _connected_components,
    _white_tophat,
)

from fpga.ref_model.fixed_point import weighted_centroid
from fpga.ref_model.golden_vectors import GoldenScene


def tophat_max_frac_part(frame_u16: npt.NDArray[np.uint16]) -> float:
    """Largest fractional part of any top-hat value (0.0 => integer-exact morphology)."""
    tophat = _white_tophat(frame_u16.astype(np.float32), _STRUCT_ELEM)
    frac = np.abs(tophat - np.round(tophat))
    return float(frac.max())


def _target_centroid_at_threshold(
    tophat: npt.NDArray[np.float32],
    frame_u16: npt.NDArray[np.uint16],
    threshold: float,
    near_xy: tuple[float, float],
) -> tuple[float, float] | None:
    """Weighted centroid of the component nearest ``near_xy`` when the top-hat is cut at ``threshold``."""
    binary = tophat > threshold
    num_labels, labeled, stats = _connected_components(binary)
    if num_labels <= 1:
        return None

    nx, ny = int(round(near_xy[0])), int(round(near_xy[1]))
    h, w = labeled.shape
    lab = 0
    for r in range(0, 4):                        # expand a small search ring to find the target label
        found = False
        for yy in range(max(ny - r, 0), min(ny + r + 1, h)):
            for xx in range(max(nx - r, 0), min(nx + r + 1, w)):
                if labeled[yy, xx] > 0:
                    lab = int(labeled[yy, xx])
                    found = True
                    break
            if found:
                break
        if found:
            break
    if lab == 0:
        return None

    x0, y0 = int(stats[lab, _CC_LEFT]), int(stats[lab, _CC_TOP])
    bw, bh = int(stats[lab, _CC_WIDTH]), int(stats[lab, _CC_HEIGHT])
    sl = (slice(y0, y0 + bh), slice(x0, x0 + bw))
    comp_mask = labeled[sl] == lab
    r = weighted_centroid(frame_u16[sl], comp_mask, x0, y0, frac_bits=None)
    return (r.cx, r.cy)


@dataclass(frozen=True)
class ThresholdSensitivity:
    scene: str
    n_frames: int
    max_centroid_shift_px: float     # worst target-centroid move over all +/- perturbations
    rms_centroid_shift_px: float


def threshold_sensitivity(scene: GoldenScene,
                          deltas: tuple[int, ...] = (1, 2)) -> ThresholdSensitivity:
    """Measure how far the target centroid moves when the threshold is perturbed +/- delta counts.

    Bounds the LOS contribution of the threshold's fixed-point rounding (<= ~1 count).
    """
    from fpv.seeker.thermal_sim import ThermalSimulator
    sim = ThermalSimulator(scene.cfg)
    frames = sim.generate(scene.n_frames)

    shifts: list[float] = []
    n_used = 0
    for frame_u16, gt in frames:
        if gt.ffc_state != "READY" or not gt.is_target_visible:
            continue
        tophat = _white_tophat(frame_u16.astype(np.float32), _STRUCT_ELEM)
        thr, _pct, _mad = _compute_threshold(tophat.ravel())
        base = _target_centroid_at_threshold(tophat, frame_u16, thr, gt.target_centroid_px)
        if base is None:
            continue
        n_used += 1
        for d in deltas:
            for signed in (float(d), -float(d)):
                pert = _target_centroid_at_threshold(
                    tophat, frame_u16, thr + signed, gt.target_centroid_px)
                if pert is not None:
                    shifts.append(float(np.hypot(pert[0] - base[0], pert[1] - base[1])))

    max_shift = max(shifts) if shifts else float("nan")
    rms_shift = float(np.sqrt(np.mean(np.square(shifts)))) if shifts else float("nan")
    return ThresholdSensitivity(scene.name, n_used, max_shift, rms_shift)


def _main() -> None:
    from fpga.ref_model.golden_vectors import GOLDEN_SCENES
    for scene in GOLDEN_SCENES:
        fracs = []
        from fpv.seeker.thermal_sim import ThermalSimulator
        for frame_u16, _gt in ThermalSimulator(scene.cfg).generate(20):
            fracs.append(tophat_max_frac_part(frame_u16))
        ts = threshold_sensitivity(scene)
        print(f"[{scene.name}] morphology max frac-part = {max(fracs):.3e} (0 => integer-exact); "
              f"threshold +/-1,2 count -> target centroid shift "
              f"max={ts.max_centroid_shift_px:.4f} rms={ts.rms_centroid_shift_px:.4f} px "
              f"(n={ts.n_frames})")


if __name__ == "__main__":
    _main()
