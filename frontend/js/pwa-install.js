/* Mkulima Sokoni — PWA registration + install prompt helper.
 * Adds:
 *   - service worker registration (root scope)
 *   - window.MkInstall.canInstall() / install() / shareUrl()
 *   - "appinstalled" tracking via localStorage flag
 *   - dispatches `mk:install:available` and `mk:install:done` events
 */
(function () {
  const SW_PATH = '/sw.js';
  const INSTALL_FLAG = 'mk_pwa_installed';
  let deferredPrompt = null;

  function isStandalone() {
    return (
      window.matchMedia &&
      (window.matchMedia('(display-mode: standalone)').matches ||
        window.matchMedia('(display-mode: minimal-ui)').matches)
    ) || window.navigator.standalone === true;
  }

  function isIOS() {
    const ua = navigator.userAgent || '';
    return /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
  }

  function registerSW() {
    if (!('serviceWorker' in navigator)) return;
    if (location.protocol !== 'https:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
      return;
    }
    window.addEventListener('load', function () {
      navigator.serviceWorker
        .register(SW_PATH, { scope: '/' })
        .then(function (reg) {
          if (reg && reg.update) {
            try { reg.update(); } catch (_) {}
          }
        })
        .catch(function () { /* ignore */ });
    });
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    window.dispatchEvent(new CustomEvent('mk:install:available'));
  });

  window.addEventListener('appinstalled', function () {
    try { localStorage.setItem(INSTALL_FLAG, '1'); } catch (_) {}
    deferredPrompt = null;
    window.dispatchEvent(new CustomEvent('mk:install:done'));
  });

  const MkInstall = {
    canInstall: function () { return !!deferredPrompt; },
    isInstalled: function () {
      try { if (localStorage.getItem(INSTALL_FLAG) === '1') return true; } catch (_) {}
      return isStandalone();
    },
    isStandalone: isStandalone,
    isIOS: isIOS,
    install: async function () {
      if (!deferredPrompt) return { outcome: 'unavailable' };
      try {
        deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice;
        deferredPrompt = null;
        return choice || { outcome: 'dismissed' };
      } catch (_) {
        return { outcome: 'dismissed' };
      }
    },
    shareUrl: async function () {
      const url = (window.location.origin || 'https://www.mkulimasokoni.com') + '/install';
      const data = {
        title: 'Mkulima Sokoni',
        text: 'Get Mkulima Sokoni — fresh farm produce direct from Kenyan farmers.',
        url: url,
      };
      if (navigator.share) {
        try { await navigator.share(data); return { ok: true }; } catch (_) { return { ok: false }; }
      }
      try {
        await navigator.clipboard.writeText(url);
        return { ok: true, copied: true };
      } catch (_) {
        return { ok: false };
      }
    },
  };

  window.MkInstall = MkInstall;
  registerSW();
})();
