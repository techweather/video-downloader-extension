# dlwithit

A browser extension + desktop app for downloading images and videos from the web.

**macOS** &nbsp;|&nbsp; **Firefox**

---

## What it does

dlwithit is a two-part tool: a Firefox extension that detects media on any webpage, and a native macOS app that handles the actual downloading. Right-click on any page to pick images, grab videos from platforms like YouTube and Vimeo, or extract embedded video files that browsers can't normally save.

Built for designers, filmmakers, and creatives who need to quickly gather visual references. The app queues downloads with progress tracking, auto-encodes VP9 to H.264, and can embed source URLs as metadata so you always know where something came from.

## Features

- **Pick Images** — visual overlay to select and download images from any page
- **Download Media** — uses yt-dlp to download from YouTube, Vimeo, Instagram, TikTok, and hundreds more
- **Extract Direct Videos** — finds video files embedded in pages (Mux, Squarespace, HLS streams, etc.)
- **Metadata embedding** — saves the source URL inside downloaded files
- **VP9 to H.264 encoding** — auto-converts WebM/VP9 downloads with parallel encoding
- **Playlist support** — detects playlists and lets you pick which videos to download
- **Organize by platform** — auto-sorts downloads into folders by source site
- **System tray** — minimizes to tray, click to show/hide
- **Auto-updates yt-dlp** — checks for updates and installs with one click

## Supported Platforms

| Component | Supported | Planned |
|-----------|-----------|---------|
| Desktop app | macOS | Windows |
| Browser extension | Firefox | Chrome |

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

## Usage

Right-click on any webpage to see three options:

| Menu item | What it does |
|-----------|-------------|
| Pick Images | Opens a visual selector — click images to download them |
| Download Media | Downloads the current page URL via yt-dlp (YouTube, Vimeo, etc.) |
| Extract Direct Videos | Scans the page source for embedded video files |

Downloads appear in the app's queue with progress bars, thumbnails, and status updates. Completed downloads have a "Show in Finder" button.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd+F1` | Pick Images |
| `Cmd+F2` | Download Media |
| `Cmd+F3` | Extract Direct Videos |

These can be customized in Firefox's extension shortcut settings (`about:addons` → gear icon → Manage Extension Shortcuts).

## Settings

- **Save location** — default `~/Downloads/dlwithit`, or set a custom folder
- **Organize by platform** — auto-create subfolders for YouTube, Instagram, etc.
- **Metadata** — none, embedded in file, or sidecar files
- **Auto-encode VP9** — convert WebM/VP9 to H.264 MP4 after download
- **Keep original** — retain the original file after encoding
- **System tray** — show/hide tray icon, minimize to tray on close

## Troubleshooting

**YouTube downloads fail or return errors**
Update yt-dlp — YouTube frequently changes its API. The app checks for updates automatically, or click the update link in settings.

**403 Forbidden errors on images**
Some CDNs reject requests with unexpected headers. dlwithit uses a minimal-headers strategy that works with most CDNs, but some sites may still block downloads.

**Extension can't connect to the app**
Make sure the app is running (check for the tray icon). The extension communicates via HTTP to `localhost:5555`.

**Videos not detected on a page**
Try "Extract Direct Videos" — it runs a deep scan of the page source looking for video URLs in scripts, data attributes, and metadata. Some sites load video URLs dynamically after interaction, which may not be detectable.

## Built With

[Python](https://python.org) ·
[PyQt5](https://riverbankcomputing.com/software/pyqt/) ·
[yt-dlp](https://github.com/yt-dlp/yt-dlp) ·
[Flask](https://flask.palletsprojects.com/) ·
[ffmpeg](https://ffmpeg.org/)
