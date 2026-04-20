/**
 * Notify open marketplace / home pages to reload the featured ticker after admin changes.
 * Uses BroadcastChannel + localStorage so other tabs update immediately.
 */
(function (global) {
  var CH = 'soko-featured-ticker-v1';

  global.notifyFeaturedTickerChanged = function () {
    try {
      localStorage.setItem('soko_featured_rev', String(Date.now()));
    } catch (e) {}
    try {
      var bc = new BroadcastChannel(CH);
      bc.postMessage({ type: 'featured' });
      bc.close();
    } catch (e) {}
  };

  /**
   * @param {function} fn — called when featured flags may have changed elsewhere
   * @returns {function} unsubscribe
   */
  global.onFeaturedTickerChanged = function (fn) {
    if (typeof fn !== 'function') return function () {};
    var onStorage = function (e) {
      if (e.key === 'soko_featured_rev') fn();
    };
    window.addEventListener('storage', onStorage);
    var bc = null;
    try {
      bc = new BroadcastChannel(CH);
      bc.onmessage = function () {
        fn();
      };
    } catch (e) {}
    return function () {
      window.removeEventListener('storage', onStorage);
      try {
        if (bc) bc.close();
      } catch (e2) {}
    };
  };
})(window);
