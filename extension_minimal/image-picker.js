// Image picker - injected into pages for continuous image selection
(function() {
  // Avoid re-injection
  if (window.__imagePickerActive) return;
  window.__imagePickerActive = true;

  let picking = true;
  let highlightBox = null;
  let lastHighlightedElement = null;
  let activeSelector = null; // Track if selector is currently open

  // Create highlight box
  function createHighlightBox() {
    highlightBox = document.createElement('div');
    highlightBox.style.position = 'fixed';
    highlightBox.style.pointerEvents = 'none';
    highlightBox.style.border = '3px solid #3498db';
    highlightBox.style.backgroundColor = 'rgba(52, 152, 219, 0.1)';
    highlightBox.style.zIndex = '999999';
    highlightBox.style.display = 'none';
    highlightBox.style.transition = 'all 0.1s ease';
    document.body.appendChild(highlightBox);
  }

  // Create toast notification
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.left = '50%';
    toast.style.transform = 'translateX(-50%)';
    toast.style.backgroundColor = type === 'success' ? '#27ae60' : '#3498db';
    toast.style.color = 'white';
    toast.style.padding = '12px 24px';
    toast.style.borderRadius = '6px';
    toast.style.fontSize = '14px';
    toast.style.zIndex = '999999';
    toast.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }

  // Extract image URL from element
  function extractImageURL(element) {
    if (!element) return null;
    
    console.log('[Image Picker Debug] Checking element:', element.tagName, element.className || '', element.id || '');
    
    // Direct img tag
    if (element.tagName === 'IMG') {
      let url = null;
      let source = '';
      
      // First check if src is just a base URL - if so, log ALL attributes
      if (element.src && (element.src.endsWith('/') || !element.src.includes('.'))) {
        console.log('[Image Picker Debug] Found suspicious src (base URL):', element.src);
        console.log('[Image Picker Debug] currentSrc (what browser displays):', element.currentSrc);
        
        console.log('[Image Picker Debug] ALL IMG attributes:');
        // Log all standard attributes
        for (let i = 0; i < element.attributes.length; i++) {
          const attr = element.attributes[i];
          console.log('  ' + attr.name + ':', attr.value);
        }
        
        console.log('[Image Picker Debug] Dataset properties:');
        // Log all dataset properties
        for (const [key, value] of Object.entries(element.dataset)) {
          console.log('  data-' + key + ':', value);
        }
        
        console.log('[Image Picker Debug] ALL element properties:');
        // Log all properties of the element object
        const allProps = Object.keys(element);
        allProps.forEach(prop => {
          try {
            const value = element[prop];
            if (typeof value === 'string' && value.length > 0 && value.length < 500) {
              console.log('  ' + prop + ':', value);
            } else if (typeof value === 'number' || typeof value === 'boolean') {
              console.log('  ' + prop + ':', value);
            }
          } catch (e) {
            // Skip properties that can't be accessed
          }
        });
        
        // Check srcset specifically
        if (element.srcset) {
          console.log('[Image Picker Debug] Srcset found:', element.srcset);
        }
      }
      
      // Check lazy loading attributes FIRST (before src)
      if (element.dataset.src) {
        url = element.dataset.src;
        source = 'data-src';
      } else if (element.dataset.lazy) {
        url = element.dataset.lazy;
        source = 'data-lazy';
      } else if (element.dataset.original) {
        url = element.dataset.original;
        source = 'data-original';
      } else if (element.dataset.fullsize) {
        url = element.dataset.fullsize;
        source = 'data-fullsize';
      } else if (element.dataset.highres) {
        url = element.dataset.highres;
        source = 'data-highres';
      } else if (element.currentSrc && element.currentSrc !== element.src && element.currentSrc.includes('.')) {
        // currentSrc shows what the browser actually displays (could be from srcset)
        url = element.currentSrc;
        source = 'currentSrc';
      } else if (element.srcset) {
        // Parse srcset to get the largest image
        const srcsetEntries = element.srcset.split(',').map(s => s.trim());
        let largestUrl = null;
        let largestWidth = 0;
        
        for (const entry of srcsetEntries) {
          const [entryUrl, descriptor] = entry.split(' ');
          if (descriptor && descriptor.endsWith('w')) {
            const width = parseInt(descriptor);
            if (width > largestWidth) {
              largestWidth = width;
              largestUrl = entryUrl;
            }
          }
        }
        
        if (largestUrl) {
          url = largestUrl;
          source = 'srcset (largest)';
        } else if (srcsetEntries.length > 0) {
          // If no width descriptors, take the first one
          url = srcsetEntries[0].split(' ')[0];
          source = 'srcset (first)';
        }
      } else if (element.src && !element.src.endsWith('/') && element.src.includes('.')) {
        // Only use src if it looks like an actual image URL
        url = element.src;
        source = 'src';
      }
      
      if (url) {
        console.log('[Image Picker Debug] Found IMG URL:', url, 'from:', source, 'size estimate:', Math.round(url.length/1024*0.75) + 'KB (base64)');
        // Filter out tiny placeholder images (likely < 10KB)
        if (url.startsWith('data:image/') && url.length < 13000) { // ~10KB base64
          console.log('[Image Picker Debug] Skipping small data URL (likely placeholder)');
          return null;
        }
        return url;
      } else {
        console.log('[Image Picker Debug] No valid image URL found in IMG element');
      }
    }
    
    // Background image
    const bgImage = window.getComputedStyle(element).backgroundImage;
    if (bgImage && bgImage !== 'none') {
      const match = bgImage.match(/url\(["']?(.+?)["']?\)/);
      if (match) {
        const url = match[1];
        console.log('[Image Picker Debug] Found background-image URL:', url);
        
        // Filter out common empty/placeholder patterns
        if (url.startsWith('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///') || // 1x1 transparent gif
            url.startsWith('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==') || // 1x1 transparent png
            url === 'about:blank') {
          console.log('[Image Picker Debug] Skipping known placeholder background image');
          return null;
        }
        return url;
      }
    }
    
    // Check for img children
    const img = element.querySelector('img');
    if (img) {
      console.log('[Image Picker Debug] Checking child img element');
      return extractImageURL(img); // Recursive call to check lazy loading
    }
    
    // Check parent for img
    if (element.parentElement) {
      const parentImg = element.parentElement.querySelector('img');
      if (parentImg) {
        console.log('[Image Picker Debug] Checking parent img element');
        return extractImageURL(parentImg); // Recursive call to check lazy loading
      }
    }
    
    console.log('[Image Picker Debug] No URL found for element');
    return null;
  }

  // Find all images at a point (for layered images)
  function findImagesAtPoint(x, y, clickTarget) {
    const elements = document.elementsFromPoint(x, y);
    const images = [];

    // Check if the click target is an <img> or has a direct <img> child
    const clickedImg = clickTarget && (
      clickTarget.tagName === 'IMG' ? clickTarget :
      clickTarget.querySelector && clickTarget.querySelector('img')
    );

    for (const el of elements) {
      const url = extractImageURL(el);
      // Skip empty URLs or data URLs (often just transparent overlays)
      if (url && !images.some(img => img.url === url) && !url.startsWith('data:')) {
        images.push({
          url: url,
          element: el,
          type: el.tagName === 'IMG' ? 'img' : 'background'
        });
      }
    }

    // If an actual <img> was clicked, hide background entries (they're just parent containers)
    if (clickedImg) {
      const imgOnly = images.filter(img => img.type === 'img');
      if (imgOnly.length > 0) {
        return imgOnly;
      }
    }

    // Sort: img entries first, then background
    images.sort((a, b) => (a.type === 'img' ? 0 : 1) - (b.type === 'img' ? 0 : 1));

    return images;
  }

  // Update highlight box position
  function updateHighlight(element) {
    if (!element || element === document.body) {
      highlightBox.style.display = 'none';
      return;
    }
    
    const rect = element.getBoundingClientRect();
    highlightBox.style.top = rect.top + 'px';
    highlightBox.style.left = rect.left + 'px';
    highlightBox.style.width = rect.width + 'px';
    highlightBox.style.height = rect.height + 'px';
    highlightBox.style.display = 'block';
  }

  // Try to get high-res version
  function getHighResUrl(url) {
    // If already has _2x, return as-is
    if (url.includes('_2x')) {
      return url;
    }
    
    // Only try to add _2x for Apple domains
    if (url.includes('apple.com')) {
      // Apple-specific patterns for high-res images
      const patterns = [
        { search: /(\.\w+)$/, replace: '_2x$1' },
        { search: /_\d+x\d+(\.\w+)$/, replace: '_2x$1' }
      ];
      
      for (const pattern of patterns) {
        if (pattern.search.test(url)) {
          return url.replace(pattern.search, pattern.replace);
        }
      }
    }
    
    // For all other sites, return original URL to prevent 404s
    return url;
  }

  // Handle mouse move
  function onMouseMove(e) {
    if (!picking) return;
    
    const target = e.target;
    if (target === highlightBox) return;
    
    // Don't update highlights if selector is open
    if (activeSelector) return;
    
    // Find the nearest image-containing element
    let imageElement = target;
    let attempts = 0;
    
    while (imageElement && attempts < 5) {
      if (extractImageURL(imageElement)) {
        break;
      }
      imageElement = imageElement.parentElement;
      attempts++;
    }
    
    if (imageElement && extractImageURL(imageElement)) {
      updateHighlight(imageElement);
      lastHighlightedElement = imageElement;
    } else {
      highlightBox.style.display = 'none';
      lastHighlightedElement = null;
    }
  }

  // Handle click
  function onClick(e) {
    if (!picking) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const images = findImagesAtPoint(e.clientX, e.clientY, e.target);
    
    // Filter out placeholder images before showing selector
    const validImages = images.filter(img => {
      return !img.url.includes('placeholder') && 
             !img.url.includes('blank') &&
             !img.url.includes('transparent');
    });
    
    if (validImages.length === 0) {
      showToast('No image found at this location');
      return;
    }
    
    if (validImages.length === 1) {
      // Single image - download directly
      const url = validImages[0].url;
      const highResUrl = getHighResUrl(url);
      
      browser.runtime.sendMessage({
        action: 'download-image',
        url: highResUrl
      });
      
      showToast('Image sent to downloader', 'success');
    } else {
      // Multiple images - show selector only if not already open
      if (!activeSelector) {
        showImageSelector(validImages, e.clientX, e.clientY);
      }
    }
  }

  // Show image selector for multiple images with fixed positioning
  function showImageSelector(images, x, y) {
    // Close any existing selector first
    if (activeSelector) {
      activeSelector.remove();
      activeSelector = null;
    }

    const selector = document.createElement('div');
    selector.setAttribute('data-image-selector', 'true');
    activeSelector = selector; // Track the active selector
    
    selector.style.position = 'fixed';
    
    // Calculate optimal position to keep selector on screen
    const maxWidth = 300;
    const maxHeight = 400;
    
    // Adjust position to keep selector on screen
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    let selectorX = Math.min(x, viewportWidth - maxWidth - 20);
    let selectorY = Math.min(y, viewportHeight - maxHeight - 20);
    
    // Ensure minimum margins
    selectorX = Math.max(10, selectorX);
    selectorY = Math.max(10, selectorY);
    
    selector.style.left = selectorX + 'px';
    selector.style.top = selectorY + 'px';
    selector.style.backgroundColor = 'white';
    selector.style.border = '2px solid #3498db';
    selector.style.borderRadius = '8px';
    selector.style.boxShadow = '0 8px 20px rgba(0,0,0,0.3)';
    selector.style.zIndex = '999999';
    selector.style.padding = '15px';
    selector.style.maxWidth = maxWidth + 'px';
    selector.style.maxHeight = maxHeight + 'px';
    selector.style.overflowY = 'auto';
    selector.style.fontFamily = 'Arial, sans-serif';
    
    // Add header with close button
    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';
    header.style.marginBottom = '15px';
    header.style.paddingBottom = '10px';
    header.style.borderBottom = '1px solid #ddd';
    
    const title = document.createElement('div');
    title.textContent = `Select Image (${images.length} found)`;
    title.style.fontWeight = 'bold';
    title.style.fontSize = '14px';
    title.style.color = '#333';
    
    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '×';
    closeBtn.style.background = 'none';
    closeBtn.style.border = 'none';
    closeBtn.style.fontSize = '20px';
    closeBtn.style.cursor = 'pointer';
    closeBtn.style.color = '#666';
    closeBtn.style.padding = '0';
    closeBtn.style.width = '24px';
    closeBtn.style.height = '24px';
    closeBtn.onclick = () => {
      // Remove any hover preview elements before closing selector
      const hoverPreviews = document.querySelectorAll('img[style*="position: fixed"][style*="width: 200px"]');
      hoverPreviews.forEach(preview => preview.remove());
      
      selector.remove();
      activeSelector = null;
    };
    
    header.appendChild(title);
    header.appendChild(closeBtn);
    selector.appendChild(header);
    
    // Add download counter
    let downloadCount = 0;
    const counter = document.createElement('div');
    counter.style.fontSize = '12px';
    counter.style.color = '#666';
    counter.style.marginBottom = '10px';
    counter.textContent = `Downloads: ${downloadCount}`;
    selector.appendChild(counter);
    
    images.forEach((img, index) => {
      const item = document.createElement('div');
      item.style.display = 'flex';
      item.style.alignItems = 'center';
      item.style.padding = '8px';
      item.style.cursor = 'pointer';
      item.style.borderRadius = '4px';
      item.style.marginBottom = '5px';
      item.style.border = '1px solid transparent';
      
      item.onmouseover = () => {
        item.style.backgroundColor = '#f0f8ff';
        item.style.border = '1px solid #3498db';
      };
      
      item.onmouseout = () => {
        item.style.backgroundColor = 'transparent';
        item.style.border = '1px solid transparent';
      };
      
      const preview = document.createElement('img');
      preview.src = img.url;
      preview.style.width = '80px';
      preview.style.height = '80px';
      preview.style.objectFit = 'cover';
      preview.style.marginRight = '12px';
      preview.style.borderRadius = '4px';
      preview.style.border = '1px solid #ddd';
      preview.title = img.url;
      
      // Only hide items for data URLs or known placeholder patterns
      preview.onerror = () => {
        // Check if it's a data URL or placeholder image that should be hidden
        if (img.url.startsWith('data:') ||
            img.url.includes('placeholder') ||
            img.url.includes('blank') ||
            img.url.includes('transparent') ||
            img.url.includes('empty.gif') ||
            img.url.includes('spacer.gif')) {
          item.style.display = 'none';
        } else {
          // For regular HTTP URLs, show a broken image icon instead of hiding
          preview.style.opacity = '0.5';
          preview.style.border = '2px dashed #ccc';
          preview.alt = 'Failed to load';
        }
      };
      
      // Add hover preview functionality
      let hoverPreview = null;
      
      preview.onmouseenter = () => {
        // Create hover preview
        hoverPreview = document.createElement('img');
        hoverPreview.src = img.url;
        hoverPreview.style.position = 'fixed';
        hoverPreview.style.width = '200px';
        hoverPreview.style.height = '200px';
        hoverPreview.style.objectFit = 'contain';
        hoverPreview.style.backgroundColor = 'white';
        hoverPreview.style.border = '2px solid #3498db';
        hoverPreview.style.borderRadius = '8px';
        hoverPreview.style.boxShadow = '0 8px 20px rgba(0,0,0,0.3)';
        hoverPreview.style.zIndex = '999999';
        hoverPreview.style.pointerEvents = 'none';
        hoverPreview.style.padding = '8px';
        
        // Position adjacent to the hovered item
        const selectorRect = selector.getBoundingClientRect();
        const itemRect = item.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        let previewX, previewY;
        
        // Horizontal positioning - try right of selector first, then left
        if (selectorRect.right + 220 < viewportWidth) {
          // Position to the right of selector
          previewX = selectorRect.right + 10;
        }
        else if (selectorRect.left - 220 > 0) {
          // Position to the left of selector
          previewX = selectorRect.left - 220;
        }
        else {
          // Fallback positioning
          previewX = Math.max(10, Math.min(selectorRect.left, viewportWidth - 220));
        }
        
        // Vertical positioning - align top edge with hovered item's top edge
        previewY = itemRect.top;
        
        // Ensure preview stays within viewport bounds
        previewY = Math.max(10, Math.min(previewY, viewportHeight - 220));
        
        hoverPreview.style.left = previewX + 'px';
        hoverPreview.style.top = previewY + 'px';
        
        document.body.appendChild(hoverPreview);
      };
      
      preview.onmouseleave = () => {
        if (hoverPreview) {
          hoverPreview.remove();
          hoverPreview = null;
        }
      };
      
      const info = document.createElement('div');
      info.style.fontSize = '12px';
      info.style.flex = '1';
      
      // Create a shortened URL for display
      const shortUrl = img.url.length > 40 ? img.url.substring(0, 40) + '...' : img.url;
      
      info.innerHTML = `
        <div style="color: #333; font-weight: 500;">Type: ${img.type}</div>
        <div style="color: #666; font-size: 11px; margin-top: 2px;">${shortUrl}</div>
        <div style="color: #3498db; font-size: 11px; margin-top: 2px;">Click to download</div>
      `;
      
      item.appendChild(preview);
      item.appendChild(info);
      
      item.onclick = (clickEvent) => {
        clickEvent.stopPropagation(); // Prevent event bubbling
        
        const highResUrl = getHighResUrl(img.url);
        browser.runtime.sendMessage({
          action: 'download-image',
          url: highResUrl,
          thumbnail: img.url
        });
        
        // Update counter
        downloadCount++;
        counter.textContent = `Downloads: ${downloadCount}`;
        
        // Visual feedback - briefly highlight the downloaded item
        item.style.backgroundColor = '#d4edda';
        item.style.border = '1px solid #27ae60';
        setTimeout(() => {
          item.style.backgroundColor = 'transparent';
          item.style.border = '1px solid transparent';
        }, 1000);
        
        showToast('Image sent to downloader', 'success');
        
        // Don't close selector - keep it open for multi-selection
      };
      
      selector.appendChild(item);
    });
    
    // Add instructions
    const instructions = document.createElement('div');
    instructions.style.fontSize = '11px';
    instructions.style.color = '#666';
    instructions.style.marginTop = '10px';
    instructions.style.padding = '8px';
    instructions.style.backgroundColor = '#f8f9fa';
    instructions.style.borderRadius = '4px';
    instructions.textContent = 'Click images to download multiple. Press ESC or click × to close.';
    selector.appendChild(instructions);
    
    document.body.appendChild(selector);
    
    // Handle clicks outside selector (but don't close it immediately)
    const handleOutsideClick = (event) => {
      if (!selector.contains(event.target)) {
        // Only close if it's been open for at least 500ms to prevent accidental closure
        setTimeout(() => {
          if (activeSelector === selector) {
            // Remove any hover preview elements before closing selector
            const hoverPreviews = document.querySelectorAll('img[style*="position: fixed"][style*="width: 200px"]');
            hoverPreviews.forEach(preview => preview.remove());
            
            selector.remove();
            activeSelector = null;
            document.removeEventListener('click', handleOutsideClick);
          }
        }, 200);
      }
    };
    
    // Add outside click handler after a brief delay
    setTimeout(() => {
      document.addEventListener('click', handleOutsideClick);
    }, 100);
  }

  // Handle escape key
  function onKeyDown(e) {
    if (e.key === 'Escape') {
      // Always remove any hover preview elements first
      const hoverPreviews = document.querySelectorAll('img[style*="position: fixed"][style*="width: 200px"]');
      hoverPreviews.forEach(preview => preview.remove());
      
      // Close any open selector first
      if (activeSelector) {
        activeSelector.remove();
        activeSelector = null;
        return; // Don't exit picker mode, just close selector
      }
      
      // Exit picker mode
      cleanup();
      showToast('Image picker deactivated');
    }
  }

  // Cleanup
  function cleanup() {
    picking = false;
    window.__imagePickerActive = false;
    
    // Remove any active hover preview elements
    const hoverPreviews = document.querySelectorAll('img[style*="position: fixed"][style*="width: 200px"]');
    hoverPreviews.forEach(preview => preview.remove());
    
    // Close any active selector
    if (activeSelector) {
      activeSelector.remove();
      activeSelector = null;
    }
    
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('click', onClick);
    document.removeEventListener('keydown', onKeyDown);
    
    if (highlightBox) {
      highlightBox.remove();
    }
    
    // Remove cursor style
    const cursorStyle = document.getElementById('image-picker-cursor');
    if (cursorStyle) cursorStyle.remove();
  }

  // Initialize
  createHighlightBox();
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('click', onClick);
  document.addEventListener('keydown', onKeyDown);
  
  // Show initial message
  showToast('Image picker activated - Click images to download, ESC to exit');
  
  // Change cursor
  const style = document.createElement('style');
  style.textContent = '* { cursor: crosshair !important; }';
  style.id = 'image-picker-cursor';
  document.head.appendChild(style);
})();