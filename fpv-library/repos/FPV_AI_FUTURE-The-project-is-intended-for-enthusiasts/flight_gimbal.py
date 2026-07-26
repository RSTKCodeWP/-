"""flight_gimbal -- the Pi-5 flight loop for the chosen build: FT640 on our gimbal, up-camera, MSP override.

This is the runnable composition of the pieces the 2026-07-19 measurement settled on:

    FT640 grabber ─▶ GimbalFlightHead ─▶ guidance command ─▶ MSP RC to the FC (only while the toggle is held)
    head IMU ──────▶      │      └─────▶ servo setpoints ──▶ the 2 gimbal servos (always -- the head keeps
                          │                                   the target centred so it is ready to commit)
    RC toggle ────────────┴──▶ engaged?

Safety model (identical to ``msp_override_flight`` -- FIRST FLIGHTS keep a pilot on the backup):
  * The FC owns arming and the manual layer. This loop NEVER arms; arming stays on the RX switch.
  * The Pi only ever writes the 4 STICK channels, and only while the operator holds the override toggle.
    Toggle down, or Pi/USB/loop dead → Betaflight drops the override and the pilot's sticks return. Both
    properties come from Betaflight (see firmware/betaflight-fork/INTERCEPTOR_CLI.md), not from this code.
  * Throttle has a HARD ceiling here regardless of what guidance asks.

The hardware ``main()`` is bench/flight only (not CI-exercised). The routing that decides what reaches the FC
and the servos is the pure ``FlightGimbalController.tick`` -- that is what the tests pin.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fpv.fpv_ai.flight_head import FlightHeadStep, GimbalFlightHead
from fpv_ai.betaflight_link.msp_codec import (
    RC_CHANNEL_ORDER,
    US_MID,
    US_MIN,
    ai_command_to_channels,
)

_FLIGHT_AXES = ("roll", "pitch", "yaw", "throttle")


@dataclass
class FlightGimbalConfig:
    switch_index: int = 5                 # MSP_RC index of the override toggle. Owner mapped MSP_OVERRIDE to
                                          # AUX2, and the MSP RC order is R,P,Y,T,AUX1,AUX2,... so AUX2 == 5.
    switch_threshold_us: int = 1600       # >= this == ENGAGED (system flies the sticks)
    throttle_max_us: int = 1700           # HARD throttle ceiling handed to guidance -- SET FOR YOUR AIRCRAFT
    throttle_min_us: int = 1000
    lostlock_throttle_us: int = 1450      # engaged but no target -> level + this gentle throttle; pilot retakes


@dataclass
class FlightGimbalOutputs:
    fc_channels: dict                     # RC channels to stream to the FC this tick
    servo_pan_rad: float                  # gimbal setpoints (servo driver converts rad -> pulse, pi5_io)
    servo_tilt_rad: float
    engaged: bool
    locked: bool
    tracking: bool
    have_cmd: bool
    step: FlightHeadStep                  # full head output, for telemetry/logging


def _neutral_channels(rc: list[int] | None, cfg: FlightGimbalConfig) -> dict:
    ch = {"roll": US_MID, "pitch": US_MID, "yaw": US_MID, "throttle": cfg.throttle_min_us,
          "aux1": US_MIN, "aux2": US_MIN, "aux3": US_MIN, "aux4": US_MIN}
    if rc is not None:                    # pass the pilot's AUX values through (unmasked; harmless)
        for i, name in enumerate(RC_CHANNEL_ORDER):
            if name.startswith("aux") and i < len(rc):
                ch[name] = int(rc[i])
    return ch


def compute_fc_channels(command, engaged: bool, rc: list[int] | None,
                        cfg: FlightGimbalConfig) -> dict:
    """What to stream to the FC. Mirrors the strapdown bridge's contract exactly, on purpose:

    - NOT engaged            -> neutral/idle; Betaflight's override is off, so the RX (pilot) flies.
    - engaged + a command    -> guidance on the 4 sticks, throttle HARD-capped.
    - engaged + no target    -> level attitude + a gentle lost-lock throttle; the pilot retakes by toggling.
    """
    ch = _neutral_channels(rc, cfg)
    if not engaged:
        return ch
    if command is not None:
        g = ai_command_to_channels(command)
        g["throttle"] = max(cfg.throttle_min_us, min(int(g["throttle"]), cfg.throttle_max_us))
        for name in _FLIGHT_AXES:
            ch[name] = int(g[name])
        return ch
    ch["roll"] = ch["pitch"] = ch["yaw"] = US_MID
    ch["throttle"] = cfg.lostlock_throttle_us
    return ch


class FlightGimbalController:
    """The pure flight brain: perception+gimbal (GimbalFlightHead) + the FC channel routing above.

    Hardware I/O is the caller's job -- ``tick`` takes a frame + head IMU sample and returns what to write.
    """

    def __init__(self, head: GimbalFlightHead, config: FlightGimbalConfig | None = None) -> None:
        self._head = head
        self.cfg = config or FlightGimbalConfig()

    def designate(self, center_px: tuple[float, float]) -> None:
        self._head.designate(center_px)

    def engaged_from_rc(self, rc: list[int] | None) -> bool:
        if rc is None or self.cfg.switch_index >= len(rc):
            return False                  # no fresh toggle reading -> treat as NOT engaged (fail to pilot)
        return int(rc[self.cfg.switch_index]) >= self.cfg.switch_threshold_us

    def tick(self, now: float, frame_u16, head_gyro_xyz, head_accel_xyz, dt: float,
             rc: list[int] | None) -> FlightGimbalOutputs:
        step = self._head.step(now, frame_u16, head_gyro_xyz, head_accel_xyz, dt)
        engaged = self.engaged_from_rc(rc)
        fc = compute_fc_channels(step.command, engaged, rc, self.cfg)
        # The gimbal tracks whether or not we are engaged -- it must already be ON the target the moment the
        # operator commits, not start slewing then.
        return FlightGimbalOutputs(
            fc_channels=fc, servo_pan_rad=step.pan_setpoint_rad, servo_tilt_rad=step.tilt_setpoint_rad,
            engaged=engaged, locked=step.locked, tracking=step.tracking,
            have_cmd=step.command is not None, step=step)


def main() -> None:  # pragma: no cover -- hardware bench/flight only
    """Pi-5 flight loop. Wires the FT640 grabber + head IMU + 2 gimbal servos + the FC over MSP.

    Run on the Pi with props OFF for the bench check, or on the aircraft with a pilot on the RX for a flight
    test. See docs/FLIGHT_TEST_OVERRIDE.md for the field procedure.
    """
    import argparse
    import time

    from fpv.seeker.geometry import ft640_intrinsics
    from fpv_ai.betaflight_link.msp_codec import channels_to_list
    from fpv_ai.betaflight_link.serial_link import MspLink
    from fpv_ai.msp_override_flight import read_rc_channels
    from seeker_core.pi5_io import (
        Pi5Camera, Pi5Config, Pi5Imu, make_i2c_imu_reader, make_pca9685_servo_writer, rad_to_pulse_us,
    )

    ap = argparse.ArgumentParser(description="Pi-5 gimbal-interceptor flight loop (FT640 + our gimbal)")
    ap.add_argument("--fc", default="/dev/ttyACM0", help="flight controller MSP serial (USB VCP)")
    ap.add_argument("--camera", default="/dev/video0", help="FT640 via CVBS->USB grabber")
    ap.add_argument("--hz", type=float, default=50.0)
    ap.add_argument("--throttle-max-us", type=int, default=1700, help="HARD throttle ceiling -- set per aircraft")
    ap.add_argument("--pan-channel", type=int, default=0, help="PCA9685 channel for the gimbal PAN servo")
    ap.add_argument("--tilt-channel", type=int, default=1, help="PCA9685 channel for the gimbal TILT servo")
    ap.add_argument("--dry", action="store_true", help="log what WOULD be sent; do not stream to the FC")
    ap.add_argument("--march", action="store_true",
                    help="dead-reckon the target bearing through a lock gap (keeps the gimbal on a CROSSING "
                         "target that would otherwise be lost when it leaves frame)")
    args = ap.parse_args()

    pi5 = Pi5Config(camera_device=args.camera)
    cam = Pi5Camera(pi5)
    imu = Pi5Imu(pi5, make_i2c_imu_reader())               # head IMU on I2C
    servo_write_us = make_pca9685_servo_writer()           # 2 gimbal servos on PCA9685 (owner's board)
    head = GimbalFlightHead(intrinsics=ft640_intrinsics(), climb_throttle=0.62, march=args.march)
    ctrl = FlightGimbalController(head, FlightGimbalConfig(throttle_max_us=args.throttle_max_us))
    link = None if args.dry else MspLink.open(args.fc)

    print("gimbal flight loop: %s  camera=%s  throttle_max=%dus  %s" % (
        args.fc, args.camera, args.throttle_max_us, "DRY" if args.dry else "LIVE"))
    dt = 1.0 / args.hz
    t0 = time.monotonic()
    try:
        while True:
            now = time.monotonic() - t0
            frame = cam.read()
            imu_s = imu.read(time.monotonic_ns())
            gyro = imu_s.gyro_rps if imu_s else (0.0, 0.0, 0.0)
            accel = imu_s.accel_mps2 if imu_s else (0.0, 0.0, 9.81)
            rc = read_rc_channels(link) if link is not None else None
            out = ctrl.tick(now, frame.pixels if frame else None, gyro, accel, dt, rc)
            # gimbal ALWAYS tracks -- drive both servos every tick, engaged or not
            servo_write_us(args.pan_channel, rad_to_pulse_us(out.servo_pan_rad, +1.0, pi5))
            servo_write_us(args.tilt_channel, rad_to_pulse_us(out.servo_tilt_rad, +1.0, pi5))
            if link is not None:
                try:
                    link.send_set_raw_rc(channels_to_list(out.fc_channels))
                except Exception:
                    pass                  # dropped frame -> FC override failsafe -> RX (pilot)
            time.sleep(max(0.0, dt - (time.monotonic() - t0 - now)))
    finally:
        cam.close()


if __name__ == "__main__":  # pragma: no cover
    main()
