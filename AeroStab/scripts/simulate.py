#!/usr/bin/env python3
"""Run AeroStab in simulation for 5 seconds and print stats."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aerostab.config import load_config
from aerostab.runtime import AeroStabRuntime
from aerostab.state import SharedState


def main():
    config = load_config()
    config.runtime.simulate = True
    config.mavlink.enabled = False
    config.web.enabled = False
    config.runtime.control_hz = 30

    shared = SharedState()
    rt = AeroStabRuntime(config, shared)
    rt.start()

    t_end = time.monotonic() + 5.0
    while time.monotonic() < t_end:
        rt.tick()
        time.sleep(1 / config.runtime.control_hz)

    rt.stop()
    s = shared.snapshot()
    print("Simulation OK")
    print(f"  FPS: {s['fps']}")
    print(f"  Position: {s['x_m']} / {s['y_m']} m")
    print(f"  Quality: {s['quality']}")
    print(f"  Track points: {s['track_points']}")
    assert s["fps"] > 5
    assert s["track_points"] > 0


if __name__ == "__main__":
    main()
