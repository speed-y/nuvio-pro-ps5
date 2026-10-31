/* PS5 adapter for the pinned frontend. Native button counters come from EVO's
 * existing pad reader, not guessed DOM events or a guessed Gamepad mapping. */
import { Router } from './routerState.js';
import { NuvioDialog } from '../components/nuvioDialog.js';

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

function enter(type, node) {
  const event = new KeyboardEvent(type, {
    key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
    bubbles: true, cancelable: true
  });
  // Preserve the old native adapter's compatibility with browser engines that
  // ignore the legacy numeric fields in KeyboardEventInit. Nuvio reads them.
  for (const field of ['keyCode', 'which']) {
    if (event[field] !== 13) Object.defineProperty(event, field, { get: () => 13 });
  }
  node.dispatchEvent(event);
}

async function openContextMenu() {
  const screen = Router.getCurrentScreen();
  const node = focusedNode();
  if (!screen || !node || document.body.classList.contains('nuvio-modal-open')) return;
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
  else if (screen.openHeroPlayMenu && node.closest('.series-detail-actions')) screen.openHeroPlayMenu();
  else if (screen.canHoldManageProfile?.(node)) screen.openOptionsDialog(screen.getProfileById(node.dataset.profileId));
  else if (screen.isHomeHoldTarget?.(node)) screen.openHoldMenuForNode(node);
  else if (screen.isPosterHoldTarget?.(node)) await screen.openPosterOptionsMenu(node);
  else return openControllerMenu();
  // Existing hold menus suppress Enter until release. Options is not Enter:
  // release that internal latch without pretending the browser emitted a key.
  enter('keyup', document.body);
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
    subtitle: 'Options: item actions · Triangle: this menu',
    buttons: [
      { label: 'Player settings', onAction: () => {
        dismiss();
        document.getElementById('__evoClose')?.click();
      } },
      { label: 'Cancel', onAction: dismiss }
    ],
    onDismiss: () => { if (visible(restore)) restore.focus({ preventScroll: true }); }
  }).mount(document.body);
}

export function initPs5Navigation() {
  if (!globalThis.__NUVIO_PS5__) return;
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
    if (redirecting || event.button !== 0) return;
    if (event.target?.closest?.('#__evoClose')) return;
    const node = focusedNode();
    if (node?.matches('input, textarea, select') && node.contains(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!node) return; // No stale, hidden or background activation.
    redirecting = true;
    try {
      if (node.matches('input, textarea, select')) {
        // Keep the browser's own text-entry mechanism, input/change handlers
        // and physical keyboard support. No replacement keyboard or prompt.
        node.focus({ preventScroll: true });
        node.click();
      } else {
        enter('keydown', node);
        enter('keyup', node.isConnected ? node : document.body);
      }
    } finally { redirecting = false; }
  };
  let openingOptions = false;
  window.addEventListener('nuvio:options', () => {
    if (openingOptions) return;
    openingOptions = true;
    openContextMenu().catch(error => console.warn('PS5 item actions failed', error))
      .finally(() => { openingOptions = false; });
  });
  window.addEventListener('nuvio:controller-menu', openControllerMenu);

  // The native hook is absent in desktop previews. Do not hammer their server.
  if (!window.__evoHook) return;
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
        }
        previous = next;
      } catch (_) { previous = null; }
    };
    request.onerror = request.ontimeout = () => { previous = null; };
    request.onloadend = () => setTimeout(poll, 150);
    request.send();
  }
  poll();
}
