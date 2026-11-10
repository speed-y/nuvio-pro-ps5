/* Observation only, not an HDMI-CEC driver or a remote-to-pad mapping.
 * Nuvio already handles browser arrow/Enter/Back events. Whether the PS5
 * delivers TV remote presses to this browser requires owner observation.
 * Call explicitly for an approved diagnostic candidate, with the existing
 * loopback logger. Importing this module starts no listeners or requests. */
let started = false;

export function startPs5TvRemoteDiagnostics(report) {
  const noop = () => {};
  if (!globalThis.__NUVIO_PS5__ || started || typeof report !== 'function' || document.hidden) return noop;
  started = true; // One bounded observation per document, never automatic rearming.
  let stopped = false;
  let count = 0;
  let timer;
  const types = ['keydown', 'keyup', 'click'];
  // Numeric classifications of existing browser contracts, not physical buttons.
  const names = ['ArrowUp', 'ArrowRight', 'ArrowDown', 'ArrowLeft', 'Enter',
    'Escape', 'Backspace', 'F1', 'F2', 'F3'];
  function number(value) {
    return Number.isInteger(value) && value >= 0 && value <= 65535 ? value : 0;
  }
  function editable(node) {
    return Boolean(node?.isContentEditable || node?.closest?.(
      'input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"]'));
  }
  function stop() {
    if (stopped) return;
    stopped = true;
    clearTimeout(timer);
    types.forEach(type => window.removeEventListener(type, observe, true));
    document.removeEventListener('visibilitychange', visibility, true);
    window.removeEventListener('pagehide', stop, true);
  }
  function emit(type, event = {}) {
    if (stopped) return;
    const message = 'ps5 remote seq=' + count + ' type=' + type +
      ' key=' + (names.indexOf(event.key) + 1) +
      ' code=' + number(event.keyCode) + ' which=' + number(event.which) +
      ' repeat=' + Number(event.repeat === true) +
      ' button=' + number(event.button) + ' detail=' + number(event.detail);
    count++;
    try { report(message); } catch (_) { stop(); }
    if (count >= 32) stop(); // Includes the ready record, at most 31 input records.
  }
  function observe(event) {
    if (stopped || document.hidden || event.isTrusted !== true ||
        event.isComposing || event.keyCode === 229 ||
        event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
        editable(event.target) || editable(document.activeElement)) return;
    // Do not encode typing as numbers. Unknown legacy-only printable codes
    // are also omitted. This may omit a remote event; it never guesses its role.
    if (event.type !== 'click' &&
        (typeof event.key === 'string' && event.key.length === 1 ||
         !names.includes(event.key) && [event.keyCode, event.which].some(code =>
           Number.isInteger(code) && code >= 32 && code <= 126))) return;
    emit(types.indexOf(event.type) + 1, event);
  }
  function visibility() { if (document.hidden) stop(); }
  types.forEach(type => window.addEventListener(type, observe, true));
  document.addEventListener('visibilitychange', visibility, true);
  window.addEventListener('pagehide', stop, true);
  timer = setTimeout(stop, 60000);
  emit(0); // Ready marker distinguishes no delivered events from no observer.
  return stop;
}
