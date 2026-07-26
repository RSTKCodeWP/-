"""Tests for the false-confirmed-per-km² metric (Task 3.7 / plan 3.8).

The mission-meaningful FP budget (design line 96): confirmed false positives divided by
the ground area the camera actually SWEPT over a clip — distinct from the per-frame
flicker rate (Task 3.6). A SAR coordinator cares about "how many empty coordinates will I
be sent to per km² I search," not a per-minute rate, because search effort scales with
area covered, not wall-clock.

Swept area is the UNION of the per-frame camera ground footprints (overlapping frames must
not double-count). We rasterise each footprint onto a fixed ground grid and count covered
cells × cell area — simple, deterministic, dependency-light, honest about overlap.
"""

from __future__ import annotations

import math

import pytest

from hades.eval.fp_per_km2 import (
    FootprintQuad,
    false_confirms_per_km2,
    swept_area_km2,
)


def _square_quad(cx: float, cy: float, half_m: float) -> FootprintQuad:
    """A square ground footprint centered at local meters (cx, cy), side 2·half_m.

    Footprints are in a local ENU-meters frame (the metric works in meters; the caller
    projects image corners to the ground once via the shared geometry). Corners CCW.
    """
    return FootprintQuad(
        corners=(
            (cx - half_m, cy - half_m),
            (cx + half_m, cy - half_m),
            (cx + half_m, cy + half_m),
            (cx - half_m, cy + half_m),
        )
    )


def test_single_footprint_area_matches_geometry():
    # One 200 m × 200 m footprint = 0.04 km². Grid raster should land within a cell of truth.
    quad = _square_quad(0.0, 0.0, 100.0)
    area = swept_area_km2([quad], cell_m=5.0)
    assert area == pytest.approx(0.04, rel=0.02)


def test_overlapping_footprints_are_not_double_counted():
    # Two identical overlapping footprints sweep the SAME ground → area ≈ one footprint,
    # not two (the union property — the whole point of the metric).
    quad = _square_quad(0.0, 0.0, 100.0)
    one = swept_area_km2([quad], cell_m=5.0)
    two = swept_area_km2([quad, quad], cell_m=5.0)
    assert two == pytest.approx(one, rel=1e-9)


def test_disjoint_footprints_add_up():
    # Two non-overlapping footprints sweep twice the area.
    a = _square_quad(0.0, 0.0, 100.0)
    b = _square_quad(1000.0, 0.0, 100.0)  # far apart, no overlap
    area = swept_area_km2([a, b], cell_m=5.0)
    assert area == pytest.approx(0.08, rel=0.02)


def test_partial_overlap_between_single_and_double():
    # Half-overlapping footprints sweep between 1× and 2× a single footprint.
    a = _square_quad(0.0, 0.0, 100.0)
    b = _square_quad(100.0, 0.0, 100.0)  # shifted by half a side → 50% overlap
    one = swept_area_km2([a], cell_m=5.0)
    area = swept_area_km2([a, b], cell_m=5.0)
    assert one < area < 2 * one


def test_false_confirms_per_km2():
    # 3 confirmed false positives over a 0.04 km² sweep → 75 / km².
    quad = _square_quad(0.0, 0.0, 100.0)
    rate = false_confirms_per_km2(n_false_confirms=3, footprints=[quad], cell_m=5.0)
    assert rate == pytest.approx(3 / 0.04, rel=0.02)


def test_zero_false_confirms_is_zero_rate():
    quad = _square_quad(0.0, 0.0, 100.0)
    rate = false_confirms_per_km2(n_false_confirms=0, footprints=[quad], cell_m=5.0)
    assert rate == 0.0


def test_zero_swept_area_yields_nan_not_div_by_zero():
    # No footprints → no area swept → the rate is undefined (NaN), never a ZeroDivisionError
    # or a misleading 0 (which would read as "perfectly clean").
    rate = false_confirms_per_km2(n_false_confirms=2, footprints=[], cell_m=5.0)
    assert math.isnan(rate)


def test_planted_false_confirms_over_known_area_fixture():
    # The plan's named acceptance shape: a fixture with a KNOWN swept area + planted false
    # confirms returns the hand-computed rate. 1 km² swept (a 1000 m square), 5 planted
    # false confirms → exactly 5 / km².
    big = _square_quad(0.0, 0.0, 500.0)  # 1000 m × 1000 m = 1 km²
    area = swept_area_km2([big], cell_m=10.0)
    assert area == pytest.approx(1.0, rel=0.02)
    rate = false_confirms_per_km2(n_false_confirms=5, footprints=[big], cell_m=10.0)
    assert rate == pytest.approx(5.0, rel=0.02)


def test_footprint_quad_requires_four_corners():
    with pytest.raises(ValueError):
        FootprintQuad(corners=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)))  # only 3
