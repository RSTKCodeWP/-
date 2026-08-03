#!/usr/bin/env python3
"""SITL scenario runner — arm/disarm, RTL path, mavlink link."""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aerostab.config import load_config
from aerostab.runtime import AeroStabRuntime
from aerostab.sitl.mock_fc import MockFlightController
from aerostab.state import SharedState


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_ticks(rt: AeroStabRuntime, hz: int, seconds: float) -> None:
    for _ in range(int(seconds * hz)):
        rt.tick()
        time.sleep(1.0 / hz)


def scenario_mavlink_link(port: int) -> None:
    fc = MockFlightController(port=port)
    fc.start()
    cfg = load_config(str(Path(__file__).parents[1] / "config" / "sitl.yaml"))
    cfg.mavlink.port = f"tcp:127.0.0.1:{port}"
    cfg.web.enabled = False
    shared = SharedState()
    rt = AeroStabRuntime(cfg, shared)
    rt.start()
    fc.wait_client(timeout_s=15)
    _run_ticks(rt, cfg.runtime.control_hz, 3.0)
    snap = shared.snapshot()
    rt.stop()
    fc.stop()
    assert snap["mavlink_connected"], "mavlink link"
    assert snap["mavlink_messages"] > 0, "odometry sent"
    assert fc.stats.vision_count > 0, "vision received"


def scenario_arm_reset(port: int) -> None:
    fc = MockFlightController(port=port, arm_at_s=1.5)
    fc.start()
    cfg = load_config(str(Path(__file__).parents[1] / "config" / "sitl.yaml"))
    cfg.mavlink.port = f"tcp:127.0.0.1:{port}"
    cfg.odometry.reset_on_arm = True
    cfg.web.enabled = False
    shared = SharedState()
    rt = AeroStabRuntime(cfg, shared)
    rt.start()
    fc.wait_client(timeout_s=15)

    # Before arm: accumulate position
    _run_ticks(rt, cfg.runtime.control_hz, 1.0)
    pre_arm = shared.snapshot()
    assert not pre_arm["armed"]

    # After arm: odometry should reset near origin
    _run_ticks(rt, cfg.runtime.control_hz, 2.5)
    post_arm = shared.snapshot()
    assert post_arm["armed"], "FC should be armed"
    dist = (post_arm["x_m"] ** 2 + post_arm["y_m"] ** 2) ** 0.5
    assert dist < 1.0, f"position should reset on arm, got {dist:.2f} m"

    rt.stop()
    fc.stop()


def scenario_rtl_path(port: int) -> None:
    fc = MockFlightController(port=port, arm_at_s=0.3, disarm_at_s=8.0)
    fc.start()
    cfg = load_config(str(Path(__file__).parents[1] / "config" / "sitl.yaml"))
    cfg.mavlink.port = f"tcp:127.0.0.1:{port}"
    cfg.rtl.enabled = True
    cfg.rtl.min_dist_m = 0.01
    cfg.rtl.save_path = str(Path("logs") / "rtl_scenario.json")
    cfg.web.enabled = False
    shared = SharedState()
    rt = AeroStabRuntime(cfg, shared)
    rt.start()
    fc.wait_client(timeout_s=15)
    _run_ticks(rt, cfg.runtime.control_hz, 9.0)
    snap = shared.snapshot()
    assert rt._rtl and rt._rtl.point_count > 3, f"RTL points={snap['rtl_points']}"
    assert snap["rtl_length_m"] > 0.1, "RTL path length"
    assert not snap["rtl_recording"], "should stop recording after disarm"
    assert Path(cfg.rtl.save_path).exists(), "RTL path file saved"
    rt.stop()
    fc.stop()


SCENARIOS = {
    "mavlink_link": scenario_mavlink_link,
    "arm_reset": scenario_arm_reset,
    "rtl_path": scenario_rtl_path,
}


def main() -> int:
    names = sys.argv[1:] or list(SCENARIOS.keys())
    failed = []
    for name in names:
        if name not in SCENARIOS:
            print(f"Unknown scenario: {name}", file=sys.stderr)
            return 2
        port = _free_port()
        print(f"▶ {name} (port {port})...", flush=True)
        try:
            SCENARIOS[name](port)
            print(f"  PASS")
        except Exception as exc:
            print(f"  FAIL: {exc}")
            failed.append(name)
    if failed:
        print(f"\n{len(failed)} scenario(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"\nAll {len(names)} scenario(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
