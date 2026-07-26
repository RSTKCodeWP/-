from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, TypeAdapter


class Telemetry(BaseModel):
    """Snapshot of vehicle state used by the validation gate and narration."""
    lat: float
    lon: float
    alt_m: float           # relative altitude above takeoff
    speed_ms: float
    battery_pct: float     # 0.0–1.0
    flight_mode: str
    armed: bool
    gps_ok: bool
    ekf_ok: bool
    roll: float = 0.0      # degrees
    pitch: float = 0.0     # degrees
    yaw: float = 0.0       # degrees


# --- Command schema (the structured-output contract) ---
class ArmTakeoffCommand(BaseModel):
    verb: Literal["arm_takeoff"]
    alt: float = Field(gt=0, le=120)


class GotoCommand(BaseModel):
    verb: Literal["goto"]
    lat: float
    lon: float
    alt: float = Field(gt=0, le=120)


class OrbitCommand(BaseModel):
    verb: Literal["orbit"]
    radius: float = Field(gt=0, le=200)
    alt: float = Field(gt=0, le=120)
    center: Optional[tuple[float, float]] = None  # (lat, lon); None = current pos


class LoiterCommand(BaseModel):
    verb: Literal["loiter"]


class ReturnToLaunchCommand(BaseModel):
    verb: Literal["return_to_launch"]


class LandCommand(BaseModel):
    verb: Literal["land"]


class TakeoverCommand(BaseModel):
    verb: Literal["takeover"]


class HandbackCommand(BaseModel):
    verb: Literal["handback"]


Command = Annotated[
    Union[
        ArmTakeoffCommand, GotoCommand, OrbitCommand, LoiterCommand,
        ReturnToLaunchCommand, LandCommand, TakeoverCommand, HandbackCommand,
    ],
    Field(discriminator="verb"),
]

_ADAPTER: TypeAdapter[Command] = TypeAdapter(Command)


def parse_command(data: dict) -> Command:
    """Validate raw dict into a typed Command (raises ValidationError on bad input)."""
    return _ADAPTER.validate_python(data)
