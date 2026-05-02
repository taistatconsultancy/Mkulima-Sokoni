#!/usr/bin/env python3
"""Inject PWA manifest/theme/apple-touch tags + register the SW on every public HTML page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

PAGES = [
    "index.html", "auth.html", "market.html", "buyer.html", "farmer.html",
    "agro-dealer.html", "product-detail.html", "seller-profile.html",
    "about.html", "faq.html", "terms.html", "privacy.html",
    "how-it-works.html", "phone-sharing.html", "profile-farmer.html",
    "profile-buyer.html", "admin-support.html",
]

HEAD_TAGS = (
    '<link rel="manifest" href="/manifest.webmanifest" />\n'
    '  <meta name="theme-color" content="#1B4332" />\n'
    '  <meta name="apple-mobile-web-app-capable" content="yes" />\n'
    '  <meta name="apple-mobile-web-app-title" content="Mkulima Sokoni" />\n'
    '  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />\n'
    '  <meta name="mobile-web-app-capable" content="yes" />\n'
    '  <link rel="apple-touch-icon" href="/assets/img/logo.jpeg" />\n'
)

SW_SCRIPT = '<script src="/js/pwa-install.js"></script>'

ANCHOR = '<script defer src="/_vercel/speed-insights/script.js"></script>'


def patch(text: str) -> str:
    if 'manifest.webmanifest' not in text and ANCHOR in text:
        text = text.replace(ANCHOR, HEAD_TAGS + '  ' + ANCHOR, 1)
    if 'pwa-install.js' not in text:
        if '</body>' in text:
            text = text.replace('</body>', SW_SCRIPT + '\n</body>', 1)
    return text


def main() -> None:
    changed = 0
    for name in PAGES:
        p = FRONTEND / name
        if not p.is_file():
            continue
        raw = p.read_text(encoding="utf-8")
        new = patch(raw)
        if new != raw:
            p.write_text(new, encoding="utf-8")
            print("patched", name)
            changed += 1
    print(f"done — {changed} files changed")


if __name__ == "__main__":
    main()
