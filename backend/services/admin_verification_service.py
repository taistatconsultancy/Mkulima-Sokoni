"""
Admin verification: update farmer/buyer profile status + audit rows.
"""
from models.user import User
from models.farmer_profile import FarmerProfile
from models.buyer_profile import BuyerProfile
from models.verification_audit import VerificationAudit
from database import execute_query
import logging

logger = logging.getLogger(__name__)


def _role_set(user_row, roles_from_table):
    roles = set(r for r in (roles_from_table or []) if r)
    raw = (user_row.get('role') or '') if user_row else ''
    for part in raw.split(','):
        p = part.strip().lower()
        if p:
            roles.add(p)
    return roles


def _is_farmer_complete(profile_row):
    if not profile_row:
        return False
    return bool(
        str(profile_row.get('farm_name') or '').strip() and
        str(profile_row.get('location') or '').strip() and
        str(profile_row.get('county') or '').strip() and
        str(profile_row.get('national_id') or '').strip()
    )


def _is_buyer_complete(profile_row):
    if not profile_row:
        return False
    return bool(
        str(profile_row.get('company_name') or '').strip() and
        str(profile_row.get('location') or '').strip() and
        str(profile_row.get('county') or '').strip() and
        str(profile_row.get('national_id') or '').strip()
    )


def apply_verification_change(
    user_id,
    action,
    reason,
    actor_decoded,
    actor_email=None,
):
    """
    action: 'approve' | 'reject'
    Returns dict with keys: updated_profiles (list), audits (list)
    Raises ValueError on bad input or nothing to update.
    """
    action = (action or '').lower().strip()
    if action not in ('approve', 'reject'):
        raise ValueError('action must be approve or reject')
    if action == 'reject' and not (reason or '').strip():
        raise ValueError('reason is required when rejecting')

    new_status = 'verified' if action == 'approve' else 'rejected'
    user = User.get_user_by_id(user_id)
    if not user:
        raise ValueError('User not found')

    uid_str = str(user['id'])
    role_names = User.get_user_roles(uid_str)
    roles = _role_set(user, role_names)

    actor_uid = actor_decoded.get('uid') if actor_decoded else None
    admin_email = actor_email or actor_decoded.get('email')

    has_seller = bool({'farmer', 'agro-dealer'} & roles)
    has_buyer = 'buyer' in roles

    updated = []
    audits = []

    seller_profile_id = None
    if has_seller and FarmerProfile.profile_exists(uid_str):
        fp = FarmerProfile.get_profile_by_user_id(uid_str)
        seller_profile_id = fp.get('id') if fp else None
        if action == 'approve' and not _is_farmer_complete(fp):
            raise ValueError('Farmer profile is incomplete. Complete required profile settings before verification.')
        prev = fp.get('certification_status') if fp else None
        FarmerProfile.update_profile(uid_str, certification_status=new_status)
        row = VerificationAudit.insert(
            user_id=uid_str,
            profile_kind='farmer',
            previous_status=prev,
            new_status=new_status,
            reason=reason if action == 'reject' else None,
            actor_type='admin',
            actor_email=admin_email,
            actor_firebase_uid=actor_uid,
        )
        updated.append('farmer_profile')
        audits.append(dict(row) if row else None)

    if has_buyer and BuyerProfile.profile_exists(uid_str):
        bp = BuyerProfile.get_profile_by_user_id(uid_str)
        if action == 'approve' and not _is_buyer_complete(bp):
            raise ValueError('Buyer profile is incomplete. Complete required profile settings before verification.')
        prev = bp.get('verification_status') if bp else None
        BuyerProfile.update_profile(uid_str, verification_status=new_status)
        row = VerificationAudit.insert(
            user_id=uid_str,
            profile_kind='buyer',
            previous_status=prev,
            new_status=new_status,
            reason=reason if action == 'reject' else None,
            actor_type='admin',
            actor_email=admin_email,
            actor_firebase_uid=actor_uid,
        )
        updated.append('buyer_profile')
        audits.append(dict(row) if row else None)

    if action == 'reject' and seller_profile_id:
        try:
            execute_query(
                """
                UPDATE products
                SET status = 'draft', updated_at = CURRENT_TIMESTAMP
                WHERE farmer_profile_id = %s::uuid
                  AND status = 'active'
                """,
                (str(seller_profile_id),),
            )
        except Exception as exc:
            logger.warning('Failed to downgrade seller products on reject: %s', exc)

    if not updated:
        raise ValueError('No farmer or buyer profile exists for this user')

    return {'updated_profiles': updated, 'audits': audits, 'new_status': new_status}
