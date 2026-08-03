"""PMW3901 / PAA5100JE optical flow sensor (SPI).

Adapted from Pimoroni pmw3901-python patterns (get_motion, SPI CS) —
https://github.com/pimoroni/pmw3901-python — into an AeroStab module
with a synthetic backend for CI / bench without hardware.
"""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

SENSOR_FOV_DEG = 42.0
SENSOR_PIXELS = 35.0


@dataclass
class PmwMotion:
    dx: int
    dy: int
    quality: float
    dt_s: float


class FlowSensor(ABC):
    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def read_motion(self) -> PmwMotion:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    def velocity_m_s(self, motion: PmwMotion, altitude_m: float) -> Tuple[float, float]:
        if motion.dt_s <= 0 or altitude_m < 0.05:
            return 0.0, 0.0
        scale = math.radians(SENSOR_FOV_DEG) / SENSOR_PIXELS
        fx = (motion.dx * scale) / motion.dt_s
        fy = (motion.dy * scale) / motion.dt_s
        return fx * altitude_m, fy * altitude_m


class SyntheticPmw3901(FlowSensor):
    def __init__(self, vx_m_s: float = 0.15, vy_m_s: float = 0.05, altitude_m: float = 2.0):
        self.vx_m_s = vx_m_s
        self.vy_m_s = vy_m_s
        self.altitude_m = altitude_m
        self._last = 0.0
        self._acc_x = 0.0
        self._acc_y = 0.0

    def start(self) -> None:
        self._last = time.monotonic()
        self._acc_x = 0.0
        self._acc_y = 0.0

    def read_motion(self) -> PmwMotion:
        now = time.monotonic()
        dt = max(1e-3, now - self._last)
        self._last = now
        scale = math.radians(SENSOR_FOV_DEG) / SENSOR_PIXELS
        denom = scale * max(self.altitude_m, 0.1)
        self._acc_x += (self.vx_m_s * dt) / denom
        self._acc_y += (self.vy_m_s * dt) / denom
        dx = int(self._acc_x)
        dy = int(self._acc_y)
        self._acc_x -= dx
        self._acc_y -= dy
        return PmwMotion(dx=dx, dy=dy, quality=0.95, dt_s=dt)

    def stop(self) -> None:
        pass


class HardwarePmw3901(FlowSensor):
    def __init__(
        self,
        chip: str = "pmw3901",
        spi_port: int = 0,
        spi_cs: int = 1,
        spi_cs_gpio: Optional[int] = None,
        rotation: int = 0,
    ):
        self.chip = chip.lower()
        self.spi_port = spi_port
        self.spi_cs = spi_cs
        self.spi_cs_gpio = spi_cs_gpio
        self.rotation = rotation % 360
        self._sensor = None
        self._last = 0.0

    def start(self) -> None:
        try:
            from pmw3901 import PMW3901, PAA5100  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pmw3901 package required for hardware sensor. Install: pip install pmw3901"
            ) from exc

        kwargs = {"spi_port": self.spi_port, "spi_cs": self.spi_cs}
        if self.spi_cs_gpio is not None:
            kwargs["spi_cs_gpio"] = self.spi_cs_gpio

        cls = PAA5100 if self.chip in ("paa5100", "paa5100je") else PMW3901
        self._sensor = cls(**kwargs)
        if hasattr(self._sensor, "set_rotation"):
            self._sensor.set_rotation(self.rotation)
        self._last = time.monotonic()
        logger.info("PMW3901 hardware started (%s)", self.chip)

    def read_motion(self) -> PmwMotion:
        if self._sensor is None:
            return PmwMotion(0, 0, 0.0, 0.0)
        now = time.monotonic()
        dt = max(1e-3, now - self._last)
        self._last = now
        try:
            dx, dy = self._sensor.get_motion()
        except Exception as exc:
            logger.warning("PMW3901 read failed: %s", exc)
            return PmwMotion(0, 0, 0.0, dt)
        mag = abs(dx) + abs(dy)
        quality = min(1.0, 0.3 + mag / 40.0) if mag else 0.2
        return PmwMotion(int(dx), int(dy), quality, dt)

    def stop(self) -> None:
        self._sensor = None


def create_pmw_sensor(cfg, simulate: bool = False) -> Optional[FlowSensor]:
    if not getattr(cfg, "enabled", False):
        return None
    if simulate or getattr(cfg, "backend", "auto") == "synthetic":
        sensor = SyntheticPmw3901()
        sensor.start()
        return sensor
    sensor = HardwarePmw3901(
        chip=getattr(cfg, "chip", "pmw3901"),
        spi_port=getattr(cfg, "spi_port", 0),
        spi_cs=getattr(cfg, "spi_cs", 1),
        spi_cs_gpio=getattr(cfg, "spi_cs_gpio", None),
        rotation=getattr(cfg, "rotation_deg", 0),
    )
    sensor.start()
    return sensor
