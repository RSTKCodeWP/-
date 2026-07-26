"""`hades-locsim` entry point - the localization meter-error report (Task 4.9).

Runs the calibrated synthetic simulator across a span of flight geometries, fuses each
target, and prints the localization error in METERS stratified by slant range x camera pitch
from nadir, plus empirical coverage and a moving-target non-convergence row. Every meter
number is a (sim) number, pending real-flight confirmation (research gate §7).
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hades-locsim", description=__doc__)
    parser.add_argument(
        "--targets", type=int, default=30,
        help="targets per geometry (more = tighter strata stats, slower)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--no-moving", action="store_true", help="skip the moving-target non-convergence row"
    )
    args = parser.parse_args(argv)

    from hades.eval.locsim_report import run_meter_error_report

    report = run_meter_error_report(
        n_targets=args.targets, seed=args.seed, include_moving=not args.no_moving
    )
    print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
