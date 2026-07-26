from pydantic_settings import BaseSettings, SettingsConfigDict


class VideoBridgeSettings(BaseSettings):
    """Video-bridge config from env / .env (prefix VB_)."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VB_", extra="ignore")

    topic: str = ""           # gz camera image topic; set from the Task 1 spike
    host: str = "0.0.0.0"
    port: int = 8082
    jpeg_quality: int = 80
    channels: int = 3         # 3=RGB, 4=RGBA
