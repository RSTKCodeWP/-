"""Cross-frame evaluation: run a detector over a labeled set, aggregate, format.

`evaluate()` is the harness that turns per-frame center-distance scores into one
acceptance report — overall precision/recall plus size- and subclass-stratified recall
(the design's per-subclass floor). The detector is injected through the `Detector`
interface, so the same harness scores the Core ML, ONNX, or a fake detector identically.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from hades.detect.detector import Detector
from hades.eval.detection_metrics import (
    FrameScore,
    GroundTruth,
    match_by_center_distance,
    recall_by_size,
    recall_by_subclass,
)

#: Default area buckets (px²) for size-stratified recall — small / medium / large.
DEFAULT_SIZE_BOUNDS: tuple[float, ...] = (0, 1024, 9216, float("inf"))


@dataclass(frozen=True)
class LabeledFrame:
    """One evaluation frame: the image plus its ground-truth boxes."""

    image: np.ndarray
    ground_truths: list[GroundTruth] = field(default_factory=list)


@dataclass(frozen=True)
class EvalReport:
    """Aggregated metrics over a dataset."""

    overall: FrameScore
    by_size: dict[str, FrameScore]
    by_subclass: dict[str, FrameScore]
    n_frames: int


def _sum_scores(scores: Sequence[FrameScore]) -> FrameScore:
    return FrameScore(
        true_positives=sum(s.true_positives for s in scores),
        false_positives=sum(s.false_positives for s in scores),
        false_negatives=sum(s.false_negatives for s in scores),
    )


def _merge_buckets(dicts: Sequence[dict[str, FrameScore]]) -> dict[str, FrameScore]:
    """Sum same-keyed FrameScores across frames (buckets/subclasses appear per frame)."""
    keys: list[str] = []
    for d in dicts:
        for k in d:
            if k not in keys:
                keys.append(k)
    return {k: _sum_scores([d[k] for d in dicts if k in d]) for k in keys}


def evaluate(
    detector: Detector,
    dataset: Sequence[LabeledFrame],
    *,
    max_distance: float,
    size_bounds: Sequence[float] = DEFAULT_SIZE_BOUNDS,
    conf_threshold: float | None = None,
) -> EvalReport:
    """Run `detector` over `dataset`, return aggregated P/R + stratified recall.

    `conf_threshold`, when given, keeps only predictions with `conf >= conf_threshold`
    BEFORE matching — so one detector pass can be re-scored across a sweep of operating
    points (the honest "recall @ conf=T, precision=Y" reporting). `None` scores every
    prediction the detector emits (the prior behavior; the detector's own threshold rules).
    """
    overall: list[FrameScore] = []
    size_dicts: list[dict[str, FrameScore]] = []
    sub_dicts: list[dict[str, FrameScore]] = []

    for lf in dataset:
        preds = detector.detect(lf.image)
        if conf_threshold is not None:
            preds = [p for p in preds if p.conf >= conf_threshold]
        gts = lf.ground_truths
        matches = match_by_center_distance(preds, gts, max_distance=max_distance)
        tp = len(matches)
        overall.append(
            FrameScore(
                true_positives=tp,
                false_positives=len(preds) - tp,
                false_negatives=len(gts) - tp,
            )
        )
        size_dicts.append(
            recall_by_size(preds, gts, max_distance=max_distance, bounds=size_bounds)
        )
        sub_dicts.append(recall_by_subclass(preds, gts, max_distance=max_distance))

    return EvalReport(
        overall=_sum_scores(overall),
        by_size=_merge_buckets(size_dicts),
        by_subclass=_merge_buckets(sub_dicts),
        n_frames=len(dataset),
    )


def _fmt(value: float | None) -> str:
    return "  n/a" if value is None else f"{value:5.3f}"


def format_report(report: EvalReport) -> str:
    """Render an `EvalReport` as a plain-text table (the hades-eval stdout)."""
    o = report.overall
    lines = [
        f"frames evaluated: {report.n_frames}",
        f"overall  precision={_fmt(o.precision)}  recall={_fmt(o.recall)}  "
        f"(TP={o.true_positives} FP={o.false_positives} FN={o.false_negatives})",
        "",
        "recall by size (px²):",
    ]
    for label, s in report.by_size.items():
        lines.append(_stratum_row(label, s))
    lines.append("")
    lines.append("recall by subclass (acceptance floor):")
    if report.by_subclass:
        for label, s in report.by_subclass.items():
            lines.append(_stratum_row(label, s))
    else:
        lines.append("  (no subclass-labeled ground truth in this set)")
    return "\n".join(lines)


def _stratum_row(label: str, s: FrameScore) -> str:
    return (
        f"  {label:>14}  recall={_fmt(s.recall)}  "
        f"(TP={s.true_positives} FN={s.false_negatives})"
    )
