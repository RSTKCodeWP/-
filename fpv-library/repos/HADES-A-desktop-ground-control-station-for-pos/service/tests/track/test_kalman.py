"""Tests for the XYAH Kalman filter + box conversions (Task 3.1).

The xyxy↔xyah conversion is the named spot where a mirrored-axis (DESIGN.md §3.2) bug
would enter the motion model, so it is round-trip-tested in isolation.
"""

from __future__ import annotations

import numpy as np

from hades.track.kalman import KalmanFilter, xyah_to_xyxy, xyxy_to_xyah


def test_xyxy_xyah_round_trip():
    box = (10.0, 20.0, 50.0, 100.0)  # w=40, h=80, aspect=0.5
    xyah = xyxy_to_xyah(box)
    assert xyah[0] == 30.0  # cx
    assert xyah[1] == 60.0  # cy
    assert xyah[2] == 0.5  # aspect = w/h
    assert xyah[3] == 80.0  # h
    back = xyah_to_xyxy(xyah)
    assert back == box  # exact inverse, no axis flip


def test_kalman_initiate_then_predict_is_stationary_for_static_box():
    kf = KalmanFilter()
    meas = xyxy_to_xyah((100.0, 100.0, 140.0, 180.0))
    mean, cov = kf.initiate(meas)
    # A freshly initiated track has zero velocity → predict leaves position unchanged.
    pred_mean, pred_cov = kf.predict(mean, cov)
    assert np.allclose(pred_mean[:4], meas)
    # Predicted covariance grows (uncertainty increases without a measurement).
    assert np.trace(pred_cov) > np.trace(cov)


def test_xyxy_to_xyah_rejects_non_finite_or_zero_height():
    # Codex P2 (kalman:31): the XYAH conversion divides w/h by height. A zero/negative or
    # non-finite box height would seed an inf/NaN aspect into the filter and corrupt every
    # downstream box. Reject at the conversion boundary rather than propagate poison.
    import pytest

    with pytest.raises(ValueError):
        xyxy_to_xyah((10.0, 20.0, 50.0, 20.0))  # zero height
    with pytest.raises(ValueError):
        xyxy_to_xyah((10.0, 20.0, 50.0, float("nan")))  # non-finite


def test_kalman_update_pulls_state_toward_measurement():
    kf = KalmanFilter()
    mean, cov = kf.initiate(xyxy_to_xyah((100.0, 100.0, 140.0, 180.0)))
    mean, cov = kf.predict(mean, cov)
    # A measurement shifted +20px in x should pull the corrected center rightward.
    moved = xyxy_to_xyah((120.0, 100.0, 160.0, 180.0))
    new_mean, _ = kf.update(mean, cov, moved)
    assert new_mean[0] > mean[0]  # cx moved toward the measurement
    assert new_mean[0] <= moved[0]  # but not past it (filter, not teleport)
