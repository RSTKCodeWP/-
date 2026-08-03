"""Sensor backends (PMW3901 / PAA5100JE)."""

from aerostab.sensors.pmw3901 import (
    FlowSensor,
    HardwarePmw3901,
    PmwMotion,
    SyntheticPmw3901,
    create_pmw_sensor,
)

__all__ = [
    "FlowSensor",
    "HardwarePmw3901",
    "PmwMotion",
    "SyntheticPmw3901",
    "create_pmw_sensor",
]
