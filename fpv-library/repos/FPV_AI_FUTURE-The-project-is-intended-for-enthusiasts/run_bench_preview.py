"""Launcher for the seeker bench dashboard in SIM mode (digital twin of the FPGA pipeline on the Mac).

Runs the SAME Python seeker the RTL/C blocks reproduce bit-exactly, on a synthetic moving-target
thermal scene, and serves the annotated video + live telemetry at http://127.0.0.1:8092.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "fpv"))

from fpv_ai.bench.observer import ObserverConfig       # noqa: E402
from fpv_ai.bench.sim_source import SimFrameSource      # noqa: E402
from fpv_ai.bench.server import run                     # noqa: E402

run(ObserverConfig(hfov_deg=48.7, border_crop=0, mask_on=False),
    host="127.0.0.1", port=8092, source=SimFrameSource(mode="sweep"))
