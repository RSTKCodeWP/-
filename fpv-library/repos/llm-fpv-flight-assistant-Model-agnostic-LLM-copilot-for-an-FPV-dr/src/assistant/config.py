from pydantic_settings import BaseSettings, SettingsConfigDict


class AssistantSettings(BaseSettings):
    """Assistant config from env / .env (prefix AS_)."""
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AS_", extra="ignore")

    openrouter_api_key: str = ""
    model: str = "google/gemini-2.0-flash-001"   # any OpenRouter model id
    base_url: str = "https://openrouter.ai/api/v1"
    safety_url: str = "ws://127.0.0.1:8765/ws"
