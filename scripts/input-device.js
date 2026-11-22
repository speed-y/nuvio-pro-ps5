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

export function inputDevice() {
  return live.device;
}

export function installInputDevice() {
  if (typeof window === 'undefined') return;
  window.__NUVIO_INPUT_DEVICE__ = live.device;
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

export function remoteGlyphName(controllerName) {
  return REMOTE_FOR[controllerName] || 'ok';
}

function key(label, fill, ink, wide) {
  const width = wide ? 78 : 46;
  return '<svg viewBox="0 0 ' + width + ' 32">' +
    '<rect x="1.5" y="3" width="' + (width - 3) + '" height="26" rx="8" fill="' + fill +
    '" stroke="#6c7196" stroke-width="1.5"/>' +
    '<text x="' + (width / 2) + '" y="21" text-anchor="middle" font-size="11" font-weight="700" fill="' +
    ink + '">' + label + '</text></svg>';
}

/** Generic remote key. Colour keys are rounded red, green, yellow and blue. */
export function remoteGlyphSvg(name) {
  if (name === 'red') return key('', '#d64545', '#fff', false).replace('></text>', '></text>');
  if (name === 'green') return key('', '#2f9e4f', '#fff', false);
  if (name === 'yellow') return key('', '#e2b11a', '#1a1a1a', false);
  if (name === 'blue') return key('', '#3b6fe2', '#fff', false);
  if (name === 'back') return key('Back', '#11131f', '#f4f4f8', true);
  if (name === 'menu') return key('Menu', '#11131f', '#f4f4f8', true);
  if (name === 'info') return key('i', '#11131f', '#f4f4f8', false);
  if (name === 'play') return key('▶', '#11131f', '#f4f4f8', false);
  if (name === 'pause') return key('❚❚', '#11131f', '#f4f4f8', false);
  if (name === 'ch-up') return key('CH+', '#11131f', '#f4f4f8', true);
  if (name === 'ch-down') return key('CH−', '#11131f', '#f4f4f8', true);
  if (name === 'arrows') return key('↕', '#11131f', '#f4f4f8', false);
  if (/^[0-9]$/.test(name)) return key(name, '#11131f', '#f4f4f8', false);
  return key('OK', '#11131f', '#f4f4f8', false);
}
