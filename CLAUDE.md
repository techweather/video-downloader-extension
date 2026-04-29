---
repo: /Users/seanstarkweather/01_Projects/dlwithit/CLAUDE.md
note: >-
  This is the editable reference copy. The authoritative version lives in the
  repo root. Sync changes back to the repo file after editing here.
---
# CLAUDE.md — dlwithit

This file is for Claude Code. It contains working preferences and session nudges — not architecture or file maps (you can discover those yourself).

---

## Who I am and how I work

- I'm a motion designer and creative technician, not a full-time developer. Explain non-obvious code decisions briefly in plain language.
- I work in Claude Code via VS Code. I prefer focused, task-by-task sessions over large sweeping changes.
- I have high visual standards. UI/UX changes should be considered, not just functional.
- I move fast when I'm energized — match that energy. Don't over-explain things I already know.

---

## How to start a session

1. Check the **Things app** for the 👾 dlwithit project. Filter by the **Next** tag to see current priorities.
2. Ask me: *"Which of these do you want to tackle today?"* — don't assume.
3. Confirm the current branch before touching anything: `git branch` and `git status`.
4. If there's an open feature branch, ask whether to continue it or start fresh.

---

## Working preferences

- **One thing at a time.** Complete and test before moving to the next task.
- **Test before telling me it's done.** If there's a way to verify something works, do it first.
- **Don't refactor things I didn't ask about.** Scope changes to what we agreed on.
- **Commits should be small and descriptive.** Commit after each meaningful unit of work, not in one big dump at the end.
- **If you're unsure about scope, ask.** A quick clarifying question beats an hour of work in the wrong direction.
- **Flag potential side effects.** If a change might break something elsewhere, say so before making it.

---

## Current priorities (as of April 2026)

Ordered — work top to bottom unless I say otherwise:

1. ~~**Fix dev Python environment**~~ — done. Python 3.12.13 via Homebrew, `.venv` rebuilt, yt-dlp 2026.03.17 confirmed. Dev app runs on port 5555.
2. ~~**Set up automated extension testing**~~ — done. Pytest suite (Tier 1) covers classify, payload routing, encoder logic. See `tests/` and the Testing section below.
3. ~~Build Chrome extension~~ — done (`extension_chrome/`, `chrome-extension` branch merged)
4. ~~Finalize icon revision and complete features branch merge~~ — done (emoji labels, branches merged to main)
5. Sign up for Apple Developer account + sign and notarize the app — account exists, payment/enrollment pending
6. ~~Fix stuck 'Starting…' hang~~ — done. Cancel button now shows immediately when queued.
7. ~~Fix duplicate naming on YouTube Shorts when logged out~~ — cancelled, non-issue.
8. ~~Make app auto-launch when extension is invoked and app isn't running~~ — code done (`dlwithit://` URL scheme + extension retry logic). **⚠️ Needs post-bundle test:** quit the app, invoke extension, confirm it auto-launches. Untestable with dev Python app — requires a rebuilt `.app` bundle.
9. ~~Verify yt-dlp version check is working~~ — done. GitHub API fetches correctly, version comparison works, label refreshes after update. Memory bug note was stale (fix was already in code).
10. ~~Prepare README screenshots~~ — placeholder structure added to both README.md and README.html. **⚠️ Waiting on assets:** Sean needs to capture a short demo screen recording (`assets/screenshots/demo.mp4`) and 1–2 stills (`assets/screenshots/app-window.png`, `context-menu.png`). Uncomment the placeholder blocks in both files when ready.
11. ~~README: add function key note~~ — done. Keyboard shortcut tables updated in both README.md and README.html with Firefox (Cmd+F1/F2), Chrome (Cmd+Ctrl+1/2), and Fn key callout.
12. **Tier 2 smoke test** — build a short, focused manual checklist around a fixed tab set (Instagram carousels, Vimeo-heavy portfolio sites, Mux embeds) to replace the existing exhaustive TESTING_CHECKLIST.md. Discussed April 2026.

### Pre-share short list (added April 27, 2026)

Lumping these in before the signed/notarized build, since momentum is good. Each lands on its own feature branch, merged to `main` with `--no-ff` so a single `git revert -m 1 <merge-commit>` can undo any feature cleanly.

13. **LICENSE file** — pick a license (MIT likely) and add `LICENSE` at repo root.
14. **README simplification pass** — second read-through of both READMEs for clarity/cuts; no new content.
15. ~~**v1 in-app updater**~~ — done. `core/app_updater.py` mirrors the yt-dlp pattern; `AppVersionCheckWorker` checks `releases/latest`, `is_newer()` gates the UI, Settings shows a clickable "Update available (X.Y.Z)" link → opens the GitHub release page. macOS notification fires once on launch via `osascript`. README "Updating dlwithit" section added to both files. 24 new tests, full Tier 1 at 81 passing. **⚠️ Notification needs post-build verification:** in dev, the Settings link path was confirmed against the live `v1.0.0` GitHub release (with `__version__` temporarily flipped to `0.9.9`), but the macOS notification never appeared — `osascript display notification` from an unsigned Python process is unreliable on modern macOS even with permissions on. Once the signed `.pkg` is built and installed (priority #20), and a follow-up release (e.g. `v1.0.1`) is published on GitHub, launch the installed `dlwithit.app` and confirm the notification banner appears within ~3s. If it still doesn't fire from the signed bundle, swap `osascript` for `pyobjc`'s `UNUserNotificationCenter` or `terminal-notifier`.
16. **Vimeo embed 401** — at minimum show a clear error instead of a cryptic one; investigate referer-header fix.
17. **Hide from Dock + launch-at-login hidden** — two related Settings prefs; biggest user-facing polish item in this batch.
18. *(Optional)* **Paste-URL fallback** in the app — small, useful when the extension fails.
19. *(Optional)* **Post-download manual encode** — right-click a completed download to re-encode (covers .webm → .mp4 after the fact).
20. **Signed/notarized `.pkg` installer with guided extension install** — pivoted to from `.dmg` for a Gatekeeper-free first-launch experience. Component-choice screen (Firefox/Chrome/both); post-install script triggers guided (not silent — see Distribution Plan note) extension install. **Hard prerequisite: priority #5 (Apple Dev enrollment + signing certs) must be done first.** See `01_Projects/dlwithit/Distribution Plan.md` in Obsidian for the full operational picture (signing, notarization sequencing, extension-install constraints, v2 destinations).

---

## Things I care about for the "ready to share" bar

Before this goes to a wider group of people, these must be true:

- [ ] App is signed and notarized (no Gatekeeper warnings)
- [x] Chrome extension works
- [x] Features branch is merged and tested
- [x] No hangs that block further downloads
- [ ] README is clear enough for a non-technical friend to install and use it
- [ ] yt-dlp updater is verified working

---

## Testing

### Tier 1 — fast pytest suite (run this after any bug fix or feature change)

```bash
cd /Users/seanstarkweather/01_Projects/dlwithit
.venv/bin/pytest tests/test_api.py tests/test_classify.py tests/test_download_payload.py tests/test_encoder_logic.py -v
```

Runs in ~2 seconds, no downloads, no browser, no app running needed.

| File | What it covers |
|---|---|
| `tests/test_api.py` | Flask endpoints: health, root, download routing, CORS |
| `tests/test_classify.py` | `/classify` with real URL patterns — YouTube, Vimeo, Instagram, TikTok, direct MP4, edge cases |
| `tests/test_download_payload.py` | All payload shapes the extension sends; crash prevention (missing `type` field); signal routing |
| `tests/test_encoder_logic.py` | Image magic-byte detection (JPEG/PNG/WebP/GIF); codec → encode decision (VP9/AV1/H264) |

### Tier 2 — manual smoke test (not yet built)

Planned: a short checklist using a fixed tab set of hard cases — Instagram carousels, Vimeo-heavy portfolio pages, Mux embeds. Replaces the existing exhaustive `TESTING_CHECKLIST.md`. See Obsidian `01_Projects/dlwithit/Test Setup` for full context.

### Dev environment notes

- Python 3.12.13 at `/opt/homebrew/bin/python3.12`
- `.venv` lives in repo root — always use `.venv/bin/python3.12` or `.venv/bin/pytest`, not system Python
- Dev app: `cd /Users/seanstarkweather/01_Projects/dlwithit && .venv/bin/python3.12 native_app.py`
- App runs on port 5555; test suite uses ports 5556–5560 to avoid conflicts
- yt-dlp note: YouTube downloads warn about missing JS runtime (deno). Downloads still work; install `brew install deno` when needed for full format support.

---

## README conventions

There are two READMEs — keep them in sync whenever one changes:

| File | Purpose | Audience |
|---|---|---|
| `README.md` | GitHub repo page | Developers / curious visitors |
| `README.html` | Ships inside the .dmg, opens in browser | End users after install |

**What stays in sync:** feature names and descriptions, keyboard shortcuts, troubleshooting content, Chrome/Firefox parity.

**What intentionally differs:** `README.md` includes source-install instructions (clone, pip, `python native_app.py`). `README.html` includes end-user install steps (drag to Applications, .xpi install, Gatekeeper workaround).

**`README.txt` was deleted** — it was redundant with `README.html`.

**⚠️ Media assets still needed:** placeholder blocks are commented out in both files. Drop files into `assets/screenshots/` and uncomment when ready:
- `demo.mp4` — short screen recording showing the full workflow
- `app-window.png` — app window with a download in progress
- `context-menu.png` — right-click context menu on a real page

`README.html` uses a `<video>` tag; `README.md` uses `![](path)` which GitHub renders as an inline player.

**⚠️ After notarization:** the Gatekeeper troubleshooting items in `README.html` ("app can't be opened", "right-click → Open", System Settings workaround) can be removed or simplified — they only exist because the app isn't signed yet.

---

## Code style and conventions

- Python for backend logic, JavaScript for the extension.
- Keep functions small and focused.
- Don't introduce new dependencies without flagging it first — I want to stay lean.
- If you write a new helper function, add a one-line comment explaining what it does.
- Match the existing code style in whatever file you're editing.

---

## Things to avoid

- Don't make UI changes I haven't asked for, even if you think they'd be better.
- Don't delete or archive any files without asking first.
- Don't combine multiple unrelated fixes into one commit.
- Don't add logging or debug output and leave it in — clean it up before finishing.

---

## Project context

**dlwithit** is a macOS menu bar app + browser extension that lets users download videos and images from the web via right-click context menu. It uses yt-dlp for video extraction and ffmpeg for encoding. The browser extension communicates with the native app via native messaging on localhost:5555.

**Extension status:** Firefox extension (`extension_minimal/`) and Chrome extension (`extension_chrome/`) both exist. Firefox uses Manifest V2 with `browser.*` APIs; Chrome uses Manifest V3 with `chrome.*` APIs and a service worker. Both have the same two functions: Image Picker (🏞️) and Video Download (▶️). Shortcuts: Firefox Cmd+F1/F2, Chrome Cmd+Ctrl+1/2.

The goal is to make it genuinely useful and shareable — not a polished commercial product, but something a technically-comfortable person can install and rely on. Contribution and usefulness matter more than perfection.

---

## Repo location

`/Users/seanstarkweather/01_Projects/dlwithit`

---

*Keep this file lean. Update priorities section when the Things list changes significantly.*
