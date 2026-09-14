## Android 2.2 preview — moon branding and Channel Points

- Replace the mobile wordmark and N icon with a crescent moon and “Nyxor — grinds while you sleep”. Use a monochrome moon for notifications.
- Resize the WebView inside native system-bar, keyboard and cutout insets so fixed navigation stays above Android buttons and gestures.
- Add a Points section with a separate game queue, live channel directory, viewer-count sorting and per-account watched-channel history.
- Track observed positive balance changes during confirmed playback; existing balances and time outside a watch session are excluded. History starts with this update.
- Reload channel/game settings each cycle, interrupt idle waits on edits, and keep checking points channels if Drops discovery fails.
- Restrict raid joins and destinations to configured points streamers or games. Recheck channel category before selecting from cached directories.
- Display actual channel reward names, prices and availability below Drops progress. Redemption is performed on Twitch.
- Least-viewed discovery paginates the Twitch directory within a bounded scan; partial results are labeled. Live Twitch authentication and physical-device verification are still required for end-to-end confirmation.

## Android 2.1 preview — boot start and background status

- Added an opt-in boot-start switch, boot receiver and sticky foreground service. Explicit stop clears restart intent; boot start is controlled separately by its switch.
- Keep the service alive when the recent-apps task is removed, serialize service teardown/startup and wait for connectivity at startup.
- Show public lock-screen status with game, channel and drop progress; refresh every 15 seconds and when the screen wakes.
- Added shortcuts to app battery and notification settings. Android force-stop and vendor cleaner restrictions still apply.

## Android 2.0.2 preview — offline check and activation guidance

- Check Android connectivity before requesting a Twitch device code; show offline/captive-network status across screens and update it when the connection changes.
- Add an explicit copy-code button and instructions for approving the same code on a phone or PC.
- User confirmed login works when the code is entered on a PC and that the earlier DNS error was caused by disabled connectivity. The phone-browser activation failure remains unconfirmed.

## Android 2.0.1 preview — network recovery

- Added Android DNS fallback and a bounded retry for failed hostname lookups across login, search and farming. System network settings and HTTPS validation remain in use.
- Added localized connection errors and a token-free Twitch connection check on the login screen.
- Incremented APK version code to support installation over the previous preview. Real-device confirmation of the reported DNS failure is still required.

## Android 2.0 preview — standalone application

- Added an Android APK with an embedded Python miner, Twitch device-code login and private app storage. Termux is not required.
- Added a local graphical interface with rounded cards, animated progress, transitions, haptic feedback and bottom navigation.
- Added an Android foreground service, renewable wake lock, persistent notification and stop action.
- Preserved shared-campaign channel selection and added tests for embedded startup, settings, authentication guards and cancellation.
- Build verified; real-device authentication, reward accrual and overnight operation still require device testing.

## Unreleased — Termux dashboard and shared campaign channels

- Redesigned the dashboard with a compact status card, per-campaign reward progress, a Channel Points card and pinned Start/Stop/Restart controls.
- Added Ukrainian and English labels, narrow-terminal spacing and scrollable Settings; moved connection and extra reward details into an expandable section.
- Prefer live channels covering the most unfinished, eligible campaigns within the highest-priority game. Streamer preferences remain tie-breakers.
- Discover campaign-restricted streamers outside the directory's first 30 results and verify their available campaigns.
- Respect campaign channel restrictions, campaign/drop time windows and claimed prerequisites when selecting rewards. Display progress only for the selected channel.
- Added offline regression tests and Textual smoke tests at 40, 80 and 120 columns in both languages.
- Fixed a dashboard refresh timer firing during screen shutdown.

## v1.0.1 — UI, stability and localization fixes

- Added Channel Points progress toward the most expensive available reward.
- Improved the mobile statistics layout.
- Added a structured HLS, Spade, PubSub and error journal.
- Added automatic journal rotation to limit storage usage.
- Aligned Settings labels, switches and language selector.
- Removed the redundant system-information panel.
- Removed the Ctrl+C footer from status tables.
- Fixed Rich markup crashes during long Channel Points sessions.
- Improved English localization of runtime statuses.
- Updated README feature statuses.
- Removed THIRD_PARTY_NOTICES.md.

# Changelog

## 1.0.0 — 2026-07-20

First complete NYXOR release combining the previously tested development stages into one clean codebase.

### Twitch Drops

- campaign discovery and priority-based game selection;
- automatic channel selection, progress tracking and reward claiming;
- exact Twitch category autocomplete;
- Drops remain the highest-priority activity.

### Channel Points

- prioritized Streamers list used when no Drops are available;
- automatic return to Drops when a campaign becomes mineable;
- one lightweight HLS player and a 20-second `minute-watched` cycle;
- Channel Points balance and per-session delta;
- immediate bonus chest claim through PubSub with polling fallback;
- Watch Streak tracking;
- experimental raid following and Moments claim;
- experimental Predictions with conservative limits, disabled by default.

### Interface and Termux

- Ukrainian and English terminal UI;
- dashboard, events, journal, history and local statistics;
- process start/stop/restart controls;
- optional Termux:API telemetry, notifications and wake lock;
- authenticated HLS and Channel Points diagnostic commands.

### Release cleanup

- synchronized all version values to `1.0.0`;
- removed personal settings, history, logs and runtime data from the release;
- removed unused legacy application modules;
- corrected installation, authentication, launch and update documentation;
- installer now validates every Python file and localization JSON file.

## 0.1.0

- initial NYXOR terminal interface;
- modular worker and local runtime state;
- game queue, history and journal;
- Ukrainian and English localization.
