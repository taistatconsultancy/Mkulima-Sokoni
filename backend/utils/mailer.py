"""
Minimal SMTP mailer for transactional emails.

Uses Gmail SMTP (App Password) when configured via env vars.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
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
    from_name = os.getenv("SMTP_FROM_NAME", "Soko Safi").strip() or "Soko Safi"
    from_email = os.getenv("SMTP_FROM_EMAIL", user).strip() or user
    return host, port, user, password, from_name, from_email


def _build_message(to_email: str, subject: str, text: str) -> EmailMessage:
    host, port, user, password, from_name, from_email = _smtp_config()
    if not from_email:
        raise ValueError("SMTP_FROM_EMAIL/SMTP_USER must be set")

    msg = EmailMessage()
    msg["To"] = to_email
    msg["From"] = f"{from_name} <{from_email}>"
    msg["Subject"] = subject
    msg.set_content(text)
    return msg


def send_email(to_email: str, subject: str, text: str) -> bool:
    """
    Send a plaintext email. Returns True if sent, False if skipped/failed.
    """
    if not smtp_enabled():
        return False

    host, port, user, password, _, _ = _smtp_config()
    if not (host and port and user and password):
        logger.warning("SMTP is enabled but config is incomplete (host/port/user/pass).")
        return False

    try:
        msg = _build_message(to_email, subject, text)
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


def send_welcome_email(to_email: str, first_name: Optional[str] = None) -> bool:
    name = (first_name or "").strip()
    greet = f"Hi {name}," if name else "Hi,"
    subject = "Welcome to Soko Safi"
    text = "\n".join(
        [
            greet,
            "",
            "Welcome to Soko Safi.",
            "Your account has been created successfully.",
            "",
            "If you signed up with email and password, please verify your email address to unlock all features.",
            "",
            "Thanks,",
            "Soko Safi Team",
        ]
    )
    return send_email(to_email, subject, text)


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
        "You have a new message in Soko Safi.",
        "",
        f"From: {from_label}",
        "",
        f"Message preview: {preview or '—'}",
    ]
    if deep_link:
        lines += ["", f"Open: {deep_link}"]
    lines += ["", "Soko Safi Team"]
    return send_email(to_email, subject, "\n".join(lines))


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
            "Soko Safi System",
        ]
    )

    any_sent = False
    for to_email in to_list:
        any_sent = send_email(to_email, subject, text) or any_sent
    return any_sent


def send_account_verified_email(to_email: str, first_name: Optional[str] = None) -> bool:
    name = (first_name or "").strip()
    greet = f"Hi {name}," if name else "Hi,"
    subject = "Your Soko Safi account is verified"
    text = "\n".join(
        [
            greet,
            "",
            "Good news — your account has been verified by our support team.",
            "You can now continue using the app.",
            "",
            "Thanks,",
            "Soko Safi Team",
        ]
    )
    return send_email(to_email, subject, text)

