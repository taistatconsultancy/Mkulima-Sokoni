"""
Phone sharing routes:
- Users must accept terms before they can view any phone numbers.
- A farmer/agro-dealer must also enable sharing for their own phone to be shown.
"""

from flask import Blueprint, request, jsonify
from models.user import User
import logging

logger = logging.getLogger(__name__)

phone_bp = Blueprint("phone_sharing", __name__, url_prefix="/api/phone-sharing")


def _get_uid_from_body(data):
    uid = (data or {}).get("firebase_uid") or (data or {}).get("uid")
    return str(uid).strip() if uid else None


@phone_bp.route("/settings", methods=["POST"])
def update_settings():
    """
    Update user's phone sharing settings.
    Body:
      firebase_uid (required)
      phone_number (optional)
      accept_terms (optional bool)  -> if true, records acceptance timestamp
      enable_sharing (optional bool)
    """
    try:
        data = request.get_json() or {}
        uid = _get_uid_from_body(data)
        if not uid:
            return jsonify({"error": "firebase_uid is required"}), 400

        phone_number = data.get("phone_number", None)
        accept_terms = data.get("accept_terms", None)
        enable_sharing = data.get("enable_sharing", None)

        if isinstance(phone_number, str):
            phone_number = phone_number.strip()
            if phone_number == "":
                phone_number = None

        if accept_terms is not None:
            accept_terms = bool(accept_terms)
        if enable_sharing is not None:
            enable_sharing = bool(enable_sharing)

        updated = User.update_phone_sharing_settings(
            uid,
            phone_number=phone_number,
            accept_terms=accept_terms,
            enable_sharing=enable_sharing,
        )
        if not updated:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"success": True, "settings": updated}), 200
    except Exception as e:
        logger.error(f"update_settings error: {str(e)}")
        return jsonify({"error": "Failed to update settings"}), 500


@phone_bp.route("/status/<firebase_uid>", methods=["GET"])
def status(firebase_uid):
    """
    Get phone sharing status for a user (only for self use in settings page).
    Query:
      viewer_uid (required) must match firebase_uid
    """
    try:
        viewer_uid = (request.args.get("viewer_uid") or "").strip()
        if not viewer_uid or viewer_uid != str(firebase_uid):
            return jsonify({"error": "Unauthorized"}), 403
        row = User.get_phone_sharing_status(str(firebase_uid))
        if not row:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"success": True, "settings": row}), 200
    except Exception as e:
        logger.error(f"status error: {str(e)}")
        return jsonify({"error": "Failed to load status"}), 500


@phone_bp.route("/phone/<seller_uid>", methods=["GET"])
def get_phone(seller_uid):
    """
    Resolve a seller's phone number for a viewer (server-side enforcement).
    Query:
      viewer_uid (required)

    Response:
      { available: bool, phone_number?: str, reason?: str }
    """
    try:
        viewer_uid = (request.args.get("viewer_uid") or "").strip()
        if not viewer_uid:
            return jsonify({"available": False, "reason": "sign_in_required"}), 200

        viewer = User.get_phone_sharing_status(viewer_uid)
        if not viewer:
            return jsonify({"available": False, "reason": "viewer_not_found"}), 200
        if not viewer.get("phone_terms_accepted_at"):
            return jsonify({"available": False, "reason": "terms_not_accepted"}), 200

        seller = User.get_phone_sharing_status(str(seller_uid))
        if not seller:
            return jsonify({"available": False, "reason": "seller_not_found"}), 200
        if not seller.get("phone_terms_accepted_at"):
            return jsonify({"available": False, "reason": "seller_terms_not_accepted"}), 200
        if not bool(seller.get("phone_sharing_enabled")):
            return jsonify({"available": False, "reason": "seller_not_sharing"}), 200
        if not (seller.get("phone_number") and str(seller.get("phone_number")).strip()):
            return jsonify({"available": False, "reason": "no_phone_on_file"}), 200

        return jsonify(
            {"available": True, "phone_number": str(seller.get("phone_number")).strip()}
        ), 200
    except Exception as e:
        logger.error(f"get_phone error: {str(e)}")
        return jsonify({"available": False, "reason": "error"}), 200

