from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def recursive_keys(value: object, prefix: str = "") -> set[str]:
    if not isinstance(value, dict):
        return set()

    # These dictionaries intentionally use language-specific source phrases
    # as keys, so only their container keys must match across locales.
    open_maps = {"runtime.exact", "runtime.replacements"}

    result: set[str] = set()
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        result.add(path)
        if path not in open_maps:
            result.update(recursive_keys(item, path))
    return result


def main() -> int:
    errors: list[str] = []

    python_files = sorted(ROOT.rglob("*.py"))
    for path in python_files:
        if "__pycache__" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as error:
            errors.append(f"Python: {path.relative_to(ROOT)}: {error}")

    json_files = [
        ROOT / "locales/uk.json",
        ROOT / "locales/en.json",
        ROOT / "nyxor_settings.example.json",
    ]
    decoded: dict[Path, object] = {}
    for path in json_files:
        try:
            decoded[path] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"JSON: {path.relative_to(ROOT)}: {error}")

    uk = decoded.get(ROOT / "locales/uk.json")
    en = decoded.get(ROOT / "locales/en.json")
    if isinstance(uk, dict) and isinstance(en, dict):
        uk_keys = recursive_keys(uk)
        en_keys = recursive_keys(en)
        for key in sorted(uk_keys - en_keys):
            errors.append(f"Locale EN missing: {key}")
        for key in sorted(en_keys - uk_keys):
            errors.append(f"Locale UK missing: {key}")

    private_paths = [
        ROOT / "cookies.jar",
        ROOT / "nyxor_settings.json",
        ROOT / "data/events.jsonl",
        ROOT / "data/history.jsonl",
        ROOT / "data/stats.json",
    ]
    for path in private_paths:
        if path.exists():
            errors.append(f"Private/runtime file included: {path.relative_to(ROOT)}")

    if errors:
        print("NYXOR self-check failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"NYXOR self-check passed: {len(python_files)} Python files, 3 JSON files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
