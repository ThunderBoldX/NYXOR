## Windows 2.3.4 preview — layout, startup modes and game search

- Place the status and moon settings shortcut beside each other without overlap, including paused state.
- Open maximized on the display under the cursor; respect its work area, taskbar and Windows scaling, with resize limits capped to small displays.
- Add app-only and app-plus-farming Windows startup modes. Preserve farming for previously enabled startup; require a valid account and saved lists before automatic farming.
- Search Twitch's public website category catalog on desktop. Match canonical names such as World of Tanks regardless of input case, without requiring account credentials.
- Use the same public catalog for game artwork and paginated live channel discovery for points, retaining viewer sorting and partial scan indications.
- Distinguish empty results, network failures, Twitch errors and rate limits; ignore stale search replies.
- Refresh English/Ukrainian desktop screenshots. Verify live World of Tanks search, artwork and channels, isolated packaged search/add flows, saved startup modes and six UI sizes. Actual farming and startup after reboot still require practical testing.

## Windows 2.3.3 preview — Twitch login recovery

- Replace rejected Android device-code initiation on desktop with native Chrome login in a dedicated NYXOR profile.
- Validate account and protected campaign access before saving a matching web context; preserve existing logins on failure.
- Refresh browser-issued proof before expiry, scope headers to Twitch GQL, and reject redirects or account changes.
- Add pending/cancel/reconnect controls and specific missing-browser, timeout and session errors.
- Keep existing Android sessions and report HTTP 400 invalid-client clearly.
- Add context, rollback, expiry, renewal, native browser ownership and cancellation checks. Live Windows account login and overnight renewal remain unverified.

## Windows 2.3.2 preview — installer process checks

- Match exact app and engine executable paths instead of every process under a directory prefix; exclude setup, uninstallers, siblings and the installer PID.
- Pass the target directory through an environment variable so spaces, parentheses and apostrophes stay data.
- Add graceful update shutdown through the shell's single-instance handler, with scoped fallback cleanup for legacy shells and orphan engines.
- Distinguish process inspection/permission errors from an app that cannot be closed.
- Verify a compiled NSIS check against a real orphan engine while another process in the same directory stays alive. Refresh desktop settings screenshots.

## Windows 2.3.1 preview — desktop app

- Package the shared farming engine and frontend as an autonomous Windows x64 app.
- Preserve moon branding, rounded purple/mint cards and animations; add a sidebar and wider dashboard/settings layouts.
- Add a moon tray icon with game/channel status, start/stop/quit controls and close-to-tray behavior.
- Add optional startup after Windows login and power management that allows display sleep while preventing automatic system sleep during normal farming.
- Reuse game artwork, priorities, Channel Points history, reward filters and energy controls from Android.
- Add English/Ukrainian desktop screenshots and build/install guides. Windows live-account farming and reboot/sleep behavior require practical testing.

## Android 2.3.1 preview — smooth moon and refreshed screenshots

- Rebuild the crescent from continuous circular arcs, removing the straight closing edge in the banner and app logo.
- Center the settings-button moon using grid alignment instead of the inline text baseline.
- Use the same crescent in the launcher icon and refresh English/Ukrainian screenshots, including reward filters, history selection and energy saving.
- Publish the Android features listed below; no additional platform project is included.

## 2.3 preview — artwork, history and energy controls

- Resolve the current Twitch category's box art through Helix, cache URLs, and use an icon fallback when unavailable.
- Add long-press history selection, right-side checkboxes and batch deletion limited to watched history. Prevent active sessions from immediately restoring deleted entries.
- Persist every confirmed drop by account/campaign/drop identity, recover pending claims from inventory, remove error-only legacy entries and retain the latest 500 rewards.
- Filter reward activity by game.
- Add optional energy saving with slower checks and UI refresh, reduced animations and Android wake-lock release.
- Avoid a date overflow when a campaign has no end date.

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
