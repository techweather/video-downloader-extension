// Injected content script — scans the page for direct video URLs and sends them to the background
(function() {
  function sendVideosToBackground(videos, pageTitle, pageUrl) {
    chrome.runtime.sendMessage({
      action: 'videos-found',
      videos: videos,
      pageTitle: pageTitle,
      pageUrl: pageUrl
    });
  }

  try {
    const videos = [];
    const processedUrls = new Set();

    function resolveUrl(url) {
      if (!url) return null;
      try {
        return new URL(url, window.location.href).href;
      } catch {
        return null;
      }
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
        const pathname = new URL(url).pathname;
        const filename = pathname.split('/').pop();
        if (filename && filename.includes('.')) return filename.split('.')[0];
      } catch {}
      return null;
    }

    // 1. <video> elements
    const videoElements = document.querySelectorAll('video');
    let blobVideoCount = 0;

    videoElements.forEach(video => {
      if (video.src) {
        if (video.src.startsWith('blob:')) { blobVideoCount++; return; }
        const url = resolveUrl(video.src);
        if (url && !processedUrls.has(url)) {
          processedUrls.add(url);
          const title = findNearbyText(video) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
          videos.push({ url, type: 'direct', title, thumbnail: findNearbyImage(video), originalFilename: getFilenameFromUrl(url) });
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
        const url = element.getAttribute(attr);
        if (url) {
          const fullUrl = resolveUrl(url);
          if (fullUrl && !processedUrls.has(fullUrl)) {
            processedUrls.add(fullUrl);
            const title = findNearbyText(element) || getFilenameFromUrl(fullUrl) || ('Video ' + (videos.length + 1));
            videos.push({ url: fullUrl, type: 'data-attribute', title, thumbnail: findNearbyImage(element), originalFilename: getFilenameFromUrl(fullUrl) });
          }
        }
      });
    });

    // 3. srcset with .mp4
    document.querySelectorAll('[srcset*=".mp4"]').forEach(element => {
      const srcset = element.getAttribute('srcset');
      if (srcset) {
        const matches = srcset.match(/[^\s,]+\.mp4/g);
        if (matches) {
          matches.forEach(match => {
            const url = resolveUrl(match);
            if (url && !processedUrls.has(url)) {
              processedUrls.add(url);
              const title = findNearbyText(element) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
              videos.push({ url, type: 'srcset', title, thumbnail: findNearbyImage(element), originalFilename: getFilenameFromUrl(url) });
            }
          });
        }
      }
    });

    // 4. Squarespace hosted videos
    document.querySelectorAll('[data-config-video]').forEach(element => {
      try {
        const configJson = element.getAttribute('data-config-video');
        if (!configJson) return;
        const config = JSON.parse(configJson);
        const sc = config.structuredContent || {};
        const alexandriaUrl = sc.alexandriaUrl || config.alexandriaUrl;
        const systemDataId = config.systemDataId;
        if (alexandriaUrl && systemDataId) {
          const baseUrl = alexandriaUrl.replace(/\{variant\}$/, '').replace(/\/$/, '');
          const hlsUrl = baseUrl + '/playlist.m3u8';
          if (!processedUrls.has(hlsUrl)) {
            processedUrls.add(hlsUrl);
            const title = config.filename
              ? config.filename.replace(/\.[^.]+$/, '')
              : findNearbyText(element) || ('Video ' + (videos.length + 1));
            videos.push({ url: hlsUrl, type: 'hls', title, thumbnail: findNearbyImage(element), originalFilename: config.filename || null });
          }
        }
      } catch (e) {}
    });

    // 5. All data-* attributes containing video URLs
    document.querySelectorAll('*').forEach(element => {
      for (const attr of element.attributes) {
        if (!attr.name.startsWith('data-') || attr.name === 'data-config-video') continue;
        const val = attr.value;
        if (!val || val.length > 2000) continue;
        const urlMatches = val.match(/https?:\/\/[^\s"'<>]+\.(mp4|webm|mov|m3u8)(\?[^\s"'<>]*)?/gi);
        if (urlMatches) {
          urlMatches.forEach(url => {
            if (!processedUrls.has(url)) {
              processedUrls.add(url);
              const isHls = url.toLowerCase().includes('.m3u8');
              const title = findNearbyText(element) || getFilenameFromUrl(url) || ('Video ' + (videos.length + 1));
              videos.push({ url, type: isHls ? 'hls' : 'data-attribute', title, thumbnail: findNearbyImage(element), originalFilename: getFilenameFromUrl(url) });
            }
          });
        }
      }
    });

    // 6. Video URLs in inline <script> tags
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
          const isHls = url.toLowerCase().includes('.m3u8');
          videos.push({ url, type: isHls ? 'hls' : 'meta-tag', title: document.title || ('Video ' + (videos.length + 1)), thumbnail: null, originalFilename: getFilenameFromUrl(url) });
        }
      }
    });

    // 9. Mux videos
    const muxIds = new Set();
    document.querySelectorAll('mux-player[playback-id]').forEach(player => {
      const id = player.getAttribute('playback-id');
      if (id) muxIds.add(id);
    });
    document.querySelectorAll('mux-player[poster*="image.mux.com"]').forEach(player => {
      const match = player.getAttribute('poster').match(/image\.mux\.com\/([A-Za-z0-9]+)/);
      if (match) muxIds.add(match[1]);
    });
    document.querySelectorAll('img[src*="image.mux.com"]').forEach(img => {
      const match = img.src.match(/image\.mux\.com\/([A-Za-z0-9]+)/);
      if (match) muxIds.add(match[1]);
    });
    document.querySelectorAll('[srcset*="image.mux.com"], [style*="image.mux.com"], [poster*="image.mux.com"]').forEach(el => {
      const text = el.getAttribute('srcset') || el.getAttribute('style') || el.getAttribute('poster') || '';
      const matches = text.matchAll(/image\.mux\.com\/([A-Za-z0-9]+)/g);
      for (const m of matches) muxIds.add(m[1]);
    });

    // 10. Mux from __NEXT_DATA__ and inline scripts
    const nextDataScript = document.querySelector('script#__NEXT_DATA__');
    if (nextDataScript) {
      try {
        const playbackMatches = nextDataScript.textContent.matchAll(/"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g);
        for (const m of playbackMatches) muxIds.add(m[1]);
      } catch (e) {}
    }
    document.querySelectorAll('script:not([src])').forEach(script => {
      const text = script.textContent;
      if (text.includes('playbackId') || text.includes('mux.com')) {
        const matches = text.matchAll(/"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g);
        for (const m of matches) muxIds.add(m[1]);
      }
    });

    const rawPageTitle = document.title || '';
    const cleanPageTitle = rawPageTitle.replace(/\s*[|\u2014\u2013-]\s*[^|\u2014\u2013-]*$/, '').trim() || 'Video';
    let muxIndex = 0;
    const muxTotal = muxIds.size;

    muxIds.forEach(playbackId => {
      const downloadUrl = 'https://stream.mux.com/' + playbackId + '/high.mp4';
      const thumbnailUrl = 'https://image.mux.com/' + playbackId + '/thumbnail.jpg?time=0';
      if (!processedUrls.has(downloadUrl)) {
        processedUrls.add(downloadUrl);
        muxIndex++;
        let title = null;
        const muxPlayer = document.querySelector('mux-player[playback-id="' + playbackId + '"]');
        if (muxPlayer) title = findNearbyText(muxPlayer);
        if (!title) {
          const thumbImg = document.querySelector('img[src*="' + playbackId + '"]');
          if (thumbImg) title = findNearbyText(thumbImg);
        }
        if (!title) title = muxTotal > 1 ? cleanPageTitle + ' - Video ' + muxIndex : cleanPageTitle;
        videos.push({ url: downloadUrl, type: 'mux', title, thumbnail: thumbnailUrl, originalFilename: playbackId });
      }
    });

    if (videos.length === 0) {
      let msg = 'No downloadable videos found on this page.';
      if (blobVideoCount > 0) {
        msg += '\n\nDetected ' + blobVideoCount + ' video player(s) using blob: URLs (streaming). Try the "Download Media" option instead, which uses yt-dlp for streaming video extraction.';
      } else {
        msg += '\nThe page may use a different video delivery method or videos may not be loaded yet.';
      }
      alert(msg);
    } else {
      sendVideosToBackground(videos, document.title, window.location.href);
    }
  } catch (error) {
    console.error('Error scanning for videos:', error);
    alert('Error scanning for videos: ' + error.message);
  }
})();
