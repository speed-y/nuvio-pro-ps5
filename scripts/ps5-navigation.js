/* PS5 adapter for the pinned frontend. F1/F2/F3 key events were observed on the
 * owner's 12.70 console. Native counters use EVO's existing pad reader. */
import { Router } from './routerState.js';
import { NuvioDialog } from '../components/nuvioDialog.js';
import { initPs5HintBar, initPs5SearchKeyboard, refreshPs5HintBar, requestPs5SearchKeyboard } from './ps5-text-input.js';
import { startPs5TvRemoteDiagnostics } from './ps5-tv-remote.js';

function visible(node) {
  return Boolean(node && node.isConnected && !node.disabled &&
    node.getAttribute('aria-disabled') !== 'true' && node.getClientRects().length);
}

function focusedNode() {
  // Dialog buttons deliberately lack .focusable. Never fall through to a page
  // behind a modal, including its two-frame initial-focus and exit animations.
  if (document.body.classList.contains('nuvio-modal-open')) {
    const dialogs = document.querySelectorAll('.nuvio-dialog-backdrop');
    const dialog = dialogs[dialogs.length - 1];
    if (!dialog || dialog.classList.contains('nuvio-dialog-backdrop-exit')) return null;
    const focused = dialog.querySelector('.focused');
    return visible(focused) ? focused : null;
  }
  const screen = Router.getCurrentScreen();
  const overlay = screen?.container?.querySelector('[data-overlay-root], .settings-dialog-backdrop');
  const root = overlay || screen?.container;
  const node = root?.querySelector('.focused') || (root?.classList?.contains('focused') ? root : null);
  return visible(node) ? node : null;
}

function navigationTarget() {
  const focused = focusedNode();
  if (focused) return focused;
  if (document.body.classList.contains('nuvio-modal-open')) {
    const dialogs = document.querySelectorAll?.('.nuvio-dialog-backdrop') || [];
    const dialog = dialogs[dialogs.length - 1];
    if (!dialog || dialog.classList?.contains?.('nuvio-dialog-backdrop-exit')) return null;
    // Never fall through to the page behind a modal; dispatch only to the active dialog itself.
    return typeof dialog.dispatchEvent === 'function' ? dialog : null;
  }
  const screen = Router.getCurrentScreen?.();
  if (visible(document.activeElement) && document.activeElement !== document.body) {
    return document.activeElement;
  }
  if (visible(screen?.container)) return screen.container;
  return typeof document.body?.dispatchEvent === 'function' ? document.body : null;
}

function dispatchKey(type, node, key = 'Enter', keyCode = 13) {
  if (typeof node?.dispatchEvent !== 'function') return;
  const event = new KeyboardEvent(type, {
    key, code: key, keyCode, which: keyCode,
    bubbles: true, cancelable: true
  });
  // Preserve the old native adapter's compatibility with browser engines that
  // ignore the legacy numeric fields in KeyboardEventInit. Nuvio reads them.
  for (const field of ['keyCode', 'which']) {
    if (event[field] !== keyCode) Object.defineProperty(event, field, { get: () => keyCode });
  }
  node.dispatchEvent(event);
}

const DIRECTION_KEYS = [
  null,
  ['ArrowUp', 38],
  ['ArrowRight', 39],
  ['ArrowDown', 40],
  ['ArrowLeft', 37]
];

function dispatchDirection(direction, count = 1) {
  const spec = DIRECTION_KEYS[direction];
  if (!spec) return;
  const [key, code] = spec;
  for (let i = 0; i < count; i++) {
    const target = navigationTarget();
    if (!target) break;
    dispatchKey('keydown', target, key, code);
    dispatchKey('keyup', target.isConnected === false && document.body?.dispatchEvent ? document.body : target, key, code);
  }
  if (typeof refreshPs5HintBar === 'function') refreshPs5HintBar();
}

const TAB_CYCLE_CONFIG = [
  ['detail', '.series-season-btn.focusable', '.focused, .selected', true],
  ['stream', '.stream-route-chip.focusable[data-addon]', '.selected, .focused', true],
  ['settings', '.settings-nav-item.focusable', '.selected, .focused', true],
  ['folderDetail', '.folder-detail-tab.focusable', '.is-selected, .focused', true],
  ['library', '.library-view-mode-button.focusable', '.selected, .focused', true],
  ['discover', '.discover-filter.focusable', '.focused, .selected', false]
];

function activateControl(node, moveFocus = true) {
  if (!visible(node)) return false;
  if (moveFocus) node.focus?.({ preventScroll: true });
  const screen = Router.getCurrentScreen?.();
  const handled = typeof screen?.onPointerActivate === 'function' ? screen.onPointerActivate(node) : false;
  if (!handled) node.click?.();
  if (typeof refreshPs5HintBar === 'function') refreshPs5HintBar();
  return true;
}

function stepTabGroup(delta) {
  const modalStreamFilters = document.body.classList.contains('nuvio-modal-open')
    ? Array.from(document.querySelectorAll?.('.nuvio-dialog-backdrop .series-stream-filter.focusable') || []).filter(visible)
    : [];
  if (modalStreamFilters.length > 1) {
    const cur = Math.max(0, modalStreamFilters.findIndex(el => el.classList.contains('selected') || el.classList.contains('focused')));
    return activateControl(modalStreamFilters[(cur + delta + modalStreamFilters.length) % modalStreamFilters.length]);
  }
  if (document.body.classList.contains('nuvio-modal-open')) return false;
  const route = Router.getCurrent?.() || '';
  const root = Router.getCurrentScreen?.()?.container;
  if (!root || root.querySelector('[data-overlay-root], .settings-dialog-backdrop')) return false;
  const entry = TAB_CYCLE_CONFIG.find(([r]) => r === route);
  if (!entry) return false;
  const [, selector, activeSel, clickAfter] = entry;
  const items = Array.from(root.querySelectorAll(selector) || []).filter(visible);
  if (items.length <= 1) return false;
  const cur = Math.max(0, items.findIndex(el => el.matches(activeSel)));
  const target = items[(cur + delta + items.length) % items.length];
  if (clickAfter) return activateControl(target);
  target.focus?.({ preventScroll: true });
  return true;
}

function triggerDetailTriggerAction(direction) {
  const route = Router.getCurrent?.() || '';
  const root = Router.getCurrentScreen?.()?.container;
  if (route !== 'detail' || !root || root.querySelector('[data-overlay-root], .settings-dialog-backdrop')) return false;
  if (direction > 0) {
    return activateControl(root.querySelector('[data-action="playDefault"]'));
  }
  const content = root.querySelector('.series-detail-content');
  if (content) {
    content.scrollTo?.({ top: 0, behavior: 'smooth' });
    content.scrollTop = 0;
  }
  root.scrollTo?.({ top: 0, behavior: 'smooth' });
  const heroBtn = root.querySelector('.series-detail-actions .focusable') || root.querySelector('[data-action="playDefault"]');
  if (visible(heroBtn)) {
    const prev = root.querySelector('.focused');
    if (prev && prev !== heroBtn) prev.classList.remove('focused');
    heroBtn.classList.add('focused');
    heroBtn.focus?.({ preventScroll: true });
    if (typeof refreshPs5HintBar === 'function') refreshPs5HintBar();
    return true;
  }
  return false;
}

function triggerTouchPadAction() {
  if (document.body.classList.contains('nuvio-modal-open')) return false;
  const route = Router.getCurrent?.() || '';
  const root = Router.getCurrentScreen?.()?.container;
  if (!root || !['home', 'library', 'discover'].includes(route)) return false;
  if (!root.querySelector('[data-overlay-root], .settings-dialog-backdrop')) {
    if (activateControl(root.querySelector('[data-action="toggleSidebar"]'))) return true;
    const sidebarItem = root.querySelector('.home-sidebar-item.focusable, .modern-sidebar-item.focusable');
    if (visible(sidebarItem)) return activateControl(sidebarItem);
  }
  return false;
}

function cancelPendingHoldTimers(screen) {
  screen?.cancelPendingHeroHold?.();
  screen?.cancelPendingEpisodeHold?.();
  screen?.cancelPendingSeasonHold?.();
  screen?.cancelPendingPosterHold?.();
  screen?.cancelPendingProfileHold?.();
  screen?.cancelPendingContinueWatchingHold?.();
  screen?.cancelPendingContinueWatchingEnter?.();
}

async function openItemActions() {
  const screen = Router.getCurrentScreen();
  const node = focusedNode();
  if (!screen || node?.matches?.('input, textarea, select') ||
    document.body.classList.contains('nuvio-modal-open')) return;
  cancelPendingHoldTimers(screen);
  if (node && screen.isEpisodeHoldTarget?.(node)) screen.openEpisodeHoldMenu(node);
  else if (node && screen.isSeasonHoldTarget?.(node)) screen.openSeasonHoldMenu(node);
  else if (node?.dataset?.action === 'toggleLibrary' && screen.openLibraryListMenu) await screen.openLibraryListMenu();
  else if (node && screen.openHeroPlayMenu && ['playDefault', 'playFromBeginning', 'ps5PlayOptions'].includes(node.dataset?.action)) screen.openHeroPlayMenu();
  else if (node && screen.canHoldManageProfile?.(node)) screen.openOptionsDialog(screen.getProfileById(node.dataset.profileId));
  else if (node && screen.isHomeHoldTarget?.(node)) screen.openHoldMenuForNode(node);
  else if (node && screen.isPosterHoldTarget?.(node)) await screen.openPosterOptionsMenu(node);
  else if (Router.getCurrent?.() === 'detail' && !screen.container?.querySelector?.('[data-overlay-root], .settings-dialog-backdrop') &&
    activateControl(screen.container?.querySelector?.('[data-action="toggleLibrary"]'), false)) return;
  else if (Router.getCurrent?.() === 'stream' && activateControl(screen.container?.querySelector?.('[data-action="refreshStreams"]'))) return;
  else return;
  // Existing hold menus suppress Enter until release. Release that internal latch.
  dispatchKey('keyup', document.body);
}

function openDisplayDiagnostics() {
  const dpr = window.devicePixelRatio || 1;
  const viewport = window.visualViewport;
  const content = document.createElement('pre');
  content.style.cssText = 'white-space:pre-wrap;font:inherit;line-height:1.6';
  content.textContent = [
    `CSS viewport: ${window.innerWidth} × ${window.innerHeight}`,
    `Device pixel ratio: ${dpr}`,
    `Viewport × DPR estimate: ${Math.round(window.innerWidth * dpr)} × ${Math.round(window.innerHeight * dpr)}`,
    `Screen (CSS px): ${window.screen.width} × ${window.screen.height}`,
    `Available screen: ${window.screen.availWidth} × ${window.screen.availHeight}`,
    viewport ? `Visual viewport: ${viewport.width} × ${viewport.height}, scale ${viewport.scale}` : 'Visual viewport: unavailable',
    '', 'Browser-reported values only. The estimate does not verify the internal rendering surface or HDMI output mode.',
    'No scaling settings changed. Compare these values with the TV signal information.'
  ].join('\n');
  let dialog;
  dialog = new NuvioDialog({
    title: 'Display diagnostics', widthVw: 70, content,
    buttons: [{ label: 'Close', onAction: () => dialog.destroy() }]
  }).mount(document.body);
}

function openControllerMenu() {
  if (document.body.classList.contains('nuvio-modal-open')) return;
  const restore = focusedNode();
  let dialog;
  const dismiss = () => {
    dialog.destroy();
    if (visible(restore)) restore.focus({ preventScroll: true });
  };
  dialog = new NuvioDialog({
    title: 'Controller menu',
    subtitle: 'Options / Square: item actions · Triangle: Search',
    buttons: [
      { label: 'Player settings', onAction: () => {
        dismiss();
        document.getElementById('__evoClose')?.click();
      } },
      { label: 'Display diagnostics', onAction: () => {
        dialog.destroy({ afterExit: openDisplayDiagnostics });
      } },
      { label: 'Cancel', onAction: dismiss }
    ],
    onDismiss: () => { if (visible(restore)) restore.focus({ preventScroll: true }); }
  }).mount(document.body);
}

async function openSearch() {
  const route = Router.getCurrent();
  // Do not escape profile/PIN selection, onboarding or an active dialog.
  if (!route || ['profileSelection', 'authQrSignIn', 'authSignIn',
    'serverConnection', 'syncCode', 'experienceModeSelection',
    'essentialAddonSetup', 'player'].includes(route) ||
    document.body.classList.contains('nuvio-modal-open') ||
    Router.getCurrentScreen()?.container?.querySelector('[data-overlay-root], .settings-dialog-backdrop')) return;
  // Search paints synchronously on PS5. Focus before awaiting decoration.
  const navigation = route !== 'search' ? Router.navigate('search') : null;
  if (Router.getCurrent() !== 'search' || document.hidden) return navigation;
  const screen = Router.getCurrentScreen();
  const input = screen?.container?.querySelector('#searchInput');
  if (!visible(input)) return navigation;
  screen.focusNode(screen.container.querySelector('.focused'), input);
  input.focus({ preventScroll: true });
  void requestPs5SearchKeyboard();
  await navigation;
}

export function initPs5Navigation() {
  if (!globalThis.__NUVIO_PS5__) return;
  if (typeof initPs5HintBar === 'function') initPs5HintBar();
  if (window.__evoHook && window.__NUVIO_PS5_TV_REMOTE_DIAGNOSTICS__ === true) {
    startPs5TvRemoteDiagnostics(imageDiagnostic);
  }
  initPs5SearchKeyboard();
  const lastShortcutAt = Object.create(null);
  function claimShortcut(name, windowMs = 180) {
    const now = Date.now();
    if (now - (lastShortcutAt[name] || 0) < windowMs) return false;
    lastShortcutAt[name] = now;
    return true;
  }
  function handleBrowseShortcut(name) {
    if (name === 'l1') return stepTabGroup(-1);
    if (name === 'r1') return stepTabGroup(1);
    if (name === 'l2') {
      if (triggerDetailTriggerAction(-1)) return true;
      dispatchDirection(1, 4);
      return true;
    }
    if (name === 'r2') {
      if (triggerDetailTriggerAction(1)) return true;
      dispatchDirection(3, 4);
      return true;
    }
    if (name === 'touchpad') return triggerTouchPadAction();
    return false;
  }
  let redirecting = false;
  window.__nuvioPs5PointerDown = (event) => {
    const node = focusedNode();
    // A pointer press must not change D-pad focus before its click arrives.
    // Preserve trusted text-field activation when the pointer is on that field.
    if (event.button === 0 && !(node?.matches('input, textarea, select') && node.contains(event.target))) {
      event.preventDefault();
    }
  };
  window.__nuvioPs5Activate = (event) => {
    // Upstream Enter handlers also use .click(). Those intentional actions
    // must reach their listeners, not recurse through another Enter event.
    if (redirecting || event.isTrusted === false || event.button !== 0) return;
    if (event.target?.closest?.('#__evoClose')) return;
    const node = focusedNode();
    if (node?.matches('input, textarea, select') && node.contains(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!node) return; // No stale, hidden or background activation.
    redirecting = true;
    try {
      if (node.matches('input, textarea, select')) {
        // Search uses our browser keyboard. Other fields retain native entry.
        node.focus({ preventScroll: true });
        node.click();
        if (node.id === 'searchInput') void requestPs5SearchKeyboard();
      } else {
        dispatchKey('keydown', node);
        dispatchKey('keyup', node.isConnected ? node : document.body);
      }
    } finally { redirecting = false; }
  };
  let openingOptions = false;
  function requestItemActions() {
    if (openingOptions) return;
    openingOptions = true;
    openItemActions().catch(error => console.warn('PS5 item actions failed', error))
      .finally(() => { openingOptions = false; });
  }
  function requestControllerMenu() {
    const node = focusedNode();
    if (document.body.classList.contains('nuvio-modal-open') || node?.matches?.('input, textarea, select')) return;
    if (!claimShortcut('controller-menu', 180)) return;
    cancelPendingHoldTimers(Router.getCurrentScreen?.());
    openControllerMenu();
  }
  let openingSearch = false;
  function requestSearch() {
    if (openingSearch) return;
    openingSearch = true;
    openSearch().catch(error => console.warn('PS5 Search shortcut failed', error))
      .finally(() => { openingSearch = false; });
  }
  const SHOULDER_BY_KEY = { F5: 'l1', 116: 'l1', F6: 'r1', 117: 'r1', F7: 'l2', 118: 'l2', F8: 'r2', 119: 'r2' };
  window.addEventListener('keydown', event => {
    const shoulder = SHOULDER_BY_KEY[event.key] || SHOULDER_BY_KEY[event.keyCode];
    if (shoulder) {
      if (document.querySelector?.('.ps5-search-keyboard')) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!event.repeat || shoulder === 'l2' || shoulder === 'r2') {
        if (claimShortcut(shoulder, event.repeat ? 90 : 180)) handleBrowseShortcut(shoulder);
      }
      return;
    }
    // Owner's ordered Up, Square, Down, Options diagnostic on build 1031-1013:
    // ArrowUp/38, F2/113, ArrowDown/40, F3/114. Later isolated Triangle: F1/112.
    if (!['F1', 'F2', 'F3'].includes(event.key) && ![112, 113, 114].includes(event.keyCode)) return;
    const isTriangle = event.key === 'F1' || event.keyCode === 112;
    const isSquare = event.key === 'F2' || event.keyCode === 113;
    // The keyboard owns Triangle/Space and Square/Delete while it is open.
    if (document.body.classList.contains('nuvio-modal-open') && (isTriangle || isSquare)) return;
    // The PIN overlay owns Square/Backspace while it is open.
    if (isSquare && Router.getCurrentScreen()?.container?.querySelector('[data-overlay-root="pin"]')) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!event.repeat) {
      if (isTriangle) requestSearch();
      else if (isSquare) requestItemActions();
      else requestControllerMenu();
    }
  }, true);
  window.addEventListener('nuvio:options', requestControllerMenu);
  window.addEventListener('nuvio:controller-menu', requestSearch);

  // The native hook is absent in desktop previews. Do not hammer their server.
  if (!window.__evoHook) return;
  document.addEventListener('visibilitychange', () => {
    imageDiagnostic('ps5 visibility hidden=' + Number(document.hidden));
  });
  // Private-candidate diagnostics: observe the failing console before changing
  // loading policy. Never send image URLs, titles, account state or raw errors.
  let imageReports = 0;
  let lastImageReport = Date.now();
  function imageDiagnostic(message) {
    const request = new XMLHttpRequest();
    request.open('GET', '/evo/log?m=' + encodeURIComponent(message), true);
    request.timeout = 1500;
    request.send();
  }
  let tmdbReports = 0;
  window.__nuvioPs5TmdbResponse = (response, payload, jsonState) => {
    // Observe the parser's result without reading another response body or
    // changing the request. Never log payload values, URLs or raw errors.
    try {
      if (document.hidden || Router.getCurrent() !== 'folderDetail' || tmdbReports >= 24) return;
      tmdbReports++;
      const status = Number(response.status);
      const shape = payload === null ? 'null' : Array.isArray(payload) ? 'array' : typeof payload === 'object' ? 'object' : 'other';
      const counts = ['results', 'items', 'cast', 'crew', 'parts'].map(key =>
        key + '=' + (Array.isArray(payload?.[key]) ? payload[key].length : -1));
      imageDiagnostic('ps5 tmdb status=' + (Number.isInteger(status) && status >= 100 && status <= 599 ? status : 0) +
        ' json=' + ([-1, 0, 1].includes(jsonState) ? jsonState : -1) + ' shape=' + shape + ' ' + counts.join(' ') +
        ' apiError=' + Number(payload?.success === false));
    } catch (_) {} // Diagnostics must not turn a successful request into a failure.
  };
  function reportImages() {
    if (imageReports >= 6 || Date.now() - lastImageReport < 10000) return;
    lastImageReport = Date.now();
    const route = Router.getCurrent();
    if (!['home', 'folderDetail'].includes(route)) return;
    const screen = Router.getCurrentScreen();
    const posters = Array.from(screen.container.querySelectorAll('.content-poster'));
    if (!posters.length && route !== 'folderDetail') return;
    imageReports++;
    if (imageReports === 1) {
      // Locally generated 2x3 lossy WebP. No CDN request or owner image is used.
      const probe = new Image();
      probe.onload = () => imageDiagnostic('ps5 format webp=' + Number(probe.naturalWidth === 2 && probe.naturalHeight === 3));
      probe.onerror = () => imageDiagnostic('ps5 format webp=0');
      probe.src = 'data:image/webp;base64,UklGRi4AAABXRUJQVlA4ICIAAAAwAQCdASoCAAMAAgA0JaAAA3AA/vOkn//5Kf/eV/ru2YAA';
    }
    const counts = { loaded: 0, failed: 0, pending: 0, deferred: 0, missing: 0, placeholder: 0 };
    function state(image) {
      if (!(image instanceof HTMLImageElement)) return 'placeholder';
      if (image.getAttribute('data-src')) return 'deferred';
      if (!image.getAttribute('src')) return 'missing';
      if (!image.complete) return 'pending';
      return image.naturalWidth > 0 ? 'loaded' : 'failed';
    }
    posters.forEach(image => { counts[state(image)]++; });
    const messages = ['ps5 images ' + route + ' ' + Object.entries(counts).map(([key, value]) => key + '=' + value).join(' ')];
    // Measure the live value; the downloaded snapshot cannot explain its absence.
    // Never log the value, profile identifiers, source addresses or error text.
    const collections = localStorage.getItem('collectionsState');
    messages.push('ps5 collections present=' + Number(collections !== null) +
      ' chars=' + (collections === null ? 0 : collections.length) +
      ' overSnapshotLimit=' + Number(collections !== null && collections.length > 524288));
    if (route === 'folderDetail') {
      const name = String(screen.folder?.title || '').toLowerCase().replace(/[^a-z]/g, '');
      const folder = ['hbomax', 'max', 'netflix', 'newmovies', 'newseries'].includes(name) ? name : 'other';
      const tabs = (screen.tabs || []).filter(tab => !tab.isAllTab);
      const sources = { addon: 0, tmdb: 0, trakt: 0, other: 0, loading: 0, errors: 0 };
      let items = 0, noArtwork = 0, markedLoading = 0;
      tabs.forEach(tab => {
        const provider = String(tab.source?.provider || 'addon').toLowerCase();
        sources[['addon', 'tmdb', 'trakt'].includes(provider) ? provider : 'other']++;
        sources.loading += Number(Boolean(tab.loading));
        sources.errors += Number(Boolean(tab.error));
        (tab.items || []).forEach(item => {
          items++;
          markedLoading += Number(Boolean(item.isLoading));
          noArtwork += Number(![item.poster, item.thumbnail, item.background, item.backdrop,
            item.backdropUrl, item.landscapePoster].some(value => String(value || '').trim()));
        });
      });
      messages.push('ps5 folder ' + folder + ' tabs=' + tabs.length + ' ' +
        Object.entries(sources).map(([key, value]) => key + '=' + value).join(' '));
      messages.push('ps5 folder items=' + items + ' noArtwork=' + noArtwork + ' markedLoading=' + markedLoading);
      const kinds = { discover: 0, list: 0, person: 0, director: 0, collection: 0, network: 0, company: 0, other: 0 };
      tabs.filter(tab => String(tab.source?.provider || '').toLowerCase() === 'tmdb').forEach(tab => {
        const kind = String(tab.source.tmdbSourceType || '').toLowerCase();
        kinds[Object.prototype.hasOwnProperty.call(kinds, kind) ? kind : 'other']++;
      });
      messages.push('ps5 tmdb sources ' + Object.entries(kinds).map(([key, value]) => key + '=' + value).join(' '));
    }
    const focused = screen.container.querySelector('.focused .content-poster');
    if (focused) {
      const src = focused.getAttribute('src') || focused.getAttribute('data-src') || '';
      const provider = /^(?:https?:)?\/\/images\.metahub\.space\//i.test(src) ? 'metahub' :
        /^(?:https?:)?\/\/image\.tmdb\.org\//i.test(src) ? 'tmdb' : src ? 'other' : 'none';
      const rect = focused.getBoundingClientRect();
      const style = getComputedStyle(focused);
      messages.push('ps5 poster state=' + state(focused) + ' provider=' + provider +
        ' lazy=' + Number(focused.getAttribute('loading') === 'lazy') +
        ' box=' + Number(rect.width > 0 && rect.height > 0) +
        ' opaque=' + Number(Number(style.opacity) > 0));
    }
    messages.forEach(imageDiagnostic);
  }
  const SHORTCUT_ACTION_NAMES = { 2: 'r2', 3: 'l1', 4: 'r1', 5: 'l2', 6: 'touchpad' };
  let previous = null;
  function poll() {
    if (document.hidden) { previous = null; setTimeout(poll, 250); return; }
    const request = new XMLHttpRequest();
    request.open('GET', '/evo/controller', true);
    request.timeout = 1500;
    request.onload = () => {
      if (document.hidden || request.status !== 200) { previous = null; return; }
      try {
        const next = JSON.parse(request.responseText);
        if (!Number.isInteger(next.options) || !Number.isInteger(next.menu)) { previous = null; return; }
        if (previous) {
          if (next.menu !== previous.menu) window.dispatchEvent(new Event('nuvio:controller-menu'));
          if (next.options !== previous.options) window.dispatchEvent(new Event('nuvio:options'));
          if (Number.isInteger(next.navigation) && Number.isInteger(previous.navigation) &&
              next.navigation !== previous.navigation &&
              Number.isInteger(next.direction) && next.direction >= 1 && next.direction <= 4) {
            dispatchDirection(next.direction, 1);
          }
          if (Number.isInteger(next.keyboard) && Number.isInteger(previous.keyboard) &&
              next.keyboard !== previous.keyboard) {
            if (document.body.classList.contains('nuvio-modal-open')) {
              if ([1, 2, 3, 4].includes(next.shortcut)) {
                window.dispatchEvent(new CustomEvent('nuvio:keyboard-shortcut', {
                  detail: ['shift', 'submit', 'left', 'right'][next.shortcut - 1]
                }));
              }
              if ([3, 4].includes(next.shortcut) && !document.querySelector?.('.ps5-search-keyboard')) {
                const modalAction = SHORTCUT_ACTION_NAMES[next.shortcut];
                if (claimShortcut(modalAction)) handleBrowseShortcut(modalAction);
              }
            } else {
              const browseAction = SHORTCUT_ACTION_NAMES[next.shortcut];
              if (browseAction && claimShortcut(browseAction)) handleBrowseShortcut(browseAction);
            }
          }
        }
        previous = next;
      } catch (_) { previous = null; }
    };
    request.onerror = request.ontimeout = () => { previous = null; };
    request.onloadend = () => {
      // Diagnostics must not change controller delivery or run in the background.
      try { if (!document.hidden) reportImages(); } catch (_) {}
      setTimeout(poll, 50);
    };
    request.send();
  }
  poll();
}
