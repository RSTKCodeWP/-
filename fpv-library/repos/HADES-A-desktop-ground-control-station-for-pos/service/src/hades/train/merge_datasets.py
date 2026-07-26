"""Merge the three staged Roboflow YOLO datasets into one single-`person` tree (Task 2.5.1).

Runs ON the cluster against the real staged labels (the part that can't be unit-tested
without the data — its primitives ARE tested in `dataset.py`). For each source it:

1. Reads the source `data.yaml` to learn that source's class names.
2. Builds a per-source `{index → "person" | DROP}` map: SARD/HERIDAL persons → person;
   VisDrone via `map_visdrone_class` (pedestrian+people → person, vehicles dropped); any
   class it can't classify as person/vehicle/ignore RAISES (no silent passthrough).
3. Rewrites every label file into the merged tree, re-indexed to class 0, dropping DROP
   boxes and degenerate (zero-area) boxes.
4. Re-splits HERIDAL by SCENE (`scene_split.py`) and **asserts the merged train is disjoint
   from the held-out test** two ways: (a) `assert_no_scene_leakage` — no HERIDAL flight
   location (scene code) spans train/test, which also covers same-scene augmented copies; and
   (b) `assert_no_leakage` — an exact decoded-pixel SHA-256 backstop for byte-identical dupes.
5. Emits one `dataset.yaml` (`nc:1 names:['person']`, absolute `path:`), asserts no split is
   empty, and writes a human-auditable summary.

This is a script, not a library entry — invoked as `python -m hades.train.merge_datasets`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .dataset import (
    DROP,
    ClassMap,
    assert_no_leakage,
    build_dataset_yaml,
    image_content_hash,
    normalize_label_file,
    parse_yolo_label,
    yolo_line,
)
from .scene_split import assert_no_scene_leakage, heridal_scene, split_scenes
from .train import map_visdrone_class

# Person class names seen across SARD/HERIDAL Roboflow exports (case-folded).
_PERSON_NAMES = {"person", "human", "people", "pedestrian"}
_SPLITS = ("train", "valid", "test")


def _read_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text())


def _source_class_map(names: list[str], *, is_visdrone: bool) -> ClassMap:
    """Build `{source_index → "person"|DROP}` from a source's ordered class names."""
    mapping: dict[int, str] = {}
    for idx, name in enumerate(names):
        key = str(name).strip().lower()
        if is_visdrone:
            # map_visdrone_class raises on a genuinely unknown class — the collision guard.
            try:
                mapping[idx] = map_visdrone_class(key)
            except ValueError:
                # 'ignored regions' / 'others' are handled by dropping the box here; the
                # image-level ignore handling is applied separately. Unknown -> re-raise.
                if "ignor" in key or key == "others":
                    mapping[idx] = DROP
                else:
                    raise
        else:
            if key in _PERSON_NAMES:
                mapping[idx] = "person"
            else:
                raise ValueError(f"unexpected non-person class {name!r} in a person dataset")
    return ClassMap(mapping)


def _find_split_dir(root: Path, split: str) -> Path | None:
    """Locate a Roboflow split dir (handles `valid` vs `val` and a nested export folder)."""
    candidates = [root / split]
    if split == "valid":
        candidates.append(root / "val")
    for base in (root, *[p for p in root.iterdir() if p.is_dir()]):
        for s in ({split, "val"} if split == "valid" else {split}):
            d = base / s
            if (d / "images").is_dir():
                return d
    for c in candidates:
        if (c / "images").is_dir():
            return c
    return None


def _decode_image(path: Path):
    import numpy as np
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


#: Fraction of HERIDAL scenes held out as the test anchor when re-splitting by scene.
HERIDAL_TEST_FRACTION = 0.2
HERIDAL_SPLIT_SEED = 0


def _heridal_test_scenes(root: Path) -> set[str]:
    """Re-split HERIDAL by SCENE (not Roboflow's random frame split) and return test scenes.

    Roboflow split HERIDAL by frame, so a flight location lands in both train and test and
    inflates recall. We pool every HERIDAL image, collect its scene codes, and deterministically
    hold out whole scenes — so no location crosses the boundary.
    """
    scenes: set[str] = set()
    for split in _SPLITS:
        sdir = _find_split_dir(root, split)
        if sdir is None:
            continue
        for img in (sdir / "images").iterdir():
            if img.suffix.lower() in _IMAGE_EXTS:
                scenes.add(heridal_scene(img.name))
    _, test = split_scenes(
        scenes, test_fraction=HERIDAL_TEST_FRACTION, seed=HERIDAL_SPLIT_SEED
    )
    return test


def _process_source(name, root, cmap, out_root, split_out, summary, hashes):
    """Copy+normalize one source's images/labels into the destination tree's splits.

    HERIDAL is re-split by SCENE (held-out test scenes → merged test; every other HERIDAL
    image → train) so no flight location spans train/test. SARD/VisDrone keep their Roboflow
    split (their test folds into train; valid → val) — they are not the held-out anchor.
    """
    summary["per_source"][name] = {"kept": 0, "dropped": 0}
    heridal_test_scenes = _heridal_test_scenes(root) if name == "heridal" else set()
    if name == "heridal":
        summary["heridal_test_scenes"] = sorted(heridal_test_scenes)
        hashes.setdefault("test_scenes", set())
        hashes.setdefault("train_scenes", set())

    for split in _SPLITS:
        sdir = _find_split_dir(root, split)
        if sdir is None:
            continue
        label_files = sorted((sdir / "labels").glob("*.txt"))
        print(f"  [{name}/{split}]: {len(label_files)} labels", flush=True)
        for label_path in label_files:
            img_path = _resolve_image(sdir / "images", label_path.stem)
            if img_path is None:
                continue

            if name == "heridal":
                scene = heridal_scene(img_path.name)
                dest = "test" if scene in heridal_test_scenes else "train"
                (hashes["test_scenes"] if dest == "test" else hashes["train_scenes"]).add(scene)
            elif split == "valid":
                dest = "val"
            else:
                dest = "train"

            lines = parse_yolo_label(label_path.read_text())
            kept = normalize_label_file(lines, cmap)
            rendered = []
            for ln in kept:
                try:
                    rendered.append(yolo_line(ln))
                except ValueError:
                    summary["degenerate_boxes"] += 1
            summary["per_source"][name]["kept"] += len(rendered)
            summary["per_source"][name]["dropped"] += len(lines) - len(kept)
            summary["dropped_boxes"] += len(lines) - len(kept)

            stem = f"{name}__{label_path.stem}"
            (split_out[dest] / "labels" / f"{stem}.txt").write_text("\n".join(rendered))
            (split_out[dest] / "images" / f"{stem}{img_path.suffix}").write_bytes(
                img_path.read_bytes()
            )
            if dest in ("test", "train"):
                h = image_content_hash(_decode_image(img_path))
                hashes["test" if dest == "test" else "train"].add(h)


def merge(sources: dict[str, Path], out_root: Path, *, leakage_guard: bool = True) -> dict:
    """Merge `sources` (name → staged root) into one single-`person` YOLO tree at `out_root`.

    Used twice by `main()`: once for the {SARD+HERIDAL} FINETUNE set (with the leakage
    guard, since it has the held-out HERIDAL test), and once for the VisDrone PRETRAIN set
    (no held-out test → guard skipped). Returns a summary dict.
    """
    out_root.mkdir(parents=True, exist_ok=True)
    split_out = {s: (out_root / s) for s in ("train", "val", "test")}
    for d in split_out.values():
        (d / "images").mkdir(parents=True, exist_ok=True)
        (d / "labels").mkdir(parents=True, exist_ok=True)

    summary = {"per_source": {}, "splits": {}, "dropped_boxes": 0, "degenerate_boxes": 0}
    hashes = {"train": set(), "test": set()}

    for name, root in sources.items():
        meta = _read_yaml(next(root.rglob("data.yaml")))
        cmap = _source_class_map(list(meta.get("names") or []), is_visdrone=(name == "visdrone"))
        _process_source(name, root, cmap, out_root, split_out, summary, hashes)

    if leakage_guard:
        # Scene-level guard (the real signal): no HERIDAL flight location spans train/test.
        assert_no_scene_leakage(
            hashes.get("train_scenes", set()), hashes.get("test_scenes", set())
        )
        # Byte-identical backstop: no exact-duplicate image crosses the boundary.
        assert_no_leakage(hashes["train"], hashes["test"])

    # A finetune set must have a non-empty held-out test; a pretrain set need not.
    required = ("train", "val", "test") if leakage_guard else ("train", "val")
    for s in required:
        n = len(list((split_out[s] / "images").glob("*")))
        summary["splits"][s] = n
        if n == 0:
            raise ValueError(f"split {s!r} is EMPTY in {out_root} — staging/class map wrong")

    yaml_path = build_dataset_yaml(
        out_root, train="train/images", val="val/images", test="test/images"
    )
    summary["dataset_yaml"] = str(yaml_path)
    return summary


_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def _resolve_image(images_dir: Path, stem: str) -> Path | None:
    """Find `stem`'s image, matching the extension CASE-INSENSITIVELY.

    HERIDAL's test images are `.JPG` (uppercase) on the cluster's case-sensitive
    filesystem; a lowercase-only lookup silently skipped EVERY held-out test image and
    emptied the anchor split. Match against the real directory entries instead.
    """
    for p in images_dir.iterdir():
        if p.stem == stem and p.suffix.lower() in _IMAGE_EXTS:
            return p
    return None


def _resolve_source_root(root: Path, name: str) -> Path | None:
    for cand in (root / name, root):
        hits = list(cand.rglob("data.yaml")) if cand.exists() else []
        if hits:
            p = hits[0].parent
            return p.parent if p.name in _SPLITS else p
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hades-merge-datasets")
    parser.add_argument("--datasets-root", default="/work/ajain1/hades/datasets")
    parser.add_argument("--finetune-out", default="/work/ajain1/hades/datasets/hades-finetune")
    parser.add_argument(
        "--pretrain-out", default="/work/ajain1/hades/datasets/visdrone-pretrain"
    )
    args = parser.parse_args(argv)
    root = Path(args.datasets_root)

    found = {n: _resolve_source_root(root, n) for n in ("sard", "heridal", "visdrone")}
    if not found["sard"] or not found["heridal"]:
        print(f"ERROR: need sard + heridal staged under {root}", file=sys.stderr)
        return 1

    # FINETUNE set = SARD + HERIDAL only (the ablation's shared finetune data, held-out
    # HERIDAL test). VisDrone is NOT here — it is a PRETRAIN, not a finetune source.
    print("=== building FINETUNE set {SARD + HERIDAL} ===", flush=True)
    ft = merge({"sard": found["sard"], "heridal": found["heridal"]}, Path(args.finetune_out))
    print(f"FINETUNE summary: {ft}\n=== leakage guard PASSED ===", flush=True)

    # PRETRAIN set = VisDrone alone (Arm B only); no held-out test, so no leakage guard.
    if found["visdrone"]:
        print("=== building PRETRAIN set {VisDrone} ===", flush=True)
        pt = merge({"visdrone": found["visdrone"]}, Path(args.pretrain_out), leakage_guard=False)
        print(f"PRETRAIN summary: {pt}", flush=True)
    else:
        print("WARNING: VisDrone not staged — Arm B pretrain unavailable", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
