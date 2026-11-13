from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    database_url: SecretStr
    session_hours: int = Field(default=24, ge=1, le=168)
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout: float = Field(default=90, ge=1, le=100)
    ollama_num_ctx: int = Field(default=4096, ge=2048, le=16384)
    github_owner: str = Field(default="alevkovskiy", validation_alias="GH_OWNER")
    github_repo: str = Field(default="NIRS_VKR", validation_alias="GH_REPO")
    github_token: SecretStr = Field(
        default=SecretStr(""), validation_alias="GH_ACTIONS_TOKEN"
    )

    @property
    def github_configured(self) -> bool:
        return bool(
            self.github_owner
            and self.github_repo
            and self.github_token.get_secret_value()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
