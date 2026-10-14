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

1. **Lock the decision and set up.** This doc, CLAUDE.md priorities, Things items, Xcode install.
2. **Pick a visual direction.** HTML mockups for Mac and Windows, light and dark. They cover layout and hierarchy (settings placement, download-row anatomy, toolbar contents), not pixel styling. Then a quick SwiftUI prototype of the winner, to see real glass on the machine.
3. **Separate the engine** (`headless-engine` branch). `core/downloader.py`, `core/encoder.py`, `core/updater.py` and `core/app_updater.py` subclass `QThread` and emit `pyqtSignal`s. Replace those with plain threads + callbacks. Extend `api/flask_server.py` with the commands the UI needs (queue, cancel, convert, settings, pick-from-list) and a live event stream for progress. The Qt app keeps working on top of the same engine until the native app reaches parity. Pytest covers the API contract.
4. **Build the Mac app** to match today's features: queue, thumbnails, progress, Convert to MP4, paste URL, video picker, menu bar, settings, updater links.
5. **Package the Mac app.** The `.pkg` ships the Swift app with the engine signed inside it. Retire the Qt UI. Record the demo and store screenshots on the new UI.
6. **Build the Windows app** in WinUI 3 against the same engine, plus a Windows installer.

## Open questions

- Event stream transport: Server-Sent Events on the existing Flask server is the lean default. Revisit only if it falls short.
- Windows installer format (MSIX vs. a classic installer) — decide in phase 6.
- Windows browser-extension wiring (native messaging host registration differs from macOS) — decide in phase 6.
