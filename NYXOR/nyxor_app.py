from __future__ import annotations

from nyxor.paths import ensure_directories
from nyxor.ui.app import NyxorApp


def main() -> None:
    ensure_directories()
    NyxorApp().run()


if __name__ == "__main__":
    main()
