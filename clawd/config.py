from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLAWD_",
        env_file=".env",
        extra="ignore",
    )

    provider: Literal["openai", "anthropic"] = "openai"
    model: str = "qwen2.5-coder:7b"
    api_key: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    db_path: str = "~/.clawd/sessions.db"


class LangfuseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANGFUSE_",
        env_file=".env",
        extra="ignore",
    )

    public_key: str | None = None
    secret_key: str | None = None
    host: str | None = None


settings = Settings()
langfuse_settings = LangfuseSettings()
