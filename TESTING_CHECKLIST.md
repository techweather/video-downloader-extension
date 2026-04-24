# dlwithit — Manual QA Checklist

Use this checklist to verify the built `dlwithit.app` before release. Test against the packaged app, not the dev server.

---

## 1. App Launch & System Behavior

- [ ] App launches without errors (double-click from Applications)
- [ ] First launch: Gatekeeper right-click → Open flow works
- [ ] App icon appears in the macOS menu bar tray
- [ ] Main window opens on first launch (or click tray icon)
- [ ] Tray icon click toggles window show/hide
- [ ] Window close button hides to tray (does not quit)
- [ ] App quits cleanly via tray menu → Quit
- [ ] No console errors or crash dialogs on launch
- [ ] Fresh install (no settings file): defaults load correctly
  - [ ] Save location shows `~/Downloads/dlwithit`
  - [ ] "Organize by platform" is ON
  - [ ] Metadata is set to "Embed in file"
  - [ ] Auto-encode VP9 is ON
  - [ ] Keep original is OFF
  - [ ] System tray is ON

---

## 2. Settings Panel

- [ ] Settings panel opens from tray menu or UI button
- [ ] Save location: default shows `~/Downloads/dlwithit`
- [ ] Save location: "Choose Folder" picker works, path updates
- [ ] Save location: custom path persists after app restart
- [ ] "Organize by platform" toggle saves and persists
- [ ] Metadata dropdown: None / Embed in file / Sidecar file — saves and persists
- [ ] Auto-encode VP9 toggle saves and persists
- [ ] Keep original toggle saves and persists (only relevant when encoding is ON)
- [ ] Settings written to `~/.dlwithit_settings.json` (not `media_downloader_settings.json`)
- [ ] yt-dlp version displayed in settings
- [ ] "Update available" link appears when yt-dlp is outdated
- [ ] yt-dlp update installs successfully and version refreshes

---

## 3. Download Media (yt-dlp)

### General

- [ ] Right-click a YouTube page → "Download Media" queues the download
- [ ] Download item appears in the queue with title and thumbnail
- [ ] Progress bar updates during download
- [ ] Status transitions: Downloading → Merging → Complete
- [ ] Completed item shows "Show in Finder" button
- [ ] "Show in Finder" reveals the file in Finder
- [ ] Cancel button works during download (removes item from queue)
- [ ] File saved to correct folder (default or custom)

### YouTube

- [ ] Standard video downloads at best quality (not 360p / format_id=18)
- [ ] Downloaded file is MP4 (H.264), not WebM/VP9 (when auto-encode is ON)
- [ ] File saved to `YouTube/` subfolder when "Organize by platform" is ON
- [ ] File saved to root folder when "Organize by platform" is OFF
- [ ] Playlist URL: playlist detection dialog appears
- [ ] Playlist: can select individual videos to download
- [ ] Playlist: selecting all and downloading works
- [ ] Age-restricted / private video shows a clear error

### Vimeo

- [ ] Standard Vimeo video downloads successfully
- [ ] File saved to `Vimeo/` subfolder when organized by platform
- [ ] Vimeo fallback (direct .mp4 extraction) works if yt-dlp fails

### Instagram

- [ ] Single image post downloads the image
- [ ] Single video post downloads the video
- [ ] Carousel post: all images/videos downloaded
- [ ] Carousel: files saved without overwriting each other
- [ ] Metadata sidecar: `_metadata/` folder inside `Instagram/` (not in root)
- [ ] Metadata sidecar with "Organize by platform" OFF: `_metadata/` inside root save folder

### TikTok / Other platforms

- [ ] TikTok video downloads without watermark (if supported by yt-dlp)
- [ ] Unsupported URL shows a meaningful error (not a crash)

### Duplicate handling (yt-dlp)

- [ ] Re-downloading a file that already exists: skips download
- [ ] Skipped item shows "Show in Finder" (not an error)
- [ ] Skipped item: Cancel button is hidden, only "Show in Finder" visible

---

## 4. Extract Direct Videos

- [ ] Right-click a page with embedded video → "Extract Direct Videos"
- [ ] Video list dialog appears with detected videos
- [ ] Each video entry shows title/URL
- [ ] Selecting a video and clicking Download starts the download
- [ ] MP4 direct URL downloads successfully
- [ ] HLS (.m3u8) stream downloads successfully via yt-dlp
- [ ] Mux video detected and downloads via `https://stream.mux.com/{id}/high.mp4`
- [ ] Squarespace video detected and downloads via HLS
- [ ] File saved to correct platform subfolder when organized by platform
- [ ] Generic filename collision: second file gets counter suffix (e.g., `video_1.mp4`), not skipped
- [ ] No video found: appropriate message shown (not a crash)

---

## 5. Pick Images

- [ ] Right-click any page → "Pick Images" opens the visual overlay
- [ ] Images on the page are highlighted/selectable
- [ ] Clicking an image selects it (visual indicator)
- [ ] Clicking again deselects it
- [ ] "Download Selected" button downloads all selected images
- [ ] Images appear in the download queue with thumbnails
- [ ] CDN images (Sanity, Cloudflare, etc.) download without 403 errors
- [ ] File saved to root save folder (no platform subfolder for images)
- [ ] Keyboard shortcut Cmd+F1 triggers Pick Images

---

## 6. VP9 → H.264 Encoding

- [ ] VP9/WebM download triggers encoding (when auto-encode is ON)
- [ ] Status shows "Encoding…" during conversion
- [ ] Encoded file is H.264 MP4
- [ ] Original WebM file removed after encoding (when "Keep original" is OFF)
- [ ] Original WebM file kept (when "Keep original" is ON)
- [ ] AV1 download also triggers encoding
- [ ] H.264 download does NOT trigger encoding (no unnecessary re-encode)
- [ ] "Cancel" during encoding stops the encode job
- [ ] Encode cancelled status shown cleanly (not an error)
- [ ] Multiple simultaneous encodes queue correctly

---

## 7. Metadata

### Embed in file

- [ ] Downloaded video has source URL embedded (check with `exiftool` or MediaInfo)
- [ ] Downloaded image has source URL embedded

### Sidecar file

- [ ] Downloaded file has a companion `.json` sidecar in `_metadata/` folder
- [ ] Sidecar contains URL and title
- [ ] Sidecar folder is inside the platform subfolder (not root) when organized by platform

### None

- [ ] No metadata embedded, no sidecar created

---

## 8. Error Handling

- [ ] Network error during download shows error state in queue item
- [ ] Error state shows "Report Error" button
- [ ] "Report Error" sends error to Discord webhook (verify in Discord)
- [ ] "Report Error" shows confirmation after sending
- [ ] yt-dlp failure (e.g., geo-blocked video) shows descriptive error message
- [ ] App does not crash on any error condition
- [ ] Extension cannot connect (app not running): extension shows a user-facing message

---

## 9. UI / Download Queue States

Verify each state renders correctly:

- [ ] **Downloading** — progress bar active, Cancel visible
- [ ] **Merging** — status label says "Merging…", progress indeterminate
- [ ] **Encoding** — status label says "Encoding…", progress indeterminate
- [ ] **Queued for encoding** — status label says "Queued for encoding…"
- [ ] **Complete** — green indicator, "Show in Finder" visible, Cancel hidden
- [ ] **Skipped (file exists)** — "Show in Finder" visible, Cancel hidden, no error indicator
- [ ] **Error** — red indicator, "Report Error" button visible
- [ ] **Cancelled** — item removed from queue OR shows cancelled state cleanly
- [ ] **Encoding cancelled** — item shows cancelled (not error)
- [ ] Queue scrolls when many items present
- [ ] Thumbnails load for all item types (not blank/broken)

---

## 10. Extension Features

- [ ] Extension icon visible in Firefox toolbar after install
- [ ] Right-click context menu shows three options: Pick Images, Download Media, Extract Direct Videos
- [ ] Keyboard shortcut Cmd+F1 → Pick Images
- [ ] Keyboard shortcut Cmd+F2 → Download Media
- [ ] Keyboard shortcut Cmd+F3 → Extract Direct Videos
- [ ] Extension connects to app on `localhost:5555`
- [ ] Video detection runs on page load (iframe/Mux detection)
- [ ] Deep video scrape (10-strategy scan) finds videos in scripts/data attrs
- [ ] Image picker overlay injects and removes cleanly without breaking page layout
- [ ] Extension works after Firefox restart (permanent install via .xpi)

---

## 11. Platform Organization

- [ ] YouTube → `YouTube/` subfolder
- [ ] Vimeo → `Vimeo/` subfolder
- [ ] Instagram → `Instagram/` subfolder
- [ ] TikTok → `TikTok/` subfolder
- [ ] Other/unknown → root save folder
- [ ] With "Organize by platform" OFF: all files go to root save folder
- [ ] Platform folders created automatically on first download

---

## 12. Build / Packaging Sanity

- [ ] `dlwithit.app` runs on a machine without Python installed
- [ ] `dlwithit.app` runs on a machine without Homebrew/ffmpeg installed
- [ ] `dlwithit.app` runs on Apple Silicon (arm64)
- [ ] `dlwithit.app` runs on Intel Mac (x86_64) — if applicable
- [ ] Bundled ffmpeg/ffprobe detected correctly inside the .app bundle
- [ ] Bundled exiftool detected correctly inside the .app bundle
- [ ] `dlwithit-extension-1.0.0.xpi` installs in Firefox without errors
