"""HeadingSource — the heading-estimation seam (Task 4.1, M11; research gate §1, §3).

The system is HEADING-LIMITED: the FPV quad has no usable magnetometer (motor/ESC
interference), so yaw is gyro-drift + GPS course-over-ground, and COG is not true heading
(wind crab 5-40 deg). `HeadingSource` is the interface that lets a future
magnetometer / aspect-diversity-triangulation impl drop in WITHOUT touching the fuse or
uncertainty callers. Building that estimator now is the single biggest scope-creep trap and
is explicitly v1.x.

The v1 impl (`ConstantHeadingSource`) does NOT estimate. It reports the configured large
heading sigma + bias from the `error_model`, verbatim. Crucially it reports the zero-mean
JITTER and the systematic BIAS as SEPARATE numbers, because the fuser needs the bias term
on its own to build the non-shrinking bias floor (§2) — a single merged sigma would let
averaging fake away a bias it cannot actually cancel (the "smug filter").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from hades.locate.error_model import SensorErrorModel


@dataclass(frozen=True)
class HeadingEstimate:
    """A heading estimate, with its jitter and bias dispersions kept SEPARATE (§2).

    `jitter_sigma_deg` is the zero-mean, frame-independent component that AVERAGES DOWN
    under multi-frame fusion. `bias_sigma_deg` is the systematic crab/COG component that
    does NOT average down and drives the bias floor. Keeping them apart is what makes the
    fused uncertainty honest on a single straight pass.
    """

    jitter_sigma_deg: float  # zero-mean heading jitter (averages down)
    bias_sigma_deg: float  # systematic heading bias (does NOT average down)


class HeadingSource(ABC):
    """Yields a `HeadingEstimate`. Impls: ConstantHeadingSource (v1), magnetometer (v1.x)."""

    @abstractmethod
    def estimate(self) -> HeadingEstimate:
        """Current heading uncertainty (jitter + bias), in degrees."""
        raise NotImplementedError


class ConstantHeadingSource(HeadingSource):
    """v1: reports the configured heading sigma/bias from the error_model — no estimation.

    This is the honest state for a magnetometer-less FPV platform: we know roughly how bad
    the heading is, and we report that, rather than pretending to measure it. The seam lets
    a real estimator replace this without any caller change.
    """

    def __init__(self, error_model: SensorErrorModel) -> None:
        self._m = error_model

    def estimate(self) -> HeadingEstimate:
        return HeadingEstimate(
            jitter_sigma_deg=self._m.yaw_jitter_sigma_deg,
            bias_sigma_deg=self._m.heading_bias_sigma_deg,
        )
