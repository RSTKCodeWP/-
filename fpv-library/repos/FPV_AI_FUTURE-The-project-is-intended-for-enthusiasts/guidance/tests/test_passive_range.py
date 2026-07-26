"""Passive parallax range: frame contract, the earned-parallax gate, and refusal without a maneuver."""

from __future__ import annotations

import math

import numpy as np

from fpv.guidance.passive_range import (
    PassiveRangeConfig,
    PassiveRangeEstimator,
    _bearing_of,
    _bearing_unit,
)


def _fly(maneuver_g: float, *, tmax: float = 6.0, dt: float = 0.02, seed: int = 0,
         noise_deg: float = 0.3):
    """Closing intercept; returns the estimate at the moment true range first crosses 40 m."""
    rng = np.random.default_rng(seed)
    ip = np.zeros(3); iv = np.array([6.0, 9.0, 32.0])
    tp = np.array([45.0, 60.0, 150.0]); tv = np.array([2.0, -3.0, -6.0])
    est = PassiveRangeEstimator(PassiveRangeConfig())
    lat = np.cross(iv, [0, 0, 1.0]); lat /= np.linalg.norm(lat)
    sigma = math.radians(noise_deg)
    for k in range(int(tmax / dt)):
        a = maneuver_g * 9.81 * math.cos(2 * math.pi * (k * dt) / tmax) * lat
        iv = iv + a * dt; ip = ip + iv * dt; tp = tp + tv * dt
        rel = tp - ip
        # bearings measured FROM THE BORESIGHT (+z), matching fpv.seeker.geometry
        az = math.atan2(rel[0], rel[2]) + rng.normal(0, sigma)
        el = math.atan2(rel[1], rel[2]) + rng.normal(0, sigma)
        out = est.update(dt, az, el, tuple(a), tuple(iv))
        r = float(np.linalg.norm(rel))
        if r <= 40.0:
            return r, out
    raise AssertionError("never closed to the gate")


def test_bearing_helpers_use_the_seeker_boresight_convention():
    """The seeker reports angles FROM the boresight (az=atan2(dx,f)); a spherical convention here would
    silently corrupt every estimate, so pin the round-trip."""
    for az, el in ((0.0, 0.0), (0.3, -0.2), (-0.45, 0.15)):
        v = _bearing_unit(az, el)
        back = _bearing_of(v)
        assert abs(back[0] - az) < 1e-9 and abs(back[1] - el) < 1e-9
    assert np.allclose(_bearing_unit(0.0, 0.0), [0.0, 0.0, 1.0]), "zero bearing must be the boresight (+z)"


def test_straight_run_is_refused_even_though_the_filter_has_a_number():
    """No maneuver -> no parallax -> no range released. The filter still holds a value (and would sound
    confident about it); the gate is what keeps that fabrication out of the commit path."""
    _, est = _fly(0.0)
    assert not est.trusted and est.range_m is None and est.t_go_s is None
    assert est.source == "unearned-parallax"
    assert est.raw_range_m > 0.0, "the filter does have a number -- that is exactly the danger"


def test_own_maneuver_earns_parallax_and_releases_a_usable_range():
    true_r, est = _fly(0.84)
    assert est.trusted and est.range_m is not None
    assert est.parallax_deg >= PassiveRangeConfig().parallax_min_deg
    assert abs(est.range_m - true_r) / true_r < 0.35, (
        f"expected a coarse-but-real range, got {est.range_m:.1f} m vs true {true_r:.1f} m")


def test_estimate_is_coarse_not_precise():
    """Honesty guard: passive parallax range is a COARSE cue. A sub-5% claim means truth leaked in."""
    true_r, est = _fly(0.84)
    assert abs(est.range_m - true_r) / true_r > 0.005


def test_gate_does_not_move_even_when_the_filter_estimate_does():
    """The gate must be driven by our own INS motion, not by the filter. Flying the SAME trajectory with a
    much noisier bearing stream drives the filter's range estimate far apart -- the earned parallax must
    barely move. (It is not bit-identical only because the reference LOS direction is taken from the first,
    noisy, bearing; that is a measurement axis, not filter state.)"""
    _, quiet = _fly(0.84, noise_deg=0.3)
    _, noisy = _fly(0.84, noise_deg=2.0)
    spread = abs(quiet.range_m - noisy.range_m) / quiet.range_m
    assert spread > 0.25, f"expected the filter estimates to diverge under noise, spread only {spread:.0%}"
    assert abs(quiet.parallax_deg - noisy.parallax_deg) < 0.05, (
        "earned parallax must track our own motion, not the filter's opinion of range")
