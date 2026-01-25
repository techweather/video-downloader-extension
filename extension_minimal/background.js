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

browser.contextMenus.create({
  id: "download-vimeo-videos",
  title: "🎬  Download All Vimeo Videos",
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
  
  console.log('Total unique video embeds found: ' + allVideos.length);
  return allVideos;
}

// Function to detect Vimeo embeds on a page (kept for backward compatibility)
function detectVimeoEmbeds() {
  console.log('Detecting Vimeo embeds...');
  
  const vimeoVideos = [];
  const processedIds = new Set();
  
  // Helper to find title from iframe's parent container
  function findVimeoTitle(iframe) {
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
  console.log(`Found ${vimeoIframes.length} Vimeo iframes`);
  
  vimeoIframes.forEach((iframe, index) => {
    try {
      const src = iframe.src;
      console.log('Processing iframe ' + (index + 1) + ': ' + src);
      
      // Extract Vimeo ID using regex
      const match = src.match(/player\.vimeo\.com\/video\/(\d+)/);
      if (match) {
        const vimeoId = match[1];
        
        // Avoid duplicates
        if (processedIds.has(vimeoId)) {
          console.log('Skipping duplicate Vimeo ID: ' + vimeoId);
          return;
        }
        processedIds.add(vimeoId);
        
        // Try to find a meaningful title
        let title = findVimeoTitle(iframe);
        if (!title) {
          title = 'Vimeo Video ' + vimeoId;
        }
        
        // Use original embed URL to preserve ?h= hash for private videos
        const vimeoUrl = iframe.src.split('#')[0];
        
        console.log('Found Vimeo video: ' + title + ' (' + vimeoUrl + ')');
        
        vimeoVideos.push({
          id: vimeoId,
          url: vimeoUrl,
          title: title,
          originalSrc: src
        });
      }
    } catch (error) {
      console.error('Error processing Vimeo iframe:', error);
    }
  });
  
  console.log('Total unique Vimeo videos found: ' + vimeoVideos.length);
  return vimeoVideos;
}

// Handle context menu clicks
browser.contextMenus.onClicked.addListener((info, tab) => {
  console.log('[DEBUG] ====== CONTEXT MENU CLICKED ======');
  console.log('[DEBUG] Menu item:', info.menuItemId);
  console.log('[DEBUG] Tab ID:', tab.id);
  console.log('[DEBUG] Tab URL:', tab.url);
  console.log('[DEBUG] Timestamp:', new Date().toISOString());

  if (info.menuItemId === "download-video") {
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
      
      if (videoEmbeds.length >= 2) {
        // Multiple embeds found - send page URL with detected video data
        console.log('[DEBUG] BRANCH: Multiple video embeds (>= 2)');
        console.log('[DEBUG] Detected embeds:', videoEmbeds.map(v => v.platform + ':' + v.id));
        
        const url = info.linkUrl || info.srcUrl || info.pageUrl;
        
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
          pageUrl: pageData.url || info.pageUrl,
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
        
        const url = info.linkUrl || info.srcUrl || info.pageUrl;
        
        sendToNativeApp({
          type: 'video',
          url: url,
          title: pageData.title || tab.title,
          thumbnail: pageData.thumbnail,
          pageUrl: pageData.url || info.pageUrl,
          source: pageData.source || new URL(url).hostname
        });
      }
    });
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
      
      // First, inject a content script that will do the scraping
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
            // Look for parent containers
            let parent = element;
            let attempts = 0;
            while (parent && attempts < 5) {
              parent = parent.parentElement;
              attempts++;
              
              // Look for headings
              const headings = parent ? parent.querySelectorAll('h1, h2, h3, h4, h5') : [];
              for (const heading of headings) {
                const text = heading.textContent.trim();
                if (text && text.length > 3 && text.length < 100) {
                  return text;
                }
              }
              
              // Look for aria-labels or titles
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
            // First check the video element itself for poster
            if (element && element.poster) {
              return resolveUrl(element.poster);
            }
            
            // Look for images in parent containers
            let parent = element;
            let attempts = 0;
            while (parent && attempts < 4) {
              parent = parent.parentElement;
              attempts++;
              
              if (parent) {
                // Look for img tags
                const imgs = parent.querySelectorAll('img');
                for (const img of imgs) {
                  if (img.src && !img.src.includes('data:') && img.width > 50) {
                    return resolveUrl(img.src);
                  }
                }
                
                // Look for background images
                const bgImage = window.getComputedStyle(parent).backgroundImage;
                if (bgImage && bgImage !== 'none') {
                  const match = bgImage.match(/url\\(["']?(.+?)["']?\\)/);
                  if (match && !match[1].includes('data:')) {
                    return resolveUrl(match[1]);
                  }
                }
              }
            }
            
            // Last resort: find any decent sized image on the page
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
                return filename.split('.')[0]; // Return without extension
              }
            } catch {}
            return null;
          }
          
          // 1. Find all <video> elements
          console.log('Looking for video elements...');
          const videoElements = document.querySelectorAll('video');
          console.log('Found', videoElements.length, 'video elements');
          
          videoElements.forEach((video, index) => {
            // Check for direct source
            if (video.src) {
              const url = resolveUrl(video.src);
              console.log('Video src:', url);
              if (url && !processedUrls.has(url)) {
                processedUrls.add(url);
                
                // Try to find a good title
                let title = findNearbyText(video);
                if (!title) {
                  const filename = getFilenameFromUrl(url);
                  title = filename || ('Video ' + (videos.length + 1));
                }
                
                // Try to find thumbnail
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
            
            // Check for <source> elements
            video.querySelectorAll('source').forEach(source => {
              const url = resolveUrl(source.src);
              console.log('Source src:', url);
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
          
          // 2. Look for Apple's lazy-loaded videos
          console.log('Looking for Apple video patterns...');
          // Apple uses data attributes
          const elementsWithVideoData = document.querySelectorAll('[data-video-src], [data-mp4-src], video[data-src]');
          console.log('Found', elementsWithVideoData.length, 'elements with video data attributes');
          
          elementsWithVideoData.forEach(element => {
            ['data-video-src', 'data-mp4-src', 'data-src'].forEach(attr => {
              const url = element.getAttribute(attr);
              if (url) {
                const fullUrl = resolveUrl(url);
                console.log('Data attribute URL:', fullUrl);
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
          
          // 3. Look in srcset attributes (Apple uses these)
          document.querySelectorAll('[srcset*=".mp4"]').forEach(element => {
            const srcset = element.getAttribute('srcset');
            if (srcset) {
              // Extract MP4 URLs from srcset
              const matches = srcset.match(/[^\\s,]+\\.mp4/g);
              if (matches) {
                matches.forEach(match => {
                  const url = resolveUrl(match);
                  if (url && !processedUrls.has(url)) {
                    console.log('Found in srcset:', url);
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
          
          console.log('Total videos found:', videos.length);
          console.log('Videos with details:', videos);
          
          if (videos.length === 0) {
            alert('No videos found on this page. The page may use a different video delivery method or videos may not be loaded yet.');
          } else {
            // Send the videos back to background script
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
  
  else if (info.menuItemId === "download-vimeo-videos") {
    console.log('Starting Vimeo video detection...');
    
    // Inject the detectVimeoEmbeds function and execute it
    browser.tabs.executeScript(tab.id, {
      code: `
        (function() {
          ${detectVimeoEmbeds.toString()}

          // Execute the detection
          const vimeoVideos = detectVimeoEmbeds();

          // Return the result
          return vimeoVideos;
        })();
      `
    }, function(results) {
      if (browser.runtime.lastError) {
        console.error('Script injection error:', browser.runtime.lastError);
        alert('Error detecting Vimeo videos: ' + browser.runtime.lastError.message);
        return;
      }
      
      const vimeoVideos = results && results[0] || [];
      console.log('Vimeo detection results:', vimeoVideos);
      
      if (vimeoVideos.length === 0) {
        alert('No Vimeo videos detected on this page.\\n\\nThis feature looks for embedded Vimeo player iframes.\\nIf you see Vimeo videos but none were detected, they might be using a different embedding method.');
        return;
      }
      
      // Get page metadata
      browser.tabs.executeScript(tab.id, {
        code: `({
          title: document.title,
          url: window.location.href
        })`
      }, function(pageResults) {
        const pageData = pageResults && pageResults[0] || {};
        
        if (vimeoVideos.length === 1) {
          // Single video - send as regular video download
          const video = vimeoVideos[0];
          console.log('Sending single Vimeo video:', video);
          
          sendToNativeApp({
            type: 'video',
            url: video.url,
            title: video.title,
            pageUrl: pageData.url || info.pageUrl,
            source: 'vimeo.com'
          });
        } else {
          // Multiple videos - send as video-list
          console.log('Sending ' + vimeoVideos.length + ' Vimeo videos as list');
          
          // Format videos for the native app
          const formattedVideos = vimeoVideos.map(video => ({
            url: video.url,
            title: video.title,
            thumbnail: null  // Vimeo thumbnails would need API call
          }));
          
          sendToNativeApp({
            type: 'video-list',
            videos: formattedVideos,
            pageTitle: pageData.title || 'Multiple Vimeo Videos',
            pageUrl: pageData.url || info.pageUrl,
            source: 'vimeo.com'
          });
        }
      });
    });
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