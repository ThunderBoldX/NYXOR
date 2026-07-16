from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nyxor.paths import SETTINGS_PATH


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default

def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)

def load_settings() -> dict[str, Any]:
    data = load_json(SETTINGS_PATH, {})
    return data if isinstance(data, dict) else {}

def save_settings(settings: dict[str, Any]) -> None:
    atomic_write_json(SETTINGS_PATH, settings)

def load_queue() -> list[str]:
    settings = load_settings()
    raw_queue = settings.get("priority_games")

    if isinstance(raw_queue, list):
        queue = [
            item.strip()
            for item in raw_queue
            if isinstance(item, str) and item.strip()
        ]
    else:
        single = settings.get("priority_game")
        queue = [single.strip()] if isinstance(single, str) and single.strip() else []

    return list(dict.fromkeys(queue))

def save_queue(queue: list[str]) -> None:
    settings = load_settings()
    settings["priority_games"] = queue

    if queue:
        settings["priority_game"] = queue[0]
    else:
        settings.pop("priority_game", None)

    preferred = settings.get("preferred_channel")
    if isinstance(preferred, dict):
        preferred_game = preferred.get("game")
        if preferred_game and preferred_game not in queue:
            settings.pop("preferred_channel", None)

    save_settings(settings)

def load_jsonl(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    items: list[dict[str, Any]] = []

    for line in lines[-limit:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(item, dict):
            items.append(item)

    return items
