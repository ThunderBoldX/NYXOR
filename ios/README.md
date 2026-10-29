# NYXOR for iPhone · 2.5.0 experimental

Shared Android/Windows 2.4.4 frontend and farming core, with UIKit, WKWebView
and embedded Python 3.13. Minimum iOS 26. First target: iPhone 16 Pro, iOS 27.0.1.

**Status: locally checked sources, not a compiled or install-ready IPA.**
Xcode compilation, simulator startup, free signing and real Twitch credit on
an iPhone still require verification. The local workspace runs Windows.

## Finite background sessions

Start farming and choose **Farm until this Drop in background** on an active
reward. A user-initiated BGContinuedProcessingTask keeps one pinned account
farming until Twitch confirms that reward was claimed. Other accounts pause
on background and may resume on returning. Progress uses confirmed Twitch
minutes plus one unit for the confirmed claim; missing inventory never means
completion. The native status identifies the account and reward.

The session stops after success, cancellation, expiry or 90 seconds without the
selected reward. Late callbacks cannot revive cancelled goals. Cold launch
starts no farming. Without a granted task, farming pauses on background.
iOS can deny or terminate a task: no permanent 24/7 operation, reboot autostart
or simulated audio/location is promised. No GPU entitlement is requested.

## Free installation from Windows

1. A macOS runner must compile and pass simulator smoke tests. The prepared
   `.github/workflows/ios-preview.yml` uses the standard `xcode-27` image and
   runs only on an `ios-preview` branch push or manual dispatch. No push or
   cloud build has been performed as part of local preparation.
2. Download its artifact and extract
   `NYXOR-iOS-2.5.0-EXPERIMENTAL-UNSIGNED.ipa`.
3. Follow the official [AltStore Classic Windows guide](https://faq.altstore.io/altstore-classic/how-to-install-altstore-windows).
   Install AltServer, connect and trust the iPhone, install AltStore Classic,
   and enable Developer Mode when iOS requests it.
4. Import the IPA in AltStore Classic to sign it with your free Apple account.
   Enter credentials only in the official signing tool, never in NYXOR, Git,
   a workflow or a chat.
5. Free signing expires after **seven days**. Keep AltServer available and
   refresh before expiration. AltStore also limits active sideloaded apps;
   see its [Getting Started guide](https://faq.altstore.io/altstore-classic/your-altstore).

An unsigned IPA cannot be installed by tapping it in Safari. Free provisioning
can limit capabilities; background requests need a real-device test. Foreground
farming remains available if iOS denies background time. TestFlight would need
separate distribution signing; it is not required for personal sideloading.

## macOS build

Use Xcode 26+ (the workflow chooses Xcode 27), Python 3.13 and XcodeGen:

```sh
python -m pip install Pillow==11.3.0
python ios/prepare.py
cd ios && xcodegen generate
xcodebuild -project NYXOR.xcodeproj -scheme NYXOR -sdk iphoneos \
  -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO build
```

Preparation pins/checks Python Apple Support, bundles only application sources,
rejects desktop binary wheels and appends iOS UI controls. Generated resources,
frameworks, builds and private signing material are ignored. The smoke check
requires an embedded-core snapshot and screenshot; it does not prove live farming.

Local checks: `tests/test_ios_sessions.py` and `tools/check_ios_ui.cjs` cover
confirmed completion, account pinning, suspend/resume, stale cancellation,
foreground fallback, two languages and several viewport sizes.

References: [Apple background processing](https://developer.apple.com/documentation/backgroundtasks/performing-long-running-tasks-on-ios-and-ipados/),
[GitHub Xcode 27 runner](https://github.blog/changelog/2026-09-10-xcode-27-runner-image-now-runs-on-macos-27/),
[Python on iOS](https://docs.python.org/3.13/using/ios.html).
