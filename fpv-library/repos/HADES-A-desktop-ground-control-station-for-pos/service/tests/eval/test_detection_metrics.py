"""Tests for the detection metrics harness (Task 2.5).

The acceptance-gate metric (design lines 90–100): match predictions to ground truth by
**center-distance** (not IoU@0.5 — tiny-object IoU is dominated by 1–2px jitter), then
report precision/recall, **size-stratified recall**, and **per-subclass recall** over the
hard subclasses (in-water/head-only, rooftop-prone, debris-occluded, in-vehicle).

Every number is asserted against a hand-computed fixture so a wrong matcher can't pass.
"""

import pytest

from hades.detect.detector import Detection
from hades.eval.detection_metrics import (
    GroundTruth,
    Match,
    match_by_center_distance,
    recall_by_size,
    recall_by_subclass,
    score_frame,
)


def gt(cx, cy, *, w=10.0, h=20.0, subclass=None):
    """A GT box centered at (cx, cy). Center-distance matching only needs the center,
    but we carry w/h so size bucketing has something to bucket on."""
    return GroundTruth(box_xyxy=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), subclass=subclass)


def pred(cx, cy, conf=0.9, *, w=10.0, h=20.0):
    return Detection(box_xyxy=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), conf=conf)


# ---- ground-truth validation ------------------------------------------------------


def test_ground_truth_rejects_inverted_box():
    # Codex P2: an inverted/degenerate label silently yields a bogus center+area and can
    # vanish from size buckets. Reject malformed GT at construction.
    with pytest.raises(ValueError):
        GroundTruth(box_xyxy=(30.0, 0.0, 10.0, 20.0))  # x_max < x_min


def test_ground_truth_rejects_zero_area_box():
    with pytest.raises(ValueError):
        GroundTruth(box_xyxy=(10.0, 0.0, 10.0, 20.0))  # zero width


def test_ground_truth_center_and_area_correct():
    g = GroundTruth(box_xyxy=(10.0, 20.0, 30.0, 60.0))
    assert g.center == (20.0, 40.0)
    assert g.area == pytest.approx(20.0 * 40.0)


def test_matched_gt_set_is_max_cardinality():
    # Codex P1 invariant: the SET of matched GTs (what stratified recall keys on) is
    # determined by max-cardinality, independent of distance-minimization. Here all three
    # GTs are simultaneously matchable, so all three must appear — no GT silently dropped.
    gts = [gt(0, 0), gt(10, 0), gt(20, 0)]
    preds = [pred(10, 0), pred(20, 0), pred(0, 0)]  # rotated; a naive pass mis-assigns
    matches = match_by_center_distance(preds, gts, max_distance=50.0)
    assert {m.gt_index for m in matches} == {0, 1, 2}  # full set -> recall not under-counted


# ---- center-distance matching -----------------------------------------------------


def test_match_pairs_nearest_within_threshold():
    gts = [gt(100, 100), gt(200, 200)]
    preds = [pred(102, 101), pred(205, 198)]
    matches = match_by_center_distance(preds, gts, max_distance=10.0)
    assert len(matches) == 2
    assert all(isinstance(m, Match) for m in matches)
    # nearest pairing: pred0->gt0, pred1->gt1
    assert {(m.pred_index, m.gt_index) for m in matches} == {(0, 0), (1, 1)}


def test_match_rejects_pairs_beyond_threshold():
    gts = [gt(100, 100)]
    preds = [pred(130, 100)]  # 30px away, threshold 10 -> no match
    assert match_by_center_distance(preds, gts, max_distance=10.0) == []


def test_match_contested_gt_goes_to_nearer_pred():
    # Two preds near one GT: cardinality is 1 either way; the CLOSER pred is the TP and
    # the farther one is the FP (min-total-distance tie-break).
    gts = [gt(100, 100)]
    preds = [pred(108, 100), pred(101, 100)]  # second is closer
    matches = match_by_center_distance(preds, gts, max_distance=10.0)
    assert len(matches) == 1
    assert matches[0].pred_index == 1  # the closer pred won the GT


def test_match_each_gt_used_once():
    gts = [gt(100, 100), gt(105, 100)]
    preds = [pred(100, 100), pred(104, 100)]
    matches = match_by_center_distance(preds, gts, max_distance=10.0)
    assert len(matches) == 2
    assert {m.gt_index for m in matches} == {0, 1}  # no GT double-counted


def test_match_is_maximum_cardinality_not_greedy():
    # I2 (review): greedy-nearest grabs pred@6->gt@5 (d=1), stranding pred@4 (whose only
    # in-threshold GT was gt@5) and orphaning gt@0 -> a manufactured FP+FN. Optimal
    # assignment matches BOTH (gt@0<-pred@4, gt@5<-pred@6). The acceptance recall must
    # not under-report in clustered survivor scenes (the hard SAR case).
    gts = [gt(0, 0), gt(5, 0)]
    preds = [pred(4, 0), pred(6, 0)]
    matches = match_by_center_distance(preds, gts, max_distance=5.0)
    assert len(matches) == 2  # greedy would give 1
    assert {m.gt_index for m in matches} == {0, 1}
    assert {m.pred_index for m in matches} == {0, 1}


def test_match_optimal_respects_threshold():
    # Optimal assignment must still never pair across more than max_distance.
    gts = [gt(0, 0), gt(100, 0)]
    preds = [pred(3, 0), pred(50, 0)]  # pred@50 is >5 from either GT
    matches = match_by_center_distance(preds, gts, max_distance=5.0)
    assert len(matches) == 1
    assert matches[0].gt_index == 0 and matches[0].pred_index == 0


def test_match_minimizes_total_distance_via_swap():
    # Both pairings have cardinality 2, but the matching must pick min TOTAL distance:
    # GTs@{0,10}, preds@{1,9} -> 0<-1, 10<-9 (cost 2), NOT 0<-9,10<-1 (cost 18).
    gts = [gt(0, 0), gt(10, 0)]
    preds = [pred(9, 0), pred(1, 0)]  # ordered so a naive index pass would mis-pair
    matches = match_by_center_distance(preds, gts, max_distance=20.0)
    assert len(matches) == 2
    by_gt = {m.gt_index: m.pred_index for m in matches}
    assert by_gt[0] == 1  # GT@0 <- pred@1
    assert by_gt[1] == 0  # GT@10 <- pred@9
    assert sum(m.distance for m in matches) == pytest.approx(2.0)


def test_match_three_clustered_survivors_full_recall():
    # Three GTs and three preds interleaved within threshold: a correct max-cardinality
    # min-cost matching recovers all three (dense-cluster SAR case).
    gts = [gt(0, 0), gt(10, 0), gt(20, 0)]
    preds = [pred(2, 0), pred(12, 0), pred(18, 0)]
    matches = match_by_center_distance(preds, gts, max_distance=8.0)
    assert len(matches) == 3
    assert {m.gt_index for m in matches} == {0, 1, 2}


# ---- precision / recall -----------------------------------------------------------


def test_score_frame_precision_recall():
    # 2 GT, 3 preds: 2 true positives, 1 false positive, 0 false negatives.
    gts = [gt(100, 100), gt(200, 200)]
    preds = [pred(100, 100), pred(200, 200), pred(400, 400)]
    s = score_frame(preds, gts, max_distance=10.0)
    assert s.true_positives == 2
    assert s.false_positives == 1
    assert s.false_negatives == 0
    assert s.precision == pytest.approx(2 / 3)
    assert s.recall == pytest.approx(1.0)


def test_score_frame_counts_false_negative():
    gts = [gt(100, 100), gt(300, 300)]
    preds = [pred(100, 100)]  # second GT missed
    s = score_frame(preds, gts, max_distance=10.0)
    assert s.true_positives == 1
    assert s.false_negatives == 1
    assert s.recall == pytest.approx(0.5)


def test_score_frame_empty_predictions_is_zero_recall_not_crash():
    s = score_frame([], [gt(1, 1)], max_distance=10.0)
    assert s.recall == 0.0
    assert s.false_negatives == 1


def test_score_frame_no_gt_precision_is_defined():
    # No GT and a spurious pred -> precision 0, recall is undefined -> reported as None.
    s = score_frame([pred(1, 1)], [], max_distance=10.0)
    assert s.precision == 0.0
    assert s.recall is None


# ---- size-stratified recall -------------------------------------------------------


def test_recall_by_size_buckets_by_gt_area():
    # tiny GT (area 100) matched; large GT (area 40000) missed.
    tiny = gt(50, 50, w=10, h=10)  # area 100
    large = gt(300, 300, w=200, h=200)  # area 40000
    preds = [pred(50, 50, w=10, h=10)]  # matches tiny only
    by_size = recall_by_size(
        preds, [tiny, large], max_distance=10.0, bounds=(0, 1024, float("inf"))
    )
    # bucket "0-1024" (tiny) -> recall 1.0 ; bucket "1024-inf" (large) -> recall 0.0
    assert by_size["0-1024"].recall == pytest.approx(1.0)
    assert by_size["1024-inf"].recall == pytest.approx(0.0)


# ---- per-subclass recall (the acceptance gate) ------------------------------------


def test_recall_by_subclass_reports_per_label_floor():
    gts = [
        gt(10, 10, subclass="in-water"),
        gt(50, 50, subclass="in-water"),
        gt(90, 90, subclass="rooftop"),
    ]
    preds = [pred(10, 10), pred(90, 90)]  # one in-water hit, one in-water miss, rooftop hit
    by_sub = recall_by_subclass(preds, gts, max_distance=10.0)
    assert by_sub["in-water"].recall == pytest.approx(0.5)
    assert by_sub["rooftop"].recall == pytest.approx(1.0)


def test_recall_by_subclass_ignores_unlabeled_gt():
    gts = [gt(10, 10, subclass="in-water"), gt(50, 50, subclass=None)]
    preds = [pred(10, 10)]
    by_sub = recall_by_subclass(preds, gts, max_distance=10.0)
    assert set(by_sub) == {"in-water"}  # the None-subclass GT is not a subclass bucket
    assert by_sub["in-water"].recall == pytest.approx(1.0)
