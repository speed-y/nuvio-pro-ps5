/* Loaded before the app. The frontend adapter owns activation and focus.
 * Do not infer physical buttons from undocumented browser keycodes. */
(function () {
  'use strict';
  window.__NUVIO_PS5__ = true;
  ['pointerdown', 'mousedown'].forEach(function (type) {
    document.addEventListener(type, function (event) {
      if (window.__nuvioPs5PointerDown) window.__nuvioPs5PointerDown(event);
    }, true);
  });
  document.addEventListener('click', function (event) {
    if (window.__nuvioPs5Activate) window.__nuvioPs5Activate(event);
  }, true);
}());
