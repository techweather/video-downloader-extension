# Native UI rewrite — plan

*Decided 2026-10-14. This replaces the PyQt5 window with fully native apps. Read this before any UI work so we don't drift back to Qt.*

## Decision

dlwithit splits into a **headless Python engine** and **native shells**:

```
┌─────────────────────┐   ┌─────────────────────┐   ┌──────────────────┐
│  Mac app (SwiftUI)  │   │ Windows app (WinUI3)│   │ Browser extension│
└──────────┬──────────┘   └──────────┬──────────┘   └────────┬─────────┘
           └──────────── local API (localhost:5555) ─────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   │  dlwithit engine (Python, no UI)  │
                   │  yt-dlp · ffmpeg · deno · encoder │
                   └───────────────────────────────────┘
```

- **Engine** stays Python because yt-dlp is Python. Each native app bundles it and launches it in the background; users never see it.
- **Mac:** SwiftUI, built with the latest Xcode. Standard controls pick up Liquid Glass automatically on macOS 26+ and look like regular macOS on older versions.
- **Windows:** WinUI 3 (Windows App SDK), Microsoft's recommended native framework. Mica backdrop on Windows 11, solid fallback on Windows 10.
- **The UIs stay thin.** Every decision (format choice, routing, encode or not, error wording) lives in the engine. A UI only displays what the engine reports and sends what the user asked for. This keeps the cost of maintaining two UIs down.

### Rejected

- **Qt 6 (PySide6).** Closer to native than Qt 5, but never real Liquid Glass, so it would mean another migration later.
- **Tauri / Electron.** The UI is a web page, so glass and Mica are imitations.
- **Flutter.** Draws its own controls, which brings back the hand-tuned spacing problem.

## Support floor

| Platform | Minimum | Notes |
|---|---|---|
| macOS | **14 Sonoma** | Gets `MenuBarExtra`, `SMAppService`, `@Observable`. Custom glass is gated with `if #available(macOS 26, *)` and falls back to `.ultraThinMaterial`. Prefer system components over custom glass, because macOS 27's clear/tinted slider only adjusts system components. |
| Windows | **Windows 10 1809** | Confirm against the exact Windows App SDK package chosen at setup. Mica is Windows 11 only. |

## Built-in replacements for current workarounds (Mac)

| Today | Native |
|---|---|
| osascript notifications, unreliable (#15) | `UNUserNotificationCenter` |
| osascript login item (#17) | `SMAppService` |
| pyobjc activation-policy toggle, tray (#17) | `MenuBarExtra` + `NSApp.setActivationPolicy` |
| `dlwithit://` handler (#8) | `onOpenURL` |
| Settings stacked at the top of the window | `Settings` scene (⌘,) + toolbar gear |

## Dev setup

- **Mac:** full Xcode from the App Store. This machine has only Command Line Tools today.
- **Windows:** no Windows dev machine. Plan: a Windows 11 ARM virtual machine on this Mac (Parallels for the least friction; VMware Fusion is free for personal use). Visual Studio + Windows App SDK run inside it. Turn on the Windows OpenSSH server so Claude can build and run tests over `ssh` from the Mac. Sam's Windows 11 PC is for real-hardware checks only, not development.
- Not needed until the Windows phase.

## Phases

1. ~~**Lock the decision and set up.**~~ Done 2026-10-14.
2. ~~**Pick a visual direction.**~~ Done 2026-10-14. Chosen: **A** (toolbar + list) with a **List | Gallery** switch from C, the **B** menu bar panel, settings in a **gear popover (S2)** backed by a **Settings window (S1, ⌘,)**. Clear lives in the "Finished" section header and Edit › Clear Finished (⌘K). Paste-a-link is a toolbar **+** and ⌘V, not a field. Canvas: https://claude.ai/artifact/1XuAFcXoTsQJwT3jNytMva
3. ~~**Separate the engine**~~ Done 2026-10-14 (`headless-engine` branch). `core/events.py` replaces QThread/pyqtSignal; `core/engine.py` owns jobs, picks and settings; `core/library.py` keeps download history; `api/flask_server.py` serves `/app/…` plus a live event stream (contract: [ENGINE_API.md](ENGINE_API.md)); `engine_main.py` runs it headless. The Qt app still works unchanged on the same workers.
4. **Build the Mac app** — feature parity reached 2026-10-14, pending Sean's hands-on test. Queue, Gallery/library, thumbnails (Quick Look of the real file), progress, Convert to MP4, paste link, video picker, error details + report, menu bar panel, settings, update check, open at login, Dock toggle, notifications, `dlwithit://` URL scheme.
5. **Package the Mac app.** Started: `engine.spec` builds the engine (PyInstaller, no Qt) and Release builds embed it in `dlwithit.app/Contents/Resources/engine/`. Still to do: signing every nested binary + notarization (needs Apple enrollment), swap the `.pkg` from the Qt app to the Swift app, change the bundle id from `com.dlwithit.prototype` to `com.dlwithit.app`, retire the Qt UI, then record the demo and screenshots.
6. **Build the Windows app** in WinUI 3 against the same engine, plus a Windows installer.

## Running it (development)

- **Debug build** (Xcode ⌘R, or `xcodebuild -project mac/dlwithit.xcodeproj -target dlwithit -configuration Debug SYMROOT=build build`): the app starts the repo's `.venv/bin/python3.12 engine_main.py` itself, so Python edits only need an app relaunch.
- **Release build**: first `.venv/bin/pyinstaller --noconfirm engine.spec`, then build with `-configuration Release`. The app runs the bundled engine.
- **Engine alone**: `DLWITHIT_TOKEN=devtoken .venv/bin/python3.12 engine_main.py`, then `curl -H 'X-Dlwithit-Token: devtoken' localhost:5555/app/state`.
- Only one thing can own port 5555. If the old Qt dlwithit is running, the new app says so and waits for you to quit it. While the Qt app is installed in /Applications, the extension's `dlwithit://wake` link opens **it**, not the new app.
- Engine output goes to `~/Library/Application Support/dlwithit/engine.log`; the library is `library.sqlite3` beside it.
- File bookmarks for moved-file tracking live in `bookmarks.plist` beside it (keyed by download id).

## Testing it as Claude (what works on this Mac)

- **Clicks and keys** work through computer-use: background `app_*` tools for buttons, foreground `computer_batch` for keystrokes such as ⌘V and Space. Convert window coordinates as screen points × (1456 ÷ 3008) for the foreground frame.
- **Menus never open from Claude's clicks**: right-click menus, the menu bar panel, `Menu` buttons such as Save to and Sort. Change `@AppStorage` settings with `defaults write com.dlwithit.prototype <key> …` to check what a menu would do, and leave the real click to Sean. The app's main menu bar works via `app_menu`.
- **Screenshots**: the computer-use screenshot sometimes comes back black or misses windows. `screencapture -x` plus `sips` cropping is reliable.
- **Every rebuild changes the app's ad-hoc signature**, so macOS may ask again for Downloads-folder access. That's Sean's to answer, and it blocks the window until he does. Signing will fix it.
- **System log**: use `/usr/bin/log show …`. Bare `log` is a zsh builtin here.
- **The extension itself** can't be triggered by Claude, because extension shortcuts and context menus live outside the page. To exercise the app side, POST the same payloads to `localhost:5555/download`, or run the extension's scan code in a page through Claude in Chrome's `javascript_tool`.
- Only one app can own port 5555. Quit the old Qt dlwithit, or a dev `native_app.py`, before testing. A stray dev Qt process shows up as `Python … native_app.py`.

## Open questions

- Event stream transport: Server-Sent Events on the existing Flask server is the lean default. Revisit only if it falls short.
- Windows installer format (MSIX vs. a classic installer) — decide in phase 6.
- Windows browser-extension wiring (native messaging host registration differs from macOS) — decide in phase 6.
