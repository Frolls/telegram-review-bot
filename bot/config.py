from __future__ import annotations

from typing import Annotated

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    backend_url: AnyHttpUrl = Field(alias="BACKEND_URL")
    internal_token: str = Field(default="changeme", alias="INTERNAL_TOKEN")
    bot_api_port: int = Field(default=8081, alias="BOT_API_PORT")
    bot_admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        alias="BOT_ADMIN_IDS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("bot_admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, list):
            return [int(item) for item in value]
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                value = value[1:-1]
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if not value:
            return []
        return value


settings = Settings()
