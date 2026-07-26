"""`hades-eval` — detection metrics on a labeled set (Task 2.5).

Runs the chosen detector over a labeled dataset and prints precision/recall + size- and
subclass-stratified recall (eval/report.py). The labeled disaster footage is the
acceptance gate; HERIDAL is the sanity gate (design lines 90–100).

The real curated dataset arrives ~2026-07-01. Until a dataset is present on disk, the
CLI exits non-zero with an honest "dataset not found" message rather than fabricating
metrics — the metric *machinery* is tested in tests/eval/, and a loader for the real
on-disk layout is wired in when the data lands.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

VALID_SETS = ("heridal", "curated")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hades-eval",
        description="Detection metrics (center-distance P/R, size + subclass recall).",
    )
    parser.add_argument(
        "--set",
        choices=VALID_SETS,
        required=True,
        help="which labeled set to evaluate (heridal=sanity gate, curated=acceptance gate)",
    )
    parser.add_argument(
        "--data",
        default=None,
        help="path to the labeled dataset root (default: data/<set>)",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=10.0,
        help="center-distance match threshold in pixels (default 10)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    data_root = Path(args.data) if args.data else Path("data") / args.set
    if not data_root.exists():
        print(
            f"hades-eval: dataset not found at {data_root}. The curated disaster set "
            f"arrives ~2026-07-01; point --data at a labeled set to evaluate. "
            f"(Metric harness: hades.eval.detection_metrics / report.)",
            file=sys.stderr,
        )
        return 1

    # A real loader for the on-disk dataset layout is wired here when the data lands;
    # the harness it feeds (evaluate/format_report) is already built and tested.
    print(
        f"hades-eval: found {data_root}, but the on-disk dataset loader is not wired "
        f"yet (lands with the real dataset). No metrics computed.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
