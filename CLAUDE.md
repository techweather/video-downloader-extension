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

1. ~~**Fix dev Python environment**~~ — done. Python 3.12.13 via Homebrew, `.venv` rebuilt, yt-dlp 2026.03.17 confirmed (now 2026.8.19 + curl_cffi — see #28). Dev app runs on port 5555.
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

13. ~~**LICENSE file**~~ — done. MIT, © 2026 techweather, at repo root. Shipped via `add-license` branch.
14. **README simplification pass** — second read-through of both READMEs for clarity/cuts; no new content.
15. ~~**v1 in-app updater**~~ — done. `core/app_updater.py` mirrors the yt-dlp pattern; `AppVersionCheckWorker` checks `releases/latest`, `is_newer()` gates the UI, Settings shows a clickable "Update available (X.Y.Z)" link → opens the GitHub release page. macOS notification fires once on launch via `osascript`. README "Updating dlwithit" section added to both files. 24 new tests, full Tier 1 at 81 passing. **⚠️ Notification needs post-build verification:** in dev, the Settings link path was confirmed against the live `v1.0.0` GitHub release (with `__version__` temporarily flipped to `0.9.9`), but the macOS notification never appeared — `osascript display notification` from an unsigned Python process is unreliable on modern macOS even with permissions on. Once the signed `.pkg` is built and installed (priority #20), and a follow-up release (e.g. `v1.0.1`) is published on GitHub, launch the installed `dlwithit.app` and confirm the notification banner appears within ~3s. If it still doesn't fire from the signed bundle, swap `osascript` for `pyobjc`'s `UNUserNotificationCenter` or `terminal-notifier`.
16. ~~**Vimeo embed 401**~~ — done. Investigation found the embed-error auto-recovery system from a prior session was already handling the common case: when a `player.vimeo.com/video/{id}` embed returns 401/403/private/restricted, `is_vimeo_embed_error()` detects it and the downloader retries against `https://vimeo.com/{id}` (the direct URL — better than the referer-header workaround originally noted). Added `vimeo_fallback_failed_error()` to wrap the rare case where both URLs fail, replacing a cryptic `401 Unauthorized` with "Couldn't access this Vimeo video. It may be private, password-protected, or geo-restricted." (original error preserved for Report Error dialog). One new test, 4 Vimeo unit tests passing.
17. ~~**Hide from Dock + launch-at-login hidden**~~ — done. New `core/macos.py` module wraps macOS-specific calls: `set_dock_visible()` flips `NSApp.setActivationPolicy_` between Regular/Accessory (live, no restart); `refresh_dock_icon()` re-applies the app icon after Accessory→Regular (macOS forgets it otherwise — the dev app was showing the bare Python rocket); `set_launch_at_login()` registers/removes a login item via osascript with the `hidden:true` flag. native_app.py honors a `--hidden` CLI flag to suppress the window on startup. Two new Settings checkboxes wired in; settings persist as `hide_from_dock` / `launch_at_login`. Adds `pyobjc-core` and `pyobjc-framework-Cocoa` (~6MB, darwin-only via marker). 18 new tests, full Tier 1 at 99 passing. Both toggles verified live in dev (Dock toggle on/off cycles correctly; login item appears in System Settings → Login Items when registered).
18. ~~*(Optional)* **Paste-URL fallback** in the app~~ — done. New `core/url_router.py` classifies a single pasted URL into `image` / `video` / `unsupported` (direct file extensions first, then yt-dlp's `ie.suitable()` for platform pages, excluding Generic). UI: a "Paste URL…" input + "Download" button row at the bottom of the main window above the footer. Routing emits `new_download` with the same payload shape as the extension, so the existing download pipeline handles it without special casing. Unsupported URLs (random pages, no detectable media) get a dialog pointing the user to the extension's 🏞️ Pick Images for page-scanning cases — by design, that flow stays extension-only because it needs in-page DOM context. 33 new tests, full Tier 1 at 132 passing. Verified live with placehold.co image + samplelib mp4 (both queued and downloaded successfully). Sean noted he may want to collapse the row into a reveal/dropdown later — `_create_paste_url_row` is its own method to make that easy.
19. ~~**Post-download manual conversion**~~ — done. A "Convert to MP4" button appears on completed download rows when the file is still VP9/VP8/AV1 (auto-convert disabled, or a direct .webm). Click the button → kicks the existing `EncodingWorker` pipeline with `keep_original=True`, so the source `.webm` stays alongside the new `_h264.mp4`. Button hides during the conversion run, restored on cancel/error so the user can retry. Right-click context menu was prototyped but removed (duplicative with the visible button). Shipped via `manual-reencode` branch. **Side effect:** aligned all user-facing copy from "encode/H.264" to "convert/MP4" — Settings checkbox is now "Auto-convert WebM/VP9 to MP4", status text is "Converting to MP4…", error labels are "Conversion Error". Internal names (`encode_vp9` setting key, `EncodingWorker` class, signal names) intentionally unchanged to avoid a settings migration.
20. **Signed/notarized `.pkg` installer with guided extension install** — pivoted to from `.dmg` for a Gatekeeper-free first-launch experience. Component-choice screen (Firefox/Chrome/both); post-install script triggers guided (not silent — see Distribution Plan note) extension install. **Hard prerequisite: priority #5 (Apple Dev enrollment + signing certs) must be done first.** See `01_Projects/dlwithit/Distribution Plan.md` in Obsidian for the full operational picture (signing, notarization sequencing, extension-install constraints, v2 destinations).

    **Version bump checklist** (for whenever the signed `.pkg` is ready to ship to testers — recommended target is `1.1.0`, not 1.0.1, since the accumulated work since 1.0.0 is squarely "minor release" territory: in-app updater #15, Vimeo error UX #16, Dock/login toggles #17, paste-URL fallback #18, Convert to MP4 #19, paste-URL disclosure #21):
    1. `version.py` — main app version constant
    2. `dlwithit.spec` — `CFBundleShortVersionString` + `CFBundleVersion` in the `info_plist` block
    3. `scripts/build_pkg.sh` — `VERSION=` near the top
    4. `installer/Distribution.xml` — all three `<pkg-ref ... version="...">` entries
    5. `build_extension.sh` — `VERSION=` (Firefox .xpi)
    6. `scripts/build_chrome_zip.sh` — `VERSION=` (Chrome CWS zip)
    7. Tag a GitHub Release `v1.1.0` (the in-app updater compares against `releases/latest`)
    **Migration note:** the March 1.0.0 build that went to ~5 of Sean's friends does NOT contain the in-app updater (that was completed *after* their build). Their migration to 1.1.0 is manual — email/text them the .pkg link, they install over the old version. The in-app updater pays off starting with releases *after* 1.1.0 (1.1.1, 1.2.0, etc.) for testers running 1.1.0+.

    **Step 1 (infrastructure) — done.** `pkg-installer` branch landed: `installer/Distribution.xml` drives the productbuild output (welcome → customize → install → conclusion, with Destination Select skipped since there's only one valid target); `installer/resources/welcome.html` + `conclusion.html` (intentionally no colored boxes — the installer HTML pane doesn't respect `prefers-color-scheme`); `scripts/build_pkg.sh` orchestrates pkgbuild → productbuild (stages under `/tmp` so pkgbuild's framework-signing root-ownership doesn't pollute the repo); `scripts/pkg_scripts/firefox/postinstall` and `chrome/postinstall` use `launchctl asuser + open --args` to handle URLs from postinstall context. **Known limitation:** postinstall GUI launching on macOS 14+ is partial — apps launch but URLs often get ignored when the app restores a previous session. The conclusion.html has a manual-fallback paragraph for this. The signed-.xpi (post-AMO) and real-CWS-URL (post-CWS) paths are different code paths inside the apps and should be more reliable — full validation waits on those landing. **Pending for Step 2:** (a) fresh PyInstaller build of `.app` from current main (the March-era `dist/dmg-staging/dlwithit.app` had corrupted `root:wheel 700` perms which got carried into the installed `/Applications/dlwithit.app` — fresh build solves this); (b) second-Mac install test; (c) once AMO returns signed `.xpi`, drop into `dist/extension/` and rebuild; (d) once CWS publishes, flip `CHROME_CWS_URL` at the top of `scripts/pkg_scripts/chrome/postinstall` to the listing URL; (e) **check the "Update yt-dlp" button in the bundled `.app`** — *corrected 2026-10-13:* the code never runs pip from a frozen bundle. `InstallUpdateWorker.run()` in `core/updater.py` checks `is_frozen()` and shows "Re-download the app to update to X" instead. So the check is just that the button shows that message rather than erroring. The real consequence: **bundled users only get a newer yt-dlp when they install a newer dlwithit** — the in-app app updater (#15) is the delivery path, so ship releases when yt-dlp breaks a major site. (f) **verify Vimeo downloads from the bundled `.app`** (#28) — right-click a Vimeo embed on a portfolio site in the installed app and confirm it downloads. This proves `curl_cffi` was collected into the bundle and survives signing/notarization (it ships native `.so` files).

21. ~~**Paste-URL UI revisit**~~ — done. Wrapped the row in a collapsible disclosure: a single muted line (`▶ Paste a URL`) that expands to reveal the input + Download button on click. Collapsed by default; state persists in Settings as `paste_url_expanded` so frequent users keep it open. A thin `#404040` separator now sits between the paste-URL area and the `Active downloads:` footer for clearer visual hierarchy. The unsupported-URL dialog also got rewritten — primary message bolded, body explains the lazy-load case, and points to **Video Download** and **Pick Images** as the two named extension actions (rich text via `QMessageBox.setTextFormat(Qt.RichText)`; emoji were tried first but choked QMessageBox's text rendering on macOS, so feature names are bolded instead). Settings toggle was ruled out — it would hide the feature from non-extension users (Safari/Edge) who need it most.

22. ~~**README mention of paste-URL fallback**~~ — done. New Features bullet/card in both READMEs frames it as an escape hatch for non-extension users (Safari/Edge, Slack/iMessage links), points users to expand `▶ Paste a URL` at the bottom of the app window, and notes that lazy-load page scanning still needs the extension.

23. ~~**README mention of Convert to MP4**~~ — done. The existing "VP9 to H.264 encoding" Features entry was rewritten to "Convert to MP4" — covers both the auto path (Settings checkbox, now labeled `Auto-convert WebM/VP9 to MP4`) and the manual button on completed items. Intro paragraph and Settings list also updated to match the new UI terminology. Two CSS bugs in `README.html` got swept up in the same pass: scoped `.feature strong` to `> strong` so inline `<strong>` mentions don't break to a new line, and bumped `.settings li strong` min-width from 160px to 220px so the wider label keeps the description column aligned.

24. ~~**Bundle deno into the .pkg for full YouTube format support**~~ — done. `dlwithit.spec` now has a `find_deno()` helper that mirrors `find_ffmpeg_tools()` and adds the deno binary (currently 157 MB on Apple Silicon — bigger than the original ~80 MB estimate) to PyInstaller's `binaries` list. Lands at `Contents/Frameworks/deno`. The GUI session's PATH on macOS doesn't include any of the directories where bundled binaries ship, so `native_app.py` now prepends `Contents/Frameworks/` to `os.environ['PATH']` at startup when running from a frozen bundle — that way yt-dlp's `shutil.which('deno')` lookup finds our bundled copy at runtime. No-op in dev (the user's shell PATH already has deno via `/opt/homebrew/bin`). Net .pkg size impact: +54 MB after gzip compression (79 MB → 133 MB), much better than the raw 157 MB binary suggests. **Verification still needed at runtime**: install the new .pkg, attempt a YouTube download in the bundled app, confirm yt-dlp does NOT emit its "no JS interpreter" warning. Tested via Tier 1 (132 passing) but YouTube-format verification requires real download against the bundled app.

25. **Extension store submissions (Firefox AMO + Chrome Web Store)** — promoted from v2 to v1 because Chrome doesn't allow any installer to install extensions on the user's behalf; CWS one-click install is the floor for a seamless UX. Submission packages already built: `dist/extension/dlwithit-connector-firefox-v1.0.0.xpi` and `dist/extension/dlwithit-connector-chrome-v1.0.0.zip` (rebuild via `bash build_extension.sh` and `bash scripts/build_chrome_zip.sh`). [PRIVACY.md](PRIVACY.md) is published; the privacy-policy URL for both listings is `https://raw.githubusercontent.com/techweather/video-downloader-extension/main/PRIVACY.md`. **⚠️ Hard-blocked on Sean's bandwidth:** both stores require at least one screenshot before review — CWS is strict (1280×800 or 640×400 promo tile); AMO accepts upload-then-edit but reviewers expect at least one. Easiest capture: a screenshot of the dlwithit app window with a couple of downloads in progress + the right-click context menu showing the two extension entries. This same screenshot can double as `assets/screenshots/app-window.png` for the README placeholder (priority #10). Submit AMO + CWS in parallel once the screenshot is captured — both have multi-day review queues, so kicking them off early means they finish around the same time as the .pkg work (#20).

26. **Instagram "empty media response" report from tester** — friend on the March 1.0.0 build hit a `DownloadError` on `https://www.instagram.com/p/Dae8b-tu-eV/` (video); full raw report + analysis in the Obsidian vault at `01_Projects/dlwithit/User Bug Reports.md`. Not necessarily a dlwithit bug — yt-dlp reports Instagram returned no media, likely private/restricted or Instagram tightening anonymous access. **First step:** open the URL in a browser NOT logged in to Instagram — if it plays, it's a yt-dlp extractor bug worth reporting upstream; if it doesn't, the error is accurate and the fix on our side is a friendlier error dialog ("this post may be private, geo-restricted, or removed — try opening the link in your browser to verify"). **Second step (if this pattern is common):** expose `--cookies-from-browser` in Settings as yt-dlp's error message itself suggests — would resolve most Instagram cases where the user is logged in but the app isn't. **Reporter migration note:** they're on the March 1.0.0 build, so any fix on main doesn't reach them until they get a new .pkg (per priority #20 migration note).

27. ~~**archive.org downloads the multi-GB master**~~ — done (2026-10-13, `archive-org-derivatives`). yt-dlp's archive.org extractor ranks an item's original upload above every derivative and reports no codecs, so `'best'` grabbed the preservation master — 94.5 GB for *The Growth of Plants*, 351 GB for *Holiday in Hawaii*. `build_format_string(quality, extractor_key)` in `core/downloader.py` now owns the quality → selector choice; once the probe names the site, archive.org items get `ARCHIVE_ORG_FORMAT` (largest derivative with a picture → the 640×480 h.264 mp4 archive.org's own player streams; master only if no such copy). Every other site's string is unchanged. Rejected: a filesize cap (a cap low enough to catch the 1.8 GB case silently drops hour-long 4K YouTube to 1440p, and HLS sizes are unknown anyway) and "prefer mp4" (codecs are unknown, and some masters *are* mp4 — 10.9 GB, 35 GB). The master is still reachable deliberately: paste the direct `archive.org/download/…/file.mov` link into Paste URL (goes through the generic extractor, not this rule). Verified live in the dev app: *Symphony in Motion* → 66 MB h.264 mp4, was a 1.8 GB mov. 21 new tests. **Follow-up in Things:** warn before any download whose known size crosses a threshold (all sites) — needs UI design.

28. ~~**Vimeo returns 401 on every video**~~ — done (2026-10-13, `vimeo-curl-cffi`). Found while wrapping up #27: every Vimeo URL failed with `HTTP Error 401: Unauthorized` — direct links and portfolio-site embeds alike — on yt-dlp 2026.03.17 *and* the then-latest 2026.8.19. Vimeo now only answers yt-dlp when it can impersonate a browser, which needs the optional `curl_cffi` package. The fix is a dependency, not code: `requirements.txt` and the in-app updater now ask for `yt-dlp[curl-cffi]`, and yt-dlp's own extra picks a matching `curl_cffi` (each yt-dlp release only accepts a version range — 2026.03.17 stops at 0.14, so the two must move together). **New dependency:** `curl_cffi` 0.16.3 + `cffi` (~7 MB, native `.so`). yt-dlp's PyInstaller hook collects it automatically, so `dlwithit.spec` is unchanged. Verified live in the dev app: a reMarkable spot embedded on andrewsiner.com downloaded at 1440×1080 h.264 + AAC (26 MB). YouTube (4K) and archive.org (#27) re-checked on the new yt-dlp. **Not yet verified:** Vimeo from the bundled `.app` — see #20 (f). **Reporter note:** the March 1.0.0 build can't get this via the yt-dlp button (frozen builds skip pip) — it arrives with the next `.pkg`.

29. ~~**Sidecar files had doubled extensions**~~ — done (2026-10-13, `sidecar-filenames`). Found while recording the demo's metadata beat: with "Metadata: Sidecar files", every sidecar came out as `X.description.description`, `X.info.json.info.json` and `X.url.webloc`, and no `.url` was written. yt-dlp swaps a template's extension for its own only when the template ends in the media's extension, so templates already ending in `.description` etc. got it appended again. `'webloc'` was never a template type, and `'writewebloc'` isn't a yt-dlp option. Both sidecar call sites in `core/downloader.py` now share `sidecar_outtmpl()` (every metadata template ends in `.%(ext)s`), and `writeurllink` asks for the `.url` alongside the `.webloc`. 4 new tests in `tests/test_sidecar_paths.py` run yt-dlp's real filename logic offline; Tier 1 at 82. Verified live on an archive.org item: `.description`, `.info.json`, `.url`, `.webloc`, `_thumbnail.jpg` in `_metadata/`. **Reporter note:** the March 1.0.0 build has the bug, so the fix arrives with the next `.pkg`.

30. **Native UI rewrite — SwiftUI (Mac) + WinUI 3 (Windows)** — decided 2026-10-14, now the top priority. The Python code becomes a headless engine behind the local API; the PyQt5 window is replaced by native apps. Mac first, Windows as a close follow. Support floor: macOS 14 Sonoma, Windows 10 1809. **Authority: [NATIVE_UI_PLAN.md](NATIVE_UI_PLAN.md)** — the architecture, rejected alternatives (Qt 6, Tauri, Flutter), dev setup, and phases. Don't spend effort polishing the Qt UI; it stays only as the shipping version until the Mac app reaches parity. The demo video and store/README screenshots (#10, #25) wait for the new UI. Apple enrollment (#5) stays on hold until Sean is ready.

    **Status 2026-10-14 (`headless-engine` branch, unmerged):** phases 1–4 done and verified in the running app, phase 5 started — see the Phases section of NATIVE_UI_PLAN.md. The SwiftUI app (`mac/`) runs on the Python engine over the local API ([ENGINE_API.md](ENGINE_API.md)); Release builds bundle the engine. **Waiting on Sean:** hands-on test of the new app (checklist in `mac/TESTING.md`), then merge `headless-engine` to `main`.

---

## Things I care about for the "ready to share" bar

Before this goes to a wider group of people, these must be true:

- [ ] App is signed and notarized (no Gatekeeper warnings)
- [x] Chrome extension works
- [x] Features branch is merged and tested
- [x] No hangs that block further downloads
- [ ] README is clear enough for a non-technical friend to install and use it
- [x] yt-dlp updater is verified working

---

## Testing

### Tier 1 — fast pytest suite (run this after any bug fix or feature change)

```bash
cd /Users/seanstarkweather/01_Projects/dlwithit
.venv/bin/pytest tests/test_api.py tests/test_classify.py tests/test_download_payload.py tests/test_encoder_logic.py tests/test_format_selection.py tests/test_sidecar_paths.py tests/test_events.py tests/test_routing.py tests/test_library.py tests/test_engine.py tests/test_app_api.py tests/test_error_summary.py tests/test_pick_enrich.py -v
```

Runs in ~2 seconds, no downloads, no browser, no app running needed.

| File | What it covers |
|---|---|
| `tests/test_api.py` | Flask endpoints: health, root, download routing, CORS |
| `tests/test_classify.py` | `/classify` with real URL patterns — YouTube, Vimeo, Instagram, TikTok, direct MP4, edge cases |
| `tests/test_download_payload.py` | All payload shapes the extension sends; crash prevention (missing `type` field); signal routing |
| `tests/test_encoder_logic.py` | Image magic-byte detection (JPEG/PNG/WebP/GIF); codec → encode decision (VP9/AV1/H264) |
| `tests/test_format_selection.py` | yt-dlp format strings per quality; archive.org picks the web copy, not the master — runs yt-dlp's real selector offline |
| `tests/test_sidecar_paths.py` | Sidecar metadata filenames — one extension each, all in `_metadata/` — via yt-dlp's real filename logic |
| `tests/test_events.py` | Qt-free signals and worker threads (`core/events.py`) |
| `tests/test_routing.py` | Which tool downloads each picked video; friendly source names |
| `tests/test_library.py` | Download library (SQLite) behind the Gallery |
| `tests/test_engine.py` | Engine job lifecycle, picks, list actions, settings — workers driven by fake signals |
| `tests/test_app_api.py` | `/app/` endpoints: token, no-CORS, actions, live event stream |
| `tests/test_error_summary.py` | One-line error text shown on failed downloads |
| `tests/test_pick_enrich.py` | Real titles/thumbnails for picker videos via oEmbed (faked, no network) |

The whole fast suite (everything except `test_real_downloads.py`, ~380 tests, ~4 s): `.venv/bin/pytest -q -m "not slow" --ignore=tests/test_real_downloads.py`

### Tier 2 — manual smoke test (not yet built)

Planned: a short checklist using a fixed tab set of hard cases — Instagram carousels, Vimeo-heavy portfolio pages, Mux embeds. Replaces the existing exhaustive `TESTING_CHECKLIST.md`. See Obsidian `01_Projects/dlwithit/Test Setup` for full context.

### Dev environment notes

- Python 3.12.13 at `/opt/homebrew/bin/python3.12`
- `.venv` lives in repo root — always use `.venv/bin/python3.12` or `.venv/bin/pytest`, not system Python
- Dev app: `cd /Users/seanstarkweather/01_Projects/dlwithit && .venv/bin/python3.12 native_app.py`
- App runs on port 5555; test suite uses ports 5556–5560 to avoid conflicts
- yt-dlp note: YouTube downloads warn about missing JS runtime (deno). Downloads still work; install `brew install deno` when needed for full format support.
- yt-dlp in `.venv` is 2026.8.19 with `curl_cffi` 0.16.3 (2026-10-13). Upgrade with `.venv/bin/python3.12 -m pip install --upgrade "yt-dlp[curl-cffi]"` — never plain `yt-dlp`, or a later release can outgrow the installed `curl_cffi` and Vimeo goes back to 401.

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

---

## Queued feature — Apple.com marketing-page media extraction (added 2026-07-25)

New capability set so dlwithit can extract motion/media from Apple product "overview" pages (`macbook-neo`, `imac`, `mac-mini`, `mac-studio`, `mac/mac-does-that`) that the generic scraper misses: `blob:` video srcs, JS-constructed CDN URLs, transparent `.mov`/`.webm`, canvas image-sequence flipbooks, and HLS `.m3u8` films.

Full self-contained plan (content types, recipes, task breakdown **A–F**, acceptance criteria, re-derivation commands):
- Repo: `APPLE_EXTRACTION_PLAN.md`
- Obsidian: `01_Projects/dlwithit/Apple.com Media Extraction — Implementation Plan.md`

Scope: **A/B/C/F** are the in-scope "Apple support" set for the current dev version; **D** (canvas flipbooks) and **E** (HLS discovery) are flagged stretch. Tracked in Things under 👾 dlwithit → "Apple.com marketing-page media extraction" (tag **Next**).

---

## ~~Queued fix — Video scan progress + double-run/duplicate guard~~ (done 2026-08-03)

Shipped via `video-scan-guard`. Per-tab `scanningTabs` guard in `triggerCombinedVideoDownload()` in both extensions (a second trigger now shows "Still scanning this page…" instead of starting a parallel scan); an in-page `#__dlwithit_scan_banner` shows "Scanning page for videos…" during the DOM scan — the scan runs in the page, so app-side status couldn't represent it. New `core/media_list.py` (`normalize_media_url` / `dedupe_videos` / `merge_video_lists`) mirrored by `dedupeVideos()` in both `background.js`; extensions dedupe before sending `video-list`, the app dedupes on receipt. `handle_video_list` keeps `_open_video_dialogs` keyed by pageUrl so a second scan merges into the open picker and raises it rather than stacking a dialog on `exec_()`'s nested event loop. 31 new tests, unit suite at 163 passing.

Deliberately skipped: parallelizing the per-video probes (the DOM scan's real cost is the `querySelectorAll('*')` attribute sweep, not network).

**Live test on andrewsiner.com (2026-08-10) found the banner and guard work, but that the "Starting…" hang was a different code path entirely** — see below.

---

## ~~Queued fix — "Starting…" hang on pages with many embedded players~~ (done 2026-08-10)

Shipped via `video-extract-speed`. andrewsiner.com never reaches the DOM-scan path: the extension finds <2 embeds, `/classify` says supported, and the page URL goes to yt-dlp — whose **generic extractor resolves all 12 embedded Vimeo videos** before the picker can appear. That was the hang (~56s observed).

Two causes, both fixed:
- **The page was fully extracted twice.** `run()` had two `extract_info(url, download=False)` calls (the metadata probe, then the playlist check). The probe already knows whether the page held several videos, so `_emit_playlist_if_multi()` now runs there and `continue`s before the second extraction is reached. Measured: one pass = 13 `extract_info` calls / 8.8s; the second pass additionally forced per-entry format selection.
- **No progress during the probe.** `YtDlpLogger` takes a `progress_callback` and parses `[download] Downloading item N of M` — the one line yt-dlp emits per entry regardless of extractor. The row now reads "Reading video 4 of 12…".

The duplicated playlist-detection block is now one `_emit_playlist_if_multi()` method used by both call sites; the second call remains a safety net for pages that only reveal themselves once full options are applied. Both extensions now clear the scan banner *before* the "no videos found" alert (`alert()` blocks the injected script, so the background page couldn't remove it until dismissed). 19 new tests, unit suite at 182 passing.

**Verified**: on the real repro page, one pass → picker with 12 videos and correct titles. **Not yet verified**: the end-to-end wall-clock improvement through the extension in a browser, and the "Reading video N of M" label appearing in the UI.

**Still open (deliberate)**: `extract_flat='in_playlist'` returns the same 12 entries in **0.4s vs 8.8s**, but with `title: None`. Worth doing if the wait is still too long — it needs titles backfilled from the extension's iframe scrape, or the picker shown immediately and titles filled in as they resolve.

**Follow-up fix (2026-08-10, `skip-data-uris`)**: page themes ship a tiny base64 placeholder as a `<video src>` to prime the player (andrewsiner.com's is 2×2, 4 frames). The scan treated it as real, so running Video Download near the top of the page gave a bogus "Found 1 video" picker, and downloading it crashed with `InvalidSchema` — `requests` has no adapter for `data:`. `resolveUrl()` now returns null for `data:` in both extensions (covers every scan pass at once); `core/media_list.is_fetchable_media_url()` is the app-side backstop. Confirmed fixed live. Unit suite at 200.

### ⚠️ Site behaviour worth remembering

**On pages with embedded players (Vimeo/YouTube iframes), right-clicking the video gives you the *player's* context menu, not the browser's** — so the extension's menu items are unreachable there. The user must right-click off the player frame, or use the keyboard shortcut (Firefox ⌘F1/⌘F2, Chrome ⌘⌃1/⌘⌃2).

Two consequences:
- Any feature keyed on "which element did you right-click" is a dead end for exactly the multi-embed pages that need it most. A viewport-prominence hint is the only workable signal — see the Things item.
- **This is a documentation problem, not a workflow problem.** Right-click stays the primary taught path in both READMEs and the demo video — most people reach for it and don't use shortcuts. The instruction to add is simply *"on a page with an embedded player, right-click just outside the player frame — right-clicking the video itself opens the player's own menu."* The keyboard shortcut is presented second, as the faster way once you know it. Do **not** restructure the docs or the demo around the shortcut (considered and rejected, Sean, 2026-08-10).

---

## Demo content & store assets — lives in a sibling repo (added 2026-10-12)

The demo video, store screenshots, and README stills are built in
**`~/01_Projects/dlwithit-demo-sites`**, deliberately outside this repo so none of it
lands in the PyInstaller bundle or the `.pkg`.

**Authority: `dlwithit-demo-sites/DEMO_PLAN.md`.** Direction, the full ~85s shot-by-shot
script with type-card copy, the five staging conditions, asset inventory, outstanding
work, and a list of directions already rejected. Read it before any demo work.

Built and working: the **EFEMRA Department** — a fictional institutional archive, four
pages, 25 public-domain/CC assets (NASA, Wikimedia, Prelinger) with provenance in
`CREDITS.md`, served by `serve.py` with per-file bandwidth throttling so the queue's
mix of states is reproducible rather than luck.

Still outstanding: the store screenshot itself (hard-blocks priorities #10 and #25 —
`assets/screenshots/` is still empty), an archive.org embed page, 13 full-frame type
cards, SVG keycap graphics, a staging script, and the shotlist → Premiere `.jsx` +
ffmpeg preview assembly.

**Claude → After Effects bridge:** Sean built one on his MacBook Pro. It is **not yet
on this machine** (After Effects 2022–2026 are installed; the bridge is not). Porting
it is tracked in Things and unlocks the shot-10 burst, the type cards, and the keycaps.
