"""
Support ticket routes.
"""
from flask import Blueprint, request, jsonify
import logging

from models.support_ticket import SupportTicket
from database import execute_query
from auth.admin_auth import decode_token_if_admin

logger = logging.getLogger(__name__)

support_bp = Blueprint('support', __name__, url_prefix='/api/support')


def _require_json():
    return request.get_json() or {}


def _is_rejected_user(firebase_uid):
    """Return True if either farmer or buyer profile is currently rejected."""
    row = execute_query(
        """
        SELECT
            fp.certification_status,
            bp.verification_status
        FROM users u
        LEFT JOIN farmer_profiles fp ON fp.user_id = u.id
        LEFT JOIN buyer_profiles bp ON bp.user_id = u.id
        WHERE u.firebase_uid = %s
        LIMIT 1
        """,
        (firebase_uid,),
        fetch_one=True
    )
    if not row:
        return False
    farmer_status = (row.get('certification_status') or '').lower()
    buyer_status = (row.get('verification_status') or '').lower()
    return farmer_status == 'rejected' or buyer_status == 'rejected'


@support_bp.route('/info', methods=['GET'])
def support_info():
    """Describe available support endpoints and required schema contract."""
    return jsonify({
        'success': True,
        'message': 'Support ticket API',
        'schema_contract': {
            'tables': ['support_tickets', 'support_ticket_messages']
        },
        'endpoints': {
            'create_ticket': 'POST /api/support/tickets',
            'my_tickets': 'GET /api/support/tickets/my/<firebase_uid>',
            'ticket_detail': 'GET /api/support/tickets/<ticket_id>?firebase_uid=<uid>',
            'add_user_message': 'POST /api/support/tickets/<ticket_id>/messages',
            'admin_tickets': 'GET /api/support/admin/tickets',
            'admin_stats': 'GET /api/support/admin/stats',
            'admin_add_message': 'POST /api/support/admin/tickets/<ticket_id>/messages',
            'admin_status': 'PATCH /api/support/admin/tickets/<ticket_id>/status',
            'admin_assign': 'PATCH /api/support/admin/tickets/<ticket_id>/assign'
        }
    }), 200


@support_bp.route('/tickets', methods=['POST'])
def create_ticket():
    """Create a ticket from buyer, farmer, or agro-dealer dashboard."""
    try:
        data = _require_json()
        firebase_uid = data.get('firebase_uid')
        category = data.get('category')
        priority = data.get('priority')
        subject = (data.get('subject') or '').strip()
        description = (data.get('description') or '').strip()

        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        if not subject:
            return jsonify({'error': 'subject is required'}), 400
        if not description:
            return jsonify({'error': 'description is required'}), 400

        ticket = SupportTicket.create_ticket(
            firebase_uid=firebase_uid,
            category=category,
            priority=priority,
            subject=subject,
            description=description
        )
        return jsonify({'success': True, 'ticket': ticket}), 201
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"Create ticket error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/tickets/my/<firebase_uid>', methods=['GET'])
def list_my_tickets(firebase_uid):
    """List current user's tickets."""
    try:
        tickets = SupportTicket.list_user_tickets(firebase_uid)
        return jsonify({'success': True, 'tickets': tickets}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:
        logger.error(f"List my tickets error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/tickets/<ticket_id>', methods=['GET'])
def ticket_detail(ticket_id):
    """Return ticket thread for owner."""
    try:
        firebase_uid = request.args.get('firebase_uid', '').strip()
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid query parameter is required'}), 400

        ticket = SupportTicket.get_ticket_detail(ticket_id, firebase_uid=firebase_uid)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        return jsonify({'success': True, 'ticket': ticket}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:
        logger.error(f"Ticket detail error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/tickets/<ticket_id>/messages', methods=['POST'])
def add_ticket_message(ticket_id):
    """Add a user reply to an existing ticket."""
    try:
        data = _require_json()
        firebase_uid = data.get('firebase_uid')
        message = (data.get('message') or '').strip()

        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        if not message:
            return jsonify({'error': 'message is required'}), 400
        if _is_rejected_user(firebase_uid):
            return jsonify({'error': 'Your account is rejected. You can view support messages but cannot reply.'}), 403

        ticket = SupportTicket.add_message(
            ticket_id=ticket_id,
            message=message,
            firebase_uid=firebase_uid,
            sender_type='user'
        )
        return jsonify({'success': True, 'ticket': ticket}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"Add ticket message error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Return ticket stats for the admin dashboard."""
    try:
        stats = SupportTicket.get_admin_stats()
        return jsonify({'success': True, 'stats': stats}), 200
    except Exception as exc:
        logger.error(f"Support admin stats error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/tickets', methods=['GET'])
def admin_tickets():
    """Return the support queue for admin-support."""
    try:
        status = request.args.get('status', '').strip().lower() or None
        priority = request.args.get('priority', '').strip().lower() or None
        search = request.args.get('search', '').strip() or None
        tickets = SupportTicket.list_admin_tickets(status=status, priority=priority, search=search)
        return jsonify({'success': True, 'tickets': tickets}), 200
    except Exception as exc:
        logger.error(f"Support admin tickets error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/tickets/<ticket_id>', methods=['GET'])
def admin_ticket_detail(ticket_id):
    """Return full ticket thread for admin-support."""
    try:
        ticket = SupportTicket.get_ticket_detail(ticket_id, is_admin=True)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        return jsonify({'success': True, 'ticket': ticket}), 200
    except Exception as exc:
        logger.error(f"Support admin ticket detail error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/tickets/<ticket_id>/messages', methods=['POST'])
def admin_add_message(ticket_id):
    """Add an admin reply or internal note."""
    try:
        data = _require_json()
        message = (data.get('message') or '').strip()
        admin_name = (data.get('admin_name') or data.get('admin_email') or 'Admin Support').strip()
        is_internal_note = bool(data.get('is_internal_note'))

        if not message:
            return jsonify({'error': 'message is required'}), 400

        ticket = SupportTicket.add_message(
            ticket_id=ticket_id,
            message=message,
            sender_type='admin',
            admin_name=admin_name,
            is_internal_note=is_internal_note
        )
        # v1: SMS to ticket owner on public admin replies only (staff notify / inbound SMS deferred)
        if not is_internal_note:
            try:
                from utils.twilio_service import send_support_ticket_sms_to_user

                send_support_ticket_sms_to_user(ticket, message, is_new_ticket=False)
            except Exception as sms_exc:
                logger.warning(
                    'Support ticket SMS to user failed (non-fatal): %s', sms_exc
                )

        return jsonify({'success': True, 'ticket': ticket}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"Support admin add message error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/tickets/<ticket_id>/status', methods=['PATCH'])
def admin_update_status(ticket_id):
    """Update support ticket status."""
    try:
        data = _require_json()
        status = data.get('status')
        admin_email = data.get('admin_email')
        resolution_summary = data.get('resolution_summary')
        ticket = SupportTicket.update_status(ticket_id, status, admin_email, resolution_summary)
        return jsonify({'success': True, 'ticket': ticket}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"Support admin status error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/tickets/<ticket_id>/assign', methods=['PATCH'])
def admin_assign(ticket_id):
    """Assign ticket to a support admin."""
    try:
        data = _require_json()
        admin_email = (data.get('admin_email') or '').strip()
        if not admin_email:
            return jsonify({'error': 'admin_email is required'}), 400

        ticket = SupportTicket.assign_ticket(ticket_id, admin_email)
        return jsonify({'success': True, 'ticket': ticket}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"Support admin assign error: {exc}")
        return jsonify({'error': str(exc)}), 500


@support_bp.route('/admin/message-user', methods=['POST'])
def admin_message_user():
    """Open an admin outreach ticket and send first message to a specific user."""
    try:
        decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        data = _require_json()
        user_id = (data.get('user_id') or '').strip()
        subject = (data.get('subject') or '').strip()
        message = (data.get('message') or '').strip()
        admin_name = (
            data.get('admin_name')
            or data.get('admin_email')
            or decoded.get('email')
            or 'Admin Support'
        )

        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        if not subject:
            return jsonify({'error': 'subject is required'}), 400
        if not message:
            return jsonify({'error': 'message is required'}), 400

        ticket = SupportTicket.create_admin_outreach_ticket(
            user_id=user_id,
            subject=subject,
            message=message,
            admin_name=admin_name,
        )

        try:
            from utils.twilio_service import send_support_ticket_sms_to_user
            send_support_ticket_sms_to_user(ticket, message, is_new_ticket=True)
        except Exception as sms_exc:
            logger.warning('Admin outreach SMS failed (non-fatal): %s', sms_exc)

        return jsonify({'success': True, 'ticket': ticket}), 201
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logger.error(f"Support admin message user error: {exc}")
        return jsonify({'error': str(exc)}), 500
