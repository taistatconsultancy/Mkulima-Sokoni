"""
Orders routes (buyer + seller).
"""
from flask import Blueprint, request, jsonify
from models.user import User
from models.farmer_profile import FarmerProfile
from database import execute_query, DatabaseOverloadError
import logging
import time

logger = logging.getLogger(__name__)

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")
_ORDERS_CACHE_TTL_SEC = 5
_orders_cache: dict[str, tuple[float, dict]] = {}


def _get_current_user_from_anywhere():
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


def _serialize_order_rows(order_rows):
    orders = []
    for r in order_rows or []:
        d = dict(r)
        if d.get("id"):
            d["id"] = str(d["id"])
        if d.get("buyer_user_id"):
            d["buyer_user_id"] = str(d["buyer_user_id"])
        if d.get("seller_profile_id"):
            d["seller_profile_id"] = str(d["seller_profile_id"])
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        if d.get("updated_at"):
            d["updated_at"] = str(d["updated_at"])
        orders.append(d)
    return orders


def _cache_get(key: str):
    item = _orders_cache.get(key)
    if not item:
        return None
    ts, payload = item
    if (time.time() - ts) > _ORDERS_CACHE_TTL_SEC:
        _orders_cache.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict):
    _orders_cache[key] = (time.time(), payload)


def _attach_items_batched(orders: list[dict]):
    if not orders:
        return
    order_ids = [o["id"] for o in orders if o.get("id")]
    if not order_ids:
        return
    item_rows = execute_query(
        """
        SELECT oi.id,
               oi.order_id,
               oi.product_id,
               oi.quantity,
               oi.unit_price_snapshot,
               p.name AS product_name,
               p.measurement_metric,
               p.image_url
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id::text = ANY(%s)
        ORDER BY oi.id
        """,
        (order_ids,),
        fetch_all=True,
    )
    by_order = {oid: [] for oid in order_ids}
    for it in item_rows or []:
        d = dict(it)
        d["id"] = str(d["id"])
        order_id = str(d.get("order_id")) if d.get("order_id") else None
        if d.get("product_id"):
            d["product_id"] = str(d["product_id"])
        d.pop("order_id", None)
        if order_id:
            by_order.setdefault(order_id, []).append(d)
    for o in orders:
        o["items"] = by_order.get(o.get("id"), [])


@orders_bp.route("/buyer", methods=["GET"])
def buyer_orders():
    try:
        user, _firebase_uid, err, code = _get_current_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])
        if not _has_any_role(user_id, user, ["buyer"]):
            return jsonify({"error": "Buyer role required"}), 403

        cache_key = f"buyer:{user_id}"
        cached = _cache_get(cache_key)
        if cached:
            return jsonify(cached), 200

        rows = execute_query(
            """
            SELECT o.*,
                   fp.farm_name AS seller_name,
                   fp.location AS seller_location
            FROM orders o
            LEFT JOIN farmer_profiles fp ON fp.id = o.seller_profile_id
            WHERE o.buyer_user_id = %s::uuid
            ORDER BY o.created_at DESC
            """,
            (user_id,),
            fetch_all=True,
        )
        orders = _serialize_order_rows(rows)
        _attach_items_batched(orders)
        payload = {"success": True, "orders": orders}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200
    except DatabaseOverloadError:
        return jsonify({"error": "Service is busy. Please retry shortly."}), 503
    except Exception as e:
        logger.error("buyer_orders: %s", e, exc_info=True)
        return jsonify({"error": "Failed to load orders"}), 500


@orders_bp.route("/seller", methods=["GET"])
def seller_orders():
    try:
        user, firebase_uid, err, code = _get_current_user_from_anywhere()
        if err:
            return jsonify({"error": err}), code
        user_id = str(user["id"])
        if not _has_any_role(user_id, user, ["farmer", "agro-dealer"]):
            return jsonify({"error": "Seller role required"}), 403

        seller_profile_id = _seller_profile_id_for(firebase_uid)
        if not seller_profile_id:
            return jsonify({"error": "Seller profile not found"}), 404

        cache_key = f"seller:{seller_profile_id}"
        cached = _cache_get(cache_key)
        if cached:
            return jsonify(cached), 200

        rows = execute_query(
            """
            SELECT o.*,
                   u.email AS buyer_email,
                   u.phone_number AS buyer_phone
            FROM orders o
            LEFT JOIN users u ON u.id = o.buyer_user_id
            WHERE o.seller_profile_id = %s::uuid
            ORDER BY o.created_at DESC
            """,
            (seller_profile_id,),
            fetch_all=True,
        )
        orders = _serialize_order_rows(rows)
        _attach_items_batched(orders)
        payload = {"success": True, "orders": orders}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200
    except DatabaseOverloadError:
        return jsonify({"error": "Service is busy. Please retry shortly."}), 503
    except Exception as e:
        logger.error("seller_orders: %s", e, exc_info=True)
        return jsonify({"error": "Failed to load seller orders"}), 500


@orders_bp.route("/<order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    try:
        data = request.get_json() or {}
        firebase_uid = data.get("firebase_uid") or request.headers.get("X-Firebase-Uid")
        if not firebase_uid:
            return jsonify({"error": "firebase_uid is required"}), 400

        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_id = str(user["id"])
        if not _has_any_role(user_id, user, ["farmer", "agro-dealer"]):
            return jsonify({"error": "Seller role required"}), 403

        seller_profile_id = _seller_profile_id_for(firebase_uid)
        if not seller_profile_id:
            return jsonify({"error": "Seller profile not found"}), 404

        status = (data.get("status") or "").strip().lower()
        if status not in ("confirmed", "completed", "cancelled"):
            return jsonify({"error": "Invalid status"}), 400

        updated = execute_query(
            """
            UPDATE orders
            SET status = %s
            WHERE id = %s::uuid AND seller_profile_id = %s::uuid
            RETURNING id, status, updated_at
            """,
            (status, order_id, seller_profile_id),
            fetch_one=True,
        )
        if not updated:
            return jsonify({"error": "Order not found"}), 404
        _orders_cache.clear()

        return jsonify(
            {
                "success": True,
                "order": {
                    "id": str(updated["id"]),
                    "status": updated["status"],
                    "updated_at": str(updated["updated_at"]) if updated.get("updated_at") else None,
                },
            }
        ), 200
    except Exception as e:
        logger.error("update_order_status: %s", e, exc_info=True)
        return jsonify({"error": "Failed to update order"}), 500

