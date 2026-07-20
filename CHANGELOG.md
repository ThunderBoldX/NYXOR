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
