from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
LOCALES_DIR = BASE_DIR / "locales"
SETTINGS_PATH = BASE_DIR / "nyxor_settings.json"
DEFAULT_LOCALE = "uk"

_cache: dict[str, dict[str, Any]] = {}


def _load(locale: str) -> dict[str, Any]:
    if locale in _cache:
        return _cache[locale]

    path = LOCALES_DIR / f"{locale}.json"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}

    if not isinstance(data, dict):
        data = {}

    _cache[locale] = data
    return data


def _locale_from_settings() -> str | None:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    value = data.get("language")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def current_locale() -> str:
    env_locale = os.environ.get("NYXOR_LANG")

    if isinstance(env_locale, str) and env_locale.strip():
        return env_locale.strip()

    return _locale_from_settings() or DEFAULT_LOCALE


def set_locale(locale: str) -> None:
    os.environ["NYXOR_LANG"] = locale


def value(key: str, default: Any = None, locale: str | None = None) -> Any:
    data: Any = _load(locale or current_locale())

    for part in key.split("."):
        if not isinstance(data, dict) or part not in data:
            return default
        data = data[part]

    return data


def tr(
    key: str,
    default: str | None = None,
    locale: str | None = None,
    **kwargs: Any,
) -> str:
    result = value(key, default if default is not None else key, locale)

    if not isinstance(result, str):
        result = default if default is not None else key

    try:
        return result.format(**kwargs)
    except (KeyError, ValueError):
        return result


def _uk_form(count: int | float) -> str:
    if not float(count).is_integer():
        return "other"

    number = abs(int(count))
    last_two = number % 100
    last = number % 10

    if last == 1 and last_two != 11:
        return "one"
    if 2 <= last <= 4 and not 12 <= last_two <= 14:
        return "few"
    return "many"


def _en_form(count: int | float) -> str:
    return "one" if float(count) == 1 else "other"


def _plural_form(locale: str, count: int | float) -> str:
    language = locale.lower().split("-", 1)[0].split("_", 1)[0]

    if language == "en":
        return _en_form(count)

    return _uk_form(count)


def plural(
    key: str,
    count: int | float,
    locale: str | None = None,
    **kwargs: Any,
) -> str:
    selected_locale = locale or current_locale()
    forms = value(key, {}, selected_locale)

    if not isinstance(forms, dict):
        return str(count)

    form = _plural_form(selected_locale, count)
    template = forms.get(form) or forms.get("other") or str(count)

    try:
        return str(template).format(count=count, **kwargs)
    except (KeyError, ValueError):
        return str(template)


def localize_battery_status(status: Any) -> str:
    if not status:
        return ""

    key = str(status).upper()
    return tr(f"battery_status.{key}", default=str(status))


def localize_runtime_message(message: Any) -> str:
    text = str(message or "").strip()

    if not text:
        return ""

    if "PersistedQueryNotFound" in text:
        return tr("errors.persisted_query")

    normalized = text.casefold()
    waiting_markers = ("waiting", "чекаю", "очікую")
    drop_markers = ("drop", "дроп")
    channel_markers = ("channel", "канал")
    online_markers = ("online", "онлайн", "у мережі")

    if (
        any(marker in normalized for marker in waiting_markers)
        and any(marker in normalized for marker in drop_markers)
        and any(marker in normalized for marker in channel_markers)
        and any(marker in normalized for marker in online_markers)
    ):
        return tr("runtime.waiting_for_drops")

    exact = value("runtime.exact", {})
    if isinstance(exact, dict) and text in exact:
        return str(exact[text])

    replacements = value("runtime.replacements", {})
    if isinstance(replacements, dict):
        # Довші фрагменти замінюємо першими.
        for source, target in sorted(
            replacements.items(),
            key=lambda item: len(str(item[0])),
            reverse=True,
        ):
            text = text.replace(str(source), str(target))

    text = re.sub(
        r"^GQL error:\s*",
        tr("errors.gql_prefix") + ": ",
        text,
        flags=re.IGNORECASE,
    )

    return text
