/* Loaded before the app. The frontend adapter owns activation and focus.
 * Do not infer physical buttons from undocumented browser keycodes. */
(function () {
  'use strict';
  window.__NUVIO_PS5__ = true;
  // Scrolling moves cards beneath the stationary browser pointer. CSS hiding
  // does not stop hover handlers from stealing D-pad focus on those cards.
  ['mouseover', 'mouseenter', 'mousemove', 'pointerover', 'pointerenter', 'pointermove'].forEach(function (type) {
    document.addEventListener(type, function (event) {
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
}());
