# dlwithit

A browser extension + desktop app for downloading images and videos from the web.

**macOS** &nbsp;|&nbsp; **Firefox** &nbsp;|&nbsp; **Chrome**

---

## What it does

dlwithit is a two-part tool: a browser extension (Firefox and Chrome) that detects media on any webpage, and a native macOS app that handles the actual downloading. Right-click on any page to pick images, grab videos from platforms like YouTube and Vimeo, or extract embedded video files that browsers can't normally save.

Built for designers, filmmakers, and creatives who need to quickly gather visual references. The app queues downloads with progress tracking, auto-converts WebM/VP9 to MP4, and can embed source URLs as metadata so you always know where something came from.

---

<!-- DEMO VIDEO: replace the line below with ![Demo](assets/screenshots/demo.mp4) or a GitHub CDN URL once recorded -->
<!-- ![Demo](assets/screenshots/demo.mp4) -->

<!-- SCREENSHOTS: one or two stills showing the app window and context menu in use -->
<!-- ![App window](assets/screenshots/app-window.png) -->
<!-- ![Context menu](assets/screenshots/context-menu.png) -->

---

## Features

- **🏞️ Image Picker** — visual overlay to select and download images from any page
- **▶️ Video Download** — uses yt-dlp to download from YouTube, Vimeo, Instagram, TikTok, and hundreds more; also scans pages for embedded video files (Mux, Squarespace, HLS streams, etc.)
- **Metadata embedding** — saves the source URL inside downloaded files
- **Convert to MP4** — auto-converts WebM/VP9 video to MP4 (H.264) so it plays in QuickTime, Premiere, etc. If a download bypasses auto-conversion, a **Convert to MP4** button appears on the completed item.
- **Playlist support** — detects playlists and lets you pick which videos to download
- **Organize by platform** — auto-sorts downloads into folders by source site
- **Paste a URL** — escape hatch for direct media URLs when you can't use the extension (Safari/Edge users, links from Slack or iMessage). Click `▶ Paste a URL` at the bottom of the app window to expand the input. Page scanning for lazy-loaded media still needs the extension.
- **Menu bar** — runs in the macOS menu bar; click the icon to show/hide the app window
- **Auto-updates yt-dlp** — checks for updates and installs with one click

## Supported Platforms

| Component | Supported | Planned |
|-----------|-----------|---------|
| Desktop app | macOS | Windows |
| Browser extension | Firefox, Chrome | — |

## Installation

### Desktop app

1. Clone this repo and install dependencies:
   ```
   pip install PyQt5 flask flask-cors yt-dlp requests
   ```
2. Make sure `ffmpeg` is installed (`brew install ffmpeg` on macOS)
3. Run the app:
   ```
   python native_app.py
   ```

### Firefox extension

1. Open Firefox and go to `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on**
3. Select `extension_minimal/manifest.json`

For permanent installation, see [Firefox_Extension_Installation.md](Firefox_Extension_Installation.md).

### Chrome extension

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension_chrome/` folder

## Usage

Right-click on any webpage to see two options:

| Menu item | What it does |
|-----------|-------------|
| 🏞️ Image Picker | Opens a visual selector — click images to download them |
| ▶️ Video Download | Downloads via yt-dlp (YouTube, Vimeo, etc.) and scans for embedded video files (Mux, HLS, etc.) |

Downloads appear in the app's queue with progress bars, thumbnails, and status updates. Completed downloads have a "Show in Finder" button.

## Keyboard Shortcuts

| Shortcut | Browser | Action |
|----------|---------|--------|
| `Cmd+F1` | Firefox | 🏞️ Image Picker |
| `Cmd+F2` | Firefox | ▶️ Video Download |
| `Cmd+Ctrl+1` | Chrome | 🏞️ Image Picker |
| `Cmd+Ctrl+2` | Chrome | ▶️ Video Download |

These can be customized in your browser's extension shortcut settings:
- **Firefox**: `about:addons` → gear icon → Manage Extension Shortcuts
- **Chrome**: `chrome://extensions/shortcuts`

> **Note for Firefox users:** On Macs where function keys control hardware features (brightness, volume, etc.), you may need to hold `Fn` as well — e.g. `Fn+Cmd+F1`. This depends on your keyboard settings in System Settings → Keyboard.

## Settings

- **Save location** — default `~/Downloads/dlwithit`, or set a custom folder
- **Organize by platform** — auto-create subfolders for YouTube, Instagram, etc.
- **Metadata** — none, embedded in file, or sidecar files
- **Auto-convert WebM/VP9 to MP4** — converts incompatible video formats to H.264 after download
- **Keep original** — retain the original file after encoding
- **System tray** — show/hide tray icon, minimize to tray on close

## Updating dlwithit

The app checks for updates on launch and surfaces a clickable "Update available" link in Settings (next to the version number) when a new release is published. You'll also see a one-time macOS notification on launch when an update is waiting.

### App

When prompted, click the link in Settings — it opens the GitHub release page in your browser. Download the new installer and run it; the new version replaces the old install.

### Firefox extension

Open `about:addons`, remove the existing "dlwithit" extension, then install the new `.xpi` from the release page (drag onto Firefox or use Install Add-on From File).

### Chrome extension

Open `chrome://extensions`, remove the existing "dlwithit" extension, then load the new unpacked extension folder from the release with **Load unpacked**.

> Extensions will auto-update via the Mozilla Add-ons store and Chrome Web Store in a future release.

## Troubleshooting

**YouTube downloads fail or return errors**
Update yt-dlp — YouTube frequently changes its API. The app checks for updates automatically, or click the update link in settings.

**403 Forbidden errors on images**
Some CDNs reject requests with unexpected headers. dlwithit uses a minimal-headers strategy that works with most CDNs, but some sites may still block downloads.

**Extension can't connect to the app**
Make sure the app is running (check for the tray icon). The extension communicates via HTTP to `localhost:5555`.

**Videos not detected on a page**
▶️ Video Download scans the page source for embedded video URLs in scripts, data attributes, and metadata. Some sites lazy-load video — if nothing is detected, scroll to the video and let it start playing for a few seconds, then invoke ▶️ Video Download again. If the video still doesn't appear, the URL may be loaded dynamically after user interaction and may not be capturable.

## Built With

[Python](https://python.org) ·
[PyQt5](https://riverbankcomputing.com/software/pyqt/) ·
[yt-dlp](https://github.com/yt-dlp/yt-dlp) ·
[Flask](https://flask.palletsprojects.com/) ·
[ffmpeg](https://ffmpeg.org/)
