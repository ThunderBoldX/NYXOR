<div align="center">

[🇺🇦 Українська](README.md) | **🇬🇧 English**

<br>

# ⚡ NYXOR

### **Nyxor — grinds while you sleep.**

A terminal assistant for automatically earning **Twitch Drops**  
on Android through **Termux**.

<br>

[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Termux-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://termux.dev/)
[![Languages](https://img.shields.io/badge/Language-UA%20%7C%20EN-2563EB?style=for-the-badge)](#languages)
[![License](https://img.shields.io/badge/License-Custom-8B5CF6?style=for-the-badge)](LICENSE)

[![Last commit](https://img.shields.io/github/last-commit/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR/commits/main)
[![Repo size](https://img.shields.io/github/repo-size/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR)
[![Issues](https://img.shields.io/github/issues/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR/issues)
[![Stars](https://img.shields.io/github/stars/ThunderBoldX/NYXOR?style=flat-square&logo=github)](https://github.com/ThunderBoldX/NYXOR/stargazers)

<br>

[About NYXOR](#about) •
[Features](#features) •
[Installation](#installation) •
[Launch](#launch) •
[Update](#update) •
[Privacy](#privacy) •
[License](#license)

</div>

---

<a id="about"></a>

## 🌙 What is NYXOR?

**NYXOR** is an Android app for automatically earning **Twitch Drops** through **Termux**.

It is made for people who want rewards from Twitch streams without keeping Twitch open all the time or checking the progress manually.

Launch NYXOR, choose the campaign you need, and continue with your day. The app runs in the terminal and shows what is happening with your Drops progress.

NYXOR is made specifically for phones: no heavy interface, unnecessary windows, or complicated setup.

> **Launch it, choose a game, and farm Drops.**

---

<a id="features"></a>

## ✨ Features

| Feature | Description |
|---|---|
| 🎁 **Twitch Drops** | Works with available Twitch Drops campaigns and rewards |
| 📺 **Automation** | Reduces the number of manual actions needed to find and watch suitable streams |
| 📊 **Terminal progress** | Shows a clear status without a browser or graphical interface |
| 📱 **Built for Termux** | The interface and launch process are optimized for Android and Termux |
| 🌐 **Ukrainian and English** | Switch languages without installing a separate version |
| 💾 **Local settings** | Settings and session data are stored only on your device |
| 🧾 **Logs** | Logs help you check the app status and find the cause of an error |
| ⚙️ **Simple installation** | The main setup is handled by `install.sh` |
| 🧩 **Independent project** | The code, file names, and interface are organized under the NYXOR brand |

---

<a id="installation"></a>

## 📦 Installation

### 1. Update Termux packages

```bash
pkg update -y && pkg upgrade -y
```

### 2. Install Git

```bash
pkg install git -y
```

### 3. Clone NYXOR

```bash
git clone https://github.com/ThunderBoldX/NYXOR.git
```

### 4. Open the project folder

```bash
cd NYXOR
```

### 5. Allow the installer to run

```bash
chmod +x install.sh
```

### 6. Start the installation

```bash
./install.sh
```

The installer will prepare the required components and check your Termux environment.

---

<a id="launch"></a>

## 🚀 Launch

```bash
cd ~/NYXOR
./NYXOR
```

When the app opens for the first time, complete the initial setup and choose your preferred interface language.

---

<a id="update"></a>

## 🔄 Update

To download the latest changes from GitHub:

```bash
cd ~/NYXOR
git pull
./install.sh
```

Then launch NYXOR as usual:

```bash
./NYXOR
```

---

## 🗑️ Uninstall

To completely remove the app together with its local data:

```bash
rm -rf ~/NYXOR
```

> ⚠️ This command permanently deletes the NYXOR folder, settings, session data, history, and local logs.

---

<a id="languages"></a>

## 🌍 Languages

NYXOR supports:

- 🇺🇦 **Ukrainian**
- 🇬🇧 **English**

You can change the language in the app settings.

---

<a id="privacy"></a>

## 🔐 Privacy and local data

NYXOR creates service files directly on your device. They should not be uploaded to GitHub or shared with other people.

Private or temporary files may include:

```text
cookies.jar
nyxor_settings.json
logs/
history/
*.log
*.pid
__pycache__/
backup/
```

These files are excluded from the repository through `.gitignore`.

> **Never publish `cookies.jar` or other session files.**  
> Someone who gets them may be able to use your active session.

NYXOR does not require you to publish your Twitch password in the repository. All personal user data should stay only on the user's device.

---

## 📁 Repository structure

```text
NYXOR/
├── NYXOR                    # app launcher
├── install.sh               # installation and environment setup
├── README.md                # Ukrainian documentation
├── README_EN.md             # English documentation
├── CHANGELOG.md             # update history
├── LICENSE                  # terms of use
├── THIRD_PARTY_NOTICES.md   # information about third-party components
└── .gitignore               # excludes private and temporary files
```

The internal structure may grow as the project develops.

---

## 🛠️ Troubleshooting

<details>
<summary><strong>Permission denied when launching</strong></summary>

Give the files permission to run:

```bash
cd ~/NYXOR
chmod +x NYXOR install.sh
./NYXOR
```

</details>

<details>
<summary><strong>Git command not found</strong></summary>

Install Git:

```bash
pkg update -y
pkg install git -y
```

</details>

<details>
<summary><strong>The app does not start after an update</strong></summary>

Run the installer again:

```bash
cd ~/NYXOR
git pull
chmod +x install.sh NYXOR
./install.sh
```

</details>

<details>
<summary><strong>The Twitch session stopped working</strong></summary>

Sessions may expire or become invalid. Open NYXOR and sign in again using the method provided by the app. Do not send your session file to other people.

</details>

<details>
<summary><strong>Where can I find the cause of an error?</strong></summary>

Check the messages in the terminal and the local logs. Before publishing an error report, remove tokens, cookies, session IDs, and any other private data.

</details>

---

## 🗺️ Roadmap

- [x] Terminal interface for Termux
- [x] Ukrainian and English languages
- [x] Local settings storage
- [x] Separate installer
- [ ] Better stability
- [ ] Clearer error messages
- [ ] More detailed campaign statistics
- [ ] Notifications when the status changes or a task is completed
- [ ] Proper GitHub Releases

---

## 🤝 Feedback

Found a bug or have an idea?

1. Check whether a similar report already exists in [Issues](https://github.com/ThunderBoldX/NYXOR/issues).
2. Create a new Issue.
3. Add your Android version, Termux version, and the steps needed to reproduce the problem.
4. Do not attach cookies, tokens, passwords, or private logs.

Pull Requests are also welcome as long as the changes do not break the project license or the rules of third-party components.

---

<a id="license"></a>

## ⚖️ License and third-party components

NYXOR is distributed under the terms listed in [`LICENSE`](LICENSE).

Information about third-party components, their authors, and their licenses is available in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

**Copyright © 2026 ThunderBoldX**

---

## ⚠️ Disclaimer

NYXOR is an independent unofficial project and is not connected with, approved by, or supported by Twitch Interactive, Inc.

The Twitch name, Twitch Drops, logos, and related trademarks belong to their respective owners.

The app may change or temporarily stop working because of Twitch updates, API changes, platform rules, or authorization changes. The user is responsible for how the app is used and for following the rules of the related services.

---

<div align="center">

### ⭐ Like NYXOR?

Give the repository a star — it helps the project grow.

<br>

**Built for Termux. Powered by the night.**

`NYXOR · grinds while you sleep`

</div>
