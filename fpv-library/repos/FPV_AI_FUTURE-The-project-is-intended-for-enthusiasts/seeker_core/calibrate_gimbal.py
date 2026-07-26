"""Gimbal + head-IMU calibration on the Pi5 (Stage S0). Runs the proven BenchRunner captures on REAL hardware
and prints the characterization the owner sends back to finish Pi5Config:

  * STATIC  (15 s, servos held at centre)  -> gyro bias & noise  -> gyro_scale sanity + bias offsets
  * SERVO STEP (30 deg open-loop step)      -> real servo slew/lag -> servo_us_per_rad, pan_sign/tilt_sign

The gimbal MUST be free to move and have mechanical end-stops. No motors/props involved here — only the 2 small
servos. CSVs land in runs/ ; send them back plus a note of WHICH WAY each axis physically moved on the step.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "/home/admin/seeker/system")
sys.path.insert(0, "/home/admin/seeker/system/fpv")

from fpv.gimbal.bench_runner import BenchRunner
from fpv.gimbal.datalog import characterize
from seeker_core.gimbal_bench_io import Pi5GimbalBenchIO

OUT = os.environ.get("OUT_DIR", "/home/admin/seeker/runs")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    io = Pi5GimbalBenchIO(dt=1 / 200)
    br = BenchRunner(io)
    try:
        print("=" * 66)
        print(" GIMBAL/IMU CALIBRATION (S0).  Gimbal free to move, end-stops present.")
        print("=" * 66)
        print(">>> STATIC (15 s): hold the head STILL. Measuring gyro bias + noise ...")
        static = br.capture_static(seconds=15.0)
        static.save_csv(os.path.join(OUT, "cal_static.csv"))
        print("STATIC:", json.dumps(characterize(static.records), default=str))
        print(">>> SERVO STEP: both axes step +30 deg. WATCH which way pan and tilt physically move ...")
        step = br.capture_servo_step()
        step.save_csv(os.path.join(OUT, "cal_servo_step.csv"))
        print("SERVO_STEP:", json.dumps(characterize(step.records), default=str))
        print("=" * 66)
        print(" DONE. Send me runs/cal_static.csv + runs/cal_servo_step.csv and tell me:")
        print("  - on the +30 deg step, did PAN move LEFT or RIGHT?  did TILT move UP or DOWN?")
        print("  - then rotate the head by hand in yaw / pitch so I can fix gyro_axis_map + signs.")
        print("=" * 66)
    finally:
        io.safe()


if __name__ == "__main__":
    main()
