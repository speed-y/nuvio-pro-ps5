/** Last device that produced a real button press. Controller is the default. */

const DEBOUNCE_MS = 200;

export function createInputDevice(now = 0) {
  return { device: 'controller', until: now };
}

/** Switch on the first press from the other device. Ignore the opposite source briefly. */
export function noteInputDevice(state, source, now) {
  if (!state || (source !== 'controller' && source !== 'remote')) return state;
  if (source === state.device || now < state.until) return state;
  state.device = source;
  state.until = now + DEBOUNCE_MS;
  return state;
}

const live = createInputDevice();
let menuSeen = false;

export function inputDevice() {
  return live.device;
}

export function remoteMenuSeen() {
  return menuSeen;
}

/** Remember a real Menu or context-menu key for the rest of this page. */
export function noteRemoteMenu() {
  if (menuSeen) return;
  menuSeen = true;
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent('nuvio-remote-menu'));
  }
}

export function installInputDevice() {
  if (typeof window === 'undefined') return;
  window.__NUVIO_INPUT_DEVICE__ = live.device;
  window.__nuvioNoteRemoteMenu = () => noteRemoteMenu();
  window.__nuvioNoteInput = (source, now) => {
    const before = live.device;
    noteInputDevice(live, source, now);
    window.__NUVIO_INPUT_DEVICE__ = live.device;
    if (before !== live.device && typeof window.dispatchEvent === 'function') {
      window.dispatchEvent(new CustomEvent('nuvio-input-device', { detail: live.device }));
    }
  };
}

const REMOTE_FOR = {
  Cross: 'ok',
  Circle: 'back',
  Options: 'menu',
  Triangle: 'yellow',
  Square: 'info',
  Dpad: 'arrows',
  L1: 'ch-down',
  R1: 'ch-up',
  L2: 'green',
  R2: 'red',
  TouchPad: 'menu',
  L3: 'info',
  R3: 'blue'
};

export function remoteGlyphFor(controllerName, menuSeenNow) {
  if (!menuSeenNow && (controllerName === 'Options' || controllerName === 'TouchPad')) return 'hold-ok';
  return REMOTE_FOR[controllerName] || 'ok';
}

export function remoteGlyphName(controllerName) {
  return remoteGlyphFor(controllerName, menuSeen);
}

const PAPER = '#141624';
const LIGHT = '#f4f4f8';
const EDGE = '#f2f2f8';

function frame(fill, inner) {
  return '<svg viewBox="0 0 64 64"><rect x="3" y="3" width="58" height="58" rx="16" fill="' + fill +
    '" stroke="' + EDGE + '" stroke-width="4"/>' + inner + '</svg>';
}

function word(text, size) {
  return frame(PAPER, '<text x="32" y="34" text-anchor="middle" dominant-baseline="middle" ' +
    'font-family="sans-serif" font-size="' + size + '" font-weight="800" fill="' + LIGHT + '">' +
    text + '</text>');
}

/** Generic remote key. Symbols are shapes. Colour keys are rounded red, green, yellow and blue. */
export function remoteGlyphSvg(name) {
  if (name === 'red') return frame('#d64545', '');
  if (name === 'green') return frame('#2f9e4f', '');
  if (name === 'yellow') return frame('#e2b11a', '');
  if (name === 'blue') return frame('#3b6fe2', '');
  if (name === 'back') {
    return frame(PAPER, '<polygon points="12,28 28,16 28,23 50,23 50,46 38,46 38,33 28,33 28,40" fill="' + LIGHT + '"/>');
  }
  if (name === 'hold-ok') {
    return frame(PAPER,
      '<path d="M32 15 a17 17 0 1 1 -14 24" fill="none" stroke="' + LIGHT +
      '" stroke-width="4" stroke-linecap="round"/>' +
      '<text x="32" y="37" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="800" fill="' +
      LIGHT + '">OK</text>');
  }
  if (name === 'menu') {
    return frame(PAPER,
      '<rect x="16" y="17" width="32" height="6" rx="3" fill="' + LIGHT + '"/>' +
      '<rect x="16" y="29" width="32" height="6" rx="3" fill="' + LIGHT + '"/>' +
      '<rect x="16" y="41" width="32" height="6" rx="3" fill="' + LIGHT + '"/>');
  }
  if (name === 'info') {
    return frame(PAPER,
      '<circle cx="32" cy="32" r="16" fill="none" stroke="' + LIGHT + '" stroke-width="4"/>' +
      '<circle cx="32" cy="23.8" r="2.8" fill="' + LIGHT + '"/>' +
      '<rect x="29.4" y="29" width="5.2" height="14" rx="2" fill="' + LIGHT + '"/>');
  }
  if (name === 'play') return frame(PAPER, '<polygon points="23,16 23,48 47,32" fill="' + LIGHT + '"/>');
  if (name === 'pause') {
    return frame(PAPER,
      '<rect x="20" y="16" width="8" height="32" rx="2" fill="' + LIGHT + '"/>' +
      '<rect x="36" y="16" width="8" height="32" rx="2" fill="' + LIGHT + '"/>');
  }
  if (name === 'arrows') {
    return frame(PAPER,
      '<rect x="27" y="12" width="10" height="40" rx="3" fill="' + LIGHT + '"/>' +
      '<rect x="12" y="27" width="40" height="10" rx="3" fill="' + LIGHT + '"/>');
  }
  if (name === 'ch-up') return word('CH+', 16);
  if (name === 'ch-down') return word('CH-', 16);
  if (/^[0-9]$/.test(name)) return word(name, 26);
  return word('OK', 20);
}
