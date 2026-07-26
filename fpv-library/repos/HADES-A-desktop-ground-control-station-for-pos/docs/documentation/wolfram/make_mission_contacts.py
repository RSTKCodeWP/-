"""Extract the baked demo-mission contacts to a flat CSV the Wolfram geospatial render reads.

The P6 demo mission (`ui/public/mission.json`) carries the localizer's real contact records:
lat/lon, R95 uncertainty radius, actionability class. This pulls them into one CSV so the
Wolfram GeoGraphics script does not have to parse the full mission wire stream. CUE_ONLY
contacts keep their null coordinate (lat/lon = NaN) - the honest "we cued it but cannot
localize it" case the demo exists to show.

Provenance (kind column): pipeline_real_scene_synthetic. The Fuser output is real; the scene
(drone pose + survivor positions) is scripted. Median error vs known truth is 1.1 m
(mission.json provenance block).

Run:
    python docs/documentation/wolfram/make_mission_contacts.py
Writes: docs/documentation/data/mission_contacts.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _find(obj: object, key: str) -> object | None:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find(v, key)
            if found is not None:
                return found
    return None


def extract(mission_json: Path, out_csv: Path) -> Path:
    data = json.loads(mission_json.read_text())
    seen: dict[int, dict] = {}
    for msg in data.get("json", []):
        blob = json.dumps(msg)
        if "r95_m" in blob and "actionability" in blob:
            tid = _find(msg, "track_id")
            if tid is None:
                continue
            lat, lon = _find(msg, "lat"), _find(msg, "lon")
            seen[tid] = {
                "track_id": tid,
                "lat": lat if lat is not None else "NaN",
                "lon": lon if lon is not None else "NaN",
                "r95_m": _find(msg, "r95_m"),
                "actionability_class": _find(msg, "actionability_class"),
                "confidence": _find(msg, "confidence") if _find(msg, "confidence") is not None
                else "NaN",
                "kind": "pipeline_real_scene_synthetic",
            }
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["track_id", "lat", "lon", "r95_m", "actionability_class", "confidence", "kind"]
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for tid in sorted(seen):
            w.writerow(seen[tid])
    print(f"wrote {len(seen)} contacts to {out_csv}")
    return out_csv


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[3]
    extract(
        repo / "ui" / "public" / "mission.json",
        repo / "docs" / "documentation" / "data" / "mission_contacts.csv",
    )
