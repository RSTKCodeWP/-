"""Open-loop onboard bench (Block-3 hardware phase, B1 integration).

Ties the REAL thermal camera + the REAL FC gyro into the full perception+guidance pipeline and
shows what the AI WOULD command -- WITHOUT ever commanding the flight controller. It reads
telemetry only (MSP_RAW_IMU) and never sends MSP_SET_RAW_RC, so it cannot arm or move motors.
This is the last hardware step before the AI is given authority over the FC: it validates the
whole onboard chain (pixels -> detect -> ego -> LOS -> IMM -> guidance) on real hardware, safely.

Gyro scale: until S0 calibration measures the deg/s-per-LSB, leave gyro_scale=0 -> ego rate is
zero -> the bench validates detection/tracking only (no ego-compensation). With a nominal scale
the roll de-rotation is active, but a flight-grade scale MUST come from S0.
"""

from __future__ import annotations

from dataclasses import dataclass

from fpv.guidance.pipeline import PipelineOutput, SeekerGuidancePipeline

from fpv_ai.betaflight_link.msp_bench import read_imu
from fpv_ai.betaflight_link.msp_codec import gyro_raw_to_radps
from fpv_ai.betaflight_link.serial_link import MspLink
from fpv_ai.sensor.thermal_capture import ThermalCapture


@dataclass(frozen=True)
class OpenLoopSample:
    frame_ok: bool
    imu_ok: bool
    gyro_radps: tuple[float, float, float]
    tracking_state: str
    locked: bool
    would_command: object | None       # the AICommand the AI WOULD send (never transmitted)
    az_rate_radps: float | None
    el_rate_radps: float | None


class OpenLoopBench:
    """Camera + gyro -> pipeline -> 'what it would command'. Never transmits RC."""

    def __init__(self, capture: ThermalCapture, link: MspLink, pipe: SeekerGuidancePipeline,
                 *, gyro_scale_deg_s_per_lsb: float = 0.0) -> None:
        self.capture = capture
        self.link = link
        self.pipe = pipe
        self.gyro_scale = gyro_scale_deg_s_per_lsb

    def step(self, now: float, dt: float) -> OpenLoopSample:
        frame = self.capture.frame_u16()
        if frame is None:
            return OpenLoopSample(False, False, (0.0, 0.0, 0.0), "NO_FRAME", False, None, None, None)

        imu = read_imu(self.link)                       # telemetry READ only -- never RC
        if imu is not None and self.gyro_scale:
            gyro = gyro_raw_to_radps(imu.gyro, self.gyro_scale)
        else:
            gyro = (0.0, 0.0, 0.0)                       # uncalibrated -> ego off (detection-only)

        out: PipelineOutput = self.pipe.step(now, frame, gyro, dt)
        az = out.imm.az_rate_radps if out.imm is not None else None
        el = out.imm.el_rate_radps if out.imm is not None else None
        return OpenLoopSample(
            frame_ok=True, imu_ok=imu is not None, gyro_radps=gyro,
            tracking_state=out.tracking_state, locked=out.locked,
            would_command=out.command, az_rate_radps=az, el_rate_radps=el,
        )


def main() -> None:  # pragma: no cover - hardware bench
    import argparse
    import time

    from fpv_ai.sensor.thermal_capture import CaptureConfig, V4L2Source, ft640_intrinsics

    ap = argparse.ArgumentParser(description="Open-loop onboard bench (READ-ONLY, never commands the FC)")
    ap.add_argument("--device", default="/dev/video0", help="thermal capture (CVBS->USB grabber)")
    ap.add_argument("--width", type=int, default=720, help="MS2109/EasyCap max is 720x480")
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fourcc", default="MJPG")
    ap.add_argument("--port", default="/dev/ttyAMA0", help="FC MSP UART")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"), default=None)
    ap.add_argument("--hfov", type=float, default=48.7)
    ap.add_argument("--gyro-scale", type=float, default=0.0, help="deg/s per LSB (0 = ego off; set from S0)")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--report-every", type=int, default=15)
    args = ap.parse_args()

    print("=" * 70)
    print(" OPEN-LOOP BENCH -- READ-ONLY. Reads camera + gyro, shows what the AI WOULD")
    print(" command. It NEVER sends RC to the FC -> cannot arm or move motors.")
    print("=" * 70)

    cap = ThermalCapture(V4L2Source(args.device, width=args.width, height=args.height, fourcc=args.fourcc),
                         CaptureConfig(roi=tuple(args.roi) if args.roi else None, invert=args.invert))
    link = MspLink.open_serial(args.port, args.baud, hardware_authorized=True)
    pipe = SeekerGuidancePipeline(intrinsics=ft640_intrinsics(hfov_deg=args.hfov))
    bench = OpenLoopBench(cap, link, pipe, gyro_scale_deg_s_per_lsb=args.gyro_scale)

    n, t0, last = 0, time.monotonic(), time.monotonic()
    while time.monotonic() - t0 < args.duration:
        now = time.monotonic()
        dt = now - last
        last = now
        s = bench.step(now, max(dt, 1e-4))
        n += 1
        if n % args.report_every == 0 and s.frame_ok:
            cmd = s.would_command
            cmd_str = ("roll=%.2f pitch=%.2f yaw=%.2f thr=%.2f" % (
                cmd.roll_cmd, cmd.pitch_cmd, cmd.yaw_rate_cmd, cmd.throttle_cmd)) if cmd else "-- (no lock)"
            print(f"[{n:5d}] {s.tracking_state:14s} lock={s.locked} imu={s.imu_ok} "
                  f"lam_az={None if s.az_rate_radps is None else round(s.az_rate_radps,4)} "
                  f"would_cmd[{cmd_str}] fps={round(1.0/dt,1) if dt>0 else '?'}")
    cap.close()
    link.close()
    print(f"[bench] done ({n} frames). Nothing was ever transmitted to the FC.")


if __name__ == "__main__":
    main()
