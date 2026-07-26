from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardSettings(BaseSettings):
    """Dashboard backend config from env / .env (prefix DASH_)."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DASH_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    safety_url: str = "ws://127.0.0.1:8765/ws"
    video_stream_url: str = "http://127.0.0.1:8082/stream.mjpg"
    video_health_url: str = "http://127.0.0.1:8082/health"
    video_poll_interval_s: float = 2.0
