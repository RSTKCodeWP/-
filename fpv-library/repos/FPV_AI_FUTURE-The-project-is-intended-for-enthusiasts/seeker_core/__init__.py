"""seeker_core — a clean-room, hardware-agnostic seeker (ГСН) core: sensor in -> actuator commands out.

See README.md. This Python package is the golden reference; an FPGA/C implementation must be bit-exact.
"""
from seeker_core.contracts import SCHEMA_VERSION  # noqa: F401

__all__ = ["SCHEMA_VERSION"]
