"""Golden reference vectors + (future) fixed-point reference models for the PL detect IP.

The Python float detector (``fpv.seeker.detect.detect_frame``) is the reference.  This package
replays it over deterministic scenes and freezes the (frame -> expected detect output) pairs the
Vitis HLS / RTL testbench consumes, plus the physical ground truth the detect IP must track.
"""

from fpga.ref_model.golden_vectors import (
    GOLDEN_SCENES,
    GoldenScene,
    FrameRecord,
    generate_scene,
    write_vectors,
)

__all__ = [
    "GOLDEN_SCENES",
    "GoldenScene",
    "FrameRecord",
    "generate_scene",
    "write_vectors",
]
