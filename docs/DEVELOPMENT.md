# Development

[README](../README.md) · [Українська](../README_UK.md)

```text
android/           Android app, embedded UI, native tests and Gradle wrapper
core/              Shared Python farming engine
  nyxor/           Runtime adapter, selection, storage and localization
    locales/       English and Ukrainian engine messages
docs/              Guides, screenshots, changelog and source checksums
tests/             Python unit and integration tests
tools/             Developer diagnostics and source checks
README.md          English project overview
README_UK.md       Ukrainian project overview
pyproject.toml     Python package metadata and dependencies
LICENSE
```

Android builds copy Python from `core/` and localization assets from `core/nyxor/locales/`. The Android service owns notifications, wake locks and startup after reboot. The previous terminal UI, shell installers and process launcher have been removed.

## Local checks

Use Python 3.12. From the repository root, create a virtual environment and install `core/requirements.txt`. No Twitch login is required for the tests.

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r core/requirements.txt
$env:PYTHONPATH = (Resolve-Path core).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/nyxor_self_check.py
```

On macOS or Linux, for development:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r core/requirements.txt
PYTHONPATH=core .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/nyxor_self_check.py
```

These commands run developer checks; the available user application is the Android APK.

## Android build

See the [Android build requirements](../android/README.md#збірка-з-вихідного-коду), then run:

```sh
cd android
./gradlew :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
```

On Windows use `gradlew.bat`. The output is `android/app/build/outputs/apk/debug/app-debug.apk` relative to the repository root.

## Data and diagnostics

Android sets `NYXOR_DATA_DIR` to its private storage directory before loading the engine. Desktop diagnostics default to `.local/` in the repository; this directory is excluded from Git. Moving the source files does not change installed Android account storage.

Optional diagnostics in `tools/` use real Twitch requests and require a local authorized session. They are for development, not installation on a phone:

```sh
python tools/nyxor_auth.py
python tools/nyxor_hls_test.py CHANNEL_LOGIN
python tools/nyxor_points_probe.py CHANNEL_LOGIN --minutes 20
```

Keep `.local/`, cookies, logs, settings and signing keys private. Source checksums are stored in `docs/CHECKSUMS.txt` with paths relative to the repository root.
