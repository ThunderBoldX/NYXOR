from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = BASE_DIR / "nyxor"
LOCALES_DIR = BASE_DIR / "locales"

SETTINGS_PATH = BASE_DIR / "nyxor_settings.json"
CORE_PATH = BASE_DIR / "nyxor_core.py"
WORKER_PATH = BASE_DIR / "nyxor_worker.py"

RUNTIME_DIR = BASE_DIR / "runtime"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

PID_PATH = RUNTIME_DIR / "nyxor.pid"
STATE_PATH = RUNTIME_DIR / "state.json"
LOG_PATH = LOG_DIR / "nyxor.log"
HISTORY_PATH = DATA_DIR / "history.jsonl"
EVENTS_PATH = DATA_DIR / "events.jsonl"
STATS_PATH = DATA_DIR / "stats.json"


def ensure_directories() -> None:
    for path in (RUNTIME_DIR, DATA_DIR, LOG_DIR):
        path.mkdir(parents=True, exist_ok=True)
