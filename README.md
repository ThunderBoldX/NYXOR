# NYXOR

> **Nyxor — grinds while you sleep.**

NYXOR is a terminal interface for managing timed drop campaigns on Android
through Termux. It provides a queue, progress dashboard, history, journal,
background execution, Android notifications, device telemetry, and Ukrainian
and English localization.

## Features

- terminal-only Textual interface;
- background worker;
- automatic campaign and channel switching;
- priority game queue;
- drop progress and claim history;
- Android notifications;
- battery and Wi-Fi telemetry through Termux:API;
- Ukrainian and English interface;
- language selector in Settings.

## Requirements

- Android;
- Termux;
- Python 3.11 or newer;
- internet connection.

For device telemetry and Android notifications, install the Termux:API
application and package.

## Installation

```bash
pkg install git -y
git clone https://github.com/ThunderBoldX/NYXOR.git
cd NYXOR
bash install.sh
```

## Authentication

Run:

```bash
cd ~/NYXOR
python nyxor_auth.py
```

Follow the Twitch device-login instructions shown in the terminal.

## Start

```bash
nyxor
```

The interface language can be changed under **Settings**.

## Updating

```bash
cd ~/NYXOR
git pull
bash install.sh
```

## Private files

The following files are intentionally excluded from Git:

- `cookies.jar`;
- `nyxor_settings.json`;
- runtime state;
- logs;
- drop history;
- local backups.

Never upload your `cookies.jar`.

## License

NYXOR is released under the MIT License.

Some portions are derived from MIT-licensed third-party code. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Disclaimer

NYXOR is an independent community project and is not affiliated with or
endorsed by Twitch.
