#!/usr/bin/env python3
"""Hardware-in-the-loop: AeroStab + mock MAVLink flight controller over TCP."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aerostab.config import load_config
from aerostab.runtime import AeroStabRuntime
from aerostab.sitl.mock_fc import MockFlightController
from aerostab.state import SharedState


def main() -> int:
    parser = argparse.ArgumentParser(description="AeroStab SITL HIL test")
    parser.add_argument(
        "-c",
        "--config",
        default=str(Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"),
    )
    parser.add_argument("--port", type=int, default=5760, help="Mock FC TCP port")
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--armed", action="store_true", help="Simulate armed FC")
    args = parser.parse_args()

    fc = MockFlightController(port=args.port, armed=args.armed)
    fc.start()

    config = load_config(args.config)
    config.mavlink.port = f"tcp:127.0.0.1:{args.port}"
    config.runtime.simulate = True
    config.web.enabled = False

    shared = SharedState()
    rt = AeroStabRuntime(config, shared)
    rt.start()
    fc.wait_client(timeout_s=20.0)

    t_end = time.monotonic() + args.seconds
    try:
        while time.monotonic() < t_end:
            rt.tick()
            time.sleep(1.0 / config.runtime.control_hz)
    finally:
        rt.stop()
        fc.stop()

    snap = shared.snapshot()
    fc_stats = fc.stats
    print("SITL HIL results")
    print(f"  MAVLink connected: {snap['mavlink_connected']}")
    print(f"  AeroStab messages sent: {snap['mavlink_messages']}")
    print(f"  FC vision received: {fc_stats.vision_count}")
    print(f"  FC optical_flow received: {fc_stats.optical_flow_count}")
    print(f"  FPS: {snap['fps']}")
    print(f"  Quality: {snap['quality']}")
    print(f"  Nav valid: {snap['nav_valid']}")
    print(f"  GPS fusion ready: {snap['nav_ready']}")

    ok = (
        snap["mavlink_connected"]
        and snap["mavlink_messages"] > 0
        and fc_stats.vision_count > 0
        and snap["fps"] > 5
        and snap["track_points"] > 0
    )
    if not ok:
        print("FAIL: integration checks not met", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
