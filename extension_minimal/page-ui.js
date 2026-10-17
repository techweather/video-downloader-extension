// In-page status UI for Video Download: the "Scanning…" pill and HUD toasts.
// The same file ships in both extensions (extension_chrome/ and extension_minimal/);
// keep them identical. It matches the image picker's look (image-picker.js).
//
// The background script never calls this directly — it injects it into the page:
//   Chrome:  scripting.executeScript({ func: dlwithitPageUI, args: [command] })
//   Firefox: tabs.executeScript({ code: `(${dlwithitPageUI})(${JSON.stringify(command)})` })
// so the function must stay self-contained (no outside variables).
//
// command fields, applied in this order:
//   banner: 'text' shows/updates the pill, null removes it
//   toast:  { title, body?, type?: 'info'|'warning', sticky? } shows a toast, null hides it

function dlwithitPageUI(command) {
  // One host per page, reused across injections (they share this window).
  let ui = window.__dlwithitPageUI;
  if (!ui || !ui.host.isConnected) {
    const host = document.createElement('dlwithit-status');
    host.style.cssText = 'all: initial; position: fixed; inset: 0; pointer-events: none; z-index: 2147483647;';
    const root = host.attachShadow({ mode: 'closed' });
    root.innerHTML = `<style>
      :host { all: initial; }
      * { box-sizing: border-box; }
      .pill, .toast {
        font: 13px/1.35 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
        -webkit-font-smoothing: antialiased;
        position: fixed; left: 50%;
        transition: opacity .2s ease, transform .2s ease;
        display: flex; align-items: center; gap: 10px;
        border-radius: 999px;
        pointer-events: none;
        cursor: default;
      }
      svg { width: 100%; height: 100%; display: block; }

      /* Pill: same material as the picker's "Pick Images" pill */
      .pill {
        --accent: #007aff;
        --fg: #1d1d1f;
        --secondary: rgba(60, 60, 67, 0.62);
        --material: rgba(246, 246, 248, 0.78);
        --edge: rgba(0, 0, 0, 0.12);
        --shadow: 0 12px 40px rgba(0, 0, 0, 0.18), 0 2px 8px rgba(0, 0, 0, 0.08);
        top: 14px;
        transform: translate(-50%, -8px); opacity: 0;
        padding: 7px 16px 7px 12px; min-height: 34px;
        color: var(--fg);
        background: var(--material);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        backdrop-filter: blur(24px) saturate(180%);
        border: 0.5px solid var(--edge);
        box-shadow: var(--shadow);
        white-space: nowrap;
      }
      @media (prefers-color-scheme: dark) {
        .pill {
          --accent: #0a84ff;
          --fg: #f5f5f7;
          --secondary: rgba(235, 235, 245, 0.6);
          --material: rgba(44, 44, 46, 0.76);
          --edge: rgba(255, 255, 255, 0.14);
          --shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 2px 8px rgba(0, 0, 0, 0.3);
        }
      }
      .pill.visible { opacity: 1; transform: translate(-50%, 0); }
      .pill-text { display: flex; gap: 8px; align-items: baseline; }
      .pill-text strong { font-weight: 600; }
      .secondary { color: var(--secondary); }

      /* macOS-style activity indicator: 8 spokes, stepped rotation */
      .spinner { width: 16px; height: 16px; flex: none; color: var(--secondary); animation: spin .8s steps(8) infinite; }
      @keyframes spin { to { transform: rotate(360deg); } }

      /* Toast: a dark HUD in both appearances, like macOS */
      .toast {
        bottom: 24px;
        transform: translate(-50%, 8px); opacity: 0;
        padding: 9px 18px 9px 10px; min-height: 42px;
        max-width: min(440px, calc(100vw - 32px));
        background: rgba(30, 30, 32, 0.82);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        backdrop-filter: blur(20px) saturate(180%);
        color: #fff; font-weight: 500;
        border: 0.5px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
      }
      .toast.visible { opacity: 1; transform: translate(-50%, 0); }
      .toast.has-body { align-items: flex-start; border-radius: 20px; padding: 11px 18px 12px 12px; }
      .toast-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
      .toast-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .toast-body { font-weight: 400; font-size: 12px; color: rgba(255, 255, 255, 0.7); white-space: normal; text-wrap: pretty; }
      .toast-icon { width: 22px; height: 22px; flex: none; margin: 0 2px; }
      .toast-icon.info { color: rgba(255, 255, 255, 0.8); }
      .toast-icon.warning { color: #ffd60a; }
    </style>`;
    document.documentElement.appendChild(host);

    const pill = document.createElement('div');
    pill.className = 'pill';
    const toast = document.createElement('div');
    toast.className = 'toast';
    root.append(pill, toast);

    ui = window.__dlwithitPageUI = { host, pill, toast, timer: null };
  }

  const ICONS = {
    info: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 9v5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="6.3" r="1.1" fill="currentColor"/></svg>',
    warning: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M8.7 3.3a1.5 1.5 0 0 1 2.6 0l6.4 11.2a1.5 1.5 0 0 1-1.3 2.2H3.6a1.5 1.5 0 0 1-1.3-2.2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M10 7.6v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="14.1" r="1.05" fill="currentColor"/></svg>',
    spinner: '<svg viewBox="0 0 20 20" aria-hidden="true">' +
      [0, 1, 2, 3, 4, 5, 6, 7].map(i =>
        `<line x1="10" y1="2.5" x2="10" y2="6.2" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" opacity="${(1 - i * 0.11).toFixed(2)}" transform="rotate(${-i * 45} 10 10)"/>`
      ).join('') + '</svg>'
  };

  // Small element helper: el('div', 'class', 'text')
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  // Remove the host once nothing is showing, so the page is left as it was.
  function removeHostIfIdle() {
    setTimeout(() => {
      if (!ui.pill.classList.contains('visible') && !ui.toast.classList.contains('visible')) {
        ui.host.remove();
        if (window.__dlwithitPageUI === ui) window.__dlwithitPageUI = null;
      }
    }, 250);
  }

  if ('banner' in command) {
    if (command.banner === null) {
      ui.pill.classList.remove('visible');
      removeHostIfIdle();
    } else {
      ui.pill.replaceChildren();
      const spinner = el('span', 'spinner');
      spinner.innerHTML = ICONS.spinner;
      const text = el('span', 'pill-text');
      text.append(el('strong', null, 'Video Download'), el('span', 'secondary', command.banner));
      ui.pill.append(spinner, text);
      // Show now rather than next frame, so a hide that follows at once wins.
      void ui.pill.offsetWidth;  // commit the hidden state so the fade-in runs
      ui.pill.classList.add('visible');
    }
  }

  if ('toast' in command) {
    clearTimeout(ui.timer);
    const t = command.toast;
    if (t === null) {
      ui.toast.classList.remove('visible');
      removeHostIfIdle();
    } else {
      const type = t.type || 'info';
      ui.toast.replaceChildren();
      ui.toast.classList.toggle('has-body', !!t.body);
      const icon = el('span', `toast-icon ${type}`);
      icon.innerHTML = ICONS[type] || ICONS.info;
      const text = el('span', 'toast-text');
      text.appendChild(el('span', 'toast-title', t.title));
      if (t.body) text.appendChild(el('span', 'toast-body', t.body));
      ui.toast.append(icon, text);
      void ui.toast.offsetWidth;  // commit the hidden state so the fade-in runs
      ui.toast.classList.add('visible');
      // Long enough to read: 2.5s, plus time for any explanation, capped at 9s.
      if (!t.sticky) {
        const readingTime = Math.min(9000, 2500 + ((t.body || '').length * 45));
        ui.timer = setTimeout(() => {
          ui.toast.classList.remove('visible');
          removeHostIfIdle();
        }, readingTime);
      }
    }
  }
}

// Toast copy shared by both extensions' background scripts.
const DLWITHIT_TOASTS = {
  stillScanning: { title: 'Still scanning this page…' },
  launching: { title: 'Opening dlwithit…', sticky: true },
  launchedTryAgain: { title: 'Opening dlwithit…', body: 'Try the download again in a few seconds.' },
  cantConnect: { title: 'Couldn’t connect to dlwithit', body: 'Open the app and try again.', type: 'warning' }
};

// The "nothing found" toast after a page scan. Self-contained, so Firefox can
// inline it into the scan code it injects.
function dlwithitNoVideosToast(blobVideoCount) {
  return {
    title: 'No downloadable videos found on this page',
    body: blobVideoCount > 0
      ? 'Found ' + blobVideoCount + ' streaming video player' + (blobVideoCount === 1 ? '' : 's') +
        ' that can’t be downloaded from here. Open a single video’s own page, then try Video Download again.'
      : 'The videos may not have loaded yet, or the page delivers them in a way dlwithit can’t read.',
    type: 'warning'
  };
}
