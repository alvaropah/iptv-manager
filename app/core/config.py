import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    xtream_host: str = os.getenv("XTREAM_HOST", "").strip().rstrip("/")
    xtream_username: str = os.getenv("XTREAM_USERNAME", "").strip()
    xtream_password: str = os.getenv("XTREAM_PASSWORD", "").strip()
    database_path: str = os.getenv("DATABASE_PATH", "data/iptv_manager.db")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))


settings = Settings()
