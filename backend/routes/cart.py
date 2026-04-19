"""
Cart routes (buyer commerce).
"""
from flask import Blueprint, request, jsonify
from models.user import User
from database import execute_query
from utils.account_access import is_rejected_user
import logging

logger = logging.getLogger(__name__)

cart_bp = Blueprint("cart", __name__, url_prefix="/api/cart")


def _get_current_user():
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
        logger.error("cart._get_current_user: %s", e, exc_info=True)
        return None, "Could not resolve user", 500


def _has_role(user_id: str, user_obj: dict, role: str) -> bool:
    try:
        roles = User.get_user_roles(user_id) or []
        if role in roles:
            return True
    except Exception:
        pass
    raw = (user_obj.get("role") or "").lower()
    return role in [r.strip() for r in raw.split(",") if r.strip()]


def _ensure_active_cart(user_id: str):
    cart = execute_query(
        """
        SELECT id, status, created_at, updated_at
        FROM carts
        WHERE buyer_user_id = %s::uuid AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
        fetch_one=True,
    )
    if cart:
        return dict(cart)

    created = execute_query(
        """
        INSERT INTO carts (buyer_user_id, status)
        VALUES (%s::uuid, 'active')
        RETURNING id, status, created_at, updated_at
        """,
        (user_id,),
        fetch_one=True,
    )
    return dict(created) if created else None


def _cart_payload(cart_id: str):
    cart = execute_query(
        """
        SELECT id, buyer_user_id, status, created_at, updated_at
        FROM carts
        WHERE id = %s::uuid
        """,
        (cart_id,),
        fetch_one=True,
    )
    if not cart:
        return None

    items = execute_query(
        """
        SELECT ci.id,
               ci.product_id,
               ci.quantity,
               ci.unit_price_snapshot,
               ci.created_at,
               p.name AS product_name,
               p.category AS product_category,
               p.product_type,
               p.measurement_metric,
               p.image_url,
               p.price,
               p.price_min,
               p.price_max,
               p.farmer_profile_id AS seller_profile_id,
               fp.farm_name AS seller_name
        FROM cart_items ci
        INNER JOIN products p ON p.id = ci.product_id
        LEFT JOIN farmer_profiles fp ON fp.id = p.farmer_profile_id
        WHERE ci.cart_id = %s::uuid
        ORDER BY ci.created_at DESC
        """,
        (cart_id,),
        fetch_all=True,
    )
    out_items = []
    total = 0.0
    for r in items or []:
        d = dict(r)
        d["id"] = str(d["id"])
        d["product_id"] = str(d["product_id"])
        d["seller_profile_id"] = str(d["seller_profile_id"])
        qty = int(d.get("quantity") or 0)
        unit = float(d.get("unit_price_snapshot") or d.get("price") or d.get("price_min") or 0)
        line = qty * unit
        d["line_total"] = line
        total += line
        out_items.append(d)

    return {
        "cart": {
            "id": str(cart["id"]),
            "buyer_user_id": str(cart["buyer_user_id"]),
            "status": cart["status"],
            "created_at": str(cart["created_at"]) if cart.get("created_at") else None,
            "updated_at": str(cart["updated_at"]) if cart.get("updated_at") else None,
        },
        "items": out_items,
        "summary": {
            "item_count": sum(int(i.get("quantity") or 0) for i in out_items),
            "total_amount": round(total, 2),
        },
    }


@cart_bp.route("", methods=["GET"])
def get_cart():
    firebase_uid = request.args.get("firebase_uid") or request.headers.get("X-Firebase-Uid")
    if not firebase_uid:
        return jsonify({"error": "firebase_uid is required"}), 400
    try:
        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_id = str(user["id"])
        if not _has_role(user_id, user, "buyer"):
            return jsonify({"error": "Buyer role required"}), 403

        cart = _ensure_active_cart(user_id)
        if not cart:
            return jsonify({"error": "Could not create cart"}), 500
        payload = _cart_payload(str(cart["id"]))
        return jsonify({"success": True, **payload}), 200
    except Exception as e:
        logger.error("get_cart: %s", e, exc_info=True)
        return jsonify({"error": "Failed to load cart"}), 500


@cart_bp.route("/items", methods=["POST"])
def add_item():
    user, err, code = _get_current_user()
    if err:
        return jsonify({"error": err}), code
    user_id = str(user["id"])
    if is_rejected_user(user.get("firebase_uid")):
        return jsonify({"error": "Your account is rejected. You cannot perform cart actions."}), 403
    if not _has_role(user_id, user, "buyer"):
        return jsonify({"error": "Buyer role required"}), 403

    data = request.get_json() or {}
    product_id = (data.get("product_id") or "").strip()
    try:
        quantity = int(data.get("quantity") or 1)
    except ValueError:
        quantity = 1
    if not product_id:
        return jsonify({"error": "product_id is required"}), 400
    if quantity < 1:
        return jsonify({"error": "quantity must be >= 1"}), 400

    try:
        cart = _ensure_active_cart(user_id)
        if not cart:
            return jsonify({"error": "Could not create cart"}), 500

        prod = execute_query(
            "SELECT id, price, price_min FROM products WHERE id = %s::uuid",
            (product_id,),
            fetch_one=True,
        )
        if not prod:
            return jsonify({"error": "Product not found"}), 404
        unit_price = prod.get("price") if prod.get("price") is not None else prod.get("price_min")

        row = execute_query(
            """
            INSERT INTO cart_items (cart_id, product_id, quantity, unit_price_snapshot)
            VALUES (%s::uuid, %s::uuid, %s, %s)
            ON CONFLICT (cart_id, product_id)
            DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
            RETURNING id
            """,
            (str(cart["id"]), product_id, quantity, unit_price),
            fetch_one=True,
        )
        payload = _cart_payload(str(cart["id"]))
        return jsonify({"success": True, "item_id": str(row["id"]) if row else None, **payload}), 201
    except Exception as e:
        logger.error("add_item: %s", e, exc_info=True)
        return jsonify({"error": "Failed to add item"}), 500


@cart_bp.route("/items/<item_id>", methods=["PUT"])
def update_item(item_id):
    user, err, code = _get_current_user()
    if err:
        return jsonify({"error": err}), code
    user_id = str(user["id"])
    if is_rejected_user(user.get("firebase_uid")):
        return jsonify({"error": "Your account is rejected. You cannot perform cart actions."}), 403
    if not _has_role(user_id, user, "buyer"):
        return jsonify({"error": "Buyer role required"}), 403

    data = request.get_json() or {}
    try:
        quantity = int(data.get("quantity") or 1)
    except ValueError:
        return jsonify({"error": "quantity must be an integer"}), 400
    if quantity < 1:
        return jsonify({"error": "quantity must be >= 1"}), 400

    try:
        cart = _ensure_active_cart(user_id)
        if not cart:
            return jsonify({"error": "Cart not found"}), 404

        updated = execute_query(
            """
            UPDATE cart_items
            SET quantity = %s
            WHERE id = %s::uuid
              AND cart_id = %s::uuid
            RETURNING id
            """,
            (quantity, item_id, str(cart["id"])),
            fetch_one=True,
        )
        if not updated:
            return jsonify({"error": "Item not found"}), 404
        payload = _cart_payload(str(cart["id"]))
        return jsonify({"success": True, **payload}), 200
    except Exception as e:
        logger.error("update_item: %s", e, exc_info=True)
        return jsonify({"error": "Failed to update item"}), 500


@cart_bp.route("/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    user, err, code = _get_current_user()
    if err:
        return jsonify({"error": err}), code
    user_id = str(user["id"])
    if is_rejected_user(user.get("firebase_uid")):
        return jsonify({"error": "Your account is rejected. You cannot perform cart actions."}), 403
    if not _has_role(user_id, user, "buyer"):
        return jsonify({"error": "Buyer role required"}), 403

    try:
        cart = _ensure_active_cart(user_id)
        if not cart:
            return jsonify({"error": "Cart not found"}), 404

        deleted = execute_query(
            """
            DELETE FROM cart_items
            WHERE id = %s::uuid
              AND cart_id = %s::uuid
            """,
            (item_id, str(cart["id"])),
        )
        if not deleted:
            return jsonify({"error": "Item not found"}), 404
        payload = _cart_payload(str(cart["id"]))
        return jsonify({"success": True, **payload}), 200
    except Exception as e:
        logger.error("delete_item: %s", e, exc_info=True)
        return jsonify({"error": "Failed to remove item"}), 500


@cart_bp.route("/checkout", methods=["POST"])
def checkout():
    user, err, code = _get_current_user()
    if err:
        return jsonify({"error": err}), code
    user_id = str(user["id"])
    if is_rejected_user(user.get("firebase_uid")):
        return jsonify({"error": "Your account is rejected. You cannot perform checkout."}), 403
    if not _has_role(user_id, user, "buyer"):
        return jsonify({"error": "Buyer role required"}), 403

    try:
        cart = execute_query(
            """
            SELECT id
            FROM carts
            WHERE buyer_user_id = %s::uuid AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
            fetch_one=True,
        )
        if not cart:
            return jsonify({"error": "No active cart"}), 400
        cart_id = str(cart["id"])

        rows = execute_query(
            """
            SELECT ci.product_id,
                   ci.quantity,
                   COALESCE(ci.unit_price_snapshot, p.price, p.price_min, 0) AS unit_price,
                   p.farmer_profile_id AS seller_profile_id
            FROM cart_items ci
            INNER JOIN products p ON p.id = ci.product_id
            WHERE ci.cart_id = %s::uuid
            """,
            (cart_id,),
            fetch_all=True,
        )
        if not rows:
            return jsonify({"error": "Cart is empty"}), 400

        by_seller = {}
        for r in rows:
            d = dict(r)
            sid = str(d["seller_profile_id"])
            by_seller.setdefault(sid, []).append(d)

        created_orders = []
        for seller_profile_id, items in by_seller.items():
            total = sum(int(i["quantity"]) * float(i["unit_price"] or 0) for i in items)
            order = execute_query(
                """
                INSERT INTO orders (buyer_user_id, seller_profile_id, status, total_amount)
                VALUES (%s::uuid, %s::uuid, 'pending', %s)
                RETURNING id, status, total_amount, created_at, updated_at
                """,
                (user_id, seller_profile_id, total),
                fetch_one=True,
            )
            if not order:
                raise RuntimeError("Failed to create order")
            order_id = str(order["id"])

            for it in items:
                execute_query(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price_snapshot)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    """,
                    (order_id, str(it["product_id"]), int(it["quantity"]), float(it["unit_price"] or 0)),
                )

            created_orders.append(
                {
                    "id": order_id,
                    "status": order["status"],
                    "total_amount": float(order["total_amount"]),
                    "seller_profile_id": seller_profile_id,
                    "created_at": str(order["created_at"]) if order.get("created_at") else None,
                }
            )

        execute_query(
            "UPDATE carts SET status = 'checked_out' WHERE id = %s::uuid",
            (cart_id,),
        )
        execute_query(
            "DELETE FROM cart_items WHERE cart_id = %s::uuid",
            (cart_id,),
        )

        # New empty active cart for continued shopping
        _ensure_active_cart(user_id)

        return jsonify({"success": True, "orders": created_orders}), 201
    except Exception as e:
        logger.error("checkout: %s", e, exc_info=True)
        return jsonify({"error": "Checkout failed"}), 500

