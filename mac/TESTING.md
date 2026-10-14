# Testing the new Mac app

About 15 minutes. Tick what works, note what doesn't.

## Before you start

1. **Quit the old dlwithit** (menu bar icon → Quit). Only one app can talk to the extension at a time. If the old one is running, the new one shows "The old dlwithit is running" and waits.
2. **Open the new app** (self-contained build, engine inside):
   ```bash
   open /Users/seanstarkweather/01_Projects/dlwithit/mac/build/Release/dlwithit.app
   ```
   Or open `mac/dlwithit.xcodeproj` in Xcode and press ⌘R (Debug: runs the repo's Python, so code changes need no rebuild).
3. The first launch asks whether dlwithit may send notifications. Allow it to test notifications.

## The checklist

**From the browser (the real workflow)**
- [ ] Right-click a YouTube video → Video Download. Row appears, shows the real title and thumbnail, progress moves, finishes.
- [ ] Same on a Vimeo-heavy portfolio page (e.g. andrewsiner.com). A **picker sheet** opens listing the videos. Untick a few, download the rest.
- [ ] Pick Images on any page with photos. Images land, with thumbnails.
- [ ] A page where the extension has to scan (no YouTube/Vimeo embed). Picker appears.
- [ ] Switch to another app while something downloads. A notification arrives when it finishes.

**In the window**
- [ ] **List | Gallery** switch. The Gallery shows everything you've downloaded, including earlier today, with real thumbnails.
- [ ] Sidebar: Downloading / Completed / Needs Attention / each source filter both views.
- [ ] **+** button. The popover pre-fills a copied link. Download works.
- [ ] Copy a link, click the window, press **⌘V**. It downloads.
- [ ] Paste something with no media (e.g. a news homepage). You get a friendly explanation.
- [ ] A failed download shows a short red reason, an **(i)** button (full details, Copy, Send Report) and **Retry**.
- [ ] Cancel a running download.
- [ ] **Clear** (Finished header, or ⌘K) empties finished rows. They stay in the Gallery.
- [ ] Right-click a row: Open, Show in Finder, Copy Original Link, Remove.
- [ ] Double-click a finished row opens the file.
- [ ] Turn off auto-convert (gear), download a WebM (YouTube 4K often is). **Convert to MP4** appears on the row and works. Turn auto-convert back on.

**Settings and menu bar**
- [ ] Gear popover and Settings window (⌘,) show your current settings, and changes stick after relaunch.
- [ ] Save folder: Choose Folder… then Show in Finder.
- [ ] Menu bar panel: progress, Recent, Clear, Open Window.
- [ ] Settings › App: Show in Dock off and on, Show in menu bar off and on.
- [ ] Open at login: on, log out and back in. The app starts in the menu bar with no window. Turn it off afterwards if you don't want it.
- [ ] Updates › Check Now says "Up to date".

**Quitting**
- [ ] Quit (⌘Q). Then re-open. Everything still in the Gallery.

## Known gaps (not bugs to report)

- **The extension's "wake" link opens the old app** while it's installed in /Applications. Keep the new app open while testing.
- Bundle id is still `com.dlwithit.prototype`. It switches to the real one when the new app replaces the old in the installer.
- Not signed or notarized yet (needs Apple enrollment). Running it from the build folder is fine on this Mac.
- WebM files show a colour placeholder instead of a thumbnail. macOS Quick Look can't preview WebM. Once converted to MP4 they get real thumbnails.
