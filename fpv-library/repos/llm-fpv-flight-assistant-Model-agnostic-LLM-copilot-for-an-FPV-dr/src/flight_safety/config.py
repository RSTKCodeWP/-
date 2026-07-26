from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Limits(BaseModel):
    """Hard safety limits enforced by the validation gate."""
    max_alt_m: float = 120.0      # regulatory-ish ceiling above takeoff
    min_alt_m: float = 0.0
    max_speed_ms: float = 12.0
    max_yaw_rate_dps: float = 90.0   # manual-control yaw-rate cap (deg/s)
    min_battery_pct: float = 0.20  # reject new commands below 20%


class Settings(BaseSettings):
    """Service configuration; values come from env / .env."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FS_", extra="ignore")

    mavlink_address: str = "udpin://0.0.0.0:14540"
    # Geofence as a list of (lat, lon) vertices forming a polygon.
    geofence: list[tuple[float, float]] = Field(default_factory=list)
    limits: Limits = Field(default_factory=Limits)
    command_min_interval_s: float = 1.0  # rate limit between accepted commands
