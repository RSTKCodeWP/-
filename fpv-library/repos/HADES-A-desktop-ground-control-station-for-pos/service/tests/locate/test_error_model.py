"""Tests for the shared sensor-error schema (Task 4.1).

`SensorErrorModel` is the SINGLE SOURCE OF TRUTH for sensor error, imported by BOTH the
geometric simulator (to inject noise) and the Monte Carlo uncertainty propagation (to
assume sigmas) — the anti-circularity discipline is structural: they share this SCHEMA,
never the same realized VALUES (research gate §3, §4 Risk B).

The headline the schema FORCES into the type system: heading sigma is split into a
zero-mean jitter term (`yaw_jitter_sigma_deg`, AVERAGES DOWN under fusion) and a
systematic bias term (`heading_bias_sigma_deg`, does NOT average down, drives the bias
floor §2). No one can collapse them to one "attitude sigma" — and roll/pitch/yaw are
three separate fields for the same reason (yaw is ~10× looser; the system is
heading-limited, not algorithm-limited).
"""

from __future__ import annotations

import dataclasses

import pytest

from hades.locate.error_model import SensorErrorModel

# --- the schema exists, is frozen, and is loadable/swappable -----------------


def test_default_construction_has_sota_grounded_values():
    m = SensorErrorModel()
    # The headline: yaw jitter is the dominant term, an order of magnitude looser than
    # roll/pitch (heading-limited, no magnetometer). These are the load-bearing defaults.
    assert m.yaw_jitter_sigma_deg == pytest.approx(20.0)
    assert m.roll_sigma_deg == pytest.approx(1.5)
    assert m.pitch_sigma_deg == pytest.approx(1.5)
    assert m.yaw_jitter_sigma_deg > 5 * m.roll_sigma_deg


def test_is_frozen_immutable():
    m = SensorErrorModel()
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.yaw_jitter_sigma_deg = 5.0  # type: ignore[misc]


def test_swappable_override_one_field():
    # Both sim and MC build their own instance; overriding one field must not disturb
    # the rest (the "shared schema, separate instances" rule, §4 Risk B).
    base = SensorErrorModel()
    perturbed = dataclasses.replace(base, yaw_jitter_sigma_deg=30.0)
    assert perturbed.yaw_jitter_sigma_deg == pytest.approx(30.0)
    assert perturbed.roll_sigma_deg == base.roll_sigma_deg
    assert perturbed.gps_horiz_sigma_m == base.gps_horiz_sigma_m


# --- the heading SPLIT is the mandatory schema change (§2, §3) ---------------


def test_heading_split_into_three_distinct_fields():
    # The fusion lens forced this: jitter averages down, bias does not (drives the
    # floor), crab is the nominal mean bias. A single "heading sigma" is insufficient.
    m = SensorErrorModel()
    assert hasattr(m, "yaw_jitter_sigma_deg")  # zero-mean, AVERAGES DOWN
    assert hasattr(m, "heading_bias_sigma_deg")  # systematic, does NOT average down
    assert hasattr(m, "crab_angle_deg")  # nominal mean wind-crab offset (a bias)
    # There must be NO collapsed single "yaw_sigma" alias that re-merges them.
    assert not hasattr(m, "yaw_sigma_deg")
    assert m.heading_bias_sigma_deg > 0.0  # a real floor-driver, not a placeholder
    assert m.crab_angle_deg == pytest.approx(8.0)


# --- the two mismatch knobs that 4.5 coverage perturbs MUST be present (§3, §5) ---


def test_time_sync_offset_field_present_default_zero():
    # The named MC-blind term. Default 0 (the MC assumes none); the mismatch fixture
    # sets it nonzero on the SIM instance only — the non-tautology proof (§5).
    m = SensorErrorModel()
    assert m.t_sync_offset_ms == pytest.approx(0.0)
    assert hasattr(m, "t_sync_jitter_ms")


def test_sigma_h_field_present():
    # Ground-plane elevation uncertainty — couples to down-range error as 1/cos^2(nadir),
    # dominates the oblique strata. 4.5 has nothing to perturb without it.
    m = SensorErrorModel()
    assert m.sigma_h_m > 0.0


def test_gps_heavy_tail_knob_present():
    # The heavy-tailed mismatch row draws Student-t on the SIM side while the MC stays
    # Gaussian (§5). The schema must carry the distribution selector + dof.
    m = SensorErrorModel()
    assert m.gps_dist == "gauss"
    studentt = dataclasses.replace(m, gps_dist="studentt", gps_studentt_dof=3.0)
    assert studentt.gps_dist == "studentt"
    assert studentt.gps_studentt_dof == pytest.approx(3.0)


def test_all_documented_fields_present():
    # Lock the full field set so a future edit can't silently drop one the sim/MC depend on.
    names = {f.name for f in dataclasses.fields(SensorErrorModel)}
    expected = {
        "gps_horiz_sigma_m",
        "gps_vert_sigma_m",
        "gps_dist",
        "gps_studentt_dof",
        "roll_sigma_deg",
        "pitch_sigma_deg",
        "yaw_jitter_sigma_deg",
        "heading_bias_sigma_deg",
        "crab_angle_deg",
        "crab_sign_random",
        "boresight_sigma_deg",
        "t_sync_offset_ms",
        "t_sync_jitter_ms",
        "sigma_h_m",
        "pixel_sigma_px",
        "foot_bias_px",
    }
    assert names == expected


# --- validation: a negative sigma is a config error, not a silent NaN source ---


def test_negative_sigma_rejected():
    with pytest.raises(ValueError):
        SensorErrorModel(gps_horiz_sigma_m=-1.0)


def test_unknown_gps_dist_rejected():
    with pytest.raises(ValueError):
        SensorErrorModel(gps_dist="cauchy")
