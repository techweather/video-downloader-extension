// Image picker - injected into pages for continuous image selection.
// The same file ships in both extensions (extension_chrome/ and extension_minimal/);
// keep them identical. Its UI lives in a shadow root so page styles can't reach it,
// and it follows the Mac app's look: system font, translucent panels, light and dark.
(function() {
  // Avoid re-injection
  if (window.__imagePickerActive) return;
  window.__imagePickerActive = true;

  // Firefox exposes `browser`, Chrome `chrome`; both take the same message.
  const api = (typeof browser !== 'undefined' && browser.runtime) ? browser : chrome;

  let picking = true;
  let activeSelector = null; // the "several images here" panel, while open

  // ---- UI host ------------------------------------------------------------

  const host = document.createElement('dlwithit-picker');
  host.style.cssText = 'all: initial; position: fixed; inset: 0; pointer-events: none; z-index: 2147483647;';
  const root = host.attachShadow({ mode: 'closed' });
  root.innerHTML = `<style>${STYLES()}</style>`;
  document.documentElement.appendChild(host);

  // True when an event happened on our own UI rather than the page.
  function isOwnUI(e) {
    return e.composedPath().includes(host);
  }

  // Small element helper: el('div', 'class', 'text')
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  const ICONS = {
    photo: '<svg viewBox="0 0 20 20" aria-hidden="true"><rect x="2.5" y="4" width="15" height="12" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="7.2" cy="8.3" r="1.5" fill="currentColor"/><path d="M3.5 14.5l4.2-4 3 2.7 2.3-2 3.5 3.3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    check: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 10.5l3.2 3.2L15 6.8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    info: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 9v5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="6.3" r="1.1" fill="currentColor"/></svg>',
    close: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M6.5 6.5l7 7M13.5 6.5l-7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  };

  // ---- mode pill: shows the picker is on, with a way out ------------------

  const pill = el('div', 'pill');
  pill.innerHTML = `<span class="pill-icon">${ICONS.photo}</span>`;
  const pillText = el('span', 'pill-text');
  pillText.append(el('strong', null, 'Pick Images'), el('span', 'secondary', 'Click an image to download it'));
  const doneBtn = el('button', 'pill-done', 'Done');
  doneBtn.title = 'Stop picking (Esc)';
  doneBtn.addEventListener('click', () => cleanup());
  pill.append(pillText, el('span', 'pill-divider'), doneBtn);
  root.appendChild(pill);

  // ---- highlight around the image under the pointer ------------------------

  const highlight = el('div', 'highlight');
  const sizeChip = el('span', 'chip');
  highlight.appendChild(sizeChip);
  root.appendChild(highlight);

  function updateHighlight(element) {
    if (!element || element === document.body) {
      highlight.classList.remove('visible');
      return;
    }
    const rect = element.getBoundingClientRect();
    highlight.style.top = rect.top + 'px';
    highlight.style.left = rect.left + 'px';
    highlight.style.width = rect.width + 'px';
    highlight.style.height = rect.height + 'px';
    const img = element.tagName === 'IMG' ? element : null;
    const size = img && img.naturalWidth ? `${img.naturalWidth} × ${img.naturalHeight}` : '';
    sizeChip.textContent = size;
    sizeChip.style.display = size && rect.width > 90 && rect.height > 40 ? '' : 'none';
    highlight.classList.add('visible');
  }

  // ---- toast (macOS HUD style) --------------------------------------------

  let toastTimer = null;
  const toast = el('div', 'toast');
  root.appendChild(toast);

  function showToast(message, { type = 'info', thumbnail = null } = {}) {
    toast.replaceChildren();
    if (thumbnail) {
      const thumb = el('img', 'toast-thumb');
      thumb.src = thumbnail;
      thumb.alt = '';
      thumb.onerror = () => thumb.remove();
      // Shaped like the picture, from square up to 16:9
      thumb.onload = () => {
        const aspect = thumb.naturalWidth / thumb.naturalHeight || 1;
        thumb.style.width = Math.round(30 * Math.min(16 / 9, Math.max(1, aspect))) + 'px';
      };
      toast.appendChild(thumb);
    } else {
      const icon = el('span', `toast-icon ${type}`);
      icon.innerHTML = type === 'success' ? ICONS.check : ICONS.info;
      toast.appendChild(icon);
    }
    toast.appendChild(el('span', null, message));
    toast.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('visible'), 2000);
  }

  // ---- finding images ------------------------------------------------------

  // ---- srcset helpers (tests/test_image_picker_srcset.py runs these in node) ----

  // [url, descriptor] pairs of a srcset, split the way browsers do: a URL is a
  // run of non-spaces (it may contain commas, e.g. Cloudinary's w_400,h_300),
  // and a comma ends the entry.
  function parseSrcset(srcset) {
    const entries = [];
    const text = srcset || '';
    let i = 0;
    while (i < text.length) {
      while (i < text.length && /[\s,]/.test(text[i])) i++;
      let j = i;
      while (j < text.length && !/\s/.test(text[j])) j++;
      let url = text.slice(i, j);
      const endedByComma = /,$/.test(url);
      url = url.replace(/,+$/, '');
      i = j;
      let descriptor = '';
      if (!endedByComma) {
        while (i < text.length && text[i] !== ',') descriptor += text[i++];
      }
      if (url) entries.push([url, descriptor.trim()]);
      i++;
    }
    return entries;
  }

  // The biggest candidate in a srcset: highest "2x"/"1200w" descriptor wins.
  // Returns { url, scale } or null. Placeholder data: entries are skipped.
  function largestFromSrcset(srcset) {
    let best = null;
    for (const [entryUrl, descriptor] of parseSrcset(srcset)) {
      if (/^data:/i.test(entryUrl)) continue;
      let scale = 1;
      if (/^[\d.]+x$/i.test(descriptor)) scale = parseFloat(descriptor);
      else if (/^\d+w$/i.test(descriptor)) scale = parseInt(descriptor, 10) / 1000;
      if (!best || scale > best.scale) best = { url: entryUrl, scale };
    }
    return best;
  }

  // Widest screen a <source media="…"> applies to; no max-width means any width.
  function mediaMaxWidth(media) {
    const match = (media || '').match(/max-width:\s*([\d.]+)px/i);
    return match ? parseFloat(match[1]) : Infinity;
  }

  // Pages often have the same picture as AVIF/WebP and JPEG/PNG. Keep the one
  // that opens everywhere (Photoshop, Premiere, older macOS).
  function typeRank(source) {
    const type = (source.getAttribute('type') || '').toLowerCase();
    return /avif|webp|jxl/.test(type) ? 0 : 1;
  }

  // The highest-resolution file a <picture> offers — not the one the browser
  // picked for this window — from the source for the widest screen at the
  // highest density. Falls back to the <img>'s own src.
  function bestPictureSource(img) {
    const picture = img.parentElement;
    let best = null;
    for (const source of picture.querySelectorAll('source')) {
      if (source.hasAttribute('data-empty')) continue;
      const candidate = largestFromSrcset(source.getAttribute('srcset'));
      if (!candidate) continue;
      const rank = [mediaMaxWidth(source.getAttribute('media')), candidate.scale, typeRank(source)];
      if (!best || rank[0] > best.rank[0] ||
          (rank[0] === best.rank[0] && (rank[1] > best.rank[1] ||
            (rank[1] === best.rank[1] && rank[2] > best.rank[2])))) {
        best = { url: candidate.url, rank };
      }
    }
    if (best) return best.url;
    const own = largestFromSrcset(img.getAttribute('srcset'));
    if (own) return own.url;
    // Lazy pictures (Apple's) keep a placeholder as the only source until they
    // scroll into view, but the <img> already names the real file.
    const src = img.getAttribute('src');
    return src && !/^data:/i.test(src) ? src : null;
  }

  // ---- end srcset helpers ----

  // Resolve a URL from the page against the page, so relative paths download.
  function absolute(url) {
    try { return new URL(url, document.baseURI).href; } catch (e) { return url; }
  }

  // Extract image URL from element
  function extractImageURL(element) {
    if (!element) return null;

    // Direct img tag
    if (element.tagName === 'IMG') {
      let url = null;

      // Check lazy loading attributes FIRST (before src)
      if (element.dataset.src) {
        url = element.dataset.src;
      } else if (element.dataset.lazy) {
        url = element.dataset.lazy;
      } else if (element.dataset.original) {
        url = element.dataset.original;
      } else if (element.dataset.fullsize) {
        url = element.dataset.fullsize;
      } else if (element.dataset.highres) {
        url = element.dataset.highres;
      } else if (element.parentElement && element.parentElement.tagName === 'PICTURE' &&
                 bestPictureSource(element)) {
        // The biggest file the <picture> offers, not the one sized for this window
        url = absolute(bestPictureSource(element));
      } else if (largestFromSrcset(element.getAttribute('srcset'))) {
        // The biggest srcset entry, not the one the browser picked for this screen
        url = absolute(largestFromSrcset(element.getAttribute('srcset')).url);
      } else if (element.currentSrc && element.currentSrc !== element.src && element.currentSrc.includes('.')) {
        // currentSrc shows what the browser actually displays
        url = element.currentSrc;
      } else if (element.src && !element.src.endsWith('/') && element.src.includes('.')) {
        // Only use src if it looks like an actual image URL
        url = element.src;
      }

      if (url) {
        // Filter out tiny placeholder images (likely < 10KB)
        if (url.startsWith('data:image/') && url.length < 13000) { // ~10KB base64
          return null;
        }
        return url;
      }
    }

    // Background image
    const bgImage = window.getComputedStyle(element).backgroundImage;
    if (bgImage && bgImage !== 'none') {
      const match = bgImage.match(/url\(["']?(.+?)["']?\)/);
      if (match) {
        const url = match[1];

        // Filter out common empty/placeholder patterns
        if (url.startsWith('data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///') || // 1x1 transparent gif
            url.startsWith('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==') || // 1x1 transparent png
            url === 'about:blank') {
          return null;
        }
        return url;
      }
    }

    // Only recurse into children/parent when not already on an <img> —
    // recursing from an <img> back to its parent finds the same element and loops forever
    if (element.tagName !== 'IMG') {
      const img = element.querySelector('img');
      if (img) {
        return extractImageURL(img);
      }
      if (element.parentElement) {
        const parentImg = element.parentElement.querySelector('img');
        if (parentImg) {
          return extractImageURL(parentImg);
        }
      }
    }

    return null;
  }

  // Find all images at a point (for layered images)
  function findImagesAtPoint(x, y, clickTarget) {
    const elements = document.elementsFromPoint(x, y).filter(e => e !== host);
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

  // Send one image to the app.
  function download(url) {
    api.runtime.sendMessage({
      action: 'download-image',
      url: getHighResUrl(url),
      thumbnail: url
    });
  }

  // ---- page events ---------------------------------------------------------

  function onMouseMove(e) {
    if (!picking) return;

    // Our own UI, or a panel open: no page highlight
    if (isOwnUI(e) || activeSelector) {
      highlight.classList.remove('visible');
      return;
    }

    // Find the nearest image-containing element
    let imageElement = e.target;
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
    } else {
      highlight.classList.remove('visible');
    }
  }

  function onClick(e) {
    if (!picking || isOwnUI(e)) return;

    e.preventDefault();
    e.stopPropagation();

    // A click on the page while the panel is open just closes it, like a popover.
    if (activeSelector) {
      closeSelector();
      return;
    }

    const images = findImagesAtPoint(e.clientX, e.clientY, e.target);

    // Filter out placeholder images before showing selector
    const validImages = images.filter(img => {
      return !img.url.includes('placeholder') &&
             !img.url.includes('blank') &&
             !img.url.includes('transparent');
    });

    if (validImages.length === 0) {
      showToast('No image here');
      return;
    }

    if (validImages.length === 1) {
      // Single image - download directly
      download(validImages[0].url);
      showToast('Sent to dlwithit', { type: 'success', thumbnail: validImages[0].url });
    } else {
      showImageSelector(validImages, e.clientX, e.clientY);
    }
  }

  function onKeyDown(e) {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    // Close the panel first; a second Esc ends picking
    if (activeSelector) {
      closeSelector();
      return;
    }
    cleanup();
  }

  // ---- the "several images here" panel ------------------------------------

  function closeSelector() {
    if (!activeSelector) return;
    activeSelector.remove();
    activeSelector = null;
  }

  function showImageSelector(images, x, y) {
    closeSelector();

    const panel = el('div', 'panel');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Choose images to download');
    activeSelector = panel;

    // Header
    const header = el('div', 'panel-header');
    const titles = el('div', 'panel-titles');
    titles.append(
      el('div', 'panel-title', `${images.length} images here`),
      el('div', 'panel-subtitle', 'Click one to download it')
    );
    const closeBtn = el('button', 'icon-button');
    closeBtn.innerHTML = ICONS.close;
    closeBtn.title = 'Close (Esc)';
    closeBtn.setAttribute('aria-label', 'Close');
    closeBtn.addEventListener('click', closeSelector);
    header.append(titles, closeBtn);

    // Grid of thumbnails
    const grid = el('div', 'grid');
    const tiles = images.map(img => {
      const tile = el('button', 'tile');
      tile.title = img.url;
      const frame = el('div', 'tile-frame');
      const preview = el('img');
      preview.src = img.url;
      preview.alt = '';
      const badge = el('span', 'badge');
      badge.innerHTML = ICONS.check;
      frame.append(preview, badge);

      const caption = el('div', 'tile-caption');
      const size = el('span', 'tile-size', img.type === 'img' ? 'Image' : 'Background');
      const name = el('span', 'tile-name', fileName(img.url));
      caption.append(size, name);
      tile.append(frame, caption);

      preview.onload = () => {
        size.textContent = `${preview.naturalWidth} × ${preview.naturalHeight}`;
        hasTransparency(img.url).then(alpha => frame.classList.toggle('alpha', alpha));
      };
      preview.onerror = () => {
        // Placeholders that failed to load aren't worth offering
        if (img.url.startsWith('data:') || /placeholder|blank|transparent|empty\.gif|spacer\.gif/.test(img.url)) {
          tile.classList.add('gone');
          tile.remove();
          updateFooter();
        } else {
          // Still offered (the full image may load fine in the app), with a plain icon
          tile.classList.add('broken');
          preview.remove();
          const icon = el('span', 'broken-icon');
          icon.innerHTML = ICONS.photo;
          frame.prepend(icon);
        }
      };

      tile.addEventListener('click', () => {
        download(img.url);
        tile.classList.add('sent');
        tile.setAttribute('aria-pressed', 'true');
        updateFooter();
        showToast('Sent to dlwithit', { type: 'success', thumbnail: img.url });
      });
      grid.appendChild(tile);
      return tile;
    });

    // Footer: everything at once
    const footer = el('div', 'panel-footer');
    const allBtn = el('button', 'primary');
    allBtn.addEventListener('click', () => {
      const pending = images.filter((_, i) => !tiles[i].classList.contains('sent') && !tiles[i].classList.contains('gone'));
      pending.forEach(img => download(img.url));
      tiles.forEach(t => t.classList.add('sent'));
      updateFooter();
      showToast(pending.length === 1 ? 'Sent to dlwithit' : `Sent ${pending.length} images to dlwithit`, { type: 'success' });
    });
    footer.appendChild(allBtn);

    function updateFooter() {
      const offered = tiles.filter(t => !t.classList.contains('gone'));
      const left = offered.filter(t => !t.classList.contains('sent')).length;
      const total = offered.length;
      allBtn.textContent = left === 0 ? 'All Sent'
        : left === total ? (left === 2 ? 'Download Both' : `Download All ${left}`)
        : (left === 1 ? 'Download the Other One' : `Download the Other ${left}`);
      allBtn.disabled = left === 0;
    }
    updateFooter();

    // Columns from the count, so the panel stays roughly square and rarely scrolls
    const columns = columnsFor(images.length);
    grid.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
    panel.style.width = panelWidth(columns) + 'px';
    panel.append(header, grid, footer);
    root.appendChild(panel);

    // Place it beside the click, kept on screen
    const margin = 12;
    const rect = panel.getBoundingClientRect();
    let left = x + 14;
    let top = y - 24;
    if (left + rect.width > window.innerWidth - margin) left = x - rect.width - 14;
    left = Math.max(margin, Math.min(left, window.innerWidth - rect.width - margin));
    top = Math.max(margin, Math.min(top, window.innerHeight - rect.height - margin));
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
    highlight.classList.remove('visible');
  }

  // How many columns the panel's grid gets: 2 → 2, 3 → 3, 4 → 2×2, 5–9 → 3, more → 4,
  // fewer if the window is too narrow.
  function columnsFor(count) {
    let columns = count <= 3 ? count : count === 4 ? 2 : count <= 9 ? 3 : 4;
    while (columns > 1 && panelWidth(columns) > window.innerWidth - 24) columns--;
    return Math.max(1, columns);
  }

  // Panel width for a column count: 150px tiles, 10px gaps, 14px side padding.
  function panelWidth(columns) {
    return columns * 150 + (columns - 1) * 10 + 28;
  }

  // Whether an image has see-through pixels, so only those get a checkerboard.
  // Reads a small copy's pixels; sites that block that get a guess from the file type.
  function hasTransparency(url) {
    return new Promise(resolve => {
      const guess = () => resolve(/\.svg(\?|#|$)/i.test(url));
      const probe = new Image();
      probe.crossOrigin = 'anonymous';
      probe.onerror = guess;
      probe.onload = () => {
        try {
          const size = 32;
          const canvas = document.createElement('canvas');
          canvas.width = canvas.height = size;
          const ctx = canvas.getContext('2d', { willReadFrequently: true });
          ctx.drawImage(probe, 0, 0, size, size);
          const data = ctx.getImageData(0, 0, size, size).data;
          for (let i = 3; i < data.length; i += 4) {
            if (data[i] < 250) return resolve(true);
          }
          resolve(false);
        } catch {
          guess();
        }
      };
      probe.src = url;
    });
  }

  // Last part of a URL's path, for a tile's caption.
  function fileName(url) {
    try {
      const path = new URL(url, location.href).pathname;
      return decodeURIComponent(path.split('/').filter(Boolean).pop() || url);
    } catch {
      return url;
    }
  }

  // ---- start and stop ------------------------------------------------------

  function cleanup() {
    picking = false;
    window.__imagePickerActive = false;
    document.removeEventListener('mousemove', onMouseMove, true);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKeyDown, true);
    const cursorStyle = document.getElementById('image-picker-cursor');
    if (cursorStyle) cursorStyle.remove();
    closeSelector();
    pill.classList.add('leaving');
    highlight.classList.remove('visible');
    setTimeout(() => host.remove(), 200);
  }

  // Capture phase, so page scripts can't swallow the clicks first.
  document.addEventListener('mousemove', onMouseMove, true);
  document.addEventListener('click', onClick, true);
  document.addEventListener('keydown', onKeyDown, true);

  // Crosshair over the page, but not over our own UI
  const style = document.createElement('style');
  style.textContent = '*:not(dlwithit-picker) { cursor: crosshair !important; }';
  style.id = 'image-picker-cursor';
  (document.head || document.documentElement).appendChild(style);

  requestAnimationFrame(() => pill.classList.add('visible'));

  // ---- styles --------------------------------------------------------------

  function STYLES() {
    return `
      :host { all: initial; }
      * { box-sizing: border-box; }
      .pill, .panel, .toast, .highlight {
        --accent: #007aff;
        --fg: #1d1d1f;
        --secondary: rgba(60, 60, 67, 0.62);
        --material: rgba(246, 246, 248, 0.78);
        --edge: rgba(0, 0, 0, 0.12);
        --separator: rgba(60, 60, 67, 0.14);
        --fill: rgba(120, 120, 128, 0.12);
        --fill-hover: rgba(120, 120, 128, 0.2);
        --shadow: 0 12px 40px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.08);
        font: 13px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
        -webkit-font-smoothing: antialiased;
        color: var(--fg);
        cursor: default;
      }
      @media (prefers-color-scheme: dark) {
        .pill, .panel, .toast, .highlight {
          --accent: #0a84ff;
          --fg: #f5f5f7;
          --secondary: rgba(235, 235, 245, 0.6);
          --material: rgba(44, 44, 46, 0.76);
          --edge: rgba(255, 255, 255, 0.14);
          --separator: rgba(84, 84, 88, 0.6);
          --fill: rgba(120, 120, 128, 0.24);
          --fill-hover: rgba(120, 120, 128, 0.36);
          --shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 2px 8px rgba(0, 0, 0, 0.3);
        }
      }
      button { font: inherit; color: inherit; cursor: default; }
      svg { width: 100%; height: 100%; display: block; }

      /* Mode pill */
      .pill {
        position: fixed; top: 14px; left: 50%;
        transform: translate(-50%, -8px); opacity: 0;
        transition: opacity .2s ease, transform .2s ease;
        display: flex; align-items: center; gap: 10px;
        padding: 6px 6px 6px 12px;
        background: var(--material);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        backdrop-filter: blur(24px) saturate(180%);
        border: 0.5px solid var(--edge);
        border-radius: 999px;
        box-shadow: var(--shadow);
        pointer-events: auto;
        white-space: nowrap;
      }
      .pill.visible { opacity: 1; transform: translate(-50%, 0); }
      .pill.leaving { opacity: 0; transform: translate(-50%, -8px); }
      .pill-icon { width: 18px; height: 18px; color: var(--accent); flex: none; }
      .pill-text { display: flex; gap: 8px; align-items: baseline; }
      .pill-text strong { font-weight: 600; }
      .secondary { color: var(--secondary); }
      .pill-divider { width: 0.5px; align-self: stretch; margin: 2px 0; background: var(--separator); }
      .pill-done {
        border: 0; background: var(--fill); border-radius: 999px;
        padding: 4px 12px; font-weight: 600;
      }
      .pill-done:hover { background: var(--fill-hover); }

      /* Highlight */
      .highlight {
        position: fixed; display: none; pointer-events: none;
        border: 2px solid var(--accent);
        border-radius: 6px;
        background: color-mix(in srgb, var(--accent) 10%, transparent);
        box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.5), 0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent);
        transition: top .08s ease, left .08s ease, width .08s ease, height .08s ease;
      }
      .highlight.visible { display: block; }
      .chip {
        position: absolute; top: 6px; left: 6px;
        padding: 1px 7px; border-radius: 999px;
        background: var(--accent); color: #fff;
        font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums;
      }

      /* Toast: a dark HUD in both appearances, like macOS */
      .toast {
        position: fixed; bottom: 24px; left: 50%;
        transform: translate(-50%, 8px); opacity: 0;
        transition: opacity .2s ease, transform .2s ease;
        display: flex; align-items: center; gap: 10px;
        padding: 6px 16px 6px 6px; min-height: 42px;
        background: rgba(30, 30, 32, 0.82);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        backdrop-filter: blur(20px) saturate(180%);
        color: #fff; font-weight: 500;
        border: 0.5px solid rgba(255, 255, 255, 0.12);
        border-radius: 999px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
        pointer-events: none;
        white-space: nowrap;
      }
      .toast.visible { opacity: 1; transform: translate(-50%, 0); }
      .toast-thumb { width: 30px; height: 30px; border-radius: 8px; object-fit: cover; flex: none; }
      .toast-icon { width: 24px; height: 24px; padding: 3px; border-radius: 999px; flex: none; margin: 0 2px 0 4px; }
      .toast-icon.success { background: #30d158; color: #fff; }
      .toast-icon.info { color: rgba(255, 255, 255, 0.8); }

      /* Panel */
      .panel {
        position: fixed; max-height: calc(100vh - 24px);
        display: flex; flex-direction: column;
        background: var(--material);
        -webkit-backdrop-filter: blur(30px) saturate(180%);
        backdrop-filter: blur(30px) saturate(180%);
        border: 0.5px solid var(--edge);
        border-radius: 14px;
        box-shadow: var(--shadow);
        pointer-events: auto;
        overflow: hidden;
        animation: pop .16s ease-out;
      }
      @keyframes pop { from { opacity: 0; transform: scale(.97); } to { opacity: 1; transform: none; } }
      .panel-header { display: flex; align-items: flex-start; gap: 8px; padding: 14px 14px 10px 16px; }
      .panel-titles { flex: 1; min-width: 0; }
      .panel-title { font-weight: 600; font-size: 13px; }
      .panel-subtitle { color: var(--secondary); font-size: 11px; margin-top: 1px; }
      .icon-button {
        width: 22px; height: 22px; padding: 5px; flex: none;
        border: 0; border-radius: 999px;
        background: var(--fill); color: var(--secondary);
      }
      .icon-button:hover { background: var(--fill-hover); color: var(--fg); }

      .grid {
        display: grid; gap: 10px;
        padding: 2px 14px 12px; overflow-y: auto;
      }
      .tile {
        display: flex; flex-direction: column; gap: 5px;
        padding: 0; border: 0; background: none; text-align: left; min-width: 0;
      }
      .tile-frame {
        position: relative; aspect-ratio: 4 / 3; border-radius: 8px; overflow: hidden;
        background-color: var(--fill);
        outline: 0.5px solid var(--edge); outline-offset: -0.5px;
        transition: box-shadow .12s ease;
      }
      /* Solid pictures fill the tile; see-through ones show whole, on a checkerboard */
      .tile-frame img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .tile-frame.alpha img { object-fit: contain; }
      .tile-frame.alpha {
        background-image:
          linear-gradient(45deg, rgba(128,128,128,.14) 25%, transparent 25%, transparent 75%, rgba(128,128,128,.14) 75%),
          linear-gradient(45deg, rgba(128,128,128,.14) 25%, transparent 25%, transparent 75%, rgba(128,128,128,.14) 75%);
        background-size: 12px 12px; background-position: 0 0, 6px 6px;
      }
      .tile:hover .tile-frame { box-shadow: 0 0 0 2.5px var(--accent); }
      .tile:focus-visible { outline: none; }
      .tile:focus-visible .tile-frame { box-shadow: 0 0 0 2.5px var(--accent); }
      .broken-icon {
        position: absolute; inset: 0; margin: auto; width: 28px; height: 28px; color: var(--secondary);
      }
      .badge {
        position: absolute; top: 6px; right: 6px; width: 22px; height: 22px; padding: 3px;
        border-radius: 999px; background: var(--accent); color: #fff;
        box-shadow: 0 1px 3px rgba(0, 0, 0, .3);
        opacity: 0; transform: scale(.6); transition: opacity .15s ease, transform .15s ease;
      }
      .tile.sent .badge { opacity: 1; transform: none; }
      .tile-caption { display: flex; flex-direction: column; min-width: 0; padding: 0 2px; }
      .tile-size { font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; }
      .tile-name {
        font-size: 11px; color: var(--secondary);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }

      .panel-footer {
        display: flex; justify-content: flex-end;
        padding: 10px 14px 12px; border-top: 0.5px solid var(--separator);
      }
      .primary {
        border: 0; border-radius: 7px; padding: 5px 14px;
        background: var(--accent); color: #fff; font-weight: 600;
        box-shadow: 0 1px 2px rgba(0, 0, 0, .15);
      }
      .primary:hover { filter: brightness(1.08); }
      .primary:disabled { background: var(--fill); color: var(--secondary); box-shadow: none; filter: none; }
    `;
  }
})();
