"""
Chat routes for buyer–farmer messaging.
"""
from flask import Blueprint, request, jsonify, g
from models.chat import Conversation, Message
from models.product import Product
from models.user import User
from models.farmer_profile import FarmerProfile
from utils.account_access import is_rejected_user
from utils.mailer import send_new_message_email, send_admin_direct_email, smtp_enabled
from auth.admin_auth import decode_token_if_admin
from database import execute_query
import logging
import os
import time

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

_chat_email_last_sent = {}


def _chat_email_throttle_seconds() -> int:
    try:
        minutes = int(os.getenv("CHAT_EMAIL_THROTTLE_MINUTES", "15"))
    except Exception:
        minutes = 15
    return max(60, minutes * 60)


def _maybe_email_other_party(convo, sender_user_id: str, message_body: str) -> None:
    """
    Best-effort email notification to the other participant in a conversation.
    Throttled per (conversation_id, recipient_user_id).
    """
    try:
        convo_id = str(convo.get("id"))
        buyer_user_id = str(convo.get("buyer_user_id"))
        farmer_profile_id = str(convo.get("farmer_profile_id"))

        # Determine recipient user id
        if str(sender_user_id) == buyer_user_id:
            # Sender is buyer -> recipient is farmer (profile owner)
            row = execute_query(
                "SELECT user_id FROM farmer_profiles WHERE id = %s::uuid",
                (farmer_profile_id,),
                fetch_one=True,
            )
            recipient_user_id = str(row.get("user_id")) if row else None
            from_label = "Buyer"
        else:
            # Sender is farmer/agro-dealer -> recipient is buyer
            recipient_user_id = buyer_user_id
            from_label = "Seller"

        if not recipient_user_id:
            return

        key = f"{convo_id}:{recipient_user_id}"
        now = time.time()
        last = _chat_email_last_sent.get(key, 0)
        if now - last < _chat_email_throttle_seconds():
            return

        recipient = User.get_user_by_id(recipient_user_id)
        if not recipient:
            return
        to_email = (recipient.get("email") or "").strip()
        if not to_email:
            return

        # Only email verified accounts by default (avoid sending to mistyped emails)
        if not recipient.get("email_verified", False):
            return

        sent = send_new_message_email(
            to_email=to_email,
            from_label=from_label,
            preview_text=message_body,
            deep_link=None,
        )
        if sent:
            _chat_email_last_sent[key] = now
    except Exception as e:
        logger.warning("Chat email notification skipped/failed: %s", e)


def _get_current_user():
    """
    Lightweight current-user resolver based on firebase_uid from request JSON.
    Frontend already stores Firebase UID in localStorage user object.
    """
    data = request.get_json(silent=True) or {}
    firebase_uid = data.get("firebase_uid") or request.headers.get("X-Firebase-Uid")
    if not firebase_uid:
        return None, "Missing firebase_uid", 401

    try:
        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return None, "User not found", 404
        return user, None, None
    except Exception as e:
        logger.error(f"Error resolving current user from firebase_uid: {str(e)}")
        return None, "Could not resolve user", 500


@chat_bp.route("/conversations", methods=["POST"])
def create_conversation():
    """
    Create or fetch a conversation for the current buyer and the farmer who owns a product.
    Expects JSON: { firebase_uid, product_id }
    """
    user, err, status = _get_current_user()
    if err:
        return jsonify({"error": err}), status
    if is_rejected_user(user.get("firebase_uid")):
        return jsonify({"error": "Your account is rejected. Chat is read-only."}), 403

    data = request.get_json() or {}
    product_id = data.get("product_id")
    if not product_id:
        return jsonify({"error": "product_id is required"}), 400

    try:
        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404

        farmer_profile_id = str(product["farmer_profile_id"])
        buyer_user_id = str(user["id"])

        convo = Conversation.find_or_create(buyer_user_id, farmer_profile_id)
        if not convo:
            return jsonify({"error": "Could not create conversation"}), 500

        return jsonify({"success": True, "conversation": convo}), 200
    except Exception as e:
        logger.error(f"create_conversation error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to create conversation"}), 500


@chat_bp.route("/conversations", methods=["GET"])
def list_conversations():
    """
    List conversations for the current user.
    Query param: role=buyer|farmer|agro-dealer (defaults from stored user.role if present).
    """
    firebase_uid = request.args.get("firebase_uid") or request.headers.get(
        "X-Firebase-Uid"
    )
    if not firebase_uid:
        return jsonify({"error": "firebase_uid is required"}), 400

    try:
        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({"error": "User not found"}), 404

        role = request.args.get("role") or (user.get("role") or "").split(",")[0]
        role = (role or "buyer").strip()

        convos = Conversation.get_for_user(str(user["id"]), role)
        return jsonify({"conversations": convos}), 200
    except Exception as e:
        logger.error(f"list_conversations error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to list conversations"}), 500


@chat_bp.route("/conversations/<conversation_id>/messages", methods=["GET"])
def get_messages(conversation_id):
    """
    Get messages for a conversation that the current user participates in.
    Query params: firebase_uid, limit, offset
    """
    firebase_uid = request.args.get("firebase_uid") or request.headers.get(
        "X-Firebase-Uid"
    )
    if not firebase_uid:
        return jsonify({"error": "firebase_uid is required"}), 400

    try:
        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({"error": "User not found"}), 404

        convo = Conversation.get_by_id_for_user(conversation_id, str(user["id"]))
        if not convo:
            return jsonify({"error": "Conversation not found"}), 404

        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))

        messages = Message.list_for_conversation(conversation_id, limit, offset)
        # Mark messages from the other participant as read when thread is opened
        try:
            Message.mark_read_for_conversation(conversation_id, str(user["id"]))
        except Exception as e:
            logger.warning(f"Could not mark messages read: {e}")
        return jsonify({"conversation": convo, "messages": messages}), 200
    except Exception as e:
        logger.error(f"get_messages error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to load messages"}), 500


@chat_bp.route("/conversations/<conversation_id>/messages", methods=["POST"])
def send_message(conversation_id):
    """
    Send a message in a conversation.
    Expects JSON: { firebase_uid, body }
    """
    user, err, status = _get_current_user()
    if err:
        return jsonify({"error": err}), status
    if is_rejected_user(user.get("firebase_uid")):
        return jsonify({"error": "Your account is rejected. You can view messages but cannot send."}), 403
    if not user.get("email_verified", False):
        return jsonify({"error": "Please verify your email address to continue."}), 403

    data = request.get_json() or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message body is required"}), 400

    try:
        convo = Conversation.get_by_id_for_user(conversation_id, str(user["id"]))
        if not convo:
            return jsonify({"error": "Conversation not found"}), 404

        msg = Message.create(conversation_id, str(user["id"]), body)
        if not msg:
            return jsonify({"error": "Could not send message"}), 500

        # Best-effort email notification to the other party (throttled)
        try:
            convo = Conversation.get_by_id_for_user(conversation_id, str(user["id"]))
            if convo:
                _maybe_email_other_party(convo, str(user["id"]), body)
        except Exception:
            pass

        return jsonify({"success": True, "message": msg}), 201
    except Exception as e:
        logger.error(f"send_message error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to send message"}), 500


@chat_bp.route("/admin/conversations", methods=["GET"])
def admin_list_conversations():
    """
    Admin: list conversations with optional search.
    Excludes conversations that have no messages yet (last_message_at is null).
    Query params:
      - q: search across participant emails/names (best-effort)
      - limit, offset
    Requires admin Firebase Bearer token.
    """
    decoded, err = decode_token_if_admin()
    if err:
        return err

    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except Exception:
        limit, offset = 50, 0
    limit = max(1, min(200, limit))
    offset = max(0, offset)

    try:
        query = """
            SELECT
              c.*,
              bu.email AS buyer_email,
              bu.firebase_uid AS buyer_firebase_uid,
              fp.farm_name,
              fp.user_id AS seller_user_id,
              su.email AS seller_email,
              su.firebase_uid AS seller_firebase_uid,
              lm.body AS last_message_body,
              lm.created_at AS last_message_created_at,
              COALESCE(uc.unread_for_buyer, 0) AS unread_for_buyer,
              COALESCE(uc.unread_for_seller, 0) AS unread_for_seller
            FROM conversations c
            JOIN users bu ON bu.id = c.buyer_user_id
            JOIN farmer_profiles fp ON fp.id = c.farmer_profile_id
            JOIN users su ON su.id = fp.user_id
            LEFT JOIN LATERAL (
              SELECT m.body, m.created_at
              FROM messages m
              WHERE m.conversation_id = c.id
              ORDER BY m.created_at DESC
              LIMIT 1
            ) lm ON TRUE
            LEFT JOIN LATERAL (
              SELECT
                COUNT(*) FILTER (WHERE m.is_read = FALSE AND m.sender_user_id <> c.buyer_user_id)::int AS unread_for_buyer,
                COUNT(*) FILTER (WHERE m.is_read = FALSE AND m.sender_user_id <> fp.user_id)::int AS unread_for_seller
              FROM messages m
              WHERE m.conversation_id = c.id
            ) uc ON TRUE
            WHERE (
              %s = '' OR
              bu.email ILIKE %s OR
              su.email ILIKE %s OR
              fp.farm_name ILIKE %s
            )
            AND c.last_message_at IS NOT NULL
            ORDER BY COALESCE(c.last_message_at, c.created_at) DESC
            LIMIT %s OFFSET %s
        """
        like = f"%{q}%"
        rows = execute_query(query, (q, like, like, like, limit, offset), fetch_all=True) or []
        return jsonify({"conversations": [dict(r) for r in rows]}), 200
    except Exception as e:
        logger.error(f"admin_list_conversations error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to list conversations"}), 500


@chat_bp.route("/admin/conversations/<conversation_id>/messages", methods=["GET"])
def admin_get_conversation_messages(conversation_id):
    """
    Admin: get messages for a conversation (no mark-read side effects).
    Requires admin Firebase Bearer token.
    """
    decoded, err = decode_token_if_admin()
    if err:
        return err

    try:
        limit = int(request.args.get("limit", 200))
        offset = int(request.args.get("offset", 0))
    except Exception:
        limit, offset = 200, 0
    limit = max(1, min(500, limit))
    offset = max(0, offset)

    try:
        convo = execute_query(
            """
            SELECT
              c.*,
              bu.email AS buyer_email,
              fp.farm_name,
              su.email AS seller_email
            FROM conversations c
            JOIN users bu ON bu.id = c.buyer_user_id
            JOIN farmer_profiles fp ON fp.id = c.farmer_profile_id
            JOIN users su ON su.id = fp.user_id
            WHERE c.id = %s::uuid
            LIMIT 1
            """,
            (conversation_id,),
            fetch_one=True,
        )
        if not convo:
            return jsonify({"error": "Conversation not found"}), 404
        messages = Message.list_for_conversation(conversation_id, limit, offset)
        return jsonify({"conversation": dict(convo), "messages": messages}), 200
    except Exception as e:
        logger.error(f"admin_get_conversation_messages error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to load messages"}), 500


@chat_bp.route("/admin/conversations/<conversation_id>/messages", methods=["POST"])
def admin_send_message(conversation_id):
    """
    Admin: send a message as a system/admin participant into an existing conversation.
    Expects JSON: { body, as: 'buyer'|'seller' (default 'seller') }
    Requires admin Firebase Bearer token.
    """
    decoded, err = decode_token_if_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message body is required"}), 400

    as_side = (data.get("as") or "seller").strip().lower()
    if as_side not in ("buyer", "seller"):
        as_side = "seller"

    try:
        # Resolve participants so admin can choose which side to message as.
        convo = execute_query(
            """
            SELECT c.*, fp.user_id AS seller_user_id
            FROM conversations c
            JOIN farmer_profiles fp ON fp.id = c.farmer_profile_id
            WHERE c.id = %s::uuid
            LIMIT 1
            """,
            (conversation_id,),
            fetch_one=True,
        )
        if not convo:
            return jsonify({"error": "Conversation not found"}), 404

        sender_user_id = str(convo["buyer_user_id"]) if as_side == "buyer" else str(convo["seller_user_id"])
        msg = Message.create(conversation_id, sender_user_id, body)
        if not msg:
            return jsonify({"error": "Could not send message"}), 500

        return jsonify({"success": True, "message": msg}), 201
    except Exception as e:
        logger.error(f"admin_send_message error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to send message"}), 500


@chat_bp.route("/admin/direct-message", methods=["POST"])
def admin_send_direct_message():
    """
    Admin: send a branded email to any registered user by email address.
    Expects JSON: { email, body, subject? }
    Requires admin Firebase Bearer token.
    """
    decoded, err = decode_token_if_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    body = (data.get("body") or "").strip()
    subject = (data.get("subject") or "").strip()

    if not email:
        return jsonify({"error": "email is required"}), 400
    if not body:
        return jsonify({"error": "Message body is required"}), 400

    user = User.get_user_by_email(email)
    if not user:
        return jsonify({"error": "No user found with that email"}), 404

    to_email = (user.get("email") or email).strip()
    admin_email = (decoded.get("email") or "").strip() or None
    default_subject = "Message from Mkulima Sokoni Admin Support"
    final_subject = subject or default_subject

    req_id = getattr(g, "request_id", "-")
    enabled = smtp_enabled()
    logger.info(
        "admin_direct_message request_id=%s admin_email=%s recipient=%s body_len=%s smtp_enabled=%s",
        req_id,
        admin_email or "-",
        to_email,
        len(body),
        enabled,
    )

    dispatched = send_admin_direct_email(to_email, final_subject, body, admin_email=admin_email)

    return jsonify(
        {
            "success": True,
            "sent_to": to_email,
            "smtp_enabled": enabled,
            "email_dispatched": dispatched if enabled else False,
        }
    ), 200
