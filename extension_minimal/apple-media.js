// Finds the animations on Apple product pages (apple.com/imac/, /mac-mini/, …).
//
// Their <video> elements play through blob: URLs, which can't be downloaded.
// What the page does give is the folder each animation lives in:
//   data-video-basepath="/105/media/us/mac-mini/2024/{uuid}/anim/ports/"
//   data-inline-media-basepath="/105/media/us/imac/2024/{uuid}/anim/hero/"
// The app tries Apple's file names in that folder (xlarge_2x.mp4, large_2x.mov, …)
// and keeps the best one — see core/apple_media.py.
//
// Injected before the Video Download page scan, which calls
// window.__dlwithitScanAppleMedia(). Keep this file identical in
// extension_chrome/ and extension_minimal/.

window.__dlwithitScanAppleMedia = function (doc, pageUrl) {
  doc = doc || document;
  pageUrl = pageUrl || window.location.href;

  const videos = [];
  const folders = [];

  // "MacBook Neo - Apple" -> "MacBook Neo"
  const product = (doc.title || '').replace(/\s*[|—–-]\s*Apple\s*$/i, '').trim() || 'Apple';

  // "/…/anim/continuity-hero/" -> "continuity hero"
  function sectionName(folder) {
    const match = folder.match(/\/anim\/([^/]+)\/?$/);
    return match ? match[1].replace(/[-_]+/g, ' ').trim() : null;
  }

  function nearbyImage(element) {
    let parent = element.parentElement;
    for (let i = 0; parent && i < 4; i++, parent = parent.parentElement) {
      const imgs = parent.querySelectorAll ? parent.querySelectorAll('img') : [];
      for (const img of imgs) {
        const src = img.currentSrc || img.src;
        if (src && !/^data:/i.test(src)) return src;
      }
    }
    return null;
  }

  const attrs = ['data-video-basepath', 'data-inline-media-basepath'];
  doc.querySelectorAll('[data-video-basepath], [data-inline-media-basepath]').forEach((element) => {
    for (const attr of attrs) {
      const basepath = element.getAttribute(attr);
      if (!basepath || /^(blob|data):/i.test(basepath.trim())) continue;
      let folder;
      try { folder = new URL(basepath.trim(), pageUrl).href; } catch (e) { continue; }
      if (!folder.endsWith('/')) folder += '/';
      if (folders.includes(folder)) continue;
      folders.push(folder);

      const section = sectionName(folder);
      videos.push({
        url: folder,
        type: 'apple-anim',
        basepath: folder,
        title: section ? product + ' - ' + section : product,
        thumbnail: nearbyImage(element),
        originalFilename: section
      });
    }
  });

  return { videos, folders };
};
