"""
Twilio SMS: verification status and support ticket alerts to users.
SMS failures are logged only; they must not affect API success or DB commits.
"""
import json
import logging
import re

from config import Config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not Config.TWILIO_ACCOUNT_SID or not Config.TWILIO_AUTH_TOKEN:
        return None
    try:
        from twilio.rest import Client

        _client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        return _client
    except Exception as e:
        logger.warning('Twilio client init failed: %s', e)
        return None


def normalize_phone_e164(raw, default_region='KE'):
    """Best-effort E.164; Kenya-oriented (0… / 254… / digits)."""
    if raw is None:
        return None
    s = re.sub(r'[\s\-]', '', str(raw).strip())
    if not s:
        return None
    if s.startswith('+'):
        digits = s[1:]
        if digits.isdigit() and 10 <= len(digits) <= 15:
            return '+' + digits
        return None
    if s.startswith('0') and len(s) >= 9:
        return '+254' + s[1:]
    if s.startswith('254') and s.isdigit():
        return '+' + s
    if s.isdigit() and len(s) >= 9:
        if default_region == 'KE':
            return '+254' + s.lstrip('0')
        return '+' + s
    return None


def _send_sms(to_e164, body=None, content_sid=None, content_variables=None):
    client = _get_client()
    if not client:
        logger.debug('Twilio: client unavailable, skip send')
        return False
    kwargs = {'to': to_e164}
    if Config.TWILIO_MESSAGING_SERVICE_SID:
        kwargs['messaging_service_sid'] = Config.TWILIO_MESSAGING_SERVICE_SID
    elif Config.TWILIO_FROM_NUMBER:
        kwargs['from_'] = Config.TWILIO_FROM_NUMBER
    else:
        logger.warning(
            'Twilio: set TWILIO_MESSAGING_SERVICE_SID or TWILIO_FROM_NUMBER'
        )
        return False
    if content_sid:
        kwargs['content_sid'] = content_sid
        if content_variables is not None:
            kwargs['content_variables'] = (
                json.dumps(content_variables)
                if isinstance(content_variables, dict)
                else content_variables
            )
    elif body:
        kwargs['body'] = body
    else:
        return False
    try:
        client.messages.create(**kwargs)
        return True
    except Exception as e:
        logger.warning('Twilio send failed: %s', e)
        return False


def _display_name(user_row):
    fn = (user_row.get('first_name') or '').strip()
    ln = (user_row.get('last_name') or '').strip()
    name = f'{fn} {ln}'.strip()
    return name or (user_row.get('email') or 'User')


def _format_body(template, mapping):
    try:
        return template.format(**mapping)
    except (KeyError, ValueError):
        return template


def send_verification_status_sms(user_row, new_status, reason=None):
    if not Config.TWILIO_VERIFICATION_SMS_ENABLED:
        return
    if not user_row:
        return
    to = normalize_phone_e164(user_row.get('phone_number'))
    if not to:
        logger.info('Twilio verification SMS skipped: no valid phone for user')
        return
    name = _display_name(user_row)
    role = (user_row.get('role') or 'member').strip()
    status = (new_status or '').lower()

    if status == 'verified':
        csid = (Config.TWILIO_VERIFY_APPROVED_CONTENT_SID or '').strip()
        if csid:
            _send_sms(
                to,
                content_sid=csid,
                content_variables={'name': name, 'role': role},
            )
        else:
            body = _format_body(
                Config.TWILIO_VERIFY_APPROVED_BODY,
                {'name': name, 'role': role, 'reason': ''},
            )
            if len(body) > 1500:
                body = body[:1497] + '...'
            _send_sms(to, body=body)
    elif status == 'rejected':
        csid = (Config.TWILIO_VERIFY_REJECTED_CONTENT_SID or '').strip()
        reason_text = (reason or 'Please review requirements in the app.').strip()[
            :280
        ]
        if csid:
            _send_sms(
                to,
                content_sid=csid,
                content_variables={
                    'name': name,
                    'role': role,
                    'reason': reason_text,
                },
            )
        else:
            body = _format_body(
                Config.TWILIO_VERIFY_REJECTED_BODY,
                {
                    'name': name,
                    'role': role,
                    'reason': reason_text,
                },
            )
            if len(body) > 1500:
                body = body[:1497] + '...'
            _send_sms(to, body=body)


def _support_app_link(ticket):
    base = (Config.SUPPORT_TICKET_DEEP_LINK_BASE or Config.PUBLIC_APP_URL or '').rstrip(
        '/'
    )
    if not base or not ticket:
        return ''
    role = (ticket.get('user_role') or '').strip().lower()
    page = 'buyer'
    if role == 'farmer':
        page = 'farmer'
    elif role in ('agro-dealer', 'agrodealer'):
        page = 'agro-dealer'
    tid = ticket.get('id')
    if tid:
        return f'{base}/{page}?supportTicket={tid}'
    return f'{base}/{page}'


def send_support_ticket_sms_to_user(ticket, message_preview, is_new_ticket=False):
    """
    Notify ticket owner (non-internal admin reply or optional new-ticket ack).
    Staff notify and inbound SMS are deferred (see project Twilio plan).
    """
    if not Config.TWILIO_SUPPORT_SMS_ENABLED:
        return
    if not ticket:
        return
    to = normalize_phone_e164(ticket.get('phone_number'))
    if not to:
        logger.info('Twilio support SMS skipped: no valid phone on ticket')
        return
    num = ticket.get('ticket_number') or str(ticket.get('id', ''))[:8]
    prev = (message_preview or '').strip().replace('\n', ' ')
    if len(prev) > 120:
        prev = prev[:117] + '...'
    intro = (
        'We received your support request'
        if is_new_ticket
        else 'New message on your support ticket'
    )
    body = f'Mkulima Sokoni [{num}]: {intro}. {prev}' if prev else f'Mkulima Sokoni [{num}]: {intro}.'
    link = _support_app_link(ticket)
    if link:
        body += f' Open: {link}'
    if len(body) > 1500:
        body = body[:1497] + '...'
    _send_sms(to, body=body)


def send_support_ticket_sms_to_staff(_ticket, _message_preview):
    """
    Reserved for Phase 2 / optional staff pings (TWILIO_SUPPORT_NOTIFY_NUMBERS).
    Not called from routes in v1.
    """
    return
