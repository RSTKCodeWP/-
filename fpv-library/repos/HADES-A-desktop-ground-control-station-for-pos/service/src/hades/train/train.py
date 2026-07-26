"""Cluster training entry + the resume/class-map helpers (Task 2.5.3).

Runs on the NCShare H200s. The `main()` is a thin shell that resolves a `TrainConfig` and
calls `YOLO(weights).train(...)`; it is NOT unit-tested (mocking the trainer proves nothing).
The two pure helpers below ARE tested, because getting them wrong wastes GPU days or
silently corrupts the ablation:

- `resume_arg`: on the **preemptible** `gpu` partition a job can be requeued mid-run. Each
  arm gets its OWN run dir (`runs/armA…`, `runs/armB…`); resume is gated on that arm's
  `last.pt` existing and is passed as an **absolute path**, never bare `True` (which scans
  sibling runs and could resume the wrong arm — the ablation-collapse trap).
- `map_visdrone_class`: the VisDrone-pretrain arm's class merge — pedestrian + people →
  person, every vehicle dropped, unknown raises (the collision guard).
"""

from __future__ import annotations

from pathlib import Path

from .dataset import DROP

#: VisDrone (Roboflow YOLO export) class names → unified target. Both human classes become
#: `person`; every vehicle is dropped so it can't poison the person prior. `ignored regions`
#: / `others` are handled at dataset-build time (image dropped), not here.
_VISDRONE_MAP = {
    "pedestrian": "person",
    "people": "person",
    "bicycle": DROP,
    "car": DROP,
    "van": DROP,
    "truck": DROP,
    "tricycle": DROP,
    "awning-tricycle": DROP,
    "bus": DROP,
    "motor": DROP,
}


def map_visdrone_class(name: str) -> str:
    """Map a VisDrone class name to `"person"` or `DROP`; raise on an unknown class."""
    key = name.strip().lower()
    if key not in _VISDRONE_MAP:
        raise ValueError(f"unknown VisDrone class {name!r}; known: {sorted(_VISDRONE_MAP)}")
    return _VISDRONE_MAP[key]


def resume_arg(arm_dir) -> str | bool:
    """Resume value for `YOLO.train()` for a per-arm run dir.

    Returns the absolute `last.pt` path when it exists (a SLURM requeue → resume in place),
    else `False` (a fresh submit → train from the pretrain weights). Passing the absolute
    path rather than `True` keeps Ultralytics from scanning sibling runs and resuming a
    different arm.
    """
    last = (Path(arm_dir) / "weights" / "last.pt").resolve()
    return str(last) if last.exists() else False


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin trainer shell
    """Resolve a config and launch one arm's training on the cluster.

    Not exercised by unit tests (it drives Ultralytics on a GPU); the tested surface is the
    two helpers above. Lazy-imports ultralytics so this module loads without the ML stack.
    """
    import argparse

    import yaml
    from ultralytics import YOLO

    from .config import TrainConfig

    parser = argparse.ArgumentParser(prog="hades-train")
    parser.add_argument("--arm", required=True, help="run name, e.g. armA_heridal_sard")
    parser.add_argument("--config", required=True, help="path to ablation.yaml")
    parser.add_argument("--project", default="/work/ajain1/hades/runs")
    args = parser.parse_args(argv)

    raw = yaml.safe_load(Path(args.config).read_text())
    cfg = TrainConfig(**raw)

    arm_dir = Path(args.project) / args.arm
    model = YOLO(cfg.weights)
    model.train(
        project=args.project,
        name=args.arm,
        exist_ok=True,  # a requeue must reuse the SAME dir, not increment to armA2
        resume=resume_arg(arm_dir),
        **cfg.to_ultralytics(),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
