"""Scene-aware re-split for HERIDAL — the honest fix for scene-level test leakage.

HERIDAL's Roboflow export splits by FRAME at random, so the same flight location (encoded in
the filename as a scene code: `test_BRK_0004_JPG.rf.<hash>.JPG` → `BRK`) lands in BOTH train
and test. The model then sees the same terrain it's later tested on, inflating the anchor
HERIDAL-test recall. We discard that split and re-partition by **whole scene** so no location
crosses the train/test boundary — a genuine held-out estimate (the DoD requires a labeled
held-out anchor; scene-overlap makes it a lie).

The split is deterministic given a seed, so the held-out set is reproducible across the two
ablation arms and the Mac re-check.
"""

from __future__ import annotations

import hashlib

#: HERIDAL Roboflow filenames begin with one of these split tokens.
_HERIDAL_SPLITS = {"train", "test", "valid", "val"}


def heridal_scene(filename: str) -> str:
    """Extract the HERIDAL scene/location code from a filename.

    `{split}_{SCENE}_{NNNN}_JPG.rf.<hash>.<ext>` → `SCENE`. Validates the shape so a malformed
    or renamed file fails loudly rather than silently yielding a wrong scene code (which would
    quietly defeat the scene-leakage guard): the leading token must be a known split and the
    field after the scene must be a numeric frame index.
    """
    parts = filename.split("_")
    if len(parts) < 3:
        raise ValueError(f"not a HERIDAL filename (need split_SCENE_NNNN...): {filename!r}")
    if parts[0] not in _HERIDAL_SPLITS:
        raise ValueError(
            f"HERIDAL filename must start with a split token {_HERIDAL_SPLITS}: {filename!r}"
        )
    if not parts[2].isdigit():
        raise ValueError(
            f"HERIDAL frame field (after the scene) must be numeric: {filename!r}"
        )
    return parts[1]


def _scene_rank(scene: str, seed: int) -> str:
    """A stable per-scene sort key from a hash of (seed, scene) — seedable, no RNG global."""
    return hashlib.sha256(f"{seed}:{scene}".encode()).hexdigest()


def split_scenes(
    scenes: set[str], *, test_fraction: float, seed: int
) -> tuple[set[str], set[str]]:
    """Partition `scenes` into (train, test) by whole scene, deterministically.

    Hold out ~`test_fraction` of the scenes as test (at least one). Deterministic in `seed`
    via a hash-rank ordering, so both ablation arms and the Mac eval reproduce the same
    held-out scenes without sharing RNG state.
    """
    ordered = sorted(scenes, key=lambda s: _scene_rank(s, seed))
    n_test = max(1, round(len(ordered) * test_fraction))
    test = set(ordered[:n_test])
    train = set(ordered[n_test:])
    return train, test


def assert_no_scene_leakage(train_scenes: set[str], test_scenes: set[str]) -> None:
    """Raise if any scene appears in BOTH train and test (the scene-level leakage guard)."""
    overlap = train_scenes & test_scenes
    if overlap:
        raise ValueError(
            f"scene leakage: {len(overlap)} HERIDAL scene(s) in both train and test "
            f"({sorted(overlap)}) — same flight location spans the split, inflating recall"
        )
