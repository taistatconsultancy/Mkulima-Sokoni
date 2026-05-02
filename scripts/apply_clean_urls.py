#!/usr/bin/env python3
"""Replace legacy *.html links in frontend/ with extensionless paths (see backend/app.py)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"


def patch(text: str) -> str:
    text = text.replace("farmer.html?action=list-produce", "/farmer?action=list-produce")
    text = text.replace("agro-dealer.html?action=list-produce", "/agro-dealer?action=list-produce")
    text = text.replace("product-detail.html?id=", "/product/")
    text = text.replace("seller-profile.html?uid=", "/seller/")
    text = text.replace("index.html#", "/#")
    pairs = [
        ("profile-farmer.html", "/profile-farmer"),
        ("profile-buyer.html", "/profile-buyer"),
        ("agro-dealer.html", "/agro-dealer"),
        ("how-it-works.html", "/how-it-works"),
        ("phone-sharing.html", "/phone-sharing"),
        ("admin-support.html", "/admin-support"),
        ("seller-profile.html", "/seller-profile"),
        ("test-image-upload.html", "/test-image-upload"),
        ("market.html", "/market"),
        ("farmer.html", "/farmer"),
        ("buyer.html", "/buyer"),
        ("privacy.html", "/privacy"),
        ("about.html", "/about"),
        ("terms.html", "/terms"),
        ("auth.html", "/auth"),
        ("faq.html", "/faq"),
        ("index.html", "/"),
    ]
    for old, new in pairs:
        text = text.replace(old, new)
    return text


def main() -> None:
    for ext in ("*.html", "*.js", "*.mjs"):
        for p in FRONTEND.rglob(ext):
            raw = p.read_text(encoding="utf-8")
            new = patch(raw)
            if new != raw:
                p.write_text(new, encoding="utf-8")
                print("patched", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
