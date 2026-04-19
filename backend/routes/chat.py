"""
Chat routes for buyer–farmer messaging.
"""
from flask import Blueprint, request, jsonify
from models.chat import Conversation, Message
from models.product import Product
from models.user import User
from models.farmer_profile import FarmerProfile
from utils.account_access import is_rejected_user
import logging

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


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

        return jsonify({"success": True, "message": msg}), 201
    except Exception as e:
        logger.error(f"send_message error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to send message"}), 500

