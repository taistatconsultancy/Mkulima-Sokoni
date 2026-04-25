"""
Minimal SMTP mailer for transactional emails.

Uses Gmail SMTP (App Password) when configured via env vars.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional, Iterable

import logging

logger = logging.getLogger(__name__)


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def smtp_enabled() -> bool:
    return _truthy(os.getenv("SMTP_ENABLED", "false"))


def _smtp_config():
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    from_name = os.getenv("SMTP_FROM_NAME", "Mkulima Sokoni").strip() or "Mkulima Sokoni"
    from_email = os.getenv("SMTP_FROM_EMAIL", user).strip() or user
    return host, port, user, password, from_name, from_email


def _build_message(to_email: str, subject: str, text: str, html: Optional[str] = None) -> EmailMessage:
    host, port, user, password, from_name, from_email = _smtp_config()
    if not from_email:
        raise ValueError("SMTP_FROM_EMAIL/SMTP_USER must be set")

    msg = EmailMessage()
    msg["To"] = to_email
    msg["From"] = formataddr((from_name, from_email))
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send_email(to_email: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    """
    Send an email (plaintext + optional HTML alternative).
    Returns True if sent, False if skipped/failed.
    """
    if not smtp_enabled():
        return False

    host, port, user, password, _, _ = _smtp_config()
    if not (host and port and user and password):
        logger.warning("SMTP is enabled but config is incomplete (host/port/user/pass).")
        return False

    try:
        msg = _build_message(to_email, subject, text, html=html)
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=12) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


def _app_public_url() -> str:
    url = (os.getenv("APP_PUBLIC_URL") or "").strip()
    return url[:-1] if url.endswith("/") else url


def _landing_url() -> str:
    """
    Landing page for emails (marketing/home). Kept as index.html for static hosting compatibility.
    """
    app = _app_public_url()
    return f"{app}/index.html" if app else ""


def _email_base_html(title: str, preheader: str, body_html: str) -> str:
    """
    Simple, modern HTML email wrapper. Keep inline styles for broad client support.
    """
    brand = os.getenv("SMTP_FROM_NAME", "Mkulima Sokoni").strip() or "Mkulima Sokoni"
    landing = _landing_url()
    support_href = f"{landing}#support" if landing else ""
    support_html = (
        f"or visit the <a href='{support_href}' style='color:#1B4332;font-weight:700;text-decoration:none;'>support page</a>."
        if support_href
        else "or visit the app support section."
    )
    pre = (preheader or "").strip()
    safe_pre = pre.replace("<", "&lt;").replace(">", "&gt;")
    return f"""\
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f6f8fb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{safe_pre}</div>
  <div style="padding:28px 14px;">
    <div style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;">
      <div style="padding:18px 22px;background:linear-gradient(135deg,#1B4332,#40916C);color:#fff;">
        <div style="font-weight:800;font-size:16px;letter-spacing:.2px;">{brand}</div>
      </div>
      <div style="padding:22px;">
        {body_html}
      </div>
      <div style="padding:16px 22px;border-top:1px solid #e5e7eb;background:#f9fafb;color:#6b7280;font-size:12px;line-height:1.5;">
        <div>
          Need help? Reply to this email
          {support_html}
        </div>
      </div>
    </div>
    <div style="max-width:640px;margin:10px auto 0;color:#9ca3af;font-size:12px;text-align:center;">
      &copy; {brand}
    </div>
  </div>
</body>
</html>
"""


def _button_html(label: str, href: str) -> str:
    h = (href or "").strip()
    return f"""\
<a href="{h}" style="display:inline-block;background:#25D366;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:999px;font-weight:700;font-size:14px;">
  {label}
</a>
"""


def _plain_link_html(label: str, href: str) -> str:
    h = (href or "").strip()
    if not h:
        return ""
    return f"""\
<div style="margin-top:12px;color:#6b7280;font-size:13px;line-height:1.6;">
  <span style="font-weight:700;color:#111827;">{label}:</span>
  <a href="{h}" style="color:#1B4332;font-weight:700;text-decoration:none;word-break:break-word;">{h}</a>
</div>
"""


def send_welcome_email(to_email: str, first_name: Optional[str] = None) -> bool:
    name = (first_name or "").strip()
    greet = f"Hi {name}," if name else "Hi,"
    subject = "Welcome to Mkulima Sokoni"
    text = "\n".join(
        [
            greet,
            "",
            "Welcome to Mkulima Sokoni.",
            "Your account has been created successfully.",
            "",
            "If you signed up with email and password, please verify your email address to unlock all features.",
            "",
            "Thanks,",
            "Mkulima Sokoni Team",
        ]
    )
    landing = _landing_url()
    app = _app_public_url()
    action = f"{app}/auth.html" if app else ""
    html_body = f"""\
<h1 style="margin:0 0 10px;font-size:20px;color:#111827;">Welcome{(' ' + name) if name else ''}.</h1>
<p style="margin:0 0 14px;color:#374151;line-height:1.6;">Your account has been created successfully.</p>
<p style="margin:0 0 16px;color:#374151;line-height:1.6;">Verify your email to unlock all features, then choose your user type inside the app.</p>
{(_button_html('Visit Mkulima Sokoni', landing) if landing else '')}
{(_plain_link_html('Sign in / verify email', action) if action else '')}
{(_plain_link_html('Landing page', landing) if landing else '')}
<div style="margin-top:18px;color:#6b7280;font-size:13px;">Thanks,<br /><strong>Mkulima Sokoni Team</strong></div>
"""
    html = _email_base_html("Welcome", "Welcome to the app.", html_body)
    return send_email(to_email, subject, text, html=html)


def send_new_message_email(
    to_email: str,
    from_label: str,
    preview_text: str,
    deep_link: Optional[str] = None,
) -> bool:
    subject = f"New message from {from_label}"
    preview = (preview_text or "").strip()
    if len(preview) > 220:
        preview = preview[:217] + "..."
    lines = [
        "You have a new message in Mkulima Sokoni.",
        "",
        f"From: {from_label}",
        "",
        f"Message preview: {preview or '—'}",
    ]
    if deep_link:
        lines += ["", f"Open: {deep_link}"]
    lines += ["", "Mkulima Sokoni Team"]
    landing = _landing_url()
    app = _app_public_url()
    action = deep_link or (f"{app}/buyer.html#messages" if app else "")
    html_body = f"""\
<h1 style="margin:0 0 10px;font-size:20px;color:#111827;">New message</h1>
<p style="margin:0 0 14px;color:#374151;line-height:1.6;">You received a new message from <strong>{from_label}</strong>.</p>
<div style="margin:0 0 16px;padding:12px 14px;border:1px solid #e5e7eb;border-radius:12px;background:#f9fafb;color:#111827;line-height:1.6;">
  {preview.replace('<','&lt;').replace('>','&gt;') or '—'}
</div>
{(_button_html('Visit Mkulima Sokoni', landing) if landing else '')}
{(_plain_link_html('Open messages', action) if action else '')}
{(_plain_link_html('Landing page', landing) if landing else '')}
<div style="margin-top:18px;color:#6b7280;font-size:13px;">Thanks,<br /><strong>Mkulima Sokoni Team</strong></div>
"""
    html = _email_base_html("New message", "You have a new message.", html_body)
    return send_email(to_email, subject, "\n".join(lines), html=html)


def _split_emails(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    parts = []
    for p in str(raw).replace(";", ",").split(","):
        e = p.strip()
        if e:
            parts.append(e)
    # de-dupe preserving order
    seen = set()
    out = []
    for e in parts:
        k = e.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def resolve_support_team_emails(admin_firebase_uids: Optional[str] = None) -> list[str]:
    """
    Returns a deduped list of support-team email recipients.

    Sources (combined):
    - SUPPORT_TEAM_EMAILS env var (comma-separated) as fallback / explicit list
    - ADMIN_FIREBASE_UIDS resolved to email addresses via Firebase Admin SDK (if available)
    """
    recipients: list[str] = []

    # Explicit fallback list (works even if Firebase Admin SDK isn't configured)
    recipients.extend(_split_emails(os.getenv("SUPPORT_TEAM_EMAILS", "")))

    raw_uids = (admin_firebase_uids if admin_firebase_uids is not None else os.getenv("ADMIN_FIREBASE_UIDS", "")).strip()
    uids = [u.strip() for u in raw_uids.split(",") if u.strip()]
    if uids:
        try:
            # Import lazily to avoid hard dependency at import time
            from auth.firebase_auth import get_firebase_user
        except Exception as e:
            logger.warning("Could not import Firebase user lookup for support recipients: %s", e)
            get_firebase_user = None

        if get_firebase_user:
            for uid in uids:
                try:
                    fu = get_firebase_user(uid)
                    email = (fu or {}).get("email")
                    if email:
                        recipients.append(str(email).strip())
                except Exception as e:
                    logger.warning("Support recipient lookup failed for uid=%s: %s", uid, e)

    # de-dupe preserving order
    seen = set()
    out = []
    for e in recipients:
        e = (e or "").strip()
        if not e:
            continue
        k = e.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def send_support_verification_request_email(
    to_emails: Iterable[str],
    user_summary: dict,
    profile_kind: str,
) -> bool:
    """
    Notify support team that a user submitted a profile for verification review.
    Best-effort: returns False if skipped/failed.
    """
    to_list = [str(e).strip() for e in (to_emails or []) if str(e or "").strip()]
    if not to_list:
        return False

    name = " ".join(
        [str(user_summary.get("first_name") or "").strip(), str(user_summary.get("last_name") or "").strip()]
    ).strip()
    email = (user_summary.get("email") or "").strip()
    phone = (user_summary.get("phone_number") or "").strip()
    roles = user_summary.get("roles") or user_summary.get("role") or ""
    roles_text = ", ".join(roles) if isinstance(roles, (list, tuple, set)) else str(roles)

    subject = f"Verification review needed ({profile_kind})"
    text = "\n".join(
        [
            "A user has submitted their profile for verification review.",
            "",
            f"Profile kind: {profile_kind}",
            f"Name: {name or '—'}",
            f"Email: {email or '—'}",
            f"Phone: {phone or '—'}",
            f"Roles: {roles_text or '—'}",
            "",
            "Please open the admin dashboard and verify the user.",
            "",
            "Mkulima Sokoni System",
        ]
    )
    landing = _landing_url()
    app = _app_public_url()
    action = f"{app}/admin-support.html" if app else ""
    safe_name = (name or "—").replace("<", "&lt;").replace(">", "&gt;")
    safe_email = (email or "—").replace("<", "&lt;").replace(">", "&gt;")
    safe_phone = (phone or "—").replace("<", "&lt;").replace(">", "&gt;")
    safe_roles = (roles_text or "—").replace("<", "&lt;").replace(">", "&gt;")
    html_body = f"""\
<h1 style="margin:0 0 10px;font-size:20px;color:#111827;">Verification review needed</h1>
<p style="margin:0 0 14px;color:#374151;line-height:1.6;">A user has submitted their profile for verification review.</p>
<div style="margin:0 0 16px;padding:12px 14px;border:1px solid #e5e7eb;border-radius:12px;background:#f9fafb;color:#111827;line-height:1.7;">
  <div><strong>Profile kind:</strong> {profile_kind}</div>
  <div><strong>Name:</strong> {safe_name}</div>
  <div><strong>Email:</strong> {safe_email}</div>
  <div><strong>Phone:</strong> {safe_phone}</div>
  <div><strong>Roles:</strong> {safe_roles}</div>
</div>
{(_button_html('Visit Mkulima Sokoni', landing) if landing else '')}
{(_plain_link_html('Open admin dashboard', action) if action else '')}
{(_plain_link_html('Landing page', landing) if landing else '')}
<div style="margin-top:18px;color:#6b7280;font-size:13px;"><strong>Mkulima Sokoni System</strong></div>
"""
    html = _email_base_html("Verification review needed", "A user submitted verification for review.", html_body)

    any_sent = False
    for to_email in to_list:
        any_sent = send_email(to_email, subject, text, html=html) or any_sent
    return any_sent


def send_account_verified_email(to_email: str, first_name: Optional[str] = None) -> bool:
    name = (first_name or "").strip()
    greet = f"Hi {name}," if name else "Hi,"
    subject = "Your Mkulima Sokoni account is verified"
    text = "\n".join(
        [
            greet,
            "",
            "Good news — your account has been verified by our support team.",
            "You can now continue using the app.",
            "",
            "Thanks,",
            "Mkulima Sokoni Team",
        ]
    )
    landing = _landing_url()
    app = _app_public_url()
    action = f"{app}/auth.html" if app else ""
    html_body = f"""\
<h1 style="margin:0 0 10px;font-size:20px;color:#111827;">Your account is verified</h1>
<p style="margin:0 0 14px;color:#374151;line-height:1.6;">Good news — your account has been verified by our support team. You can now continue using the app.</p>
{(_button_html('Visit Mkulima Sokoni', landing) if landing else '')}
{(_plain_link_html('Open the app', action) if action else '')}
{(_plain_link_html('Landing page', landing) if landing else '')}
<div style="margin-top:18px;color:#6b7280;font-size:13px;">Thanks,<br /><strong>Mkulima Sokoni Team</strong></div>
"""
    html = _email_base_html("Account verified", "Your account is verified.", html_body)
    return send_email(to_email, subject, text, html=html)

