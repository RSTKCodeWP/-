"""Tests for the HeadingSource interface + v1 constant-sigma impl (Task 4.1, M11).

`HeadingSource` is a SEAM, not an estimator. The system is heading-limited (no usable
magnetometer); v1 simply reports the configured large heading sigma + bias from the
`error_model`. The interface exists so a future magnetometer / aspect-diversity
triangulation impl can drop in WITHOUT touching the fuse/uncertainty callers (research
gate §1, §3). Building that estimator now is the single biggest scope-creep trap and is
explicitly v1.x.
"""

from __future__ import annotations

import pytest

from hades.locate.error_model import SensorErrorModel
from hades.locate.heading_source import ConstantHeadingSource, HeadingEstimate, HeadingSource


def test_constant_source_is_a_heading_source():
    assert issubclass(ConstantHeadingSource, HeadingSource)


def test_v1_reports_the_configured_large_sigma_and_bias():
    # v1 returns the error_model's heading terms verbatim — it does NOT estimate.
    m = SensorErrorModel()
    src = ConstantHeadingSource(m)
    est = src.estimate()
    assert isinstance(est, HeadingEstimate)
    # The jitter (zero-mean) and the bias (systematic) are reported SEPARATELY so the
    # fuser can build the non-shrinking bias floor (§2). A single merged sigma would
    # destroy the floor.
    assert est.jitter_sigma_deg == pytest.approx(m.yaw_jitter_sigma_deg)
    assert est.bias_sigma_deg == pytest.approx(m.heading_bias_sigma_deg)


def test_swapped_error_model_changes_the_estimate():
    # The seam: a different (e.g. retuned-from-flight) error_model flows straight through.
    import dataclasses

    tight = dataclasses.replace(SensorErrorModel(), yaw_jitter_sigma_deg=5.0)
    src = ConstantHeadingSource(tight)
    assert src.estimate().jitter_sigma_deg == pytest.approx(5.0)


def test_interface_is_abstract():
    # HeadingSource itself cannot be instantiated — it's the seam, impls fill it.
    with pytest.raises(TypeError):
        HeadingSource()  # type: ignore[abstract]
