from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _int_env("PORT", 8000)
    data_dir: str = os.getenv("TESTFORGE_DATA_DIR", ".testforge-data")
    allowed_hosts: tuple[str, ...] = tuple(filter(None, (item.strip() for item in os.getenv("ALLOWED_HOSTS", "*").split(","))))
    max_request_bytes: int = _int_env("MAX_REQUEST_BYTES", 262_144)
    rate_limit_per_minute: int = _int_env("RATE_LIMIT_PER_MINUTE", 60)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
