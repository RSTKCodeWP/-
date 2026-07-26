"""Arm sanity gate (ultraplan P2-o): is an arm's run healthy enough to spend the next slot?

After Arm A finishes, run this before submitting Arm B — costs seconds, saves a 12 h H200
slot if Arm A revealed a pipeline bug (bad class map, leaked split, mis-normalized labels).
Checks the arm's `results.csv`: (1) it exists and has epochs, (2) training loss decreased
(converged, not diverged/NaN), (3) val recall (metrics/recall(B)) reached a non-degenerate
floor. Exit 0 = healthy (proceed), non-zero = stop and investigate.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

MIN_RECALL = 0.30  # non-degenerate floor; the REAL acceptance floor (0.80) is checked later


def check(run_dir: Path) -> tuple[bool, str]:
    results = run_dir / "results.csv"
    if not results.exists():
        return False, f"no results.csv in {run_dir}"
    rows = list(csv.DictReader(results.open()))
    if not rows:
        return False, "results.csv has no epochs"

    def col(row, *names):
        for n in names:
            for k, v in row.items():
                if k.strip() == n:
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None
        return None

    first, last = rows[0], rows[-1]
    train_loss_first = col(first, "train/box_loss")
    train_loss_last = col(last, "train/box_loss")
    recall_last = col(last, "metrics/recall(B)")

    if train_loss_first is not None and train_loss_last is not None:
        if not (train_loss_last < train_loss_first):
            return False, (
                f"train box_loss did not decrease ({train_loss_first} -> {train_loss_last}) "
                f"— diverged/NaN?"
            )
    if recall_last is None:
        return False, "no metrics/recall(B) column in results.csv"
    if recall_last < MIN_RECALL:
        return False, f"val recall {recall_last:.3f} < {MIN_RECALL} floor — degenerate"
    return True, (
        f"healthy: {len(rows)} epochs, box_loss {train_loss_first}->{train_loss_last}, "
        f"val recall {recall_last:.3f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check-arm")
    parser.add_argument("--run-dir", required=True, help="runs/<arm> dir")
    args = parser.parse_args(argv)
    ok, msg = check(Path(args.run_dir))
    print(("OK: " if ok else "FAIL: ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
