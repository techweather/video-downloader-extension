# Testing the new Mac app

Claude tested everything it could drive on 2026-10-14 (list at the bottom). What's left needs your hands: about 10 minutes.

## Before you start

1. **Quit the old dlwithit** (its menu bar icon → Quit). Only one app can talk to the extension at a time.
2. Open the new app:
   ```bash
   open /Users/seanstarkweather/01_Projects/dlwithit/mac/build/Release/dlwithit.app
   ```
3. If a macOS dialog says **"claude" would like to control this Mac**, click **Don't Allow**. Claude triggered it by accident; nothing needs it.

## Your list

- [ ] **Turn on notifications:** System Settings › Notifications › dlwithit (it's set to *Denied*), then switch to another app during a download. A "Downloaded" banner should appear when it finishes.
- [ ] **The extension, for real**, in Chrome *and* Firefox (keep the new app open — the wake link still opens the old app):
  - [ ] Right-click → Video Download on a YouTube video.
  - [ ] Same on a portfolio page with several Vimeo embeds → picker appears.
  - [ ] Pick Images → images land.
  - [ ] The keyboard shortcuts (Chrome ⌘⌃1/2, Firefox ⌘F1/F2).
- [ ] **Menus** (Claude's clicks can't open menus on this Mac):
  - [ ] Menu bar icon → the panel shows progress, Recent, Clear, Open Window.
  - [ ] Right-click a download row → Open, Show in Finder, Copy Original Link, Remove.
  - [ ] Settings › Save to › Choose Folder… → pick a folder, then switch back.
- [ ] *(Optional)* Open at login: turn it on, log out and in. The app should start in the menu bar with no window. Then turn it off again if you don't want it.

## Added 2026-10-15 (Claude tested all of these in the Release build)

Worth a minute of your own clicking when you have energy:

- [ ] Gallery: ⌘-click, ⇧-click, drag a rectangle on empty space, ⌘A, Esc. Right-click a card that isn't selected → it gets selected.
- [ ] Select some items, switch List ↔ Gallery (⌘1 / ⌘2): the selection stays.
- [ ] Click a sidebar entry, press ⌘A straight away: everything in the content is selected.
- [ ] Menu bar panel: section headers read "In Progress" and "Finished".

## Already verified by Claude

Clicked through in the running app, the self-contained Release build with its bundled engine:

- Engine starts with the app and stops when it quits. The library and settings survive a relaunch.
- Downloads: YouTube, Vimeo (bundled curl_cffi), direct MP4/WebM/OGG, images; MP4 conversion with bundled ffmpeg (WebM, Theora); a YouTube title replacing the pasted link.
- Picker sheet from a multi-embed page and from the extension's real DOM scan run on a live page (w3schools); untick, download selected.
- List ↔ Gallery, sidebar filters, Quick Look thumbnails, Convert to MP4 button, Cancel, Retry, Clear (button and ⌘K), failed row with plain-English error, Error Details sheet (Copy; Send not pressed).
- **+** popover (pre-filled link, friendly message for a page with no media), ⌘V paste.
- Show in Finder selects the file.
- Settings window: shows real settings, Check Now ("Up to date"), Show in Dock off/on, Show in menu bar off/on, Open at login registers and unregisters in System Settings.
- The old Qt app still works with the shared engine code.

## Known gaps (not bugs)

- The extension's wake link opens the old app while it's installed in /Applications.
- Bundle id is still `com.dlwithit.prototype`; not signed or notarized yet (needs Apple enrollment).
- WebM files show a placeholder thumbnail (Quick Look can't preview WebM) until converted.
- The extension's DOM scan guesses thumbnails from nearby images, so a page's unrelated picture can appear (seen on w3schools). Extension behaviour, unchanged.
