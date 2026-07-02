"""Конфигурация бота - только токен и строка подключения к БД."""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")

    @classmethod
    def validate(cls) -> list[str]:
        errors = []
        if not cls.TOKEN:
            errors.append("DISCORD_TOKEN не задан в .env")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL не задан в .env")
        return errors
