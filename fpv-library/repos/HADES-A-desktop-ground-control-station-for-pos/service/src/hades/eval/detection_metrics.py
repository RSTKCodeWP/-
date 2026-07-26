"""Detection metrics — center-distance matching, P/R, size- and subclass-stratified recall.

The acceptance-gate metric (design lines 90–100):

- **Match by center-distance**, not IoU@0.5: a survivor box is a handful of pixels, so
  IoU is dominated by 1–2px jitter and would reject correct detections. A prediction
  matches a ground-truth box when their centers are within `max_distance` pixels.
- **Precision / recall** from the one-to-one matching (greedy by ascending distance, each
  GT consumed once). Recall is `None` when there is no GT (undefined, not 0).
- **Size-stratified recall** (`recall_by_size`): bucket GT by box area to expose the
  small-target recall cliff (the design's core difficulty).
- **Per-subclass recall** (`recall_by_subclass`): the real acceptance floor, keyed off the
  hard-subclass labels (in-water/head-only, rooftop-prone, debris-occluded, in-vehicle).

Pure geometry over `Detection` (predictions) and `GroundTruth` (labels); no model here, so
it runs deterministically on CI. `box_xyxy` is original-frame pixels (DESIGN.md §3.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class GroundTruth:
    """One labeled survivor box. `subclass` is the hard-subclass tag (or None)."""

    box_xyxy: tuple[float, float, float, float]
    subclass: str | None = None

    def __post_init__(self) -> None:
        x_min, y_min, x_max, y_max = self.box_xyxy
        # A malformed/inverted label silently yields a bogus center+area and can vanish
        # from size buckets, corrupting stratified metrics (Codex P2). Reject it on load.
        if x_max <= x_min or y_max <= y_min:
            raise ValueError(
                f"GroundTruth box_xyxy must be ordered with positive area: {self.box_xyxy}"
            )

    @property
    def center(self) -> tuple[float, float]:
        x_min, y_min, x_max, y_max = self.box_xyxy
        return (x_min + x_max) / 2.0, (y_min + y_max) / 2.0

    @property
    def area(self) -> float:
        x_min, y_min, x_max, y_max = self.box_xyxy
        return (x_max - x_min) * (y_max - y_min)


@dataclass(frozen=True)
class Match:
    """A prediction↔ground-truth pairing and the center distance that joined them."""

    pred_index: int
    gt_index: int
    distance: float


@dataclass(frozen=True)
class FrameScore:
    """TP/FP/FN counts and derived precision/recall for a matched frame (or set)."""

    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float | None:
        denom = self.true_positives + self.false_positives
        return None if denom == 0 else self.true_positives / denom

    @property
    def recall(self) -> float | None:
        denom = self.true_positives + self.false_negatives
        return None if denom == 0 else self.true_positives / denom


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x_min, y_min, x_max, y_max = box
    return (x_min + x_max) / 2.0, (y_min + y_max) / 2.0


def match_by_center_distance(
    predictions: Sequence,
    ground_truths: Sequence[GroundTruth],
    *,
    max_distance: float,
) -> list[Match]:
    """Match predictions to GT by center distance — **maximum cardinality, min total dist**.

    A prediction may pair with any GT whose center is within `max_distance`. The result
    is a maximum-cardinality bipartite matching (so TP — and hence precision/recall — is
    never under-reported): greedy-nearest would strand a matchable pair in clustered
    survivor scenes (review I2) — preds@{4,6}, GTs@{0,5}, thr=5 — greedy takes 6↔5 and
    orphans both 4 and 0 (TP=1); the optimal matches both (TP=2).

    Among all maximum matchings it then minimizes total pair distance via distance-
    reducing swaps, so a contested GT goes to the *nearer* prediction (the real
    detection) and the farther one is the FP. Result is deterministic.
    """
    # adj[pi] = GT indices within threshold, ordered nearest-first.
    adj: list[list[int]] = []
    dist_of: dict[tuple[int, int], float] = {}
    for pi, p in enumerate(predictions):
        px, py = _center(p.box_xyxy)
        near: list[tuple[float, int]] = []
        for gi, g in enumerate(ground_truths):
            gx, gy = g.center
            dist = ((px - gx) ** 2 + (py - gy) ** 2) ** 0.5
            if dist <= max_distance:
                near.append((dist, gi))
                dist_of[(pi, gi)] = dist
        near.sort(key=lambda c: c[0])
        adj.append([gi for _, gi in near])

    gt_to_pred: dict[int, int] = {}  # gt index -> matched pred index

    def _augment(pi: int, seen: set[int]) -> bool:
        for gi in adj[pi]:
            if gi in seen:
                continue
            seen.add(gi)
            if gi not in gt_to_pred or _augment(gt_to_pred[gi], seen):
                gt_to_pred[gi] = pi
                return True
        return False

    for pi in range(len(predictions)):
        _augment(pi, set())

    _minimize_total_distance(gt_to_pred, adj, dist_of)

    matches = [
        Match(pred_index=pi, gt_index=gi, distance=dist_of[(pi, gi)])
        for gi, pi in gt_to_pred.items()
    ]
    matches.sort(key=lambda m: m.pred_index)
    return matches


def _minimize_total_distance(
    gt_to_pred: dict[int, int],
    adj: list[list[int]],
    dist_of: dict[tuple[int, int], float],
) -> None:
    """Cardinality-preserving local search that reduces total matched distance.

    Moves repeated to a fixed point, each keeping every matched pred matched (so the
    matched-GT SET — what precision/recall and stratified recall key on — is unchanged):
    (1) a matched pred hops to a closer free GT; (move 3) an unmatched pred displaces a
    farther holder of a contested GT; (2) two matched preds swap GTs when that lowers
    their summed distance. This is a LOCAL search: it does not guarantee the global
    min-distance assignment (a rare 3-cycle can be left distance-suboptimal, Codex P1),
    but that only affects which pred is labeled the TP and its diagnostic `Match.distance`
    — NOT any reported metric, because the matched-GT set is fixed by the upstream
    max-cardinality phase. Frame sizes are tiny (a handful of survivors), so a min-cost
    solver would be over-engineering for a field that no metric reads.
    """
    pred_to_gt = {pi: gi for gi, pi in gt_to_pred.items()}
    n_preds = len(adj)
    improved = True
    while improved:
        improved = False
        # Move 1: a matched pred hops to a nearer free GT.
        for pi, gi in list(pred_to_gt.items()):
            for cand in adj[pi]:  # nearest-first
                if cand == gi:
                    break  # already on its nearest reachable GT
                if cand not in gt_to_pred and dist_of[(pi, cand)] < dist_of[(pi, gi)]:
                    del gt_to_pred[gi]
                    gt_to_pred[cand] = pi
                    pred_to_gt[pi] = cand
                    improved = True
                    break
        # Move 3: an UNMATCHED pred displaces the holder of a shared GT when it is closer
        # (contested single GT — cardinality is unchanged since the displaced pred frees
        # up, and we only do it when no closer free GT exists for the incoming pred).
        for pi in range(n_preds):
            if pi in pred_to_gt:
                continue
            for cand in adj[pi]:  # nearest-first reachable GT
                holder = gt_to_pred.get(cand)
                if holder is not None and dist_of[(pi, cand)] < dist_of[(holder, cand)]:
                    gt_to_pred[cand] = pi
                    pred_to_gt[pi] = cand
                    del pred_to_gt[holder]
                    improved = True
                    break
        # Move 2: two matched preds swap GTs if the summed distance drops.
        preds = list(pred_to_gt)
        for a_i in range(len(preds)):
            for b_i in range(a_i + 1, len(preds)):
                pa, pb = preds[a_i], preds[b_i]
                ga, gb = pred_to_gt[pa], pred_to_gt[pb]
                if (pa, gb) not in dist_of or (pb, ga) not in dist_of:
                    continue  # a swap would exceed one pair's threshold
                before = dist_of[(pa, ga)] + dist_of[(pb, gb)]
                after = dist_of[(pa, gb)] + dist_of[(pb, ga)]
                if after < before:
                    pred_to_gt[pa], pred_to_gt[pb] = gb, ga
                    gt_to_pred[gb], gt_to_pred[ga] = pa, pb
                    improved = True


def score_frame(
    predictions: Sequence,
    ground_truths: Sequence[GroundTruth],
    *,
    max_distance: float,
) -> FrameScore:
    """Count TP/FP/FN from a center-distance matching."""
    matches = match_by_center_distance(predictions, ground_truths, max_distance=max_distance)
    tp = len(matches)
    fp = len(predictions) - tp
    fn = len(ground_truths) - tp
    return FrameScore(true_positives=tp, false_positives=fp, false_negatives=fn)


def recall_by_size(
    predictions: Sequence,
    ground_truths: Sequence[GroundTruth],
    *,
    max_distance: float,
    bounds: Sequence[float],
) -> dict[str, FrameScore]:
    """Recall stratified by GT box area into the buckets defined by `bounds`.

    `bounds` is ascending edges, e.g. `(0, 1024, inf)` -> buckets "0-1024", "1024-inf".
    A GT lands in bucket `i` when `bounds[i] <= area < bounds[i+1]`. Each bucket's score
    has FP=0 (false positives aren't attributable to a GT size); only recall is meaningful.
    """
    matches = match_by_center_distance(predictions, ground_truths, max_distance=max_distance)
    matched_gt = {m.gt_index for m in matches}

    edges = list(bounds)
    labels = [_bucket_label(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
    tp = {lab: 0 for lab in labels}
    fn = {lab: 0 for lab in labels}

    for gi, g in enumerate(ground_truths):
        lab = _bucket_for(g.area, edges, labels)
        if lab is None:
            continue
        if gi in matched_gt:
            tp[lab] += 1
        else:
            fn[lab] += 1

    return {
        lab: FrameScore(true_positives=tp[lab], false_positives=0, false_negatives=fn[lab])
        for lab in labels
    }


def recall_by_subclass(
    predictions: Sequence,
    ground_truths: Sequence[GroundTruth],
    *,
    max_distance: float,
) -> dict[str, FrameScore]:
    """Recall per hard-subclass label — the acceptance floor (design line 100).

    GT with `subclass=None` is excluded (it's not one of the named hard subclasses).
    FP=0 per bucket: a false positive isn't attributable to a GT subclass.
    """
    matches = match_by_center_distance(predictions, ground_truths, max_distance=max_distance)
    matched_gt = {m.gt_index for m in matches}

    tp: dict[str, int] = {}
    fn: dict[str, int] = {}
    for gi, g in enumerate(ground_truths):
        if g.subclass is None:
            continue
        tp.setdefault(g.subclass, 0)
        fn.setdefault(g.subclass, 0)
        if gi in matched_gt:
            tp[g.subclass] += 1
        else:
            fn[g.subclass] += 1

    return {
        sub: FrameScore(true_positives=tp[sub], false_positives=0, false_negatives=fn[sub])
        for sub in tp
    }


def _bucket_label(lo: float, hi: float) -> str:
    hi_str = "inf" if hi == float("inf") else f"{int(hi)}"
    return f"{int(lo)}-{hi_str}"


def _bucket_for(area: float, edges: list[float], labels: list[str]) -> str | None:
    for i in range(len(edges) - 1):
        if edges[i] <= area < edges[i + 1]:
            return labels[i]
    return None
