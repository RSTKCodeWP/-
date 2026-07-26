"""`hades-export-doc-data` - the data layer behind every documentation figure (Task 7.1).

Phase 7 documents the FINISHED, MEASURED system. Every graph in the README and the in-app
docs reads from a flat file this CLI writes. The rule is the content gate's rule: every
number traces to a real artifact.

Two provenance classes, both honest:

  Curated transcriptions (detection + real-time). These numbers live in committed result
  docs (`docs/plans/p2.5-acceptance.md`, `p2.5-training-results.md`, `spike-latency-results.md`,
  `p5-latency-budget.md`). They are transcribed here as module constants, each carrying an
  inline `# source:` comment naming the file. The test suite asserts every transcribed value
  against the same committed numbers, so a typo fails CI - the transcription is auditable.

  Live regeneration (localization + coverage). These come from running the REAL code
  (`eval/locsim_report.py`, `eval/coverage.py`) at seed=0. They are deterministic, so they
  reproduce exactly and can never drift from the system they document.

Honesty tags travel with the data: every localization meter row is `kind="sim"`, and the
latency floor is `measurement="floor"` (a dev/CI software-GL number, not the field number).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

# --- detection (curated transcriptions; tests assert each against the committed doc) ----

# source: docs/plans/p2.5-acceptance.md - confidence-threshold sweep on the .pt checkpoint,
# imgsz=960, 50px center-distance, HERIDAL held-out test. SAR can spend precision for recall.
DETECTION_CONF_SWEEP: list[dict[str, float]] = [
    {"conf": 0.05, "recall": 0.69, "precision": 0.37},
    {"conf": 0.10, "recall": 0.63, "precision": 0.46},
    {"conf": 0.25, "recall": 0.51, "precision": 0.62},
]

# source: docs/plans/p2.5-training-results.md - recall/precision by inference resolution
# (Arm A, HERIDAL held-out, conf=0.25). 960 peaks, ties 1280 within noise, better precision.
DETECTION_RESOLUTION: list[dict[str, Any]] = [
    {"resolution": 640, "recall": 0.417, "precision": 0.689, "chosen": False},
    {"resolution": 960, "recall": 0.510, "precision": 0.624, "chosen": True},
    {"resolution": 1280, "recall": 0.511, "precision": 0.559, "chosen": False},
    {"resolution": 1920, "recall": 0.452, "precision": 0.442, "chosen": False},
]

# source: docs/plans/p2.5-acceptance.md - shipped FP16 Core ML vs .pt float32 at the
# acceptance operating point. FP16 did NOT degrade; the decode path is slightly more permissive.
DETECTION_QUANT_DELTA: dict[str, Any] = {
    "pt": {"recall": 0.509, "precision": 0.624, "tp": 732, "fp": 442, "fn": 706},
    "fp16": {"recall": 0.551, "precision": 0.676, "tp": 793, "fp": 380, "fn": 645},
    "recall_gain": 0.042,
    "precision_gain": 0.052,
    "note": "FP16 Core ML did not degrade vs float32; shipped model is the FP16 .mlpackage.",
}

# --- real-time (curated transcriptions) -------------------------------------------------

# source: docs/plans/spike-latency-results.md - ANE forward-pass FPS, MacBook Air M4, FP16,
# ComputeUnits.all. All three clear the >=10 fps detection gate; 960 is the shipped resolution.
FPS_BY_RESOLUTION: list[dict[str, Any]] = [
    {"resolution": 640, "fps": 292.8, "median_ms": 3.4, "gate_fps": 10},
    {"resolution": 960, "fps": 63.1, "median_ms": 15.8, "gate_fps": 10},
    {"resolution": 1280, "fps": 56.7, "median_ms": 17.6, "gate_fps": 10},
]

# source: docs/plans/spike-latency-results.md - ANE placement proof at 640px: ALL tracks
# CPU_AND_NE (~3.5 ms), not CPU_ONLY (~19.8 ms), so the neural engine served the model.
ANE_SPEEDUP: list[dict[str, Any]] = [
    {"compute_unit": "CPU_ONLY", "latency_ms": 19.8, "speedup": 1.0},
    {"compute_unit": "CPU_AND_NE", "latency_ms": 3.5, "speedup": 5.6},
    {"compute_unit": "ALL", "latency_ms": 3.8, "speedup": 5.2},
]

# source: docs/plans/p5-latency-budget.md + ui/tests/latency.spec.ts - in-app glass-to-glass
# (socket -> decode -> paint w/ overlay), 90 frames. A FLOOR: dev/CI software GL, small frames;
# the on-device field run on real-resolution frames is pending. Clears the 120 ms budget ~5.4x.
LATENCY_BUDGET: dict[str, Any] = {
    "n": 90,
    "p50_ms": 1.9,
    "p95_ms": 22.4,
    "max_ms": 33.6,
    "mean_ms": 4.5,
    "budget_ms": 120,
    "measurement": "floor",
    "note": "Dev/CI floor under software GL; on-device field measurement pending.",
}

# --- qualitative figure references (paths, not pixels) ----------------------------------

QUALITATIVE_REFS: dict[str, Any] = {
    "survivor_map": {
        "path": "docs/assets/p6/demo-site.png",
        "caption": "Coordinator UI: live survivor map with tier-colored pins, uncertainty "
        "ellipses, drone track and coverage. Replayed from a real-pipeline bake.",
        "status": "rendered",
    },
    "coordinator_full": {
        "path": "docs/assets/p5/coordinator-full.png",
        "caption": "Full coordinator layout: map, contact list, and live video feed over one "
        "global selection model.",
        "status": "rendered",
    },
    "boxes_on_footage": {
        "path": "docs/documentation/figures/showcase/showcase-boxes.png",
        "source": "real HERIDAL holdout aerial frame + Arm A ONNX detector",
        "tool": "hades.cli.make_showcase",
        "caption": "Real person detections on a HERIDAL aerial search frame (full scene "
        "+ zoomed crop). Boxes are live model output, not hand-drawn.",
        "status": "rendered",
    },
    "before_after": {
        "path": "docs/documentation/figures/showcase/showcase-before-after.png",
        "stock_model": "service/models/yolo11s_640.onnx",
        "tuned_model": "artifacts/armA_heridal_sard/models/yolo11s_960.onnx",
        "caption": "Stock YOLO11s vs HADES SAR fine-tune on the same HERIDAL frame: the "
        "P2.5 win made visible.",
        "status": "rendered",
    },
}


# --- live generators (deterministic, seed=0) --------------------------------------------


def _localization_strata(seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the real meter-error report; return populated strata + the moving-target row."""
    from hades.eval.locsim_report import run_meter_error_report

    report = run_meter_error_report(n_targets=30, seed=seed, include_moving=True)
    strata = [
        {
            "range_bin": s.range_bin,
            "pitch_bin": s.pitch_bin,
            "n": s.n,
            "median_m": round(s.median_m, 2),
            "mean_m": round(s.mean_m, 2),
            "p90_m": round(s.p90_m, 2),
            "max_m": round(s.max_m, 2),
            "coverage": round(s.coverage, 3),
            "kind": "sim",
        }
        for s in report.strata
        if s.n > 0
    ]
    moving = {
        "convergence": report.moving.convergence,
        "median_r95_m": round(report.moving.median_r95_m, 1),
        "actionability_class": report.moving.actionability_class,
        "kind": "sim",
    }
    return strata, moving


def _coverage_matrix(seed: int, n_trials: int) -> list[dict[str, Any]]:
    """Run the real coverage matrix; return one row per (sim, fuser) noise pairing."""
    from hades.eval.coverage import run_coverage_matrix

    return [
        {
            "name": r.name,
            "coverage": round(r.coverage, 3),
            "mean_nees": round(r.mean_nees, 2),
            "median_r95_m": round(r.median_r95_m, 2),
            "n_frames": r.n_frames,
            "n_trials": r.n_trials,
            "kind": "sim",
        }
        for r in run_coverage_matrix(n_trials=n_trials, seed=seed)
    ]


# --- writers ----------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: _csv_cell(row[k]) for k in fields})


def _csv_cell(v: Any) -> Any:
    """Booleans render as lowercase json-style so CSV consumers parse them uniformly."""
    if isinstance(v, bool):
        return "true" if v else "false"
    return v


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n")


def export_all(out_dir: Path, *, seed: int = 0, coverage_trials: int = 200) -> dict[str, Any]:
    """Write all four metric families to flat files under `out_dir`; return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(out_dir / "detection_conf_sweep.csv", DETECTION_CONF_SWEEP,
               ["conf", "recall", "precision"])
    _write_csv(out_dir / "detection_resolution.csv", DETECTION_RESOLUTION,
               ["resolution", "recall", "precision", "chosen"])
    _write_json(out_dir / "detection_quant_delta.json", DETECTION_QUANT_DELTA)

    strata, moving = _localization_strata(seed)
    _write_csv(out_dir / "localization_strata.csv", strata,
               ["range_bin", "pitch_bin", "n", "median_m", "mean_m", "p90_m", "max_m",
                "coverage", "kind"])
    _write_json(out_dir / "localization_moving.json", moving)
    _write_csv(out_dir / "coverage_matrix.csv", _coverage_matrix(seed, coverage_trials),
               ["name", "coverage", "mean_nees", "median_r95_m", "n_frames", "n_trials", "kind"])

    _write_csv(out_dir / "fps_by_resolution.csv", FPS_BY_RESOLUTION,
               ["resolution", "fps", "median_ms", "gate_fps"])
    _write_csv(out_dir / "ane_speedup.csv", ANE_SPEEDUP,
               ["compute_unit", "latency_ms", "speedup"])
    _write_json(out_dir / "latency_budget.json", LATENCY_BUDGET)

    _write_json(out_dir / "qualitative_refs.json", QUALITATIVE_REFS)

    manifest = _manifest()
    _write_json(out_dir / "manifest.json", manifest)
    return manifest


def _manifest() -> dict[str, Any]:
    """Tie every data file to the artifact it came from - the traceability contract."""
    return {
        "seed": 0,
        "families": [
            {"family": "detection", "file": "detection_conf_sweep.csv",
             "source": "docs/plans/p2.5-acceptance.md (confidence sweep)"},
            {"family": "detection", "file": "detection_resolution.csv",
             "source": "docs/plans/p2.5-training-results.md (resolution table)"},
            {"family": "detection", "file": "detection_quant_delta.json",
             "source": "docs/plans/p2.5-acceptance.md (FP16 vs .pt)"},
            {"family": "localization", "file": "localization_strata.csv",
             "source": "eval/locsim_report.py run_meter_error_report seed=0 (sim)"},
            {"family": "localization", "file": "localization_moving.json",
             "source": "eval/locsim_report.py moving-target row seed=0 (sim)"},
            {"family": "localization", "file": "coverage_matrix.csv",
             "source": "eval/coverage.py run_coverage_matrix seed=0 (sim)"},
            {"family": "real_time", "file": "fps_by_resolution.csv",
             "source": "docs/plans/spike-latency-results.md (ANE FPS)"},
            {"family": "real_time", "file": "ane_speedup.csv",
             "source": "docs/plans/spike-latency-results.md (ANE placement)"},
            {"family": "real_time", "file": "latency_budget.json",
             "source": "docs/plans/p5-latency-budget.md (in-app p95, floor)"},
            {"family": "qualitative", "file": "qualitative_refs.json",
             "source": "docs/assets/p5,p6 + fixtures/models (figure references)"},
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hades-export-doc-data", description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parents[4] / "docs" / "documentation" / "data",
        help="output directory for the flat data files",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--coverage-trials", type=int, default=200,
        help="trials per coverage row (more = tighter, slower)",
    )
    args = parser.parse_args(argv)

    manifest = export_all(args.out, seed=args.seed, coverage_trials=args.coverage_trials)
    print(f"wrote {len(manifest['families'])} data files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
