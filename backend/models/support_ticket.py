"""
Support ticket model and data access helpers.

Schema contract expected by this model:

Table: support_tickets
  - id UUID PRIMARY KEY
  - ticket_number TEXT UNIQUE NOT NULL
  - user_id UUID NOT NULL REFERENCES users(id)
  - user_role TEXT NOT NULL
  - category TEXT NOT NULL
  - priority TEXT NOT NULL
  - subject TEXT NOT NULL
  - description TEXT NOT NULL
  - status TEXT NOT NULL
  - assigned_admin_email TEXT NULL
  - resolution_summary TEXT NULL
  - created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  - updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
  - resolved_at TIMESTAMP NULL
  - closed_at TIMESTAMP NULL

Table: support_ticket_messages
  - id UUID PRIMARY KEY
  - ticket_id UUID NOT NULL REFERENCES support_tickets(id)
  - sender_type TEXT NOT NULL
  - sender_user_id UUID NULL REFERENCES users(id)
  - sender_name TEXT NULL
  - message TEXT NOT NULL
  - is_internal_note BOOLEAN NOT NULL DEFAULT FALSE
  - created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
"""
from datetime import datetime
import logging
import random

from database import execute_query
from models.user import User

logger = logging.getLogger(__name__)


class SupportTicket:
    """Support ticket data access layer."""

    VALID_STATUSES = {
        'open',
        'in_progress',
        'waiting_for_user',
        'resolved',
        'closed'
    }
    VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}
    VALID_CATEGORIES = {
        'account',
        'orders',
        'payments',
        'products',
        'delivery',
        'verification',
        'technical',
        'other'
    }

    @staticmethod
    def _normalize_ticket(row):
        if not row:
            return None

        ticket = dict(row)
        for field in ('id', 'user_id'):
            if ticket.get(field) is not None:
                ticket[field] = str(ticket[field])
        for field in ('created_at', 'updated_at', 'resolved_at', 'closed_at'):
            if ticket.get(field):
                ticket[field] = str(ticket[field])
        return ticket

    @staticmethod
    def _normalize_message(row):
        if not row:
            return None

        message = dict(row)
        for field in ('id', 'ticket_id', 'sender_user_id'):
            if message.get(field) is not None:
                message[field] = str(message[field])
        if message.get('created_at'):
            message['created_at'] = str(message['created_at'])
        return message

    @staticmethod
    def generate_ticket_number():
        """Generate a readable support ticket number."""
        stamp = datetime.utcnow().strftime('%Y%m%d')
        suffix = random.randint(1000, 9999)
        return f"TKT-{stamp}-{suffix}"

    @staticmethod
    def get_user_context(firebase_uid):
        """Resolve the logged-in user from Firebase UID."""
        query = """
            SELECT id, firebase_uid, email, first_name, last_name, phone_number, role
            FROM users
            WHERE firebase_uid = %s
            LIMIT 1
        """
        result = execute_query(query, (firebase_uid,), fetch_one=True)
        if not result:
            return None

        user = dict(result)
        user['id'] = str(user['id'])
        user['display_name'] = (
            f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip()
            or user.get('email')
            or 'User'
        )
        return user

    @staticmethod
    def create_ticket(firebase_uid, category, priority, subject, description):
        """Create a support ticket and its opening message."""
        user = SupportTicket.get_user_context(firebase_uid)
        if not user:
            raise ValueError('User not found')

        category = (category or 'other').strip().lower()
        priority = (priority or 'medium').strip().lower()
        if category not in SupportTicket.VALID_CATEGORIES:
            category = 'other'
        if priority not in SupportTicket.VALID_PRIORITIES:
            priority = 'medium'

        ticket_number = SupportTicket.generate_ticket_number()
        insert_ticket = """
            INSERT INTO support_tickets (
                ticket_number,
                user_id,
                user_role,
                category,
                priority,
                subject,
                description,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'open', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, ticket_number, user_id, user_role, category, priority, subject,
                      description, status, assigned_admin_email, resolution_summary,
                      created_at, updated_at, resolved_at, closed_at
        """
        ticket = execute_query(
            insert_ticket,
            (
                ticket_number,
                user['id'],
                user.get('role') or 'buyer',
                category,
                priority,
                subject.strip(),
                description.strip()
            ),
            fetch_one=True
        )
        ticket = SupportTicket._normalize_ticket(ticket)

        insert_message = """
            INSERT INTO support_ticket_messages (
                ticket_id,
                sender_type,
                sender_user_id,
                sender_name,
                message,
                is_internal_note,
                created_at
            )
            VALUES (%s, 'user', %s, %s, %s, FALSE, CURRENT_TIMESTAMP)
        """
        execute_query(
            insert_message,
            (
                ticket['id'],
                user['id'],
                user['display_name'],
                description.strip()
            )
        )

        return SupportTicket.get_ticket_detail(ticket['id'], firebase_uid=firebase_uid)

    @staticmethod
    def list_user_tickets(firebase_uid):
        """List tickets created by a specific user."""
        user = SupportTicket.get_user_context(firebase_uid)
        if not user:
            raise ValueError('User not found')

        query = """
            SELECT
                st.id,
                st.ticket_number,
                st.user_id,
                st.user_role,
                st.category,
                st.priority,
                st.subject,
                st.description,
                st.status,
                st.assigned_admin_email,
                st.resolution_summary,
                st.created_at,
                st.updated_at,
                st.resolved_at,
                st.closed_at,
                COALESCE(msg.message_count, 0) AS message_count,
                last_msg.message AS last_message,
                last_msg.created_at AS last_message_at
            FROM support_tickets st
            LEFT JOIN (
                SELECT ticket_id, COUNT(*) AS message_count
                FROM support_ticket_messages
                GROUP BY ticket_id
            ) msg ON msg.ticket_id = st.id
            LEFT JOIN (
                SELECT DISTINCT ON (ticket_id)
                    ticket_id,
                    message,
                    created_at
                FROM support_ticket_messages
                WHERE is_internal_note = FALSE
                ORDER BY ticket_id, created_at DESC
            ) last_msg ON last_msg.ticket_id = st.id
            WHERE st.user_id = %s
            ORDER BY st.updated_at DESC, st.created_at DESC
        """
        rows = execute_query(query, (user['id'],), fetch_all=True)
        tickets = []
        for row in rows:
            ticket = SupportTicket._normalize_ticket(row)
            if ticket.get('last_message_at'):
                ticket['last_message_at'] = str(ticket['last_message_at'])
            tickets.append(ticket)
        return tickets

    @staticmethod
    def list_admin_tickets(status=None, priority=None, search=None):
        """List all tickets for admin-support queue."""
        clauses = []
        params = []

        if status and status != 'all':
            clauses.append("st.status = %s")
            params.append(status)
        if priority and priority != 'all':
            clauses.append("st.priority = %s")
            params.append(priority)
        if search:
            clauses.append(
                "(st.ticket_number ILIKE %s OR st.subject ILIKE %s OR st.description ILIKE %s OR "
                "u.email ILIKE %s OR COALESCE(u.first_name, '') ILIKE %s OR COALESCE(u.last_name, '') ILIKE %s)"
            )
            search_value = f"%{search}%"
            params.extend([search_value] * 6)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ''
        query = f"""
            SELECT
                st.id,
                st.ticket_number,
                st.user_id,
                st.user_role,
                st.category,
                st.priority,
                st.subject,
                st.description,
                st.status,
                st.assigned_admin_email,
                st.resolution_summary,
                st.created_at,
                st.updated_at,
                st.resolved_at,
                st.closed_at,
                u.email AS user_email,
                u.first_name,
                u.last_name,
                COALESCE(msg.message_count, 0) AS message_count
            FROM support_tickets st
            JOIN users u ON u.id = st.user_id
            LEFT JOIN (
                SELECT ticket_id, COUNT(*) AS message_count
                FROM support_ticket_messages
                GROUP BY ticket_id
            ) msg ON msg.ticket_id = st.id
            {where_clause}
            ORDER BY
                CASE st.priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                st.updated_at DESC,
                st.created_at DESC
        """
        rows = execute_query(query, tuple(params), fetch_all=True)
        tickets = []
        for row in rows:
            ticket = SupportTicket._normalize_ticket(row)
            ticket['user_name'] = (
                f"{(ticket.get('first_name') or '').strip()} {(ticket.get('last_name') or '').strip()}".strip()
                or ticket.get('user_email')
                or 'User'
            )
            tickets.append(ticket)
        return tickets

    @staticmethod
    def get_ticket_detail(ticket_id, firebase_uid=None, is_admin=False):
        """Get ticket with message thread."""
        params = [ticket_id]
        access_clause = ""
        if not is_admin:
            user = SupportTicket.get_user_context(firebase_uid)
            if not user:
                raise ValueError('User not found')
            access_clause = "AND st.user_id = %s"
            params.append(user['id'])

        query = f"""
            SELECT
                st.id,
                st.ticket_number,
                st.user_id,
                st.user_role,
                st.category,
                st.priority,
                st.subject,
                st.description,
                st.status,
                st.assigned_admin_email,
                st.resolution_summary,
                st.created_at,
                st.updated_at,
                st.resolved_at,
                st.closed_at,
                u.email AS user_email,
                u.first_name,
                u.last_name,
                u.phone_number
            FROM support_tickets st
            JOIN users u ON u.id = st.user_id
            WHERE st.id = %s
            {access_clause}
            LIMIT 1
        """
        ticket = execute_query(query, tuple(params), fetch_one=True)
        if not ticket:
            return None

        ticket = SupportTicket._normalize_ticket(ticket)
        ticket['user_name'] = (
            f"{(ticket.get('first_name') or '').strip()} {(ticket.get('last_name') or '').strip()}".strip()
            or ticket.get('user_email')
            or 'User'
        )

        message_query = """
            SELECT id, ticket_id, sender_type, sender_user_id, sender_name,
                   message, is_internal_note, created_at
            FROM support_ticket_messages
            WHERE ticket_id = %s
            ORDER BY created_at ASC
        """
        messages = execute_query(message_query, (ticket_id,), fetch_all=True)
        ticket['messages'] = [SupportTicket._normalize_message(row) for row in messages]
        return ticket

    @staticmethod
    def add_message(ticket_id, message, firebase_uid=None, sender_type='user',
                    admin_name=None, is_internal_note=False):
        """Add a reply or internal note to a ticket."""
        ticket = SupportTicket.get_ticket_detail(ticket_id, firebase_uid=firebase_uid, is_admin=(sender_type == 'admin'))
        if not ticket:
            raise ValueError('Ticket not found')

        sender_user_id = None
        sender_name = admin_name or 'Admin Support'
        if sender_type == 'user':
            user = SupportTicket.get_user_context(firebase_uid)
            if not user:
                raise ValueError('User not found')
            sender_user_id = user['id']
            sender_name = user['display_name']

        insert_query = """
            INSERT INTO support_ticket_messages (
                ticket_id,
                sender_type,
                sender_user_id,
                sender_name,
                message,
                is_internal_note,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """
        execute_query(
            insert_query,
            (ticket_id, sender_type, sender_user_id, sender_name, message.strip(), is_internal_note)
        )

        next_status = ticket['status']
        if sender_type == 'admin' and not is_internal_note and ticket['status'] == 'open':
            next_status = 'in_progress'
        elif sender_type == 'admin' and not is_internal_note and ticket['status'] == 'resolved':
            next_status = 'in_progress'
        elif sender_type == 'user' and ticket['status'] in ('resolved', 'closed'):
            next_status = 'open'
        elif sender_type == 'user' and ticket['status'] == 'waiting_for_user':
            next_status = 'in_progress'

        execute_query(
            """
            UPDATE support_tickets
            SET status = %s,
                updated_at = CURRENT_TIMESTAMP,
                resolved_at = CASE WHEN %s = 'resolved' THEN COALESCE(resolved_at, CURRENT_TIMESTAMP) ELSE resolved_at END,
                closed_at = CASE WHEN %s = 'closed' THEN COALESCE(closed_at, CURRENT_TIMESTAMP) ELSE closed_at END
            WHERE id = %s
            """,
            (next_status, next_status, next_status, ticket_id)
        )

        if sender_type == 'admin':
            return SupportTicket.get_ticket_detail(ticket_id, is_admin=True)
        return SupportTicket.get_ticket_detail(ticket_id, firebase_uid=firebase_uid)

    @staticmethod
    def update_status(ticket_id, status, admin_email=None, resolution_summary=None):
        """Update ticket workflow state."""
        status = (status or '').strip().lower()
        if status not in SupportTicket.VALID_STATUSES:
            raise ValueError('Invalid status')

        query = """
            UPDATE support_tickets
            SET status = %s,
                resolution_summary = COALESCE(%s, resolution_summary),
                assigned_admin_email = COALESCE(%s, assigned_admin_email),
                updated_at = CURRENT_TIMESTAMP,
                resolved_at = CASE
                    WHEN %s = 'resolved' THEN CURRENT_TIMESTAMP
                    WHEN %s IN ('open', 'in_progress', 'waiting_for_user') THEN NULL
                    ELSE resolved_at
                END,
                closed_at = CASE
                    WHEN %s = 'closed' THEN CURRENT_TIMESTAMP
                    WHEN %s != 'closed' THEN NULL
                    ELSE closed_at
                END
            WHERE id = %s
        """
        count = execute_query(
            query,
            (
                status,
                resolution_summary,
                admin_email,
                status,
                status,
                status,
                status,
                ticket_id
            )
        )
        if not count:
            raise ValueError('Ticket not found')
        return SupportTicket.get_ticket_detail(ticket_id, is_admin=True)

    @staticmethod
    def assign_ticket(ticket_id, admin_email):
        """Assign ticket to support staff."""
        count = execute_query(
            """
            UPDATE support_tickets
            SET assigned_admin_email = %s,
                status = CASE WHEN status = 'open' THEN 'in_progress' ELSE status END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (admin_email, ticket_id)
        )
        if not count:
            raise ValueError('Ticket not found')
        return SupportTicket.get_ticket_detail(ticket_id, is_admin=True)

    @staticmethod
    def get_admin_stats():
        """High-level admin ticket counters."""
        query = """
            SELECT
                COUNT(*) AS total_tickets,
                COUNT(*) FILTER (WHERE status = 'open') AS open_tickets,
                COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_tickets,
                COUNT(*) FILTER (WHERE status = 'waiting_for_user') AS waiting_for_user_tickets,
                COUNT(*) FILTER (WHERE status = 'resolved') AS resolved_tickets,
                COUNT(*) FILTER (WHERE status = 'closed') AS closed_tickets,
                COUNT(*) FILTER (WHERE priority = 'urgent') AS urgent_tickets,
                COUNT(*) FILTER (WHERE priority = 'high') AS high_priority_tickets
            FROM support_tickets
        """
        stats = execute_query(query, fetch_one=True) or {}
        return dict(stats)

    @staticmethod
    def create_admin_outreach_ticket(user_id, subject, message, admin_name='Admin Support'):
        """Create a support ticket opened by admin and send first admin message."""
        user = User.get_user_by_id(user_id)
        if not user:
            raise ValueError('User not found')

        user_role = (user.get('role') or 'user').split(',')[0].strip() or 'user'
        ticket_number = SupportTicket.generate_ticket_number()
        ticket = execute_query(
            """
            INSERT INTO support_tickets (
                ticket_number, user_id, user_role, category, priority, subject, description,
                status, created_at, updated_at
            )
            VALUES (%s, %s::uuid, %s, 'verification', 'medium', %s, %s, 'in_progress', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (ticket_number, user_id, user_role, subject.strip(), message.strip()),
            fetch_one=True,
        )
        if not ticket:
            raise ValueError('Failed to create support ticket')

        execute_query(
            """
            INSERT INTO support_ticket_messages (
                ticket_id, sender_type, sender_user_id, sender_name, message, is_internal_note, created_at
            )
            VALUES (%s::uuid, 'admin', NULL, %s, %s, FALSE, CURRENT_TIMESTAMP)
            """,
            (str(ticket['id']), (admin_name or 'Admin Support').strip(), message.strip()),
        )

        # Return full ticket with thread for API response/SMS helpers.
        return SupportTicket.get_ticket_detail(str(ticket['id']), is_admin=True)
