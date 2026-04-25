/**
 * Polls GET /products/meta then refetches GET /products when aggregate signature changes.
 * Reduces full-list traffic while keeping dashboards aligned with listing edits.
 */
(function (global) {
  'use strict';

  var timer = null;
  var lastSig = null;
  var opts = {};

  function signatureFromMeta(m) {
    if (!m || typeof m !== 'object') return '';
    return String(m.count || 0) + '|' + String(m.latest_updated_at || '');
  }

  function apiBaseNorm(base) {
    return (base || '').replace(/\/$/, '');
  }

  async function fetchMeta(apiBase, status) {
    var u =
      apiBaseNorm(apiBase) +
      '/products/meta?status=' +
      encodeURIComponent(status || 'active');
    var r = await fetch(u);
    if (!r.ok) throw new Error('meta ' + r.status);
    return r.json();
  }

  async function fetchList(apiBase, status) {
    var u =
      apiBaseNorm(apiBase) +
      '/products?status=' +
      encodeURIComponent(status || 'active');
    var r = await fetch(u);
    if (!r.ok) throw new Error('list ' + r.status);
    return r.json();
  }

  async function tick() {
    if (document.visibilityState !== 'visible') return;
    var apiBase = opts.apiBase;
    var status = opts.status || 'active';
    try {
      var meta = await fetchMeta(apiBase, status);
      var sig = signatureFromMeta(meta);
      if (lastSig !== null && sig === lastSig) return;
      lastSig = sig;
      var products = await fetchList(apiBase, status);
      try {
        sessionStorage.setItem('productsCache', JSON.stringify(products));
      } catch (e) {}
      try {
        localStorage.setItem('soko_products_cache_v1', JSON.stringify(products));
        localStorage.setItem('soko_products_cache_v1_ts', String(Date.now()));
      } catch (e2) {}
      if (typeof opts.onRefresh === 'function') {
        await opts.onRefresh(products, meta);
      }
    } catch (e) {
      /* ignore transient network errors */
    }
  }

  global.SokoMarketplaceSync = {
    start: function (apiBase, options) {
      options = options || {};
      opts.apiBase = apiBase;
      opts.status = options.status || 'active';
      opts.onRefresh = options.onRefresh;
      opts.intervalMs = options.intervalMs || 12000;

      if (timer) {
        clearInterval(timer);
        timer = null;
      }

      (async function seed() {
        try {
          var meta = await fetchMeta(opts.apiBase, opts.status);
          lastSig = signatureFromMeta(meta);
        } catch (e) {
          lastSig = null;
        }
        timer = setInterval(tick, opts.intervalMs);
      })();
    },

    stop: function () {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    },

    /** Call after local create/update so the next poll refetches full list */
    invalidate: function () {
      lastSig = null;
    },

    fetchMeta: fetchMeta,
    fetchList: fetchList,
    signatureFromMeta: signatureFromMeta,
  };
})(typeof window !== 'undefined' ? window : this);
