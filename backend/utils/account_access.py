"""
Account access helpers for cross-route policy checks.
"""
from database import execute_query


def is_rejected_user(firebase_uid):
    """Return True when either seller or buyer profile is rejected."""
    if not firebase_uid:
        return False
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
        fetch_one=True,
    )
    if not row:
        return False
    farmer_status = (row.get("certification_status") or "").lower()
    buyer_status = (row.get("verification_status") or "").lower()
    return farmer_status == "rejected" or buyer_status == "rejected"

