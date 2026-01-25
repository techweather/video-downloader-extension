# Firefox Extension Installation Guide
## Media Downloader Connector v2.0

This guide will walk you through installing the Media Downloader Connector extension in Firefox.

## Prerequisites

1. **Native App Running**: Ensure the Media Downloader native application is running on port 5555
   - Run `./dist/Media\ Downloader.app` (macOS) or `./dist/Media\ Downloader\ \(Portable\)` 
   - The app should show "Native app running on http://127.0.0.1:5555" in the terminal

## Installation Methods

### Method 1: Temporary Installation (Developer Mode)

**Best for testing and development**

1. **Open Firefox** and navigate to `about:debugging`
2. Click **"This Firefox"** in the left sidebar
3. Click **"Load Temporary Add-on..."** button
4. Navigate to the project folder and select one of:
   - `dist/extension/media-downloader-connector-firefox-v2.0.zip` (built package)
   - `extension_minimal/manifest.json` (development files)
5. The extension will be loaded and active immediately

**Notes:**
- ✅ Quick and easy for testing
- ⚠️ Extension is removed when Firefox restarts
- ⚠️ Shows as "temporary" in the extensions list

### Method 2: Permanent Installation (Manual)

**For personal use without Mozilla signing**

1. **Extract the extension**:
   ```bash
   cd dist/extension
   unzip media-downloader-connector-firefox-v2.0.zip -d media-downloader-connector
   ```

2. **Enable unsigned extensions** (Firefox Developer Edition or ESR):
   - Navigate to `about:config`
   - Search for `xpinstall.signatures.required`
   - Set value to `false`

3. **Install the extension**:
   - Navigate to `about:addons`
   - Click the gear icon → "Install Add-on From File..."
   - Select the extracted `manifest.json` file

**Notes:**
- ✅ Persistent across Firefox restarts
- ⚠️ Only works with Firefox Developer Edition or ESR
- ⚠️ Requires disabling signature verification

### Method 3: Mozilla Signing (Official Distribution)

**For public distribution**

1. **Create Mozilla Developer Account**:
   - Go to https://addons.mozilla.org/developers/
   - Sign up for a developer account

2. **Submit for Signing**:
   - Upload `media-downloader-connector-firefox-v2.0.zip`
   - Choose "Unlisted" for personal use or "Listed" for public
   - Wait for automated review (usually minutes)

3. **Download Signed Extension**:
   - Download the signed `.xpi` file
   - Install normally through Firefox

**Notes:**
- ✅ Works in all Firefox versions
- ✅ No configuration changes needed
- ⏳ Requires Mozilla review process

## Usage Instructions

Once installed:

1. **Right-click on any image or video** on a webpage
2. Select **"Download with Media Downloader"** from the context menu
3. The media will be sent to the native app for download
4. Check the native app window to see download progress

## Troubleshooting

### Extension Not Working

**Check Native App Connection:**
```bash
curl http://127.0.0.1:5555/download -X POST -H "Content-Type: application/json" -d '{"test": true}'
```
Should return: `{"status": "success"}`

**Common Issues:**

1. **"Native app not responding"**:
   - Ensure the native app is running on port 5555
   - Check firewall settings
   - Restart the native app

2. **"Extension not found in context menu"**:
   - Refresh the webpage after installing
   - Check that the extension is enabled in `about:addons`

3. **"Downloads not starting"**:
   - Check native app logs for errors
   - Verify the URL is supported by yt-dlp
   - Try with a different media source

### Uninstallation

**Temporary Installation:**
- Extension automatically removed on Firefox restart
- Or go to `about:debugging` → "This Firefox" → "Remove"

**Permanent Installation:**
- Go to `about:addons`
- Find "Media Downloader Connector"
- Click "..." → "Remove"

## Development

### Building from Source

```bash
# Navigate to project root
cd /path/to/image-video-downloader

# Build the extension
cd extension_minimal
zip -r ../dist/extension/media-downloader-connector-firefox-v2.0.zip * -x "*.DS_Store" "*.git*" "*__pycache__*"

# Output will be in dist/extension/
```

### File Structure

```
extension_minimal/
├── manifest.json       # Extension metadata and permissions
├── background.js       # Context menu and communication logic
├── image-picker.js     # Media detection and extraction
├── icon-16.png        # Extension icon (16x16)
├── icon-48.png        # Extension icon (48x48)
└── icon-128.png       # Extension icon (128x128)
```

## Security Notes

- Extension requires `<all_urls>` permission to detect media on any website
- Only sends URLs to localhost:5555 (your local native app)
- No data is sent to external servers
- All media processing happens locally

## Support

If you encounter issues:

1. Check the browser console for JavaScript errors (F12)
2. Verify the native app is running and accessible
3. Test with supported media sources (YouTube, Instagram, etc.)
4. Check that the extension has necessary permissions

---

**Version**: 2.0  
**Compatible**: Firefox 60+  
**Permissions**: Context Menus, Active Tab, All URLs  
**Native App**: Media Downloader v1.0