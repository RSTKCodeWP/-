"""Shared YOLO output decode + NMS — the SINGLE place raw output becomes `Detection`s.

The exported model has `nms=False` (bench/export_coreml.py), so the raw output is
`(1, 4 + n_classes, n_anchors)` — rows 0–3 are box `(cx, cy, w, h)` in *letterbox*
pixels, rows `4..` are per-class scores (no objectness in YOLO11). v1 is single-class:
only **person == COCO class 0 == row 4** is kept.

Both the Core ML and ONNX backends import THIS module — the decode is never
re-implemented per backend (mirrors the plan's single-source-of-truth rule for the
ray→ground math). Boxes are mapped back to original-frame pixels via the `Letterbox`
metadata before they leave, so a coordinate never escapes in letterboxed space
(DESIGN.md §3.2).
"""

from __future__ import annotations

import numpy as np

from .detector import Detection
from .preprocess import Letterbox

#: Class index of `person` in the model's output rows (row `4 + this`). It is 0 for the
#: stock COCO export. NOTE (P2.5): the fine-tuned single-`person`-class model MUST also
#: place person at index 0, or this reads the wrong score row — assert it at export time.
PERSON_CLASS_INDEX = 0


def decode_yolo(
    raw: np.ndarray,
    lb: Letterbox,
    *,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.7,
) -> list[Detection]:
    """Decode raw YOLO output `(1, 4+C, A)` to person `Detection`s in original pixels.

    Steps: select the person-class row, threshold, convert `(cx,cy,w,h)`→`xyxy` in
    letterbox space, un-letterbox to original pixels, then NMS. Returns `[]` when no
    anchor clears the threshold (an empty scene is normal, not an error).

    Orientation guard (review C1): the channel axis (`4+C`, ~84) is far smaller than the
    anchor axis (`A`, ~8400). A transposed export `(1, A, 4+C)` would pass a naive
    `shape[0]==1` check and then `pred[4]` would silently read anchor #4's vector instead
    of the person-score row — yielding an EMPTY map over a scene full of survivors. We
    refuse the wrong orientation loudly rather than index into it.
    """
    if raw.ndim != 3 or raw.shape[0] != 1:
        raise ValueError(f"expected raw shape (1, 4+C, A), got {raw.shape}")
    channels, anchors = raw.shape[1], raw.shape[2]
    if channels <= 4 + PERSON_CLASS_INDEX or channels >= anchors:
        # The detection head is channel-major: a small box+class axis, a large anchor
        # axis. `channels >= anchors` means a transposed/garbage layout — reject it.
        raise ValueError(
            f"raw must be channel-major (1, 4+C, A) with 4+C < A; got "
            f"(1, {channels}, {anchors}) — looks transposed or malformed"
        )

    pred = raw[0]  # (4+C, A)
    person_scores = pred[4 + PERSON_CLASS_INDEX]  # (A,)
    keep = person_scores > conf_threshold  # strict > matches Ultralytics' reference
    if not keep.any():
        return []

    cx, cy, w, h = pred[0, keep], pred[1, keep], pred[2, keep], pred[3, keep]
    confs = person_scores[keep]

    # (cx,cy,w,h) -> (x_min,y_min,x_max,y_max) in letterbox pixels.
    half_w, half_h = w / 2.0, h / 2.0
    lx_min, ly_min = cx - half_w, cy - half_h
    lx_max, ly_max = cx + half_w, cy + half_h

    dets: list[Detection] = []
    for i in range(confs.shape[0]):
        x_min, y_min = lb.unletterbox_xy(float(lx_min[i]), float(ly_min[i]))
        x_max, y_max = lb.unletterbox_xy(float(lx_max[i]), float(ly_max[i]))
        # A box fully on the pad can clamp to a zero-area sliver; skip degenerate boxes.
        if x_max <= x_min or y_max <= y_min:
            continue
        dets.append(
            Detection(box_xyxy=(x_min, y_min, x_max, y_max), conf=float(confs[i]), cls="person")
        )

    return nms_xyxy(dets, iou_threshold=iou_threshold)


def nms_xyxy(detections: list[Detection], *, iou_threshold: float = 0.7) -> list[Detection]:
    """Greedy non-max suppression over `Detection`s by IoU; highest-conf wins.

    Single-class (person), so suppression is global — no per-class grouping needed.
    """
    if len(detections) <= 1:
        return list(detections)

    boxes = np.array([d.box_xyxy for d in detections], dtype=np.float64)
    scores = np.array([d.conf for d in detections], dtype=np.float64)
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]  # high conf first

    kept: list[int] = []
    while order.size > 0:
        i = int(order[0])
        kept.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        # IoU of box i against the remaining boxes.
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        union = areas[i] + areas[rest] - inter
        # Guard union==0 (two zero-area boxes): 0/0 = nan and `nan <= thr` is False, which
        # would silently drop a disjoint box (review I3). No overlap when union is 0.
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        order = rest[iou <= iou_threshold]

    return [detections[i] for i in kept]
