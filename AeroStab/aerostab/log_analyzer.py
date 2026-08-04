"""Flight log analyzer — produces .aerostab JSON reports from CSV logs."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class FlightReport:
    source: str
    samples: int
    duration_s: float
    distance_m: float
    max_speed_m_s: float
    mean_speed_m_s: float
    mean_quality: float
    min_quality: float
    nav_valid_pct: float
    armed_pct: float
    mean_altitude_m: float
    final_xy_m: tuple
    drift_per_min_m: float
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["final_xy_m"] = list(self.final_xy_m)
        return d


def analyze_csv(path: str | Path) -> FlightReport:
    path = Path(path)
    rows: List[Dict[str, float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            try:
                rows.append({k: float(raw[k]) for k in raw if raw[k] != ""})
            except (ValueError, KeyError):
                continue

    warnings: List[str] = []
    if len(rows) < 2:
        return FlightReport(
            source=str(path),
            samples=len(rows),
            duration_s=0,
            distance_m=0,
            max_speed_m_s=0,
            mean_speed_m_s=0,
            mean_quality=0,
            min_quality=0,
            nav_valid_pct=0,
            armed_pct=0,
            mean_altitude_m=0,
            final_xy_m=(0.0, 0.0),
            drift_per_min_m=0,
            warnings=["too few samples"],
        )

    t0, t1 = rows[0]["t"], rows[-1]["t"]
    duration = max(0.0, t1 - t0)
    dist = 0.0
    speeds = []
    qualities = []
    alts = []
    nav_ok = 0
    armed_n = 0
    for i, r in enumerate(rows):
        q = r.get("quality", 0.0)
        qualities.append(q)
        alts.append(r.get("alt", 0.0))
        vx, vy = r.get("vx", 0.0), r.get("vy", 0.0)
        speeds.append(math.hypot(vx, vy))
        if r.get("nav_valid", 1.0) >= 0.5:
            nav_ok += 1
        if r.get("armed", 0.0) >= 0.5:
            armed_n += 1
        if i > 0:
            dx = r.get("x", 0.0) - rows[i - 1].get("x", 0.0)
            dy = r.get("y", 0.0) - rows[i - 1].get("y", 0.0)
            dist += math.hypot(dx, dy)

    mean_q = sum(qualities) / len(qualities)
    min_q = min(qualities)
    mean_spd = sum(speeds) / len(speeds)
    max_spd = max(speeds)
    fx, fy = rows[-1].get("x", 0.0), rows[-1].get("y", 0.0)
    drift_rate = (math.hypot(fx, fy) / max(duration / 60.0, 1e-6)) if duration > 0 else 0.0

    if mean_q < 0.35:
        warnings.append("low mean tracking quality")
    if nav_ok / len(rows) < 0.7:
        warnings.append("nav_valid below 70%")
    if drift_rate > 5.0:
        warnings.append("high position drift rate")
    if max_spd > 12.0:
        warnings.append("peak speed unusually high — check FOV/altitude")

    return FlightReport(
        source=str(path),
        samples=len(rows),
        duration_s=round(duration, 2),
        distance_m=round(dist, 2),
        max_speed_m_s=round(max_spd, 3),
        mean_speed_m_s=round(mean_spd, 3),
        mean_quality=round(mean_q, 3),
        min_quality=round(min_q, 3),
        nav_valid_pct=round(100.0 * nav_ok / len(rows), 1),
        armed_pct=round(100.0 * armed_n / len(rows), 1),
        mean_altitude_m=round(sum(alts) / len(alts), 2),
        final_xy_m=(round(fx, 2), round(fy, 2)),
        drift_per_min_m=round(drift_rate, 2),
        warnings=warnings,
    )


def write_report(report: FlightReport, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"format": "aerostab.flight_report.v1", "report": report.to_dict()}, f, indent=2)
    return out


def analyze_latest(log_dir: str | Path) -> Optional[FlightReport]:
    log_dir = Path(log_dir)
    csvs = sorted(log_dir.glob("*.csv"))
    if not csvs:
        return None
    return analyze_csv(csvs[-1])


def cli_main(argv: list[str] | None = None) -> int:
    """Entry point for ``aerostab-analyze`` console script."""
    import argparse
    import json
    import sys

    p = argparse.ArgumentParser(description="AeroStab flight log analyzer")
    p.add_argument("log", nargs="?", help="CSV log path")
    p.add_argument("-d", "--dir", default="logs", help="Log directory")
    p.add_argument("-o", "--out", help="Output report path")
    p.add_argument("--json", action="store_true", help="Print JSON only")
    args = p.parse_args(argv)

    if args.log:
        report = analyze_csv(args.log)
    else:
        report = analyze_latest(args.dir)
        if report is None:
            print(f"No CSV logs in {args.dir}", file=sys.stderr)
            return 1

    if args.out:
        write_report(report, args.out)
        print(f"Wrote {args.out}")
    elif args.json:
        print(json.dumps({"format": "aerostab.flight_report.v1", "report": report.to_dict()}, indent=2))
    else:
        r = report
        print(f"Source:     {r.source}")
        print(f"Samples:    {r.samples}")
        print(f"Duration:   {r.duration_s} s")
        print(f"Distance:   {r.distance_m} m")
        print(f"Speed:      mean {r.mean_speed_m_s} / max {r.max_speed_m_s} m/s")
        print(f"Quality:    mean {r.mean_quality} / min {r.min_quality}")
        print(f"Nav valid:  {r.nav_valid_pct}%")
        print(f"Armed:      {r.armed_pct}%")
        print(f"Altitude:   {r.mean_altitude_m} m")
        print(f"Final XY:   {r.final_xy_m}")
        print(f"Drift/min:  {r.drift_per_min_m} m")
        print("Warnings:   " + (", ".join(r.warnings) if r.warnings else "none"))
        out = Path(r.source).with_suffix(".aerostab.json")
        write_report(report, out)
        print(f"Report:     {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli_main())
