// Service worker for Chrome Manifest V3

// Context menus must be created in onInstalled in MV3 service workers
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "pick-images",
    title: "🖼️  Image Picker (ESC to stop)",
    contexts: ["all"]
  });
  chrome.contextMenus.create({
    id: "download-video",
    title: "🎬  Video Download (this page)",
    contexts: ["all"]
  });
});

// Detect embedded videos and collect page metadata.
// Must be self-contained — no references to outer scope (injected via func:).
function collectPageData() {
  const allVideos = [];
  const processedIds = new Set();

  function findVideoTitle(iframe) {
    let parent = iframe;
    let attempts = 0;
    while (parent && attempts < 6) {
      parent = parent.parentElement;
      attempts++;
      if (parent) {
        const headings = parent.querySelectorAll('h1, h2, h3, h4, h5, h6');
        for (const heading of headings) {
          const text = heading.textContent.trim();
          if (text && text.length > 3 && text.length < 100) return text;
        }
        const ariaLabel = parent.getAttribute('aria-label');
        if (ariaLabel && ariaLabel.length > 3) return ariaLabel;
        const title = parent.getAttribute('title');
        if (title && title.length > 3) return title;
        const figcaption = parent.querySelector('figcaption');
        if (figcaption) {
          const text = figcaption.textContent.trim();
          if (text && text.length > 3) return text;
        }
        const textElements = parent.querySelectorAll('p, span, div[class*="title"], div[class*="caption"]');
        for (const element of textElements) {
          const text = element.textContent.trim();
          if (text && text.length > 5 && text.length < 80 && !text.includes('http')) return text;
        }
      }
    }
    return null;
  }

  // Vimeo iframes
  document.querySelectorAll('iframe[src*="player.vimeo.com/video/"]').forEach(iframe => {
    try {
      const match = iframe.src.match(/player\.vimeo\.com\/video\/(\d+)/);
      if (match) {
        const vimeoId = match[1];
        if (!processedIds.has('vimeo_' + vimeoId)) {
          processedIds.add('vimeo_' + vimeoId);
          const title = findVideoTitle(iframe) || ('Vimeo Video ' + vimeoId);
          allVideos.push({ id: vimeoId, url: iframe.src.split('#')[0], title, platform: 'vimeo', originalSrc: iframe.src });
        }
      }
    } catch (e) {}
  });

  // YouTube iframes
  document.querySelectorAll('iframe[src*="youtube.com/embed/"], iframe[src*="youtube-nocookie.com/embed/"]').forEach(iframe => {
    try {
      const match = iframe.src.match(/\/embed\/([a-zA-Z0-9_-]+)/);
      if (match) {
        const youtubeId = match[1];
        if (!processedIds.has('youtube_' + youtubeId)) {
          processedIds.add('youtube_' + youtubeId);
          const title = findVideoTitle(iframe) || ('YouTube Video ' + youtubeId);
          allVideos.push({ id: youtubeId, url: 'https://www.youtube.com/watch?v=' + youtubeId, title, platform: 'youtube', originalSrc: iframe.src });
        }
      }
    } catch (e) {}
  });

  // Mux videos
  const muxIds = new Set();
  document.querySelectorAll('mux-player[playback-id]').forEach(p => {
    const id = p.getAttribute('playback-id');
    if (id) muxIds.add(id);
  });
  document.querySelectorAll('mux-player[poster*="image.mux.com"]').forEach(p => {
    const m = p.getAttribute('poster').match(/image\.mux\.com\/([A-Za-z0-9]+)/);
    if (m) muxIds.add(m[1]);
  });
  document.querySelectorAll('img[src*="image.mux.com"]').forEach(img => {
    const m = img.src.match(/image\.mux\.com\/([A-Za-z0-9]+)/);
    if (m) muxIds.add(m[1]);
  });
  const nextDataScript = document.querySelector('script#__NEXT_DATA__');
  if (nextDataScript) {
    try {
      const re = /"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g;
      let m;
      while ((m = re.exec(nextDataScript.textContent)) !== null) muxIds.add(m[1]);
    } catch (e) {}
  }
  document.querySelectorAll('script:not([src])').forEach(script => {
    const text = script.textContent;
    if (text.indexOf('playbackId') !== -1 || text.indexOf('mux.com') !== -1) {
      const re = /"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g;
      let m;
      while ((m = re.exec(text)) !== null) muxIds.add(m[1]);
    }
  });

  const pageTitle = document.title || '';
  const cleanPageTitle = pageTitle.replace(/\s*[|\u2014\u2013-]\s*[^|\u2014\u2013-]*$/, '').trim() || 'Video';
  let muxIndex = 0;
  const muxTotal = muxIds.size;

  muxIds.forEach(playbackId => {
    if (processedIds.has('mux_' + playbackId)) return;
    processedIds.add('mux_' + playbackId);
    muxIndex++;
    let title = null;
    const muxPlayer = document.querySelector('mux-player[playback-id="' + playbackId + '"]');
    if (muxPlayer) title = findVideoTitle(muxPlayer);
    if (!title) {
      const thumbImg = document.querySelector('img[src*="' + playbackId + '"]');
      if (thumbImg) title = findVideoTitle(thumbImg);
    }
    if (!title) title = muxTotal > 1 ? cleanPageTitle + ' - Video ' + muxIndex : cleanPageTitle;
    allVideos.push({
      id: playbackId,
      url: 'https://stream.mux.com/' + playbackId + '/high.mp4',
      title,
      platform: 'mux',
      originalSrc: 'https://stream.mux.com/' + playbackId
    });
  });

  // Page metadata
  let thumbnail = null;
  const metaSelectors = [
    'meta[property="og:image"]',
    'meta[name="twitter:image"]',
    'meta[itemprop="thumbnailUrl"]',
    'link[rel="image_src"]'
  ];
  for (const selector of metaSelectors) {
    const meta = document.querySelector(selector);
    if (meta) { thumbnail = meta.content || meta.href; break; }
  }
  if (window.location.hostname.includes('youtube.com')) {
    const videoId = new URLSearchParams(window.location.search).get('v');
    if (videoId) thumbnail = 'https://img.youtube.com/vi/' + videoId + '/maxresdefault.jpg';
  }
  if (window.location.hostname.includes('instagram.com')) {
    const img = document.querySelector('article img');
    if (img) thumbnail = img.src;
  }

  return {
    embeds: allVideos,
    pageData: {
      title: document.title,
      thumbnail,
      source: window.location.hostname,
      url: window.location.href
    }
  };
}

// Self-contained DOM scan injected into the page as a last resort.
// Returns results directly — no message passing needed.
function domScanForVideos() {
  const videos = [];
  const processedUrls = new Set();
  let blobVideoCount = 0;

  function resolveUrl(url) {
    if (!url) return null;
    try { return new URL(url, window.location.href).href; } catch { return null; }
  }

  function findNearbyText(element) {
    let parent = element;
    let attempts = 0;
    while (parent && attempts < 5) {
      parent = parent.parentElement;
      attempts++;
      const headings = parent ? parent.querySelectorAll('h1, h2, h3, h4, h5') : [];
      for (const heading of headings) {
        const text = heading.textContent.trim();
        if (text && text.length > 3 && text.length < 100) return text;
      }
      if (parent) {
        const ariaLabel = parent.getAttribute('aria-label');
        if (ariaLabel && ariaLabel.length > 3) return ariaLabel;
        const title = parent.getAttribute('title');
        if (title && title.length > 3) return title;
      }
    }
    return null;
  }

  function findNearbyImage(element) {
    if (element && element.poster) return resolveUrl(element.poster);
    let parent = element;
    let attempts = 0;
    while (parent && attempts < 4) {
      parent = parent.parentElement;
      attempts++;
      if (parent) {
        const imgs = parent.querySelectorAll('img');
        for (const img of imgs) {
          if (img.src && !img.src.includes('data:') && img.width > 50) return resolveUrl(img.src);
        }
        const bgImage = window.getComputedStyle(parent).backgroundImage;
        if (bgImage && bgImage !== 'none') {
          const match = bgImage.match(/url\(["']?(.+?)["']?\)/);
          if (match && !match[1].includes('data:')) return resolveUrl(match[1]);
        }
      }
    }
    const allImages = document.querySelectorAll('img');
    for (const img of allImages) {
      if (img.src && !img.src.includes('data:') && img.width > 200 && img.height > 100) return resolveUrl(img.src);
    }
    return null;
  }

  function getFilenameFromUrl(url) {
    try {
      const filename = new URL(url).pathname.split('/').pop();
      if (filename && filename.includes('.')) return filename.split('.')[0];
    } catch {}
    return null;
  }

  // 1. <video> elements
  document.querySelectorAll('video').forEach((video) => {
    if (video.src) {
      if (video.src.startsWith('blob:')) { blobVideoCount++; }
      else {
        const url = resolveUrl(video.src);
        if (url && !processedUrls.has(url)) {
          processedUrls.add(url);
          const title = findNearbyText(video) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
          videos.push({ url, type: 'direct', title, thumbnail: findNearbyImage(video), originalFilename: getFilenameFromUrl(url) });
        }
      }
    }
    video.querySelectorAll('source').forEach(source => {
      if (source.src && source.src.startsWith('blob:')) { blobVideoCount++; return; }
      const url = resolveUrl(source.src);
      if (url && !processedUrls.has(url)) {
        processedUrls.add(url);
        const title = findNearbyText(video) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
        videos.push({ url, type: source.type || 'direct', title, thumbnail: findNearbyImage(video), originalFilename: getFilenameFromUrl(url) });
      }
    });
  });

  // 2. data attribute videos
  document.querySelectorAll('[data-video-src], [data-mp4-src], video[data-src]').forEach(element => {
    ['data-video-src', 'data-mp4-src', 'data-src'].forEach(attr => {
      const fullUrl = resolveUrl(element.getAttribute(attr));
      if (fullUrl && !processedUrls.has(fullUrl)) {
        processedUrls.add(fullUrl);
        const title = findNearbyText(element) || getFilenameFromUrl(fullUrl) || ('Video ' + (videos.length + 1));
        videos.push({ url: fullUrl, type: 'data-attribute', title, thumbnail: findNearbyImage(element), originalFilename: getFilenameFromUrl(fullUrl) });
      }
    });
  });

  // 3. srcset with .mp4
  document.querySelectorAll('[srcset*=".mp4"]').forEach(element => {
    const srcset = element.getAttribute('srcset');
    if (srcset) {
      (srcset.match(/[^\s,]+\.mp4/g) || []).forEach(match => {
        const url = resolveUrl(match);
        if (url && !processedUrls.has(url)) {
          processedUrls.add(url);
          const title = findNearbyText(element) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
          videos.push({ url, type: 'srcset', title, thumbnail: findNearbyImage(element), originalFilename: getFilenameFromUrl(url) });
        }
      });
    }
  });

  // 4. Squarespace (data-config-video)
  document.querySelectorAll('[data-config-video]').forEach(element => {
    try {
      const config = JSON.parse(element.getAttribute('data-config-video') || '{}');
      const sc = config.structuredContent || {};
      const alexandriaUrl = sc.alexandriaUrl || config.alexandriaUrl;
      if (alexandriaUrl && config.systemDataId) {
        const hlsUrl = alexandriaUrl.replace(/\{variant\}$/, '').replace(/\/$/, '') + '/playlist.m3u8';
        if (!processedUrls.has(hlsUrl)) {
          processedUrls.add(hlsUrl);
          const title = config.filename ? config.filename.replace(/\.[^.]+$/, '') : findNearbyText(element) || ('Video ' + (videos.length + 1));
          videos.push({ url: hlsUrl, type: 'hls', title, thumbnail: findNearbyImage(element), originalFilename: config.filename || null });
        }
      }
    } catch (e) {}
  });

  // 5. All data-* attributes containing video URLs
  document.querySelectorAll('*').forEach(element => {
    for (const attr of element.attributes) {
      if (!attr.name.startsWith('data-') || attr.name === 'data-config-video') continue;
      if (!attr.value || attr.value.length > 2000) continue;
      const urlMatches = attr.value.match(/https?:\/\/[^\s"'<>]+\.(mp4|webm|mov|m3u8)(\?[^\s"'<>]*)?/gi);
      if (urlMatches) {
        urlMatches.forEach(url => {
          if (!processedUrls.has(url)) {
            processedUrls.add(url);
            const title = findNearbyText(element) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
            videos.push({ url, type: url.toLowerCase().includes('.m3u8') ? 'hls' : 'data-attribute', title, thumbnail: findNearbyImage(element), originalFilename: getFilenameFromUrl(url) });
          }
        });
      }
    }
  });

  // 6. Inline <script> tags
  document.querySelectorAll('script:not([src])').forEach(script => {
    const text = script.textContent;
    if (!text || text.length > 500000) return;
    const urlPattern = /https?:\/\/[^\s"'<>{}]+\.(mp4|webm|mov)(\?[^\s"'<>{}]*)?/gi;
    let match;
    while ((match = urlPattern.exec(text)) !== null) {
      const url = match[0];
      if (!processedUrls.has(url)) {
        processedUrls.add(url);
        videos.push({ url, type: 'script-json', title: getFilenameFromUrl(url) || ('Video ' + (videos.length + 1)), thumbnail: null, originalFilename: getFilenameFromUrl(url) });
      }
    }
  });

  // 7. Preload/prefetch link tags
  document.querySelectorAll('link[rel="preload"][as="video"], link[rel="prefetch"][as="video"], link[rel="preload"][href*=".mp4"], link[rel="preload"][href*=".webm"], link[rel="prefetch"][href*=".mp4"]').forEach(link => {
    const url = resolveUrl(link.href);
    if (url && !processedUrls.has(url)) {
      processedUrls.add(url);
      videos.push({ url, type: 'preload', title: getFilenameFromUrl(url) || ('Video ' + (videos.length + 1)), thumbnail: null, originalFilename: getFilenameFromUrl(url) });
    }
  });

  // 8. Meta tags
  ['meta[property="og:video"]', 'meta[property="og:video:url"]', 'meta[property="og:video:secure_url"]', 'meta[name="twitter:player:stream"]'].forEach(selector => {
    const meta = document.querySelector(selector);
    if (meta && meta.content) {
      const url = resolveUrl(meta.content);
      if (url && !processedUrls.has(url)) {
        processedUrls.add(url);
        videos.push({ url, type: url.toLowerCase().includes('.m3u8') ? 'hls' : 'meta-tag', title: document.title || ('Video ' + (videos.length + 1)), thumbnail: null, originalFilename: getFilenameFromUrl(url) });
      }
    }
  });

  // 9. Mux detection
  const muxIds = new Set();
  document.querySelectorAll('mux-player[playback-id]').forEach(p => { const id = p.getAttribute('playback-id'); if (id) muxIds.add(id); });
  document.querySelectorAll('mux-player[poster*="image.mux.com"]').forEach(p => { const m = p.getAttribute('poster').match(/image\.mux\.com\/([A-Za-z0-9]+)/); if (m) muxIds.add(m[1]); });
  document.querySelectorAll('img[src*="image.mux.com"]').forEach(img => { const m = img.src.match(/image\.mux\.com\/([A-Za-z0-9]+)/); if (m) muxIds.add(m[1]); });
  document.querySelectorAll('[srcset*="image.mux.com"], [style*="image.mux.com"], [poster*="image.mux.com"]').forEach(el => {
    const text = el.getAttribute('srcset') || el.getAttribute('style') || el.getAttribute('poster') || '';
    for (const m of text.matchAll(/image\.mux\.com\/([A-Za-z0-9]+)/g)) muxIds.add(m[1]);
  });
  const nextDataScript = document.querySelector('script#__NEXT_DATA__');
  if (nextDataScript) {
    try { for (const m of nextDataScript.textContent.matchAll(/"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g)) muxIds.add(m[1]); } catch (e) {}
  }
  document.querySelectorAll('script:not([src])').forEach(script => {
    const text = script.textContent;
    if (text.includes('playbackId') || text.includes('mux.com')) {
      for (const m of text.matchAll(/"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g)) muxIds.add(m[1]);
    }
  });

  const cleanPageTitle = (document.title || '').replace(/\s*[|\u2014\u2013-]\s*[^|\u2014\u2013-]*$/, '').trim() || 'Video';
  let muxIndex = 0;
  const muxTotal = muxIds.size;
  muxIds.forEach(playbackId => {
    const downloadUrl = 'https://stream.mux.com/' + playbackId + '/high.mp4';
    if (!processedUrls.has(downloadUrl)) {
      processedUrls.add(downloadUrl);
      muxIndex++;
      let title = null;
      const muxPlayer = document.querySelector('mux-player[playback-id="' + playbackId + '"]');
      if (muxPlayer) title = findNearbyText(muxPlayer);
      if (!title) { const thumbImg = document.querySelector('img[src*="' + playbackId + '"]'); if (thumbImg) title = findNearbyText(thumbImg); }
      if (!title) title = muxTotal > 1 ? cleanPageTitle + ' - Video ' + muxIndex : cleanPageTitle;
      videos.push({ url: downloadUrl, type: 'mux', title, thumbnail: 'https://image.mux.com/' + playbackId + '/thumbnail.jpg?time=0', originalFilename: playbackId });
    }
  });

  return { videos, blobVideoCount, pageTitle: document.title, pageUrl: window.location.href };
}

// Combined video download:
// 1. Run collectPageData to find platform embeds (Vimeo/YouTube/Mux)
// 2. If found, send to app directly
// 3. If not, classify the URL via /classify
// 4. If supported by yt-dlp, send as video
// 5. If not, run DOM scan as last resort
async function triggerCombinedVideoDownload(tab) {
  let results;
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: collectPageData
    });
  } catch (e) {
    return;
  }

  const result = (results && results[0] && results[0].result) || { embeds: [], pageData: {} };
  const videoEmbeds = result.embeds;
  const pageData = result.pageData;
  const pageUrl = pageData.url || tab.url;

  if (videoEmbeds.length >= 1) {
    if (videoEmbeds.length >= 2) {
      sendToNativeApp({
        type: 'video',
        url: pageUrl,
        title: pageData.title || tab.title,
        thumbnail: pageData.thumbnail,
        pageUrl,
        source: pageData.source || new URL(pageUrl).hostname,
        detectedMultipleEmbeds: true,
        embedCount: videoEmbeds.length,
        embedPlatforms: videoEmbeds.map(v => v.platform),
        detectedVideos: videoEmbeds.map(v => ({ id: v.id, platform: v.platform, url: v.url, title: v.title }))
      }, tab.id);
    } else {
      sendToNativeApp({
        type: 'video',
        url: pageUrl,
        title: pageData.title || tab.title,
        thumbnail: pageData.thumbnail,
        pageUrl,
        source: pageData.source || new URL(pageUrl).hostname
      }, tab.id);
    }
    return;
  }

  // No platform embeds — classify the URL
  let classified;
  try {
    const response = await fetch('http://127.0.0.1:5555/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: pageUrl })
    });
    classified = await response.json();
  } catch {
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => alert('Failed to connect to dlwithit app. Make sure it is running.')
    }).catch(() => {});
    return;
  }

  if (classified.supported) {
    sendToNativeApp({
      type: 'video',
      url: pageUrl,
      title: pageData.title || tab.title,
      thumbnail: pageData.thumbnail,
      pageUrl,
      source: pageData.source || new URL(pageUrl).hostname
    }, tab.id);
  } else {
    // DOM scan — last resort
    let scanResults;
    try {
      scanResults = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: domScanForVideos
      });
    } catch (e) {
      return;
    }

    const scan = (scanResults && scanResults[0] && scanResults[0].result) || { videos: [], blobVideoCount: 0 };
    if (scan.videos.length === 0) {
      let msg = 'No downloadable videos found on this page.';
      if (scan.blobVideoCount > 0) {
        msg += '\n\nDetected ' + scan.blobVideoCount + ' video player(s) using blob: URLs (streaming). Try navigating to a specific video page first, then use Video Download.';
      } else {
        msg += '\nThe page may use a different video delivery method or videos may not be loaded yet.';
      }
      chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (message) => alert(message),
        args: [msg]
      }).catch(() => {});
    } else {
      sendToNativeApp({
        type: 'video-list',
        videos: scan.videos,
        pageTitle: scan.pageTitle,
        pageUrl: scan.pageUrl,
        source: new URL(scan.pageUrl).hostname
      }, tab.id);
    }
  }
}

// Keyboard shortcuts
chrome.commands.onCommand.addListener(async (command) => {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tabs || !tabs[0]) return;
  const tab = tabs[0];
  if (command === "pick-images") {
    chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["image-picker.js"] });
  } else if (command === "download-video") {
    triggerCombinedVideoDownload(tab);
  }
});

// Context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "download-video") {
    triggerCombinedVideoDownload(tab);
  } else if (info.menuItemId === "pick-images") {
    chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["image-picker.js"] });
  }
});

// Messages from content scripts (image-picker.js)
chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.action === "download-image") {
    sendToNativeApp({
      type: 'image',
      url: message.url,
      thumbnail: message.thumbnail || message.url,
      pageUrl: sender.tab.url,
      source: new URL(sender.tab.url).hostname
    });
  }
});

async function sendToNativeApp(data, tabId) {
  try {
    const response = await fetch('http://127.0.0.1:5555/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return await response.json();
  } catch (error) {
    if (tabId) {
      chrome.scripting.executeScript({
        target: { tabId },
        func: () => alert('Failed to connect to dlwithit app. Make sure it is running.')
      }).catch(() => {});
    }
  }
}
