from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID

from .config import settings
from .models import StoredGeneration


def data_dir() -> Path:
    path = Path(os.getenv("TESTFORGE_DATA_DIR", settings.data_dir))
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(generation: StoredGeneration) -> StoredGeneration:
    target = data_dir() / f"{generation.id}.json"
    target.write_text(generation.model_dump_json(indent=2), encoding="utf-8")
    return generation


def get(generation_id: UUID) -> StoredGeneration | None:
    target = data_dir() / f"{generation_id}.json"
    if not target.exists():
        return None
    return StoredGeneration.model_validate_json(target.read_text(encoding="utf-8"))


def list_all() -> list[StoredGeneration]:
    result = []
    for target in data_dir().glob("*.json"):
        try:
            result.append(StoredGeneration.model_validate_json(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            continue
    return sorted(result, key=lambda item: item.created_at, reverse=True)
