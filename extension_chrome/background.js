// Service worker for Chrome Manifest V3

// Context menus must be created in onInstalled in MV3 service workers
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "pick-images",
    title: "🖼️  Pick Images (ESC to stop)",
    contexts: ["all"]
  });
  chrome.contextMenus.create({
    id: "download-video",
    title: "🔗  Download Media (works with platform URLs)",
    contexts: ["all"]
  });
  chrome.contextMenus.create({
    id: "scrape-videos",
    title: "🔎  Extract Direct Videos (scrapes page source)",
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

async function triggerVideoDownload(tab, contextInfo) {
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

  const url = (contextInfo && (contextInfo.linkUrl || contextInfo.srcUrl || contextInfo.pageUrl)) || pageData.url || tab.url;

  if (videoEmbeds.length >= 2) {
    const detectedVideos = videoEmbeds.map(video => ({
      id: video.id,
      platform: video.platform,
      url: video.url,
      title: video.title
    }));
    sendToNativeApp({
      type: 'video',
      url,
      title: pageData.title || tab.title,
      thumbnail: pageData.thumbnail,
      pageUrl: pageData.url || (contextInfo && contextInfo.pageUrl) || tab.url,
      source: pageData.source || new URL(url).hostname,
      detectedMultipleEmbeds: true,
      embedCount: videoEmbeds.length,
      embedPlatforms: videoEmbeds.map(v => v.platform),
      detectedVideos
    }, tab.id);
  } else {
    sendToNativeApp({
      type: 'video',
      url,
      title: pageData.title || tab.title,
      thumbnail: pageData.thumbnail,
      pageUrl: pageData.url || (contextInfo && contextInfo.pageUrl) || tab.url,
      source: pageData.source || new URL(url).hostname
    }, tab.id);
  }
}

async function triggerScrapeVideos(tab) {
  // Show scroll-first reminder in the tab context (alert/confirm not available in service worker)
  let confirmResults;
  try {
    confirmResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: function() {
        return confirm(
          "📄 IMPORTANT: Video Detection Tips\n\n" +
          "✅ For best results, SCROLL through the entire page first!\n" +
          "✅ This loads lazy-loaded videos and dynamic content\n" +
          "✅ Wait for videos to appear before running this scan\n\n" +
          "Many modern websites only load videos when they come into view.\n\n" +
          "Click OK to proceed with video detection, or Cancel to scroll first."
        );
      }
    });
  } catch (e) {
    return;
  }

  const userConfirmed = confirmResults && confirmResults[0] && confirmResults[0].result;
  if (!userConfirmed) return;

  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["video-scrape.js"]
    });
  } catch (e) {}
}

// Keyboard shortcuts
chrome.commands.onCommand.addListener((command) => {
  chrome.tabs.query({ active: true, currentWindow: true }, function(tabs) {
    if (!tabs || !tabs[0]) return;
    const tab = tabs[0];
    if (command === "pick-images") {
      chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["image-picker.js"] });
    } else if (command === "download-video") {
      triggerVideoDownload(tab, null);
    } else if (command === "scrape-videos") {
      triggerScrapeVideos(tab);
    }
  });
});

// Context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "download-video") {
    triggerVideoDownload(tab, info);
  } else if (info.menuItemId === "pick-images") {
    chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["image-picker.js"] });
  } else if (info.menuItemId === "scrape-videos") {
    triggerScrapeVideos(tab);
  }
});

// Messages from content scripts
chrome.runtime.onMessage.addListener((message, sender) => {
  if (message.action === "download-image") {
    sendToNativeApp({
      type: 'image',
      url: message.url,
      thumbnail: message.thumbnail || message.url,
      pageUrl: sender.tab.url,
      source: new URL(sender.tab.url).hostname
    });
  } else if (message.action === "videos-found") {
    sendToNativeApp({
      type: 'video-list',
      videos: message.videos,
      pageTitle: message.pageTitle,
      pageUrl: message.pageUrl,
      source: new URL(message.pageUrl).hostname
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
