"""Bot configuration - token and database connection string."""

import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "!")
    PROXY_URL: str = os.getenv("PROXY_URL", "")  # socks5://host:port or http://host:port

    @classmethod
    def validate(cls) -> list[str]:
        errors = []
        if not cls.TOKEN:
            errors.append("DISCORD_TOKEN not set in .env")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL not set in .env")
        return errors
