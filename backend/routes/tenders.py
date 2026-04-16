"""
Tenders routes (buyer demand posts + seller bids).
"""
from flask import Blueprint, request, jsonify
from models.user import User
from models.farmer_profile import FarmerProfile
from database import execute_query
import logging

logger = logging.getLogger(__name__)

tenders_bp = Blueprint("tenders", __name__, url_prefix="/api/tenders")


def _get_user_from_anywhere():
    data = request.get_json(silent=True) or {}
    firebase_uid = (
        request.args.get("firebase_uid")
        or data.get("firebase_uid")
        or request.headers.get("X-Firebase-Uid")
    )
    if not firebase_uid:
        return None, None, "Missing firebase_uid", 401
    user = User.get_user_by_firebase_uid(firebase_uid)
    if not user:
        return None, None, "User not found", 404
    return user, firebase_uid, None, None


def _has_any_role(user_id: str, user_obj: dict, roles: list[str]) -> bool:
    try:
        stored = set(User.get_user_roles(user_id) or [])
        if stored.intersection(roles):
            return True
    except Exception:
        pass
    raw = (user_obj.get("role") or "").lower()
    raw_roles = {r.strip() for r in raw.split(",") if r.strip()}
    return bool(raw_roles.intersection(set(roles)))


def _seller_profile_id_for(firebase_uid: str):
    user_id = FarmerProfile.get_user_id_by_firebase_uid(firebase_uid)
    if not user_id:
        return None
    profile = FarmerProfile.get_profile_by_user_id(user_id)
    return str(profile.get("id")) if profile else None


def _serialize_tender_rows(rows):
    tenders = []
    for r in rows or []:
        d = dict(r)
        if d.get("id"):
            d["id"] = str(d["id"])
        if d.get("buyer_user_id"):
            d["buyer_user_id"] = str(d["buyer_user_id"])
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        if d.get("updated_at"):
            d["updated_at"] = str(d["updated_at"])
        if d.get("deadline"):
            d["deadline"] = str(d["deadline"])
        tenders.append(d)
    return tenders


@tenders_bp.route("", methods=["GET"])
def list_tenders():
    try:
        user, firebase_uid, err, code = _get_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])

        if _has_any_role(user_id, user, ["buyer"]):
            rows = execute_query(
                """
                SELECT t.*,
                       (SELECT COUNT(*) FROM tender_bids tb WHERE tb.tender_id = t.id) AS bid_count
                FROM tenders t
                WHERE t.buyer_user_id = %s::uuid
                ORDER BY t.created_at DESC
                """,
                (user_id,),
                fetch_all=True,
            )
            return jsonify({"success": True, "tenders": _serialize_tender_rows(rows)}), 200

        if not _has_any_role(user_id, user, ["farmer", "agro-dealer"]):
            return jsonify({"error": "Unauthorized"}), 403

        seller_profile_id = _seller_profile_id_for(firebase_uid)
        if not seller_profile_id:
            return jsonify({"error": "Seller profile not found"}), 404

        rows = execute_query(
            """
            SELECT t.*,
                   (SELECT COUNT(*) FROM tender_bids tb WHERE tb.tender_id = t.id) AS bid_count,
                   tb.id AS my_bid_id,
                   tb.price AS my_bid_price,
                   tb.message AS my_bid_message,
                   tb.status AS my_bid_status
            FROM tenders t
            LEFT JOIN tender_bids tb
              ON tb.tender_id = t.id AND tb.seller_profile_id = %s::uuid
            WHERE t.status = 'open'
            ORDER BY t.created_at DESC
            """,
            (seller_profile_id,),
            fetch_all=True,
        )
        return jsonify({"success": True, "tenders": _serialize_tender_rows(rows)}), 200
    except Exception as e:
        logger.error("list_tenders: %s", e, exc_info=True)
        return jsonify({"error": "Failed to load tenders"}), 500


@tenders_bp.route("", methods=["POST"])
def create_tender():
    try:
        user, _firebase_uid, err, code = _get_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])
        if not _has_any_role(user_id, user, ["buyer"]):
            return jsonify({"error": "Buyer role required"}), 403

        data = request.get_json() or {}
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400

        tender = execute_query(
            """
            INSERT INTO tenders (
                buyer_user_id, title, product_category, quantity, unit, location,
                deadline, notes, status
            )
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, 'open')
            RETURNING *
            """,
            (
                user_id,
                title,
                data.get("product_category"),
                data.get("quantity"),
                data.get("unit"),
                data.get("location"),
                data.get("deadline"),
                data.get("notes"),
            ),
            fetch_one=True,
        )
        out = dict(tender) if tender else None
        if out and out.get("id"):
            out["id"] = str(out["id"])
        return jsonify({"success": True, "tender": out}), 201
    except Exception as e:
        logger.error("create_tender: %s", e, exc_info=True)
        return jsonify({"error": "Failed to create tender"}), 500


@tenders_bp.route("/<tender_id>/bids", methods=["POST"])
def submit_bid(tender_id):
    try:
        user, firebase_uid, err, code = _get_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])
        if not _has_any_role(user_id, user, ["farmer", "agro-dealer"]):
            return jsonify({"error": "Seller role required"}), 403

        seller_profile_id = _seller_profile_id_for(firebase_uid)
        if not seller_profile_id:
            return jsonify({"error": "Seller profile not found"}), 404

        tender = execute_query(
            "SELECT id, status FROM tenders WHERE id = %s::uuid",
            (tender_id,),
            fetch_one=True,
        )
        if not tender:
            return jsonify({"error": "Tender not found"}), 404
        if (tender.get("status") or "").lower() != "open":
            return jsonify({"error": "Tender is closed"}), 400

        data = request.get_json() or {}
        try:
            price = float(data.get("price"))
        except Exception:
            return jsonify({"error": "price is required"}), 400
        message = (data.get("message") or "").strip() or None

        bid = execute_query(
            """
            INSERT INTO tender_bids (tender_id, seller_profile_id, price, message, status)
            VALUES (%s::uuid, %s::uuid, %s, %s, 'submitted')
            ON CONFLICT (tender_id, seller_profile_id)
            DO UPDATE SET price = EXCLUDED.price, message = EXCLUDED.message, status = 'submitted'
            RETURNING *
            """,
            (tender_id, seller_profile_id, price, message),
            fetch_one=True,
        )
        out = dict(bid) if bid else None
        if out and out.get("id"):
            out["id"] = str(out["id"])
        return jsonify({"success": True, "bid": out}), 201
    except Exception as e:
        logger.error("submit_bid: %s", e, exc_info=True)
        return jsonify({"error": "Failed to submit bid"}), 500


@tenders_bp.route("/<tender_id>/bids", methods=["GET"])
def list_bids(tender_id):
    try:
        user, firebase_uid, err, code = _get_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])

        tender = execute_query(
            "SELECT id, buyer_user_id FROM tenders WHERE id = %s::uuid",
            (tender_id,),
            fetch_one=True,
        )
        if not tender:
            return jsonify({"error": "Tender not found"}), 404

        is_buyer_owner = str(tender["buyer_user_id"]) == user_id and _has_any_role(user_id, user, ["buyer"])
        is_seller = _has_any_role(user_id, user, ["farmer", "agro-dealer"])

        if not is_buyer_owner and not is_seller:
            return jsonify({"error": "Unauthorized"}), 403

        if is_buyer_owner:
            rows = execute_query(
                """
                SELECT tb.*, fp.farm_name, fp.location,
                       u.first_name, u.last_name
                FROM tender_bids tb
                LEFT JOIN farmer_profiles fp ON fp.id = tb.seller_profile_id
                LEFT JOIN users u ON u.id = fp.user_id
                WHERE tb.tender_id = %s::uuid
                ORDER BY tb.created_at DESC
                """,
                (tender_id,),
                fetch_all=True,
            )
        else:
            seller_profile_id = _seller_profile_id_for(firebase_uid)
            if not seller_profile_id:
                return jsonify({"error": "Seller profile not found"}), 404
            rows = execute_query(
                """
                SELECT tb.*
                FROM tender_bids tb
                WHERE tb.tender_id = %s::uuid AND tb.seller_profile_id = %s::uuid
                """,
                (tender_id, seller_profile_id),
                fetch_all=True,
            )

        bids = []
        for r in rows or []:
            d = dict(r)
            if d.get("id"):
                d["id"] = str(d["id"])
            if d.get("tender_id"):
                d["tender_id"] = str(d["tender_id"])
            if d.get("seller_profile_id"):
                d["seller_profile_id"] = str(d["seller_profile_id"])
            if d.get("created_at"):
                d["created_at"] = str(d["created_at"])
            bids.append(d)

        return jsonify({"success": True, "bids": bids}), 200
    except Exception as e:
        logger.error("list_bids: %s", e, exc_info=True)
        return jsonify({"error": "Failed to load bids"}), 500


@tenders_bp.route("/<tender_id>", methods=["PUT"])
def close_tender(tender_id):
    try:
        user, _firebase_uid, err, code = _get_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])
        if not _has_any_role(user_id, user, ["buyer"]):
            return jsonify({"error": "Buyer role required"}), 403

        updated = execute_query(
            """
            UPDATE tenders
            SET status = 'closed'
            WHERE id = %s::uuid AND buyer_user_id = %s::uuid
            RETURNING id, status, updated_at
            """,
            (tender_id, user_id),
            fetch_one=True,
        )
        if not updated:
            return jsonify({"error": "Tender not found"}), 404

        return jsonify(
            {
                "success": True,
                "tender": {
                    "id": str(updated["id"]),
                    "status": updated["status"],
                    "updated_at": str(updated["updated_at"]) if updated.get("updated_at") else None,
                },
            }
        ), 200
    except Exception as e:
        logger.error("close_tender: %s", e, exc_info=True)
        return jsonify({"error": "Failed to close tender"}), 500

