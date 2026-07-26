"""Tests for cross-frame metric aggregation + report formatting + the hades-eval CLI (Task 2.5).

`evaluate()` runs a detector over a labeled dataset and aggregates per-frame scores into
one report (overall P/R + size- and subclass-stratified recall). The detector is injected,
so a `StubDetector`-style fake makes the aggregation deterministic and offline.
"""

import numpy as np
import pytest

from hades.cli.eval import main as eval_main
from hades.detect.detector import Detection, Detector
from hades.eval.detection_metrics import GroundTruth
from hades.eval.report import LabeledFrame, evaluate, format_report


class _FakeDetector(Detector):
    """Returns a preset list of Detections per call, in sequence (one per frame)."""

    def __init__(self, per_frame: list[list[Detection]]):
        self._per_frame = per_frame
        self._i = 0

    def detect(self, frame: np.ndarray) -> list[Detection]:
        out = self._per_frame[self._i]
        self._i += 1
        return out


def _box(cx, cy, w=10, h=20):
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def _frame():
    return np.zeros((48, 64, 3), dtype=np.uint8)


def test_evaluate_aggregates_precision_recall_across_frames():
    dataset = [
        LabeledFrame(image=_frame(), ground_truths=[GroundTruth(box_xyxy=_box(100, 100))]),
        LabeledFrame(image=_frame(), ground_truths=[GroundTruth(box_xyxy=_box(200, 200))]),
    ]
    detector = _FakeDetector(
        [
            [Detection(box_xyxy=_box(100, 100), conf=0.9)],  # frame 0: hit
            [],  # frame 1: miss
        ]
    )
    report = evaluate(detector, dataset, max_distance=10.0)
    assert report.overall.true_positives == 1
    assert report.overall.false_negatives == 1
    assert report.overall.recall == pytest.approx(0.5)
    assert report.overall.precision == pytest.approx(1.0)


def test_evaluate_conf_threshold_filters_low_conf_predictions():
    # An honest operating-point sweep needs evaluate() to apply the threshold itself, so
    # the SAME detector output can be scored at many conf levels. A 0.4-conf prediction is
    # a TP at thr=0.25 but dropped (FN) at thr=0.5.
    dataset = [
        LabeledFrame(image=_frame(), ground_truths=[GroundTruth(box_xyxy=_box(100, 100))]),
    ]
    detector = _FakeDetector([[Detection(box_xyxy=_box(100, 100), conf=0.4)]])
    lenient = evaluate(detector, dataset, max_distance=10.0, conf_threshold=0.25)
    assert lenient.overall.true_positives == 1

    detector2 = _FakeDetector([[Detection(box_xyxy=_box(100, 100), conf=0.4)]])
    strict = evaluate(detector2, dataset, max_distance=10.0, conf_threshold=0.5)
    assert strict.overall.true_positives == 0
    assert strict.overall.false_negatives == 1


def test_evaluate_default_conf_threshold_keeps_all_predictions():
    # No threshold given -> behaves as before (scores whatever the detector emits).
    dataset = [
        LabeledFrame(image=_frame(), ground_truths=[GroundTruth(box_xyxy=_box(100, 100))]),
    ]
    detector = _FakeDetector([[Detection(box_xyxy=_box(100, 100), conf=0.3)]])
    report = evaluate(detector, dataset, max_distance=10.0)
    assert report.overall.true_positives == 1


def test_evaluate_reports_per_subclass_recall():
    dataset = [
        LabeledFrame(
            image=_frame(),
            ground_truths=[
                GroundTruth(box_xyxy=_box(10, 10), subclass="in-water"),
                GroundTruth(box_xyxy=_box(50, 50), subclass="rooftop"),
            ],
        )
    ]
    detector = _FakeDetector([[Detection(box_xyxy=_box(10, 10), conf=0.9)]])  # in-water hit only
    report = evaluate(detector, dataset, max_distance=10.0)
    assert report.by_subclass["in-water"].recall == pytest.approx(1.0)
    assert report.by_subclass["rooftop"].recall == pytest.approx(0.0)


def test_format_report_is_human_readable_and_mentions_floors():
    dataset = [
        LabeledFrame(
            image=_frame(),
            ground_truths=[GroundTruth(box_xyxy=_box(10, 10), subclass="in-water")],
        )
    ]
    detector = _FakeDetector([[Detection(box_xyxy=_box(10, 10), conf=0.9)]])
    report = evaluate(detector, dataset, max_distance=10.0)
    text = format_report(report)
    assert "precision" in text.lower()
    assert "recall" in text.lower()
    assert "in-water" in text


def test_eval_cli_reports_missing_dataset_without_crashing(capsys):
    # No dataset on disk yet (real data arrives ~2026-07-01). The CLI must exit cleanly
    # with an honest "no dataset" message, never a fabricated metric or a traceback.
    rc = eval_main(["--set", "curated", "--data", "/nonexistent/path"])
    assert rc != 0
    err = capsys.readouterr().err.lower()
    assert "dataset" in err or "not found" in err


def test_eval_cli_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        eval_main(["--help"])
    assert exc.value.code == 0 or exc.value.code is None
