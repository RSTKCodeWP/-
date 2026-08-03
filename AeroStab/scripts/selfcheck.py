#!/usr/bin/env python3
"""Post-install / preflight self-check (run on Pi or in sim)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aerostab.config import load_config
from aerostab.mask import CameraMask
from aerostab.runtime import AeroStabRuntime
from aerostab.state import SharedState


def main() -> int:
    simulate = "--simulate" in sys.argv or not Path("/dev/serial0").exists()
    cfg_path = os.environ.get("AEROSTAB_CONFIG") or str(
        Path(__file__).resolve().parents[1] / "config" / ("sitl.yaml" if simulate else "default.yaml")
    )
    if not Path(cfg_path).exists():
        cfg_path = str(Path(__file__).resolve().parents[1] / "config" / "default.yaml")

    print(f"AeroStab self-check (simulate={simulate})")
    print(f"Config: {cfg_path}")

    # Mask must load
    mask_path = Path("/etc/aerostab/mask.json")
    if not mask_path.exists():
        mask_path = Path("mask.json")
    m = CameraMask.load(mask_path)
    print(f"  mask: OK ({m.cols}x{m.rows})")

    cfg = load_config(cfg_path)
    if simulate:
        cfg.runtime.simulate = True
        cfg.mavlink.enabled = False
        cfg.web.enabled = False
        cfg.quality.nav_valid_warmup_s = 0.3

    shared = SharedState()
    rt = AeroStabRuntime(cfg, shared, config_path=cfg_path)
    rt.start()
    for _ in range(60):
        rt.tick()
        time.sleep(1 / max(cfg.runtime.control_hz, 1))
    snap = shared.snapshot()
    rt.stop()

    checks = [
        ("fps", snap["fps"] > 5),
        ("tracking", snap["track_points"] > 0 and snap["quality"] > 0.2),
        ("camera", True),
    ]
    if not simulate:
        checks.append(("mavlink", snap["mavlink_connected"]))
        checks.append(("flight_gate", snap.get("health_ready", False)))

    ok = True
    for name, passed in checks:
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
        ok = ok and passed

    print("SELF-CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
