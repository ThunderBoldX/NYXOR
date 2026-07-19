<div align="center">

[🇺🇦 Українська](README.md) | **🇬🇧 English**

# ⚡ NYXOR

### **Nyxor — grinds while you sleep.**

Terminal automation for **Twitch Drops** and **Channel Points**  
on Android through **Termux**.

[![Version](https://img.shields.io/badge/version-1.0.0-7C3AED?style=for-the-badge)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/Android-Termux-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://termux.dev/)
[![Languages](https://img.shields.io/badge/UA-English-2563EB?style=for-the-badge)](#-languages)
[![License](https://img.shields.io/badge/License-MIT-8B5CF6?style=for-the-badge)](LICENSE)

</div>

---

## 🌙 What NYXOR does

NYXOR runs one lightweight Twitch HLS player and automatically chooses what to farm:

1. **Drops always have the highest priority.**
2. When no active Drops are available, NYXOR watches the first online channel from the **Streamers** tab and farms Channel Points.
3. When Drops become available again, NYXOR automatically switches back.

The application does not run two parallel streams and does not require the browser to remain open after authentication.

## ✨ Features

| Feature | Status |
|---|---|
| 🎁 Twitch Drops discovery, progress and automatic claim | ✅ |
| 🎮 Prioritized game list | ✅ |
| 🔎 Live search for exact Twitch categories | ✅ |
| 📺 Prioritized streamer list for Channel Points | ✅ |
| 🔁 Automatic Drops ↔ Channel Points fallback | ✅ |
| 🎬 One low-quality HLS player | ✅ |
| 💰 Channel Points earning | ✅ |
| 🎁 Automatic bonus chest claim | ✅ |
| 🔥 Watch Streak tracking | Experimental |
| 🎭 Raid following without interrupting Drops | Experimental |
| 🎬 Automatic Moments claim | Experimental |
| 🔮 Predictions with spending limits | Experimental, disabled by default |
| 🌍 Ukrainian and English UI | ✅ |
| 📊 Dashboard, journal, history and local statistics | ✅ |
| 🔋 Wake lock and optional Termux:API telemetry | ✅ |

## 📦 Installation

> Use a current Termux build from F-Droid or GitHub rather than the outdated Google Play build.

```bash
pkg update -y && pkg upgrade -y
pkg install git -y
git clone https://github.com/ThunderBoldX/NYXOR.git
cd NYXOR
chmod +x install.sh
./install.sh
```

## 🔐 First authentication

```bash
cd ~/NYXOR
python nyxor_auth.py
```

NYXOR displays a Twitch device code and opens the authorization page. The authenticated session is stored locally in `cookies.jar`.

## 🚀 Launch

```bash
nyxor
```

Inside the application:

- add Twitch categories in the **Games** tab;
- add fallback channels in the **Streamers** tab;
- press **Start** on the dashboard.

## ⚙️ Selection logic

```text
Active Drops?
├─ Yes → select the highest-priority game → find a channel → farm Drops + Points
└─ No  → find the first online streamer → farm Channel Points

During a cycle:
HLS → minute-watched → balance → bonus claim → PubSub events
```

## 🔮 Predictions

Automatic Predictions are **disabled by default** because they spend Channel Points.

Default conservative profile:

```json
{
  "enabled": false,
  "strategy": "most_voted",
  "percentage": 2,
  "max_points": 1000,
  "minimum_balance": 5000,
  "reserve_points": 3000,
  "seconds_before_close": 20
}
```

The values can be changed in `nyxor_settings.json`. Review `max_points` and `reserve_points` before enabling Predictions.

## 🧪 Diagnostics

Test HLS on an online channel:

```bash
cd ~/NYXOR
python nyxor_hls_test.py LOGIN
```

Seven-minute Channel Points test:

```bash
python nyxor_points_probe.py LOGIN
```

Longer test:

```bash
python nyxor_points_probe.py LOGIN --minutes 20
```

Logs and state:

```bash
tail -n 150 ~/NYXOR/logs/nyxor.log
cat ~/NYXOR/runtime/state.json
```

## 🔄 Update

```bash
cd ~/NYXOR
git pull
./install.sh
```

`cookies.jar`, `nyxor_settings.json`, history and local logs are ignored by Git and should remain untouched during a normal update.

## 🗑️ Remove the command

```bash
cd ~/NYXOR
./uninstall.sh
```

This removes the `nyxor` command but keeps the project folder and private data. To remove everything:

```bash
rm -rf ~/NYXOR
```

## 🔐 Privacy

Never publish or share:

```text
cookies.jar
nyxor_settings.json
logs/
runtime/
data/
backups/
```

`cookies.jar` contains an active Twitch session. These files are excluded through `.gitignore`.

## 📁 Main structure

```text
NYXOR/
├── nyxor_app.py                 # terminal UI
├── nyxor_core.py                # Drops + Points main loop
├── nyxor_player.py              # Twitch HLS
├── nyxor_points.py              # balance and bonus chests
├── nyxor_rewards.py             # PubSub, streak, raids, Moments, Predictions
├── nyxor_auth.py                # Twitch authentication
├── nyxor_hls_test.py            # HLS diagnostics
├── nyxor_points_probe.py        # Channel Points test
├── nyxor/                       # UI, localization, storage and runtime
├── locales/                     # Ukrainian and English translations
├── install.sh
└── nyxor_settings.example.json
```

## 🌍 Languages

- 🇺🇦 Ukrainian
- 🇬🇧 English

Change the language in **Settings**, then restart the interface.

## ⚠️ Important

NYXOR is an independent unofficial project and is not affiliated with Twitch Interactive, Inc. Twitch may change its APIs, persisted queries, HLS or reward mechanisms, which can temporarily break individual features.

Automation may conflict with platform rules. You are responsible for using the application and for any account-related risk.

## ⚖️ License

NYXOR is distributed under the [MIT License](LICENSE). Some code is derived from MIT-licensed components; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<div align="center">

**Built for Termux. Powered by the night.**

`NYXOR · grinds while you sleep`

</div>
