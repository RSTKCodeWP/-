"""Tests closing out the detect front-end fixed-point budget (M0).

Establishes the two facts the HLS/RTL detect IP relies on:
  * the white top-hat (and thus every downstream statistic) is INTEGER-EXACT -> no quantisation
    error budget for the morphology stage, only line-buffer resources;
  * the threshold's <=1-count fixed-point rounding moves the target LOS by << the S1 sub-pixel budget.

With the centroid divide (test_fixed_point_centroid: <=4-8 fractional bits) this means the whole
front-end maps to fixed-point with the divide as the ONLY non-trivial quantiser.
"""

from __future__ import annotations

import numpy as np
import pytest

from fpv.seeker.thermal_sim import ThermalSimulator

from fpga.ref_model.golden_vectors import GOLDEN_SCENES
from fpga.ref_model.frontend_fixed_point import (
    tophat_max_frac_part,
    threshold_sensitivity,
)


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_morphology_is_integer_exact(scene):
    """The white top-hat is integer-valued on every frame -> erode/dilate min-max is HW-exact."""
    worst = 0.0
    for frame_u16, _gt in ThermalSimulator(scene.cfg).generate(min(scene.n_frames, 40)):
        worst = max(worst, tophat_max_frac_part(frame_u16))
    assert worst < 1e-9, (
        f"{scene.name}: top-hat has a non-integer value (max frac {worst:.2e}) -- morphology would "
        f"need an error budget, unexpected for min/max on integer counts")


@pytest.mark.parametrize("scene", GOLDEN_SCENES, ids=lambda s: s.name)
def test_threshold_quantization_is_negligible_for_los(scene):
    """A +/-1..2 count threshold perturbation (the fixed-point rounding) barely moves the LOS."""
    ts = threshold_sensitivity(scene)
    print(f"\n[{scene.name}] threshold +/-1,2 count -> target centroid shift "
          f"max={ts.max_centroid_shift_px:.4f} rms={ts.rms_centroid_shift_px:.4f} px (n={ts.n_frames})")
    assert ts.n_frames >= 20
    # far under the scene's sub-pixel budget (0.10 px 14-bit / 0.35 px 8-bit)
    assert ts.max_centroid_shift_px < 0.1 * scene.centroid_rmse_gate_px + 0.03, (
        f"{scene.name}: threshold rounding moved the centroid {ts.max_centroid_shift_px:.4f} px "
        f"-- larger than expected for a <=1-count quantiser")
    assert ts.rms_centroid_shift_px < ts.max_centroid_shift_px + 1e-9
