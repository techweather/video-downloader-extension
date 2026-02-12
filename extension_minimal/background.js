// Create context menu items
browser.contextMenus.create({
  id: "pick-images",
  title: "🖼️  Pick Images (ESC to stop)",
  contexts: ["page"]
});

browser.contextMenus.create({
  id: "download-video",
  title: "🔗  Download Media (works with platform URLs)",
  contexts: ["page", "link", "video"]
});

browser.contextMenus.create({
  id: "download-image", 
  title: "🔗  Download Media (works with platform URLs)",
  contexts: ["image"]
});

browser.contextMenus.create({
  id: "scrape-videos",
  title: "🔎  Extract Direct Videos (scrapes page source)",
  contexts: ["page"]
});

// Function to detect video embeds (Vimeo and YouTube) on a page
function detectVideoEmbeds() {
  console.log('Detecting video embeds...');
  
  const allVideos = [];
  const processedIds = new Set();
  
  // Helper to find title from iframe's parent container
  function findVideoTitle(iframe) {
    let parent = iframe;
    let attempts = 0;
    
    // Search parent containers for title text
    while (parent && attempts < 6) {
      parent = parent.parentElement;
      attempts++;
      
      if (parent) {
        // Look for headings in container
        const headings = parent.querySelectorAll('h1, h2, h3, h4, h5, h6');
        for (const heading of headings) {
          const text = heading.textContent.trim();
          if (text && text.length > 3 && text.length < 100) {
            return text;
          }
        }
        
        // Look for titles in data attributes or aria-labels
        const ariaLabel = parent.getAttribute('aria-label');
        if (ariaLabel && ariaLabel.length > 3) return ariaLabel;
        
        const title = parent.getAttribute('title');
        if (title && title.length > 3) return title;
        
        // Look for figcaption or similar descriptive elements
        const figcaption = parent.querySelector('figcaption');
        if (figcaption) {
          const text = figcaption.textContent.trim();
          if (text && text.length > 3) return text;
        }
        
        // Look for any nearby text elements
        const textElements = parent.querySelectorAll('p, span, div[class*="title"], div[class*="caption"]');
        for (const element of textElements) {
          const text = element.textContent.trim();
          if (text && text.length > 5 && text.length < 80 && !text.includes('http')) {
            return text;
          }
        }
      }
    }
    
    return null;
  }
  
  // Find all Vimeo iframes
  const vimeoIframes = document.querySelectorAll('iframe[src*="player.vimeo.com/video/"]');
  console.log('Found ' + vimeoIframes.length + ' Vimeo iframes');
  
  vimeoIframes.forEach((iframe, index) => {
    try {
      const src = iframe.src;
      console.log('Processing Vimeo iframe ' + (index + 1) + ': ' + src);
      
      // Extract Vimeo ID using regex
      const match = src.match(/player\.vimeo\.com\/video\/(\d+)/);
      if (match) {
        const vimeoId = match[1];
        
        // Avoid duplicates
        if (processedIds.has('vimeo_' + vimeoId)) {
          console.log('Skipping duplicate Vimeo ID: ' + vimeoId);
          return;
        }
        processedIds.add('vimeo_' + vimeoId);
        
        // Try to find a meaningful title
        let title = findVideoTitle(iframe);
        if (!title) {
          title = 'Vimeo Video ' + vimeoId;
        }
        
        // Use original embed URL to preserve ?h= hash for private videos
        const vimeoUrl = iframe.src.split('#')[0];
        
        console.log('Found Vimeo video: ' + title + ' (' + vimeoUrl + ')');
        
        allVideos.push({
          id: vimeoId,
          url: vimeoUrl,
          title: title,
          platform: 'vimeo',
          originalSrc: src
        });
      }
    } catch (error) {
      console.error('Error processing Vimeo iframe:', error);
    }
  });
  
  // Find all YouTube iframes
  const youtubeIframes = document.querySelectorAll('iframe[src*="youtube.com/embed/"], iframe[src*="youtube-nocookie.com/embed/"]');
  console.log('Found ' + youtubeIframes.length + ' YouTube iframes');
  
  youtubeIframes.forEach((iframe, index) => {
    try {
      const src = iframe.src;
      console.log('Processing YouTube iframe ' + (index + 1) + ': ' + src);
      
      // Extract YouTube ID using regex
      const match = src.match(/\/embed\/([a-zA-Z0-9_-]+)/);
      if (match) {
        const youtubeId = match[1];
        
        // Avoid duplicates
        if (processedIds.has('youtube_' + youtubeId)) {
          console.log('Skipping duplicate YouTube ID: ' + youtubeId);
          return;
        }
        processedIds.add('youtube_' + youtubeId);
        
        // Try to find a meaningful title
        let title = findVideoTitle(iframe);
        if (!title) {
          title = 'YouTube Video ' + youtubeId;
        }
        
        // Construct YouTube URL
        const youtubeUrl = 'https://www.youtube.com/watch?v=' + youtubeId;
        
        console.log('Found YouTube video: ' + title + ' (' + youtubeUrl + ')');
        
        allVideos.push({
          id: youtubeId,
          url: youtubeUrl,
          title: title,
          platform: 'youtube',
          originalSrc: src
        });
      }
    } catch (error) {
      console.error('Error processing YouTube iframe:', error);
    }
  });
  
  // Find Mux videos from thumbnails and page data
  const muxIds = new Set();

  // Check img elements for Mux thumbnail URLs
  document.querySelectorAll('img[src*="image.mux.com"]').forEach(function(img) {
    var match = img.src.match(/image\.mux\.com\/([A-Za-z0-9]+)/);
    if (match) muxIds.add(match[1]);
  });

  // Check __NEXT_DATA__ for playbackId fields
  var nextDataScript = document.querySelector('script#__NEXT_DATA__');
  if (nextDataScript) {
    try {
      var nextText = nextDataScript.textContent;
      var re = /"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g;
      var m;
      while ((m = re.exec(nextText)) !== null) {
        muxIds.add(m[1]);
      }
    } catch (e) {}
  }

  // Also check other inline scripts
  document.querySelectorAll('script:not([src])').forEach(function(script) {
    var text = script.textContent;
    if (text.indexOf('playbackId') !== -1 || text.indexOf('mux.com') !== -1) {
      var re = /"playbackId"\s*:\s*"([A-Za-z0-9]+)"/g;
      var m;
      while ((m = re.exec(text)) !== null) {
        muxIds.add(m[1]);
      }
    }
  });

  console.log('Found ' + muxIds.size + ' Mux playback IDs');

  // Build a clean base title from page title (strip site name suffixes)
  var pageTitle = document.title || '';
  // Remove common site name patterns: " — Site Name", " | Site Name", " - Site Name"
  var cleanPageTitle = pageTitle.replace(/\s*[\|\u2014\u2013\-]\s*[^|\u2014\u2013\-]*$/, '').trim();
  if (!cleanPageTitle) cleanPageTitle = 'Video';

  var muxIndex = 0;
  var muxTotal = muxIds.size;

  muxIds.forEach(function(playbackId) {
    if (processedIds.has('mux_' + playbackId)) return;
    processedIds.add('mux_' + playbackId);
    muxIndex++;

    var downloadUrl = 'https://stream.mux.com/' + playbackId + '/high.mp4';

    // Try to find title from nearby thumbnail element
    var title = null;
    var thumbImg = document.querySelector('img[src*="' + playbackId + '"]');
    if (thumbImg) title = findVideoTitle(thumbImg);

    // Fall back to page title with sequence number
    if (!title) {
      title = muxTotal > 1 ? cleanPageTitle + ' - Video ' + muxIndex : cleanPageTitle;
    }

    allVideos.push({
      id: playbackId,
      url: downloadUrl,
      title: title,
      platform: 'mux',
      originalSrc: 'https://stream.mux.com/' + playbackId
    });
  });

  console.log('Total unique video embeds found: ' + allVideos.length);
  return allVideos;
}

// Reusable function to trigger video download on a tab
function triggerVideoDownload(tab, contextInfo) {
  console.log('[DEBUG] Starting enhanced video detection...');
  console.log('[DEBUG] Executing script on tab:', tab.id);

  // First, scan the page for video embeds
  browser.tabs.executeScript(tab.id, {
    code: `
      (function() {
        ${detectVideoEmbeds.toString()}

        // Execute the detection
        const videoEmbeds = detectVideoEmbeds();

        // Also get page metadata
        let thumbnail = null;

        // Try various meta tags for thumbnail
        const metaTags = [
          'meta[property="og:image"]',
          'meta[name="twitter:image"]',
          'meta[itemprop="thumbnailUrl"]',
          'link[rel="image_src"]'
        ];

        for (const selector of metaTags) {
          const meta = document.querySelector(selector);
          if (meta) {
            thumbnail = meta.content || meta.href;
            break;
          }
        }

        // YouTube specific
        if (window.location.hostname.includes('youtube.com')) {
          const videoId = new URLSearchParams(window.location.search).get('v');
          if (videoId) {
            thumbnail = 'https://img.youtube.com/vi/' + videoId + '/maxresdefault.jpg';
          }
        }

        // Instagram specific - try to find image in post
        if (window.location.hostname.includes('instagram.com')) {
          const img = document.querySelector('article img');
          if (img) thumbnail = img.src;
        }

        // Return both video embeds and page data
        return {
          embeds: videoEmbeds,
          pageData: {
            title: document.title,
            thumbnail: thumbnail,
            source: window.location.hostname,
            url: window.location.href
          }
        };
      })();
    `
  }, function(results) {
    console.log('[DEBUG] ====== EXECUTESCRIPT CALLBACK ======');
    console.log('[DEBUG] Callback fired at:', new Date().toISOString());
    console.log('[DEBUG] Raw results:', results);
    console.log('[DEBUG] browser.runtime.lastError:', browser.runtime.lastError);

    if (browser.runtime.lastError) {
      console.error('[DEBUG] ERROR: Script injection failed:', browser.runtime.lastError.message);
      return;
    }

    const result = results && results[0] || { embeds: [], pageData: {} };
    const videoEmbeds = result.embeds;
    const pageData = result.pageData;

    console.log('[DEBUG] Parsed result:', result);
    console.log('[DEBUG] Video embeds found:', videoEmbeds ? videoEmbeds.length : 0);

    console.log('Video embed detection results:', videoEmbeds);
    console.log('Found', videoEmbeds.length, 'video embeds');

    // Determine the URL to use (from context menu info or page URL)
    const url = (contextInfo && (contextInfo.linkUrl || contextInfo.srcUrl || contextInfo.pageUrl)) || pageData.url || tab.url;

    if (videoEmbeds.length >= 2) {
      // Multiple embeds found - send page URL with detected video data
      console.log('[DEBUG] BRANCH: Multiple video embeds (>= 2)');
      console.log('[DEBUG] Detected embeds:', videoEmbeds.map(v => v.platform + ':' + v.id));

      // Format detected videos for the app
      const detectedVideos = videoEmbeds.map(video => ({
        id: video.id,
        platform: video.platform,
        url: video.url,
        title: video.title
      }));

      sendToNativeApp({
        type: 'video',
        url: url,
        title: pageData.title || tab.title,
        thumbnail: pageData.thumbnail,
        pageUrl: pageData.url || (contextInfo && contextInfo.pageUrl) || tab.url,
        source: pageData.source || new URL(url).hostname,
        detectedMultipleEmbeds: true,
        embedCount: videoEmbeds.length,
        embedPlatforms: videoEmbeds.map(v => v.platform),
        detectedVideos: detectedVideos
      });
    } else {
      // 0-1 embeds found - use current behavior (send page URL for yt-dlp)
      console.log('[DEBUG] BRANCH: Standard behavior (0-1 embeds)');
      console.log('[DEBUG] Using yt-dlp for page URL');

      sendToNativeApp({
        type: 'video',
        url: url,
        title: pageData.title || tab.title,
        thumbnail: pageData.thumbnail,
        pageUrl: pageData.url || (contextInfo && contextInfo.pageUrl) || tab.url,
        source: pageData.source || new URL(url).hostname
      });
    }
  });
}

// Reusable function to trigger video scraping on a tab
function triggerScrapeVideos(tab) {
  console.log('Starting video scrape...');

  // Show informative alert about scrolling first
  browser.tabs.executeScript(tab.id, {
    code: `
      (function() {
        if (confirm("📄 IMPORTANT: Video Detection Tips\\n\\n" +
                   "✅ For best results, SCROLL through the entire page first!\\n" +
                   "✅ This loads lazy-loaded videos and dynamic content\\n" +
                   "✅ Wait for videos to appear before running this scan\\n\\n" +
                   "Many modern websites only load videos when they come into view.\\n\\n" +
                   "Click OK to proceed with video detection, or Cancel to scroll first.")) {
          // User confirmed, proceed with scanning
          return true;
        } else {
          // User cancelled, stop here
          return false;
        }
      })();
    `
  }, function(results) {
    if (browser.runtime.lastError) {
      console.error('Script injection error:', browser.runtime.lastError);
      return;
    }

    const userConfirmed = results && results[0];
    if (!userConfirmed) {
      console.log('User cancelled video scraping to scroll first');
      return;
    }

    console.log('User confirmed, proceeding with video scraping...');

    // Inject the video scraping script
    browser.tabs.executeScript(tab.id, {
      code: `
        (function() {
          console.log('Video scraper starting...');

          // Send result back to background script
          function sendVideosToBackground(videos, pageTitle, pageUrl) {
            browser.runtime.sendMessage({
              action: 'videos-found',
              videos: videos,
              pageTitle: pageTitle,
              pageUrl: pageUrl
            });
          }

          try {
            const videos = [];
            const processedUrls = new Set();

            // Helper to resolve relative URLs
            function resolveUrl(url) {
              if (!url) return null;
              try {
                return new URL(url, window.location.href).href;
              } catch {
                return null;
              }
            }

            // Helper to find nearby text for better naming
            function findNearbyText(element) {
              let parent = element;
              let attempts = 0;
              while (parent && attempts < 5) {
                parent = parent.parentElement;
                attempts++;

                const headings = parent ? parent.querySelectorAll('h1, h2, h3, h4, h5') : [];
                for (const heading of headings) {
                  const text = heading.textContent.trim();
                  if (text && text.length > 3 && text.length < 100) {
                    return text;
                  }
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

            // Helper to find nearby image as thumbnail
            function findNearbyImage(element) {
              if (element && element.poster) {
                return resolveUrl(element.poster);
              }

              let parent = element;
              let attempts = 0;
              while (parent && attempts < 4) {
                parent = parent.parentElement;
                attempts++;

                if (parent) {
                  const imgs = parent.querySelectorAll('img');
                  for (const img of imgs) {
                    if (img.src && !img.src.includes('data:') && img.width > 50) {
                      return resolveUrl(img.src);
                    }
                  }

                  const bgImage = window.getComputedStyle(parent).backgroundImage;
                  if (bgImage && bgImage !== 'none') {
                    const match = bgImage.match(/url\\(["']?(.+?)["']?\\)/);
                    if (match && !match[1].includes('data:')) {
                      return resolveUrl(match[1]);
                    }
                  }
                }
              }

              const allImages = document.querySelectorAll('img');
              for (const img of allImages) {
                if (img.src && !img.src.includes('data:') && img.width > 200 && img.height > 100) {
                  return resolveUrl(img.src);
                }
              }
              return null;
            }

            // Helper to extract filename from URL
            function getFilenameFromUrl(url) {
              try {
                const pathname = new URL(url).pathname;
                const filename = pathname.split('/').pop();
                if (filename && filename.includes('.')) {
                  return filename.split('.')[0];
                }
              } catch {}
              return null;
            }

            // 1. Find all <video> elements
            console.log('Looking for video elements...');
            const videoElements = document.querySelectorAll('video');
            console.log('Found', videoElements.length, 'video elements');

            let blobVideoCount = 0;

            videoElements.forEach((video, index) => {
              if (video.src) {
                // Skip blob: URLs (from MediaSource/HLS players like Mux) - not directly downloadable
                if (video.src.startsWith('blob:')) {
                  console.log('Skipping blob: URL on video element', index);
                  blobVideoCount++;
                  return;
                }
                const url = resolveUrl(video.src);
                if (url && !processedUrls.has(url)) {
                  processedUrls.add(url);
                  let title = findNearbyText(video);
                  if (!title) {
                    const filename = getFilenameFromUrl(url);
                    title = filename || ('Video ' + (videos.length + 1));
                  }
                  const thumbnail = findNearbyImage(video);
                  videos.push({
                    url: url,
                    type: 'direct',
                    title: title,
                    thumbnail: thumbnail,
                    originalFilename: getFilenameFromUrl(url)
                  });
                }
              }

              video.querySelectorAll('source').forEach(source => {
                if (source.src && source.src.startsWith('blob:')) {
                  blobVideoCount++;
                  return;
                }
                const url = resolveUrl(source.src);
                if (url && !processedUrls.has(url)) {
                  processedUrls.add(url);
                  let title = findNearbyText(video);
                  if (!title) {
                    const filename = getFilenameFromUrl(url);
                    title = filename || ('Video ' + (videos.length + 1));
                  }
                  const thumbnail = findNearbyImage(video);
                  videos.push({
                    url: url,
                    type: source.type || 'direct',
                    title: title,
                    thumbnail: thumbnail,
                    originalFilename: getFilenameFromUrl(url)
                  });
                }
              });
            });

            console.log('Blob video elements skipped:', blobVideoCount);

            // 2. Look for data attribute videos
            const elementsWithVideoData = document.querySelectorAll('[data-video-src], [data-mp4-src], video[data-src]');
            elementsWithVideoData.forEach(element => {
              ['data-video-src', 'data-mp4-src', 'data-src'].forEach(attr => {
                const url = element.getAttribute(attr);
                if (url) {
                  const fullUrl = resolveUrl(url);
                  if (fullUrl && !processedUrls.has(fullUrl)) {
                    processedUrls.add(fullUrl);
                    let title = findNearbyText(element);
                    if (!title) {
                      const filename = getFilenameFromUrl(fullUrl);
                      title = filename || ('Video ' + (videos.length + 1));
                    }
                    const thumbnail = findNearbyImage(element);
                    videos.push({
                      url: fullUrl,
                      type: 'data-attribute',
                      title: title,
                      thumbnail: thumbnail,
                      originalFilename: getFilenameFromUrl(fullUrl)
                    });
                  }
                }
              });
            });

            // 3. Look in srcset attributes
            document.querySelectorAll('[srcset*=".mp4"]').forEach(element => {
              const srcset = element.getAttribute('srcset');
              if (srcset) {
                const matches = srcset.match(/[^\\s,]+\\.mp4/g);
                if (matches) {
                  matches.forEach(match => {
                    const url = resolveUrl(match);
                    if (url && !processedUrls.has(url)) {
                      processedUrls.add(url);
                      let title = findNearbyText(element);
                      if (!title) {
                        const filename = getFilenameFromUrl(url);
                        title = filename || ('Video ' + (videos.length + 1));
                      }
                      const thumbnail = findNearbyImage(element);
                      videos.push({
                        url: url,
                        type: 'srcset',
                        title: title,
                        thumbnail: thumbnail,
                        originalFilename: getFilenameFromUrl(url)
                      });
                    }
                  });
                }
              }
            });

            // 4. Squarespace hosted videos (data-config-video JSON attribute)
            console.log('Looking for Squarespace hosted videos...');
            document.querySelectorAll('[data-config-video]').forEach(element => {
              try {
                const configJson = element.getAttribute('data-config-video');
                if (!configJson) return;
                const config = JSON.parse(configJson);
                const sc = config.structuredContent || {};
                const alexandriaUrl = sc.alexandriaUrl || config.alexandriaUrl;
                const systemDataId = config.systemDataId;

                if (alexandriaUrl && systemDataId) {
                  // Build HLS playlist URL from the alexandria base
                  // Format: https://video.squarespace-cdn.com/content/v1/{libraryId}/{dataId}/playlist.m3u8
                  const baseUrl = alexandriaUrl.replace(/\\{variant\\}$/, '').replace(/\\/$/, '');
                  const hlsUrl = baseUrl + '/playlist.m3u8';

                  if (!processedUrls.has(hlsUrl)) {
                    processedUrls.add(hlsUrl);
                    const title = config.filename
                      ? config.filename.replace(/\\.[^.]+$/, '')  // strip extension
                      : findNearbyText(element) || ('Video ' + (videos.length + 1));
                    const thumbnail = findNearbyImage(element);
                    console.log('Found Squarespace video:', title, hlsUrl);
                    videos.push({
                      url: hlsUrl,
                      type: 'hls',
                      title: title,
                      thumbnail: thumbnail,
                      originalFilename: config.filename || null
                    });
                  }
                }
              } catch (e) {
                console.log('Error parsing data-config-video:', e);
              }
            });

            // 5. Scan ALL data-* attributes for video URLs (.mp4, .webm, .mov, .m3u8)
            console.log('Scanning data-* attributes for video URLs...');
            document.querySelectorAll('*').forEach(element => {
              for (const attr of element.attributes) {
                if (!attr.name.startsWith('data-') || attr.name === 'data-config-video') continue;
                const val = attr.value;
                if (!val || val.length > 2000) continue;
                // Match URLs containing video extensions
                const urlMatches = val.match(/https?:\\/\\/[^\\s"'<>]+\\.(mp4|webm|mov|m3u8)(\\?[^\\s"'<>]*)?/gi);
                if (urlMatches) {
                  urlMatches.forEach(url => {
                    if (!processedUrls.has(url)) {
                      processedUrls.add(url);
                      const isHls = url.toLowerCase().includes('.m3u8');
                      let title = findNearbyText(element);
                      if (!title) {
                        const filename = getFilenameFromUrl(url);
                        title = filename || ('Video ' + (videos.length + 1));
                      }
                      console.log('Found video URL in', attr.name + ':', url);
                      videos.push({
                        url: url,
                        type: isHls ? 'hls' : 'data-attribute',
                        title: title,
                        thumbnail: findNearbyImage(element),
                        originalFilename: getFilenameFromUrl(url)
                      });
                    }
                  });
                }
              }
            });

            // 6. Video URLs in inline <script> tags (JSON configs, framework data)
            console.log('Scanning inline scripts for video URLs...');
            document.querySelectorAll('script:not([src])').forEach(script => {
              const text = script.textContent;
              if (!text || text.length > 500000) return;
              // Match full video URLs
              const urlPattern = /https?:\\/\\/[^\\s"'<>{}]+\\.(mp4|webm|mov)(\\?[^\\s"'<>{}]*)?/gi;
              let match;
              while ((match = urlPattern.exec(text)) !== null) {
                const url = match[0];
                if (!processedUrls.has(url)) {
                  processedUrls.add(url);
                  console.log('Found video URL in script tag:', url);
                  videos.push({
                    url: url,
                    type: 'script-json',
                    title: getFilenameFromUrl(url) || ('Video ' + (videos.length + 1)),
                    thumbnail: null,
                    originalFilename: getFilenameFromUrl(url)
                  });
                }
              }
            });

            // 7. Preload/prefetch link tags
            console.log('Looking for preloaded video links...');
            document.querySelectorAll('link[rel="preload"][as="video"], link[rel="prefetch"][as="video"], link[rel="preload"][href*=".mp4"], link[rel="preload"][href*=".webm"], link[rel="prefetch"][href*=".mp4"]').forEach(link => {
              const url = resolveUrl(link.href);
              if (url && !processedUrls.has(url)) {
                processedUrls.add(url);
                console.log('Found preloaded video:', url);
                videos.push({
                  url: url,
                  type: 'preload',
                  title: getFilenameFromUrl(url) || ('Video ' + (videos.length + 1)),
                  thumbnail: null,
                  originalFilename: getFilenameFromUrl(url)
                });
              }
            });

            // 8. Meta tags (og:video, twitter:player:stream)
            console.log('Looking for video meta tags...');
            ['meta[property="og:video"]', 'meta[property="og:video:url"]', 'meta[property="og:video:secure_url"]', 'meta[name="twitter:player:stream"]'].forEach(selector => {
              const meta = document.querySelector(selector);
              if (meta && meta.content) {
                const url = resolveUrl(meta.content);
                if (url && !processedUrls.has(url)) {
                  processedUrls.add(url);
                  console.log('Found video meta tag:', selector, url);
                  const isHls = url.toLowerCase().includes('.m3u8');
                  videos.push({
                    url: url,
                    type: isHls ? 'hls' : 'meta-tag',
                    title: document.title || ('Video ' + (videos.length + 1)),
                    thumbnail: null,
                    originalFilename: getFilenameFromUrl(url)
                  });
                }
              }
            });

            // 9. Detect Mux videos from image.mux.com thumbnail URLs in the DOM
            console.log('Looking for Mux video thumbnails...');
            const muxIds = new Set();

            // Check all img elements for Mux thumbnail URLs
            document.querySelectorAll('img[src*="image.mux.com"]').forEach(img => {
              const match = img.src.match(/image\\.mux\\.com\\/([A-Za-z0-9]+)/);
              if (match) muxIds.add(match[1]);
            });

            // Also check srcset, style, and data attributes for Mux references
            document.querySelectorAll('[srcset*="image.mux.com"], [style*="image.mux.com"], [poster*="image.mux.com"]').forEach(el => {
              const text = el.getAttribute('srcset') || el.getAttribute('style') || el.getAttribute('poster') || '';
              const matches = text.matchAll(/image\\.mux\\.com\\/([A-Za-z0-9]+)/g);
              for (const m of matches) muxIds.add(m[1]);
            });

            // 10. Detect Mux videos from __NEXT_DATA__ or inline JSON (Next.js / React SSR pages)
            console.log('Looking for Mux playback IDs in page data...');
            const nextDataScript = document.querySelector('script#__NEXT_DATA__');
            if (nextDataScript) {
              try {
                const nextData = nextDataScript.textContent;
                const playbackMatches = nextData.matchAll(/"playbackId"\\s*:\\s*"([A-Za-z0-9]+)"/g);
                for (const m of playbackMatches) muxIds.add(m[1]);
                console.log('Found playbackIds in __NEXT_DATA__');
              } catch (e) {
                console.log('Error parsing __NEXT_DATA__:', e);
              }
            }

            // Also scan all script tags for playbackId patterns (skip already-scanned ones)
            document.querySelectorAll('script:not([src])').forEach(script => {
              const text = script.textContent;
              if (text.includes('playbackId') || text.includes('mux.com')) {
                const matches = text.matchAll(/"playbackId"\\s*:\\s*"([A-Za-z0-9]+)"/g);
                for (const m of matches) muxIds.add(m[1]);
              }
            });

            console.log('Found', muxIds.size, 'unique Mux playback IDs');

            // Build a clean base title from page title (strip site name suffixes)
            const rawPageTitle = document.title || '';
            const cleanPageTitle = rawPageTitle.replace(/\s*[|\u2014\u2013-]\s*[^|\u2014\u2013-]*$/, '').trim() || 'Video';
            let muxIndex = 0;
            const muxTotal = muxIds.size;

            // Convert Mux IDs to downloadable video entries
            muxIds.forEach(playbackId => {
              const downloadUrl = 'https://stream.mux.com/' + playbackId + '/high.mp4';
              const thumbnailUrl = 'https://image.mux.com/' + playbackId + '/thumbnail.jpg?time=0';
              if (!processedUrls.has(downloadUrl)) {
                processedUrls.add(downloadUrl);
                muxIndex++;

                // Try to find a title from a nearby element that uses this ID as a thumbnail
                let title = null;
                const thumbImg = document.querySelector('img[src*="' + playbackId + '"]');
                if (thumbImg) {
                  title = findNearbyText(thumbImg);
                }
                // Fall back to page title with sequence number
                if (!title) {
                  title = muxTotal > 1 ? cleanPageTitle + ' - Video ' + muxIndex : cleanPageTitle;
                }

                videos.push({
                  url: downloadUrl,
                  type: 'mux',
                  title: title,
                  thumbnail: thumbnailUrl,
                  originalFilename: playbackId
                });
              }
            });

            console.log('Total videos found:', videos.length);

            if (videos.length === 0) {
              let msg = 'No downloadable videos found on this page.';
              if (blobVideoCount > 0) {
                msg += '\\n\\nDetected ' + blobVideoCount + ' video player(s) using blob: URLs (streaming). Try the "Download Media" option instead, which uses yt-dlp for streaming video extraction.';
              } else {
                msg += '\\nThe page may use a different video delivery method or videos may not be loaded yet.';
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
      `
    }, function() {
      if (browser.runtime.lastError) {
        console.error('Script injection error:', browser.runtime.lastError);
      }
    });
  });
}

// Handle keyboard shortcuts
browser.commands.onCommand.addListener((command) => {
  console.log('[DEBUG] ====== KEYBOARD COMMAND ======');
  console.log('[DEBUG] Command:', command);
  console.log('[DEBUG] Timestamp:', new Date().toISOString());

  // Get the active tab for all commands
  browser.tabs.query({ active: true, currentWindow: true }, function(tabs) {
    if (!tabs || !tabs[0]) {
      console.error('[DEBUG] No active tab found');
      return;
    }

    const tab = tabs[0];
    console.log('[DEBUG] Active tab:', tab.id, tab.url);

    if (command === "pick-images") {
      // Same as context menu pick-images - inject image picker
      browser.tabs.executeScript(tab.id, { file: "image-picker.js" });
    }
    else if (command === "download-video") {
      // Same as context menu download-video
      triggerVideoDownload(tab, null);
    }
    else if (command === "scrape-videos") {
      // Same as context menu scrape-videos - extract direct videos
      triggerScrapeVideos(tab);
    }
  });
});

// Handle context menu clicks
browser.contextMenus.onClicked.addListener((info, tab) => {
  console.log('[DEBUG] ====== CONTEXT MENU CLICKED ======');
  console.log('[DEBUG] Menu item:', info.menuItemId);
  console.log('[DEBUG] Tab ID:', tab.id);
  console.log('[DEBUG] Tab URL:', tab.url);
  console.log('[DEBUG] Timestamp:', new Date().toISOString());

  if (info.menuItemId === "download-video") {
    triggerVideoDownload(tab, info);
  }
  
  else if (info.menuItemId === "download-image") {
    console.log('[DEBUG] ====== DOWNLOAD IMAGE ======');
    console.log('[DEBUG] Image URL:', info.srcUrl);
    console.log('[DEBUG] Page URL:', info.pageUrl);

    sendToNativeApp({
      type: 'image',
      url: info.srcUrl,
      thumbnail: info.srcUrl,  // For images, use the image itself as thumbnail
      pageUrl: info.pageUrl,
      source: new URL(info.pageUrl).hostname
    });
  }
  
  else if (info.menuItemId === "pick-images") {
    // Inject the image picker script
    browser.tabs.executeScript(tab.id, { file: "image-picker.js" });
  }
  
  else if (info.menuItemId === "scrape-videos") {
    // Use the refactored function
    triggerScrapeVideos(tab);
  }
});

// Listen for messages from content scripts
browser.runtime.onMessage.addListener((message, sender) => {
  console.log('[DEBUG] ====== MESSAGE FROM CONTENT SCRIPT ======');
  console.log('[DEBUG] Action:', message.action);
  console.log('[DEBUG] Sender tab:', sender.tab ? sender.tab.id : 'unknown');
  console.log('[DEBUG] Full message:', message);
  
  if (message.action === "download-image") {
    sendToNativeApp({
      type: 'image',
      url: message.url,
      thumbnail: message.thumbnail || message.url,
      pageUrl: sender.tab.url,
      source: new URL(sender.tab.url).hostname
    });
  }
  else if (message.action === "videos-found") {
    console.log('Videos found, sending to native app:', message.videos.length);
    
    // Send to native app
    sendToNativeApp({
      type: 'video-list',
      videos: message.videos,
      pageTitle: message.pageTitle,
      pageUrl: message.pageUrl,
      source: new URL(message.pageUrl).hostname
    });
  }
});

// Send data to native app
function sendToNativeApp(data) {
  console.log('[DEBUG] ====== SENDING TO NATIVE APP ======');
  console.log('[DEBUG] Timestamp:', new Date().toISOString());
  console.log('[DEBUG] Data type:', data.type);
  console.log('[DEBUG] URL:', data.url);
  console.log('[DEBUG] Full payload:', JSON.stringify(data, null, 2));

  // Simple HTTP POST to local native app
  console.log('[DEBUG] Making fetch request to http://127.0.0.1:5555/download');

  fetch('http://127.0.0.1:5555/download', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data)
  })
  .then(response => {
    console.log('[DEBUG] Fetch response received');
    console.log('[DEBUG] Response status:', response.status);
    console.log('[DEBUG] Response ok:', response.ok);
    return response.json();
  })
  .then(result => {
    console.log('[DEBUG] Native app result:', result);
    console.log('[DEBUG] ====== DOWNLOAD REQUEST COMPLETE ======');
  })
  .catch(error => {
    console.error('[DEBUG] FETCH ERROR:', error);
    console.error('[DEBUG] Error message:', error.message);
    console.error('[DEBUG] Error stack:', error.stack);
    alert('Failed to connect to downloader app. Make sure it is running.');
  });
}