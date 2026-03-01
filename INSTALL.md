# dlwithit — Installation Guide

## Requirements

- macOS (Apple Silicon or Intel)
- Firefox browser

All other dependencies (ffmpeg, yt-dlp, exiftool, etc.) are bundled — nothing else to install.

---

## Installing the App

1. Download `dlwithit.app`
2. Move it to your Applications folder
3. **First launch:** Right-click the app → **Open** (required to bypass Gatekeeper — the app is not notarized)
4. Click **Open** in the confirmation dialog
5. Grant permission to access your Downloads folder when prompted

---

## Installing the Firefox Extension

**Option A: Direct install (recommended)**

1. Download `dlwithit-extension-1.0.0.xpi`
2. In Firefox, go to **File → Open File** and select the `.xpi` file (or drag it onto a Firefox window)
3. Click **Add** when prompted
4. The dlwithit icon will appear in your toolbar

**Option B: Load as temporary add-on**

1. Download and unzip the `dlwithit-extension` folder
2. In Firefox, navigate to `about:debugging`
3. Click **This Firefox** → **Load Temporary Add-on**
4. Select `manifest.json` from the extension folder

> Note: Temporary add-ons are removed when Firefox restarts.

---

## First Use

1. Launch the dlwithit app — it will appear in your menu bar
2. In Firefox, right-click on any page to see the dlwithit options:
   - **Pick Images** — visual picker to select and download images from the page
   - **Download Media** — download videos via yt-dlp (YouTube, Vimeo, Instagram, etc.)
   - **Extract Direct Videos** — find embedded video files on the page

Downloads are saved to `~/Downloads/dlwithit/` by default, organized by platform.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Cmd+F1 | Pick Images |
| Cmd+F2 | Download Media |
| Cmd+F3 | Extract Direct Videos |

---

## Troubleshooting

**"App can't be opened because it is from an unidentified developer"**
Right-click the app → Open, then click Open in the dialog.

**Extension doesn't seem to work / nothing happens**
The dlwithit app must be running for the extension to work. Look for the icon in your menu bar — if it's not there, launch the app from your Applications folder.

**Downloads fail or show errors**
Some sites may not be supported. Try using "Extract Direct Videos" as an alternative, or report the error to help improve dlwithit.

**YouTube downloads failing?**
Try updating yt-dlp — if an update is available, you'll see an "Update available" link in the app settings.

**Downloaded video won't play or shows as corrupted**
Some websites lazy-load videos, meaning the video only fully loads when you scroll to it and let it play. If a downloaded video won't play:
1. Go back to the page
2. Scroll to the video and let it play for a few seconds
3. Run "Extract Direct Videos" again
4. The new download should work correctly

This is especially common on sites like Apple.com that use advanced video loading techniques.
