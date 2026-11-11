/* PS5 adapter for the pinned frontend. F1/F2/F3 key events were observed on the
 * owner's 12.70 console. Native counters use EVO's existing pad reader. */
import { Router } from './routerState.js';
import { NuvioDialog } from '../components/nuvioDialog.js';
import { initPs5SearchKeyboard, requestPs5SearchKeyboard } from './ps5-text-input.js';
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
  const node = root?.querySelector('.focused') || (root?.classList.contains('focused') ? root : null);
  return visible(node) ? node : null;
}

function dispatchKey(type, node, key = 'Enter', keyCode = 13) {
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

async function openContextMenu() {
  const screen = Router.getCurrentScreen();
  const node = focusedNode();
  if (!screen || !node || node.matches('input, textarea, select') ||
    document.body.classList.contains('nuvio-modal-open')) return;
  // A menu press must not leave an earlier hold timer or delayed X pending.
  screen.cancelPendingHeroHold?.();
  screen.cancelPendingEpisodeHold?.();
  screen.cancelPendingSeasonHold?.();
  screen.cancelPendingPosterHold?.();
  screen.cancelPendingProfileHold?.();
  screen.cancelPendingContinueWatchingHold?.();
  screen.cancelPendingContinueWatchingEnter?.();
  if (screen.isEpisodeHoldTarget?.(node)) screen.openEpisodeHoldMenu(node);
  else if (screen.isSeasonHoldTarget?.(node)) screen.openSeasonHoldMenu(node);
  else if (node.dataset.action === 'toggleLibrary' && screen.openLibraryListMenu) await screen.openLibraryListMenu();
  else if (screen.openHeroPlayMenu && (node.closest('.series-detail-actions') ||
    ['playDefault', 'ps5PlayOptions'].includes(node.dataset.action))) screen.openHeroPlayMenu();
  else if (screen.canHoldManageProfile?.(node)) screen.openOptionsDialog(screen.getProfileById(node.dataset.profileId));
  else if (screen.isHomeHoldTarget?.(node)) screen.openHoldMenuForNode(node);
  else if (screen.isPosterHoldTarget?.(node)) await screen.openPosterOptionsMenu(node);
  else return openControllerMenu();
  // Existing hold menus suppress Enter until release. Options is not Enter:
  // release that internal latch without pretending the browser emitted a key.
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
  if (window.__evoHook && window.__NUVIO_PS5_TV_REMOTE_DIAGNOSTICS__ === true) {
    startPs5TvRemoteDiagnostics(imageDiagnostic);
  }
  initPs5SearchKeyboard();
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
  function requestOptions() {
    if (openingOptions) return;
    openingOptions = true;
    openContextMenu().catch(error => console.warn('PS5 item actions failed', error))
      .finally(() => { openingOptions = false; });
  }
  let openingSearch = false;
  function requestSearch() {
    if (openingSearch) return;
    openingSearch = true;
    openSearch().catch(error => console.warn('PS5 Search shortcut failed', error))
      .finally(() => { openingSearch = false; });
  }
  window.addEventListener('keydown', event => {
    // Owner's ordered Up, Square, Down, Options diagnostic on build 1031-1013:
    // ArrowUp/38, F2/113, ArrowDown/40, F3/114. Later isolated Triangle: F1/112.
    if (!['F1', 'F2', 'F3'].includes(event.key) && ![112, 113, 114].includes(event.keyCode)) return;
    // The keyboard owns Triangle/Space and Square/Delete while it is open.
    if (document.body.classList.contains('nuvio-modal-open') &&
        (event.key === 'F1' || event.key === 'F2' || [112, 113].includes(event.keyCode))) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!event.repeat) {
      if (event.key === 'F1' || event.keyCode === 112) requestSearch();
      else requestOptions();
    }
  }, true);
  window.addEventListener('nuvio:options', requestOptions);
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
          else if (next.options !== previous.options) window.dispatchEvent(new Event('nuvio:options'));
          else if (Number.isInteger(next.navigation) && Number.isInteger(previous.navigation) &&
              next.navigation !== previous.navigation &&
              Number.isInteger(next.direction) && next.direction >= 1 && next.direction <= 4) {
            const node = focusedNode();
            if (node) {
              const [key, code] = [null, ['ArrowUp', 38], ['ArrowRight', 39],
                ['ArrowDown', 40], ['ArrowLeft', 37]][next.direction];
              dispatchKey('keydown', node, key, code);
              dispatchKey('keyup', node.isConnected ? node : document.body, key, code);
            }
          }
          if (document.body.classList.contains('nuvio-modal-open') &&
              Number.isInteger(next.keyboard) && Number.isInteger(previous.keyboard) &&
              next.keyboard !== previous.keyboard && [1, 2, 3, 4].includes(next.shortcut)) {
            window.dispatchEvent(new CustomEvent('nuvio:keyboard-shortcut', {
              detail: ['shift', 'submit', 'left', 'right'][next.shortcut - 1]
            }));
          }
        }
        previous = next;
      } catch (_) { previous = null; }
    };
    request.onerror = request.ontimeout = () => { previous = null; };
    request.onloadend = () => {
      // Diagnostics must not change controller delivery or run in the background.
      try { if (!document.hidden) reportImages(); } catch (_) {}
      setTimeout(poll, 150);
    };
    request.send();
  }
  poll();
}
