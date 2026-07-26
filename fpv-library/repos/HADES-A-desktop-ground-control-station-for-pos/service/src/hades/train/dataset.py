"""Normalize SARD + HERIDAL (+ VisDrone pretrain) to a single `person` class (Task 2.5.1).

All three source sets are **Roboflow YOLO exports** (verified): one `.txt` per image with
lines `cls cx cy w h`, normalized to `[0, 1]`, plus a `data.yaml`. So one parser suffices;
the real work is the **per-source class merge** to a single `person` and the guards the
phase-end adversarial review (ultraplan) flagged:

- **Class-index collisions.** Each source uses index 0 for a different thing — SARD `human`,
  VisDrone `pedestrian` — and VisDrone is multi-class (`car`, `van`, …). A naive "rewrite
  everything to 0" would silently merge vehicles into `person`. So the merge is an EXPLICIT
  per-source `{source_index → "person" | DROP}` map, and **any unmapped index raises** — no
  silent passthrough.
- **Tiny-survivor boxes.** A survivor is a handful of pixels; a box that rounds to zero
  width/height is degenerate and is rejected at emit time (mirrors the positive-area
  invariant `Detection`/`GroundTruth` already enforce), not silently written.
- **Content-hash leakage.** Roboflow rehashes filenames (`gss1006_jpg.rf.<hash>.jpg`), so a
  name-based train/test dedup is useless. The held-out manifest is keyed on a hash of the
  **decoded pixels** instead (see `image_content_hash`), so an augmented/renamed copy of a
  test frame can't sneak into train undetected.

Pure logic — numpy is only needed by `image_content_hash`, imported lazily — so the merge
rules unit-test on CI without the ML stack. The file-walking / `dataset.yaml` generation /
`validate()` that touch real staged data live alongside and reuse these primitives.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Sentinel: a source class that must be dropped (e.g. a VisDrone vehicle), not emitted.
DROP = "__drop__"

#: Every emitted label is this single class index — honors `PERSON_CLASS_INDEX = 0` in
#: `hades.detect.postprocess`, which the fine-tuned single-class export must also satisfy.
PERSON_INDEX = 0


@dataclass(frozen=True)
class LabelLine:
    """One YOLO box: class index + normalized center/size in `[0, 1]`."""

    cls_index: int
    cx: float
    cy: float
    w: float
    h: float


@dataclass(frozen=True)
class ClassMap:
    """Per-source `{source_index → "person" | DROP}`. Unmapped indices are an error.

    Explicit by construction so a new/unexpected source class fails loudly rather than
    silently becoming `person` (the vehicle-poisoning trap).
    """

    mapping: dict[int, str]

    def resolve(self, cls_index: int) -> str:
        if cls_index not in self.mapping:
            raise ValueError(
                f"unmapped source class index {cls_index}; "
                f"known: {sorted(self.mapping)} — refusing silent passthrough"
            )
        return self.mapping[cls_index]


def parse_yolo_label(text: str) -> list[LabelLine]:
    """Parse a Roboflow-YOLO `.txt`. Empty text → `[]` (a valid negative/background frame)."""
    lines: list[LabelLine] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        parts = s.split()
        if len(parts) != 5:
            raise ValueError(f"malformed YOLO label line (need 5 fields): {raw!r}")
        cls_index = int(parts[0])
        cx, cy, w, h = (float(p) for p in parts[1:])
        lines.append(LabelLine(cls_index, cx, cy, w, h))
    return lines


def normalize_label_file(lines: list[LabelLine], class_map: ClassMap) -> list[LabelLine]:
    """Apply the class map: keep mapped persons (re-indexed to `PERSON_INDEX`), drop DROP.

    Raises via `ClassMap.resolve` on any unmapped source class — the collision guard.
    """
    out: list[LabelLine] = []
    for ln in lines:
        target = class_map.resolve(ln.cls_index)
        if target == DROP:
            continue
        out.append(LabelLine(PERSON_INDEX, ln.cx, ln.cy, ln.w, ln.h))
    return out


def yolo_line(line: LabelLine) -> str:
    """Render one normalized label back to a YOLO `.txt` line, guarding degenerate boxes.

    Rejects a zero/negative-area box (a survivor rounded to nothing) and out-of-range
    coordinates rather than emitting a label the trainer would silently swallow or that
    would later crash the eval value objects.
    """
    if not (line.w > 0.0 and line.h > 0.0):
        raise ValueError(f"box has non-positive area (w={line.w}, h={line.h})")
    for name, v in (("cx", line.cx), ("cy", line.cy), ("w", line.w), ("h", line.h)):
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"{name}={v} outside normalized [0, 1]")
    return f"{line.cls_index} {line.cx:.6f} {line.cy:.6f} {line.w:.6f} {line.h:.6f}"


def image_content_hash(image) -> str:
    """SHA-256 of an image's **decoded pixels** — the leakage-guard key.

    Filename-based dedup is useless against Roboflow's `.rf.<hash>` renames and augmented
    copies; hashing the pixel buffer detects the same frame regardless of its name. Takes an
    HxWx3 uint8 array (numpy lazy-imported so the module loads without the ML stack).
    """
    import hashlib

    import numpy as np

    arr = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
    return hashlib.sha256(arr.tobytes()).hexdigest()


def assert_no_leakage(train_hashes: set[str], holdout_hashes: set[str]) -> None:
    """Raise if any held-out (test) image content-hash appears in the training set.

    The single guard that, if it fails open, invalidates the whole phase: a test image in
    train inflates the reported recall silently (the number goes *up*, looking like success).
    """
    overlap = train_hashes & holdout_hashes
    if overlap:
        raise ValueError(
            f"test/train leakage: {len(overlap)} held-out image(s) found in the training "
            f"set (by pixel content-hash) — reported recall would be inflated"
        )


def build_dataset_yaml(
    path,
    *,
    train: str,
    val: str,
    test: str,
    out_name: str = "dataset.yaml",
):
    """Write an Ultralytics `dataset.yaml` pinned to a single `person` class.

    `path` is the ABSOLUTE dataset root; Ultralytics resolves `train`/`val`/`test` relative
    to it (not CWD), so an absolute root is the fix for the silent-wrong-data footgun. The
    `nc: 1`/`names: ['person']` lines are the `PERSON_CLASS_INDEX = 0` decode contract.
    """
    from pathlib import Path

    root = Path(path).resolve()
    text = (
        f"path: {root}\n"
        f"train: {train}\n"
        f"val: {val}\n"
        f"test: {test}\n"
        f"nc: 1\n"
        f"names: ['person']\n"
    )
    out = root / out_name
    out.write_text(text)
    return out
