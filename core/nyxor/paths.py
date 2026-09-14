from __future__ import annotations

from pathlib import Path
import os


SOURCE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = Path(os.environ.get("NYXOR_DATA_DIR", str(SOURCE_DIR.parent / ".local")))
LOCALES_DIR = (BASE_DIR / "locales") if "NYXOR_DATA_DIR" in os.environ else Path(__file__).resolve().parent / "locales"

SETTINGS_PATH = BASE_DIR / "nyxor_settings.json"

RUNTIME_DIR = BASE_DIR / "runtime"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

STATE_PATH = RUNTIME_DIR / "state.json"
LOG_PATH = LOG_DIR / "nyxor.log"
HISTORY_PATH = DATA_DIR / "history.jsonl"
EVENTS_PATH = DATA_DIR / "events.jsonl"
STATS_PATH = DATA_DIR / "stats.json"


def ensure_directories() -> None:
    for path in (RUNTIME_DIR, DATA_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
