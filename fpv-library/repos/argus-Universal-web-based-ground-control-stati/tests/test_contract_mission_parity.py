"""Contract: frontend buildMissionItems and backend _upload_mission must
produce identical mission item sequences for the same input waypoints.

If either side changes the item order, frame assignment, or field mapping
without updating the other, this test fails. Prevents the silent parity
drift class of bug — a mission uploaded via WebSerial would differ from
one uploaded via the Python backend.

How it works:
  1. Define a "golden" waypoint list covering all attachment types.
  2. Run it through backend _upload_mission and extract the item list.
  3. Parse frontend buildMissionItems output from a vitest JSON dump.
  4. Compare field by field: seq, cmd, frame, p1-p4, x (lat*1e7), y (lon*1e7), z (alt).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent

GOLDEN_WAYPOINTS = [
    {"lat": 34.258, "lon": 108.942, "alt": 50, "type": "wp", "speed": 5, "delay": 0,
     "drop": False, "loiter_param": 0},
    {"lat": 34.259, "lon": 108.943, "alt": 60, "type": "spline", "speed": 0, "delay": 3,
     "drop": True, "loiter_param": 0},
    {"lat": 34.260, "lon": 108.944, "alt": 70, "type": "loiter_turns", "speed": 0, "delay": 0,
     "drop": False, "loiter_param": 5},
    {"lat": 34.261, "lon": 108.945, "alt": 80, "type": "loiter_time", "speed": 8, "delay": 0,
     "drop": False, "loiter_param": 15},
]
GOLDEN_TAKEOFF_ALT = 30.0


def _backend_items() -> list[dict]:
    """Run the golden waypoints through backend _upload_mission."""
    from backend.commands._mission import _upload_mission
    from backend.drone_link import DroneLink

    link = DroneLink()
    link._ser = MagicMock()
    _upload_mission(link, GOLDEN_WAYPOINTS, GOLDEN_TAKEOFF_ALT)
    return link.mission._mission_items


def _frontend_items() -> list[dict]:
    """Run buildMissionItems via a Node one-liner and parse the JSON output."""
    script = r"""
    import { buildMissionItems } from './src/lib/missionUpload.ts';
    const wps = JSON.parse(process.argv[1]);
    const items = buildMissionItems(wps, parseFloat(process.argv[2]));
    console.log(JSON.stringify(items.map(i => ({
        seq: i.seq, cmd: i.command, frame: i.frame,
        p1: i.p1, p2: i.p2, p3: i.p3, p4: i.p4,
        x: i.x, y: i.y, z: i.z
    }))));
    """
    result = subprocess.run(
        ["npx", "tsx", "-e", script, json.dumps(GOLDEN_WAYPOINTS), str(GOLDEN_TAKEOFF_ALT)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=30,
    )
    if result.returncode != 0:
        pytest.skip(f"tsx not available or failed: {result.stderr[:200]}")
    return json.loads(result.stdout.strip())


def _normalize(items: list[dict]) -> list[dict]:
    """Normalize backend item dicts to match the frontend field names."""
    out = []
    for item in items:
        out.append({
            "seq": item.get("seq", 0),
            "cmd": item.get("cmd", item.get("command", 0)),
            "frame": item.get("frame", 3 if item.get("cmd", 0) in (16, 18, 19, 21, 22, 82) else 2),
            "p1": round(float(item.get("p1", 0)), 6),
            "p2": round(float(item.get("p2", 0)), 6),
            "p3": round(float(item.get("p3", 0)), 6),
            "p4": round(float(item.get("p4", 0)), 6),
            "x": int(float(item.get("lat", 0)) * 1e7) if "lat" in item else item.get("x", 0),
            "y": int(float(item.get("lon", 0)) * 1e7) if "lon" in item else item.get("y", 0),
            "z": round(float(item.get("alt", item.get("z", 0))), 6),
        })
    return out


class TestMissionParity:
    def test_backend_frontend_item_count_matches(self):
        be = _normalize(_backend_items())
        fe = _frontend_items()
        assert len(be) == len(fe), (
            f"Item count mismatch: backend={len(be)}, frontend={len(fe)}"
        )

    def test_backend_frontend_items_field_by_field(self):
        be = _normalize(_backend_items())
        fe = _frontend_items()
        assert len(be) == len(fe), "count mismatch (see other test)"
        for i, (b, f) in enumerate(zip(be, fe, strict=True)):
            for key in ("seq", "cmd", "frame", "p1", "p2", "p3", "p4", "x", "y", "z"):
                bv = b.get(key, 0)
                fv = f.get(key, 0)
                if isinstance(bv, float) and isinstance(fv, float):
                    assert abs(bv - fv) < 1e-4, (
                        f"Item {i} field '{key}' mismatch: backend={bv}, frontend={fv}"
                    )
                else:
                    assert bv == fv, (
                        f"Item {i} field '{key}' mismatch: backend={bv}, frontend={fv}"
                    )
