/* Loaded before the app. The frontend adapter owns activation and focus.
 * Do not infer physical buttons from undocumented browser keycodes. */
(function () {
  'use strict';
  window.__NUVIO_PS5__ = true;
  // Moving/scrolling cards beneath a pointer must never trigger hover focus steals.
  ['mouseover', 'mouseenter', 'mousemove', 'mouseout', 'mouseleave',
   'pointerover', 'pointerenter', 'pointermove', 'pointerout', 'pointerleave'].forEach(function (type) {
    document.addEventListener(type, function (event) {
      event.preventDefault?.();
      event.stopImmediatePropagation();
    }, true);
  });
  ['pointerdown', 'mousedown'].forEach(function (type) {
    document.addEventListener(type, function (event) {
      if (window.__nuvioPs5PointerDown) window.__nuvioPs5PointerDown(event);
    }, true);
  });
  document.addEventListener('click', function (event) {
    if (window.__nuvioPs5Activate) window.__nuvioPs5Activate(event);
  }, true);
  document.addEventListener('keydown', function (event) {
    if (event.repeat) return;
    var key = event.key;
    var remoteKey = key === 'ArrowUp' || key === 'ArrowDown' || key === 'ArrowLeft' ||
      key === 'ArrowRight' || key === 'Enter' || key === 'Escape' || key === 'Backspace' ||
      (typeof key === 'string' && (key.indexOf('Media') === 0 || key.indexOf('Digit') === 0 ||
        key.indexOf('Audio') === 0));
    if (remoteKey && window.__nuvioNoteInput) window.__nuvioNoteInput('remote', performance.now());
  }, true);
  var padButtons = [];
  function pollGamepads() {
    var pads = navigator.getGamepads ? navigator.getGamepads() : null;
    if (pads && window.__nuvioNoteInput) {
      for (var i = 0; i < pads.length; i++) {
        var pad = pads[i];
        if (!pad || !pad.buttons) continue;
        var mask = 0;
        for (var b = 0; b < pad.buttons.length && b < 24; b++) {
          if (pad.buttons[b] && pad.buttons[b].pressed) mask |= 1 << b;
        }
        var previous = padButtons[i] || 0;
        if ((mask & ~previous) !== 0) window.__nuvioNoteInput('controller', performance.now());
        padButtons[i] = mask;
      }
    }
    if (typeof requestAnimationFrame === 'function') requestAnimationFrame(pollGamepads);
  }
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(pollGamepads);
}());
