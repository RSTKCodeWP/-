"""Gimbal hardware data-logging + characterization.

The owner's FIRST hardware step is to collect data from the gimbal. This defines the LOG FORMAT and a
`characterize()` that turns a raw log into the numbers that calibrate the controller/plant: gyro
bias & noise, servo max slew rate & command-tracking error, and centroid jitter. Log on hardware in
this format, and the same numbers feed straight back into GimbalConfig / GimbalPlant.

Recommended captures (props OFF):
  * STATIC hold (gimbal still)      -> gyro bias & noise, centroid jitter on a fixed warm target.
  * STEP / fast slew commands       -> servo max rate & tracking error (cmd vs feedback).
  * hand-SHAKE the base             -> stabilisation residual (pointing error while tracking).
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from math import nan
from pathlib import Path
from typing import Optional

import numpy as np

_NAN = float(nan)


@dataclass
class GimbalLogRecord:
    t_ns: int                         # capture time (ns) — share the frame/IMU clock on the real head
    gx: float; gy: float; gz: float   # gyro (rad/s), head IMU
    ax: float; ay: float; az: float   # accel (m/s^2), head IMU
    pan_cmd: float; tilt_cmd: float   # commanded servo angles (rad)
    pan_fb: float = _NAN              # servo feedback angle (rad) if available, else NaN
    tilt_fb: float = _NAN
    cx: float = _NAN; cy: float = _NAN  # target centroid (px), NaN if not detected
    in_fov: bool = False


class GimbalLogger:
    """Accumulate records and write a CSV. Portable: the same schema is emitted by the Zynq/MCU logger."""

    def __init__(self) -> None:
        self.records: list[GimbalLogRecord] = []

    def add(self, rec: GimbalLogRecord) -> None:
        self.records.append(rec)

    def save_csv(self, path: str | Path) -> None:
        cols = [f.name for f in fields(GimbalLogRecord)]
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in self.records:
                w.writerow(asdict(r))


def load_csv(path: str | Path) -> list[GimbalLogRecord]:
    out: list[GimbalLogRecord] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            out.append(GimbalLogRecord(
                t_ns=int(row["t_ns"]),
                gx=float(row["gx"]), gy=float(row["gy"]), gz=float(row["gz"]),
                ax=float(row["ax"]), ay=float(row["ay"]), az=float(row["az"]),
                pan_cmd=float(row["pan_cmd"]), tilt_cmd=float(row["tilt_cmd"]),
                pan_fb=float(row["pan_fb"]), tilt_fb=float(row["tilt_fb"]),
                cx=float(row["cx"]), cy=float(row["cy"]),
                in_fov=row["in_fov"] in ("True", "true", "1")))
    return out


def characterize(records: list[GimbalLogRecord]) -> dict:
    """Recover the numbers that calibrate the controller/plant. Segment-aware interpretation:
    gyro bias/noise are meaningful on a STATIC segment; servo rate/tracking on a STEP/slew segment."""
    if len(records) < 3:
        return {"n": len(records), "error": "need >=3 records"}
    t = np.array([r.t_ns for r in records], dtype=float) * 1e-9
    dt = float(np.median(np.diff(t))) or 0.002
    gyro = np.array([[r.gx, r.gy, r.gz] for r in records])
    out: dict = {"n": len(records), "dt_s": dt, "rate_hz": 1.0 / dt,
                 "gyro_bias_rps": tuple(round(float(v), 5) for v in gyro.mean(axis=0)),
                 "gyro_noise_rps": tuple(round(float(v), 5) for v in gyro.std(axis=0))}
    for axis, (ck, fk) in (("pan", ("pan_cmd", "pan_fb")), ("tilt", ("tilt_cmd", "tilt_fb"))):
        cmd = np.array([getattr(r, ck) for r in records])
        fb = np.array([getattr(r, fk) for r in records])
        if np.isnan(fb).all():
            continue
        out[f"servo_{axis}_rate_max_dps"] = round(float(np.degrees(np.abs(np.diff(fb)).max() / dt)), 1)
        out[f"servo_{axis}_track_rms_deg"] = round(float(np.degrees(np.sqrt(np.mean((cmd - fb) ** 2)))), 3)
    cx = np.array([r.cx for r in records if r.in_fov and r.cx == r.cx])
    if cx.size > 2:
        out["centroid_jitter_px"] = round(float(np.std(cx)), 3)
    return out
