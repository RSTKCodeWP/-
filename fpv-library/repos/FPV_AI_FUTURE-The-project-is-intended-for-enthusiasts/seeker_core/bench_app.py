"""Runnable seeker-head bench app — the real-time loop that drives the head on the stand.

Same loop for SIM and Pi5: read a Frame + IMU, step the assembled head, write the gimbal servos, print
telemetry. Operator two-press is a pluggable callable (GPIO buttons wire here on the Pi). Airframe
channels are never actuated on the bench (no motors) — Pi5Servos writes only the 2 gimbal servos.

    python3 -m seeker_core.bench_app --sim                 # run the head in sim (no hardware)
    python3 -m seeker_core.bench_app --sim --commit        # sim a verified two-press commit
    # Pi5: build Pi5Config + hooks, wire Pi5Camera/Pi5Imu/Pi5Servos (pi5_io.py), then call run(...).
"""
from __future__ import annotations

import argparse
import math
import time
from typing import Callable, Optional

from seeker_core.adapters import SimCameraSource
from seeker_core.contracts import (
    ActuatorChannel, ImuSample, OperatorButton, OperatorCommand, Provenance, SeekerOutput,
)
from seeker_core.core import SeekerCore
from seeker_core.head import bench_seeker_head


class SimImu:
    """A synthetic head IMU (a gentle shake) for running the app without hardware."""
    def read(self, t_ns: int) -> ImuSample:
        t = t_ns * 1e-9
        return ImuSample(gyro_rps=(0.0, 0.3 * math.sin(2 * math.pi * 2.0 * t),
                                   0.4 * math.sin(2 * math.pi * 1.5 * t)),
                         accel_mps2=(0.0, 0.0, 9.80665),
                         provenance=Provenance("sim-imu", t_ns, synthetic=True))


def telemetry_line(out: SeekerOutput) -> str:
    g = out.gimbal
    return (f"{'LOCK' if out.track.locked else 'search':<6} q={out.track.quality:.2f} "
            f"los_yaw={0.0 if g is None else g.los_rate_yaw:+.3f} "
            f"pan={0.0 if g is None else g.pan_setpoint_rad:+.3f} "
            f"tilt={0.0 if g is None else g.tilt_setpoint_rad:+.3f} "
            f"g_req={out.guidance.required_g:.2f} auth={out.authority.reason}")


def run(camera, imu, sink, operator: Callable[[], OperatorCommand], *, head: Optional[SeekerCore] = None,
        dt: float = 1 / 200, ticks: int = 1000, realtime: bool = False,
        on_telemetry: Optional[Callable[[SeekerOutput], None]] = None) -> "tuple[int, Optional[SeekerOutput]]":
    head = head or bench_seeker_head()
    n = 0
    last: Optional[SeekerOutput] = None
    t0 = time.monotonic()
    for _ in range(ticks):
        frame = camera.read()
        if frame is None:
            continue
        out = head.step(frame, imu.read(time.monotonic_ns()), operator(), dt)
        if sink is not None:
            sink.write(out.actuators)
        last, n = out, n + 1
        if on_telemetry is not None:
            on_telemetry(out)
        if realtime:                                    # pace the loop to dt on hardware
            time.sleep(max(0.0, t0 + n * dt - time.monotonic()))
    return n, last


def main() -> None:
    ap = argparse.ArgumentParser(description="Seeker-head bench app (sim / Pi5).")
    ap.add_argument("--sim", action="store_true", help="run the head in sim (no hardware)")
    ap.add_argument("--ticks", type=int, default=400)
    ap.add_argument("--commit", action="store_true", help="(sim) simulate a verified two-press commit")
    a = ap.parse_args()
    if not a.sim:
        raise SystemExit("Pi5 mode: build Pi5Config + hooks, wire Pi5Camera/Pi5Imu/Pi5Servos (seeker_core."
                         "pi5_io), then call bench_app.run(cam, imu, sink, operator, realtime=True).")
    op = (lambda: OperatorCommand(OperatorButton.COMMIT, b"sig", 0)) if a.commit \
        else (lambda: OperatorCommand(OperatorButton.NONE, None, 0))
    printed = {"t": 0.0}

    def tele(out: SeekerOutput) -> None:
        now = time.monotonic()
        if now - printed["t"] > 0.4:
            print(telemetry_line(out))
            printed["t"] = now

    n, last = run(SimCameraSource(), SimImu(), None, op, ticks=a.ticks, on_telemetry=tele)
    print(f"[bench_app:sim] {n} ticks; last: {telemetry_line(last) if last else 'n/a'}")


if __name__ == "__main__":
    main()
