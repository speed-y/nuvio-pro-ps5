/* Native PS5 IME connected to Nuvio's existing Search field, never a prompt. */
import { Router } from './routerState.js';

let pending = false;
let keyboardReturnRead = false;
export async function requestPs5SearchKeyboard(navigationContext = {}) {
  if (navigationContext.isBackNavigation ||
      !globalThis.__NUVIO_PS5__ || !window.__evoHook || pending ||
      Router.getCurrent() !== 'search') return;
  const nativeSession = typeof window.__nuvioPrepareKeyboard === 'function';
  const returning = nativeSession && !keyboardReturnRead &&
    new URLSearchParams(window.location.search).get('nuvioKeyboardReturn') === '1';
  const screen = Router.getCurrentScreen();
  const input = screen?.container?.querySelector('#searchInput');
  if (!input?.isConnected || document.hidden) return;
  pending = true;
  screen.container.querySelector('.ps5-search-keyboard-status')?.remove();
  const current = () => Router.getCurrent() === 'search' &&
    Router.getCurrentScreen() === screen && input.isConnected;
  try {
    if (nativeSession && !returning) {
      // Save Search and the selected profile before recreating the browser.
      Router.persistWebOsResumeRoute('search', { query: input.value });
      window.__nuvioSavePlaybackReturn();
      window.__nuvioPrepareKeyboard(); // Flush the existing console storage bridge.
    }
    if (returning) keyboardReturnRead = true;
    let response = await fetch(returning ? '/evo/text-input' :
      '/evo/text-input?open=' + encodeURIComponent(input.value), { cache: 'no-store' });
    while (response.status === 202) {
      await new Promise(resolve => setTimeout(resolve, 150));
      response = await fetch('/evo/text-input', { cache: 'no-store' });
    }
    if (!current()) return;
    if (response.status === 200) {
      const value = await response.text();
      if (!current()) return;
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      // Use Search's own submit path to focus results, not a stale input node.
      screen.cancelScheduledInputSearch();
      await screen.runSearchFromInput(input, { autoFocusResults: true, rememberToHistory: true });
    } else if (response.status !== 204) {
      // No virtual-keyboard fallback, browser replacement or silent failure.
      throw new Error('Native Search keyboard unavailable');
    }
  } catch (_) {
    if (current()) {
      let status = screen.container.querySelector('.ps5-search-keyboard-status');
      if (!status) {
        status = document.createElement('p');
        status.className = 'ps5-search-keyboard-status';
        status.setAttribute('role', 'status');
        status.style.cssText = 'margin:24px 48px;font-size:24px;color:var(--text-color)';
        input.closest('.search-header').insertAdjacentElement('afterend', status);
      }
      status.textContent = 'The PS5 keyboard could not open. Press Triangle to retry, or Circle to return.';
    }
  } finally {
    pending = false;
  }
}

export function initPs5SearchKeyboard() {
  if (!globalThis.__NUVIO_PS5__) return;
  // Screen mount handles sidebar entry. Mere focus/rerender must not reopen IME.
  // Triangle and X/click on the textbox remain explicit repeatable requests.
  window.addEventListener('click', event => {
    if (event.target?.id === 'searchInput') void requestPs5SearchKeyboard();
  }, true);
}
