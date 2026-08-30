"""
Chat models and database operations for buyer–farmer messaging.
"""
from database import execute_query
import logging

logger = logging.getLogger(__name__)


class Conversation:
    """Represents a buyer–farmer conversation."""

    @staticmethod
    def find_or_create(buyer_user_id, farmer_profile_id):
        """
        Find existing conversation for this buyer/farmer pair or create a new one.
        """
        try:
            # Try find first
            query_find = """
                SELECT *
                FROM conversations
                WHERE buyer_user_id = %s::uuid
                  AND farmer_profile_id = %s::uuid
                LIMIT 1
            """
            existing = execute_query(
                query_find,
                (buyer_user_id, farmer_profile_id),
                fetch_one=True,
            )
            if existing:
                return dict(existing)

            # Create new conversation
            query_create = """
                INSERT INTO conversations (buyer_user_id, farmer_profile_id)
                VALUES (%s::uuid, %s::uuid)
                RETURNING *
            """
            created = execute_query(
                query_create,
                (buyer_user_id, farmer_profile_id),
                fetch_one=True,
            )
            return dict(created) if created else None
        except Exception as e:
            logger.error(f"Error in Conversation.find_or_create: {str(e)}")
            raise

    @staticmethod
    def get_for_user(user_id, role):
        """
        List conversations for a user.
        - As buyer: user participates via buyer_user_id.
        - As farmer: via farmer_profile_id joined to farmer_profiles.user_id.
        """
        try:
            if role == "buyer":
                query = """
                    SELECT
                        c.*,
                        fp.farm_name,
                        fp.location,
                        fp.county,
                        lm.body AS last_message_body,
                        lm.created_at AS last_message_created_at,
                        COALESCE(uc.unread_count, 0) AS unread_count
                    FROM conversations c
                    JOIN farmer_profiles fp ON c.farmer_profile_id = fp.id
                    LEFT JOIN LATERAL (
                        SELECT m.body, m.created_at
                        FROM messages m
                        WHERE m.conversation_id = c.id
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) lm ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*)::int AS unread_count
                        FROM messages m
                        WHERE m.conversation_id = c.id
                          AND m.is_read = FALSE
                          AND m.sender_user_id <> %s::uuid
                    ) uc ON TRUE
                    WHERE c.buyer_user_id = %s::uuid
                    ORDER BY COALESCE(c.last_message_at, c.created_at) DESC
                """
                rows = execute_query(query, (user_id, user_id), fetch_all=True)
            else:
                # Farmer / agro-dealer: conversations where their profile participates
                query = """
                    SELECT
                        c.*,
                        fp.farm_name,
                        fp.location,
                        fp.county,
                        lm.body AS last_message_body,
                        lm.created_at AS last_message_created_at,
                        COALESCE(uc.unread_count, 0) AS unread_count
                    FROM conversations c
                    JOIN farmer_profiles fp ON c.farmer_profile_id = fp.id
                    LEFT JOIN LATERAL (
                        SELECT m.body, m.created_at
                        FROM messages m
                        WHERE m.conversation_id = c.id
                        ORDER BY m.created_at DESC
                        LIMIT 1
                    ) lm ON TRUE
                    LEFT JOIN LATERAL (
                        SELECT COUNT(*)::int AS unread_count
                        FROM messages m
                        WHERE m.conversation_id = c.id
                          AND m.is_read = FALSE
                          AND m.sender_user_id <> %s::uuid
                    ) uc ON TRUE
                    WHERE fp.user_id = %s::uuid
                    ORDER BY COALESCE(c.last_message_at, c.created_at) DESC
                """
                rows = execute_query(query, (user_id, user_id), fetch_all=True)
            return [dict(r) for r in (rows or [])]
        except Exception as e:
            logger.error(f"Error in Conversation.get_for_user: {str(e)}")
            raise

    @staticmethod
    def get_by_id_for_user(conversation_id, user_id):
        """
        Fetch a single conversation ensuring the given user participates in it.
        """
        try:
            query = """
                SELECT c.*
                FROM conversations c
                LEFT JOIN farmer_profiles fp ON c.farmer_profile_id = fp.id
                WHERE c.id = %s::uuid
                  AND (c.buyer_user_id = %s::uuid OR fp.user_id = %s::uuid)
                LIMIT 1
            """
            row = execute_query(
                query,
                (conversation_id, user_id, user_id),
                fetch_one=True,
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in Conversation.get_by_id_for_user: {str(e)}")
            raise

    @staticmethod
    def count_admin_unreplied_conversations():
        """
        Conversations with unread buyer/seller messages (matches admin chat red badges).
        """
        try:
            query = """
                SELECT COUNT(*) AS c
                FROM conversations c
                JOIN farmer_profiles fp ON fp.id = c.farmer_profile_id
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) FILTER (
                            WHERE m.is_read = FALSE AND m.sender_user_id <> c.buyer_user_id
                        )::int AS unread_for_buyer,
                        COUNT(*) FILTER (
                            WHERE m.is_read = FALSE AND m.sender_user_id <> fp.user_id
                        )::int AS unread_for_seller
                    FROM messages m
                    WHERE m.conversation_id = c.id
                ) uc ON TRUE
                WHERE c.last_message_at IS NOT NULL
                  AND (COALESCE(uc.unread_for_buyer, 0) + COALESCE(uc.unread_for_seller, 0)) > 0
            """
            row = execute_query(query, fetch_one=True) or {}
            return int(row.get('c') or 0)
        except Exception as e:
            logger.error(f"Error in Conversation.count_admin_unreplied_conversations: {str(e)}")
            raise


class Message:
    """Represents a chat message in a conversation."""

    @staticmethod
    def list_for_conversation(conversation_id, limit=100, offset=0):
        try:
            query = """
                SELECT *
                FROM messages
                WHERE conversation_id = %s::uuid
                ORDER BY created_at ASC
                LIMIT %s OFFSET %s
            """
            rows = execute_query(
                query,
                (conversation_id, limit, offset),
                fetch_all=True,
            )
            return [dict(r) for r in (rows or [])]
        except Exception as e:
            logger.error(f"Error in Message.list_for_conversation: {str(e)}")
            raise

    @staticmethod
    def create(conversation_id, sender_user_id, body):
        try:
            query = """
                INSERT INTO messages (conversation_id, sender_user_id, body)
                VALUES (%s::uuid, %s::uuid, %s)
                RETURNING *
            """
            row = execute_query(
                query,
                (conversation_id, sender_user_id, body),
                fetch_one=True,
            )

            # Update conversation last_message_at
            if row:
                execute_query(
                    """
                    UPDATE conversations
                    SET last_message_at = CURRENT_TIMESTAMP
                    WHERE id = %s::uuid
                    """,
                    (conversation_id,),
                )

            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error in Message.create: {str(e)}")
            raise

    @staticmethod
    def mark_read_for_conversation(conversation_id, reader_user_id):
        """
        Mark all messages in a conversation as read for the reader,
        excluding messages sent by the reader.
        """
        try:
            query = """
                UPDATE messages
                SET is_read = TRUE
                WHERE conversation_id = %s::uuid
                  AND is_read = FALSE
                  AND sender_user_id <> %s::uuid
            """
            return execute_query(query, (conversation_id, reader_user_id))
        except Exception as e:
            logger.error(f"Error in Message.mark_read_for_conversation: {str(e)}")
            raise

