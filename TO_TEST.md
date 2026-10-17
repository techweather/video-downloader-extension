# To test (Sean)

Running list of everything Claude couldn't check itself. Tick items off, and tell Claude about anything that's off. Claude adds to this list as new work lands.

Last updated: 2026-10-17.

## 1. Install (do this first; everything below uses the installed app)

- [ ] Quit any running dlwithit (menu bar icon › Quit).
- [ ] Open `dist/dlwithit-installer-v1.0.0.pkg`. It isn't signed yet, so right-click › Open if macOS blocks it. Pick both Chrome and Firefox.
  - This replaces the old Qt app in /Applications with the new one. That's intended.
- [ ] dlwithit opens from /Applications, and the window looks like the one you've been testing.
- [ ] If macOS asks for Downloads-folder access, click Allow.

## 2. The app

- [ ] **Notifications:** System Settings › Notifications › dlwithit › Allow. Start a download, switch to another app, and a "Downloaded" banner appears.
- [ ] **Menu bar panel:** click the menu bar icon. It shows "In Progress" / "Finished", Clear, and Open Window.
- [ ] **Sort menu** (toolbar ↑↓): pick Name, then Size. The order changes.
- [ ] **Gallery** (⌘2): ⌘-click, ⇧-click, drag a box on empty space, ⌘A, Esc. Right-click a card that isn't selected: it gets selected.
- [ ] Select a few items, press ⌘1 and then ⌘2: the selection stays.
- [ ] **YouTube:** paste a YouTube link (⌘V). It downloads in full quality. Tell Claude when it's done, and Claude will check the log for the "no JS runtime" warning.
- [ ] **Vimeo:** Video Download on a portfolio page with Vimeo embeds (e.g. andrewsiner.com). The picker appears, then the files download.
- [ ] **Open at login** *(optional)*: turn it on in Settings, log out and back in. The app starts in the menu bar with no window.

## 3. Extensions (reload them first)

Chrome: `chrome://extensions` › reload **dlwithit Connector**. Firefox: `about:debugging#/runtime/this-firefox` › Reload.

- [ ] **Wake link:** quit dlwithit, then use Video Download on any page. The app should open by itself and the download start.
- [ ] **Pick Images:** the pill, highlight, panel and toasts work in Chrome **and** Firefox. Esc closes the panel, then ends picking.
- [ ] **Video Download, no videos:** on a plain text page (e.g. a Wikipedia article), a "Scanning…" pill shows, then a dark toast. There should be no grey browser alert.
- [ ] **Video Download, twice quickly:** a "Still scanning…" toast, and only one picker.
- [ ] **Apple animations:** Video Download on apple.com/macbook-neo, /imac, /mac-mini and /mac-studio. The animations land in the app and play. See-through ones stay `.mov`/`.webm` and don't convert to MP4.
- [ ] **Apple stills:** Pick Images on an apple.com product photo. The file is the large `_2x` version, not a small one.
- [ ] **Keyboard shortcuts:** Chrome ⌘⌃1 / ⌘⌃2, Firefox ⌘F1 / ⌘F2.

## Done

Move items here (or just delete them) once they pass.
