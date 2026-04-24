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

1. **Set up automated extension testing** — use Claude in Chrome MCP to navigate test pages and trigger the Chrome extension via keyboard shortcuts (Cmd+Ctrl+1/2), verifying downloads land in the app queue. Should cover: YouTube, Vimeo embed, direct MP4, image picker. Requires dev app running on port 5555 and extension loaded unpacked. Build this before new features so regressions are caught automatically.
2. ~~Build Chrome extension~~ — done (`extension_chrome/`, `chrome-extension` branch merged)
3. ~~Finalize icon revision and complete features branch merge~~ — done (emoji labels, branches merged to main)
4. Sign up for Apple Developer account + sign and notarize the app — account exists, payment/enrollment pending
5. Fix stuck 'Starting…' hang — cancel button should always be available
6. Fix duplicate naming on YouTube Shorts when logged out
7. Make app auto-launch when extension is invoked and app isn't running
8. Verify yt-dlp version check is working
9. Prepare README screenshots
10. README: add function key note (Cmd+Ctrl+1/2 for Chrome, Cmd+F1/F2 for Firefox)

---

## Things I care about for the "ready to share" bar

Before this goes to a wider group of people, these must be true:

- [ ] App is signed and notarized (no Gatekeeper warnings)
- [ ] Chrome extension works
- [ ] Features branch is merged and tested
- [ ] No hangs that block further downloads
- [ ] README is clear enough for a non-technical friend to install and use it
- [ ] yt-dlp updater is verified working

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
