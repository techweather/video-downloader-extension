# Privacy Policy — dlwithit Connector (browser extension)

_Last updated: 2026-05-20_

## What this extension does

The dlwithit Connector is a companion extension for the **dlwithit** macOS app. Its only job is to send the URL of a video or image you choose (via the right-click menu or a keyboard shortcut) to the dlwithit app running locally on your own computer. The app then downloads that media to your Mac.

## What data is collected

**None.** The extension does not collect, store, transmit, sell, or share any personal information, browsing history, or usage data.

## Where data is sent

URLs you explicitly trigger a download on are sent **only to `http://127.0.0.1:5555`** — that is, to the dlwithit app running on your own computer (`127.0.0.1` is the local loopback address; the data never leaves your machine via this extension).

The extension does not contact any remote server, third-party analytics service, or telemetry endpoint.

## Permissions explained

- **`contextMenus` / `activeTab` / `scripting`** — used to add the right-click "Pick Images" and "Video Download" entries and to read the page when you invoke them.
- **`<all_urls>` / host permissions** — required because downloads can be triggered on any website you visit.
- **`nativeMessaging` (Firefox) / `http://127.0.0.1:5555/*` (Chrome)** — used to communicate with the dlwithit app on your local machine.

## Third parties

None. The extension does not embed third-party SDKs, fonts, scripts, or analytics.

## Children

The extension is not directed at children and does not knowingly collect any data from them (or from anyone).

## Contact

Source code: [github.com/techweather/video-downloader-extension](https://github.com/techweather/video-downloader-extension)

Questions or concerns: open an issue on the GitHub repository.
