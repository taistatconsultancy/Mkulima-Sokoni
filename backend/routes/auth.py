"""
Authentication routes for Phase 1
"""
from flask import Blueprint, request, jsonify
from models.user import User
from models.farmer_profile import FarmerProfile
from models.buyer_profile import BuyerProfile
from auth.firebase_auth import verify_firebase_token, get_firebase_user
from auth.admin_auth import decode_token_if_admin
from models.verification_audit import VerificationAudit, AdminImpersonationLog, AuthLoginAudit
from services.admin_verification_service import apply_verification_change
from utils.cloudinary_service import delete_image
from utils.mailer import send_welcome_email, send_account_verified_email
import logging
import uuid
import re
from urllib.parse import urlparse
from database import execute_query

logger = logging.getLogger(__name__)


def _client_ip():
    xff = request.headers.get('X-Forwarded-For') or request.headers.get('x-forwarded-for')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr


def _cloudinary_public_id_from_url(url):
    """Extract Cloudinary public_id from a delivery URL."""
    if not url or 'res.cloudinary.com' not in str(url):
        return None
    try:
        parsed = urlparse(str(url))
        parts = [p for p in parsed.path.split('/') if p]
        if 'upload' not in parts:
            return None
        upload_idx = parts.index('upload')
        public_parts = parts[upload_idx + 1:]
        if public_parts and re.match(r'^v\d+$', public_parts[0]):
            public_parts = public_parts[1:]
        if not public_parts:
            return None
        filename = public_parts[-1]
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]
        public_parts[-1] = filename
        return '/'.join(public_parts)
    except Exception:
        return None


def _purge_user_cloudinary_assets(user_id):
    """Delete known user-linked Cloudinary assets before hard delete."""
    rows = execute_query(
        """
        SELECT image_url AS url FROM products p
        INNER JOIN farmer_profiles fp ON fp.id = p.farmer_profile_id
        WHERE fp.user_id = %s::uuid
        UNION ALL
        SELECT profile_image_url AS url FROM farmer_profiles WHERE user_id = %s::uuid
        UNION ALL
        SELECT id_front_url AS url FROM farmer_profiles WHERE user_id = %s::uuid
        UNION ALL
        SELECT id_back_url AS url FROM farmer_profiles WHERE user_id = %s::uuid
        UNION ALL
        SELECT profile_selfie_url AS url FROM farmer_profiles WHERE user_id = %s::uuid
        UNION ALL
        SELECT profile_image_url AS url FROM buyer_profiles WHERE user_id = %s::uuid
        UNION ALL
        SELECT id_front_url AS url FROM buyer_profiles WHERE user_id = %s::uuid
        UNION ALL
        SELECT id_back_url AS url FROM buyer_profiles WHERE user_id = %s::uuid
        """,
        (
            str(user_id), str(user_id), str(user_id), str(user_id),
            str(user_id), str(user_id), str(user_id), str(user_id)
        ),
        fetch_all=True,
    )
    deleted = 0
    failed = 0
    seen = set()
    for row in rows or []:
        public_id = _cloudinary_public_id_from_url((row or {}).get('url'))
        if not public_id or public_id in seen:
            continue
        seen.add(public_id)
        if delete_image(public_id):
            deleted += 1
        else:
            failed += 1
    return {'deleted': deleted, 'failed': failed}


def extract_user_id(user):
    """
    Safely extract user_id from user object, ensuring it's a UUID not a timestamp
    """
    if not user:
        return None
    
    # Try to get id using different methods
    user_id = None
    if hasattr(user, 'get'):
        user_id = user.get('id')
    elif hasattr(user, '__getitem__'):
        user_id = user['id'] if 'id' in user else None
    else:
        user_id = getattr(user, 'id', None)
    
    # Validate it's a UUID, not a timestamp
    if user_id:
        # Check if it looks like a timestamp (ISO format with 'T')
        if isinstance(user_id, str) and 'T' in user_id:
            logger.error(f"CRITICAL: user_id is a timestamp '{user_id}' instead of UUID!")
            logger.error(f"User object: {user}")
            # Try to find the actual UUID in other fields
            if hasattr(user, 'keys'):
                for key in user.keys():
                    val = user[key] if hasattr(user, '__getitem__') else getattr(user, key, None)
                    if isinstance(val, str) and len(val) == 36 and val.count('-') == 4 and 'T' not in val:
                        try:
                            uuid.UUID(val)
                            logger.warning(f"Found valid UUID in key '{key}': {val}")
                            return val
                        except (ValueError, AttributeError):
                            continue
            return None
        
        # Validate it's a valid UUID format
        if isinstance(user_id, str):
            if len(user_id) == 36 and user_id.count('-') == 4 and 'T' not in user_id:
                try:
                    uuid.UUID(user_id)
                    return user_id
                except (ValueError, AttributeError):
                    logger.error(f"user_id '{user_id}' is not a valid UUID format")
                    return None
        
        return user_id
    
    return user_id

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def _normalize_role_slug(raw):
    s = str(raw or '').strip().lower().replace(' ', '')
    if s == 'agrodealer':
        return 'agro-dealer'
    return s


def _resolved_role_slugs_for_user(user):
    """
    Authoritative roles from DB: users.role (CSV) plus user_roles junction.
    Matches logic used elsewhere (e.g. tenders/cart).
    """
    if not user:
        return []
    slugs = set()
    for part in str(user.get('role') or '').split(','):
        n = _normalize_role_slug(part)
        if n:
            slugs.add(n)
    user_id = extract_user_id(user)
    if user_id:
        try:
            for r in User.get_user_roles(user_id) or []:
                n = _normalize_role_slug(r)
                if n:
                    slugs.add(n)
        except Exception as exc:
            logger.warning('get_user_roles failed in _resolved_role_slugs_for_user: %s', exc)
    priority = ['admin', 'farmer', 'agro-dealer', 'buyer']
    ordered = [x for x in priority if x in slugs]
    rest = sorted(slugs - set(priority))
    return ordered + rest


def _first_dashboard_for_slugs(slugs):
    """Same dashboard priority as frontend auth.html (extensionless paths)."""
    sset = set(slugs or [])
    order = [
        ('admin', '/admin-support'),
        ('farmer', '/farmer'),
        ('agro-dealer', '/agro-dealer'),
        ('buyer', '/buyer'),
    ]
    for slug, page in order:
        if slug in sset:
            return page
    return '/'


@auth_bp.route('/verify-dashboard-session', methods=['POST'])
def verify_dashboard_session():
    """
    Authoritative dashboard access: verifies Firebase ID token, loads user from DB,
    returns resolved roles. Cannot be satisfied by editing localStorage alone.
    Body JSON: { id_token, dashboard: 'farmer'|'buyer'|'agro-dealer' }
    """
    try:
        data = request.get_json() or {}
        id_token = data.get('id_token')
        dashboard = _normalize_role_slug(data.get('dashboard'))

        if not id_token:
            return jsonify({'error': 'id_token is required'}), 400
        if dashboard not in ('farmer', 'buyer', 'agro-dealer'):
            return jsonify({'error': 'Invalid dashboard'}), 400

        decoded = verify_firebase_token(id_token)
        if not decoded:
            return jsonify({'error': 'Invalid or expired token'}), 401

        firebase_uid = (decoded.get('uid') or '').strip()
        if not firebase_uid:
            return jsonify({'error': 'Invalid token payload'}), 401

        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        roles = _resolved_role_slugs_for_user(user)
        allowed = dashboard in set(roles)
        role_csv = ','.join(roles) if roles else (user.get('role') or '')
        redirect = _first_dashboard_for_slugs(roles)

        return jsonify({
            'success': True,
            'roles': roles,
            'role': role_csv,
            'allowed': allowed,
            'redirect': redirect,
        }), 200
    except Exception as e:
        logger.error('verify_dashboard_session: %s', e, exc_info=True)
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user
    Expects: { firebase_uid, email, phone_number, role }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        email = data.get('email')
        phone_number = data.get('phone_number')
        role = data.get('role', 'buyer')  # Default to buyer
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        
        if not firebase_uid or not email:
            return jsonify({'error': 'firebase_uid and email are required'}), 400
        if not phone_number or not str(phone_number).strip():
            return jsonify({'error': 'phone_number is required'}), 400
        
        # Check if user already exists
        if User.user_exists(firebase_uid):
            return jsonify({'error': 'User already exists'}), 409
        
        # Create user
        user = User.create_user(firebase_uid, email, phone_number, role, first_name, last_name)
        
        # Extract and validate user_id
        user_id = extract_user_id(user)
        if not user_id:
            logger.error(f"Failed to extract user_id after user creation: {user}")
            return jsonify({'error': 'Failed to create user'}), 500
        
        # If multi-role (e.g., "farmer,buyer"), add to user_roles table
        roles_list = []
        if ',' in role:
            roles_list = [r.strip() for r in role.split(',')]
            for r in roles_list:
                User.add_user_role(user_id, r)
        else:
            roles_list = [role]
            User.add_user_role(user_id, role)
        
        # Automatically create empty profiles based on roles
        try:
            if 'farmer' in roles_list or 'agro-dealer' in roles_list:
                if not FarmerProfile.profile_exists(user_id):
                    FarmerProfile.create_profile(
                        user_id,
                        farm_name=None,
                        location=None,
                        county=None
                    )
            
            if 'buyer' in roles_list:
                if not BuyerProfile.profile_exists(user_id):
                    BuyerProfile.create_profile(
                        user_id,
                        company_name=None,
                        location=None,
                        county=None
                    )
        except Exception as e:
            logger.warning(f"Could not auto-create profiles: {str(e)}")

        # Send welcome email (best-effort)
        try:
            send_welcome_email(email, first_name=first_name)
        except Exception as e:
            logger.warning("Welcome email skipped/failed: %s", e)
        
        return jsonify({
            'success': True,
            'user': user,
            'message': 'User registered successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login user and update latest_sign_in
    Expects: { id_token } (Firebase ID token)
    """
    try:
        data = request.get_json()
        id_token = data.get('id_token')
        
        if not id_token:
            return jsonify({'error': 'id_token is required'}), 400
        
        # Verify Firebase token
        decoded_token = verify_firebase_token(id_token)
        if not decoded_token:
            AuthLoginAudit.log(success=False, client_ip=_client_ip())
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        firebase_uid = decoded_token['uid']
        email = decoded_token.get('email')
        User.update_email_verified(firebase_uid, decoded_token.get('email_verified', False))
        
        # Check if user exists in database
        user = User.get_user_by_firebase_uid(firebase_uid)
        
        if not user:
            # New user - return flag for role selection
            first_name = decoded_token.get('first_name')
            last_name = decoded_token.get('last_name')
            AuthLoginAudit.log(firebase_uid=firebase_uid, email=email, success=True, client_ip=_client_ip())
            return jsonify({
                'success': True,
                'new_user': True,
                'firebase_uid': firebase_uid,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'message': 'User not found. Please complete registration.'
            }), 200
        
        # Update latest_sign_in
        User.update_latest_sign_in(firebase_uid)
        AuthLoginAudit.log(firebase_uid=firebase_uid, email=email, success=True, client_ip=_client_ip())
        
        # Extract and validate user_id
        user_id = extract_user_id(user)
        if not user_id:
            logger.error(f"Failed to extract user_id in login: {user}")
            return jsonify({'error': 'Invalid user data'}), 500
        
        # Get all roles if using user_roles table
        user_roles = User.get_user_roles(user_id)
        if user_roles:
            user['roles'] = user_roles
        
        return jsonify({
            'success': True,
            'new_user': False,
            'user': user,
            'message': 'Login successful'
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/google-signin', methods=['POST'])
def google_signin():
    """
    Handle Google sign-in
    Expects: { id_token }
    Returns: user data or new_user flag for role selection
    """
    try:
        data = request.get_json()
        id_token = data.get('id_token')
        
        if not id_token:
            return jsonify({'error': 'id_token is required'}), 400
        
        # Verify Firebase token
        decoded_token = verify_firebase_token(id_token)
        if not decoded_token:
            AuthLoginAudit.log(success=False, client_ip=_client_ip())
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        firebase_uid = decoded_token['uid']
        email = decoded_token.get('email')
        first_name = decoded_token.get('first_name')
        last_name = decoded_token.get('last_name')
        User.update_email_verified(firebase_uid, decoded_token.get('email_verified', False))
        
        # Check if user exists
        user = User.get_user_by_firebase_uid(firebase_uid)
        
        if not user:
            # New user - needs role selection (cold start)
            AuthLoginAudit.log(firebase_uid=firebase_uid, email=email, success=True, client_ip=_client_ip())
            return jsonify({
                'success': True,
                'new_user': True,
                'firebase_uid': firebase_uid,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'message': 'Please select your role to continue'
            }), 200
        
        # Existing user - update sign-in time
        User.update_latest_sign_in(firebase_uid)
        AuthLoginAudit.log(firebase_uid=firebase_uid, email=email, success=True, client_ip=_client_ip())
        
        # Extract and validate user_id
        user_id = extract_user_id(user)
        if not user_id:
            logger.error(f"Failed to extract user_id in google_signin: {user}")
            return jsonify({'error': 'Invalid user data'}), 500
        
        # Get all roles
        user_roles = User.get_user_roles(user_id)
        if user_roles:
            user['roles'] = user_roles
        
        return jsonify({
            'success': True,
            'new_user': False,
            'user': user,
            'message': 'Sign-in successful'
        }), 200
        
    except Exception as e:
        logger.error(f"Google sign-in error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/complete-registration', methods=['POST'])
def complete_registration():
    """
    Complete registration for new users (especially Google sign-in)
    Expects: { firebase_uid, email, phone_number, role }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        email = data.get('email')
        phone_number = data.get('phone_number')
        role = data.get('role')  # Can be single role or comma-separated
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        
        if not firebase_uid or not email or not role:
            return jsonify({'error': 'firebase_uid, email, and role are required'}), 400
        if not phone_number or not str(phone_number).strip():
            return jsonify({'error': 'phone_number is required'}), 400
        
        # Check if user already exists
        if User.user_exists(firebase_uid):
            # User exists, just update role if needed
            user = User.update_user_role(firebase_uid, role)
            # Update latest_sign_in for existing user completing registration
            User.update_latest_sign_in(firebase_uid)
        else:
            # Create new user (created_at and latest_sign_in will both be set to CURRENT_TIMESTAMP)
            user = User.create_user(firebase_uid, email, phone_number, role, first_name, last_name)
        
        # Extract and validate user_id
        user_id = extract_user_id(user)
        if not user_id:
            logger.error(f"Failed to extract user_id in complete_registration: {user}")
            return jsonify({'error': 'Invalid user data'}), 500
        
        # Handle multi-role support
        roles_list = []
        if ',' in role:
            roles_list = [r.strip() for r in role.split(',')]
            for r in roles_list:
                User.add_user_role(user_id, r)
        else:
            roles_list = [role]
            User.add_user_role(user_id, role)
        
        # Automatically create empty profiles based on roles
        try:
            if 'farmer' in roles_list or 'agro-dealer' in roles_list:
                if not FarmerProfile.profile_exists(user_id):
                    FarmerProfile.create_profile(
                        user_id,
                        farm_name=None,
                        location=None,
                        county=None
                    )
            
            if 'buyer' in roles_list:
                if not BuyerProfile.profile_exists(user_id):
                    BuyerProfile.create_profile(
                        user_id,
                        company_name=None,
                        location=None,
                        county=None
                    )
        except Exception as e:
            logger.warning(f"Could not auto-create profiles: {str(e)}")

        # Send welcome email for newly created accounts (best-effort)
        # If the user already existed, this will still be best-effort but harmless.
        try:
            send_welcome_email(email, first_name=first_name)
        except Exception as e:
            logger.warning("Welcome email skipped/failed: %s", e)
        
        # Get all roles
        user_roles = User.get_user_roles(user_id)
        if user_roles:
            user['roles'] = user_roles
        
        return jsonify({
            'success': True,
            'user': user,
            'message': 'Registration completed successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Complete registration error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/user/<firebase_uid>', methods=['GET'])
def get_user(firebase_uid):
    """
    Get user by Firebase UID
    """
    try:
        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Extract and validate user_id
        user_id = extract_user_id(user)
        if not user_id:
            logger.error(f"Failed to extract user_id in get_user: {user}")
            return jsonify({'error': 'Invalid user data'}), 500
        
        # Get all roles
        user_roles = User.get_user_roles(user_id)
        if user_roles:
            user['roles'] = user_roles
        
        return jsonify({
            'success': True,
            'user': user
        }), 200
        
    except Exception as e:
        logger.error(f"Get user error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/user-by-email', methods=['GET'])
def get_user_by_email():
    """
    Get user by email (for admin/super-user client access).
    Query param: ?email=user@example.com
    Requires admin Firebase token.
    """
    try:
        _decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        email = request.args.get('email', '').strip()
        if not email:
            return jsonify({'error': 'email query parameter is required'}), 400

        user = User.get_user_by_email(email)
        if not user:
            return jsonify({'error': 'No user found with that email'}), 404

        user_id = extract_user_id(user)
        if user_id:
            user_roles = User.get_user_roles(user_id)
            if user_roles:
                user['roles'] = user_roles

        return jsonify({'success': True, 'user': user}), 200

    except Exception as e:
        logger.error(f"Get user by email error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/admin/stats', methods=['GET'])
def admin_stats():
    """
    Return live platform stats for the admin dashboard.
    """
    try:
        _decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        from database import execute_query

        total_users = execute_query("SELECT COUNT(*) AS c FROM users", fetch_one=True)['c']
        new_this_week = execute_query(
            "SELECT COUNT(*) AS c FROM users WHERE created_at >= NOW() - INTERVAL '7 days'",
            fetch_one=True
        )['c']
        pending_verification = execute_query(
            """
            SELECT COUNT(*) AS c FROM (
                SELECT DISTINCT fp.user_id AS id
                FROM farmer_profiles fp
                WHERE COALESCE(fp.certification_status, 'pending') = 'pending'
                UNION
                SELECT DISTINCT bp.user_id AS id
                FROM buyer_profiles bp
                WHERE COALESCE(bp.verification_status, 'pending') = 'pending'
            ) pending_users
            """,
            fetch_one=True,
        )['c']
        verified_users = execute_query(
            """
            SELECT COUNT(*) AS c FROM (
                SELECT DISTINCT fp.user_id AS id
                FROM farmer_profiles fp
                WHERE COALESCE(fp.certification_status, 'pending') = 'verified'
                UNION
                SELECT DISTINCT bp.user_id AS id
                FROM buyer_profiles bp
                WHERE COALESCE(bp.verification_status, 'pending') = 'verified'
            ) verified_users
            """,
            fetch_one=True,
        )['c']
        total_products = execute_query("SELECT COUNT(*) AS c FROM products", fetch_one=True)['c']
        active_products = execute_query(
            "SELECT COUNT(*) AS c FROM products WHERE status = 'active'",
            fetch_one=True
        )['c']

        return jsonify({
            'total_users': total_users,
            'new_this_week': new_this_week,
            'pending_verification': pending_verification,
            'verified_users': verified_users,
            'total_products': total_products,
            'active_products': active_products
        }), 200

    except Exception as e:
        logger.error(f"Admin stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/admin/users', methods=['GET'])
def admin_users():
    """
    Return all users for the admin users table.
    """
    try:
        _decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        from database import execute_query
        rows = execute_query("""
            SELECT u.id, u.firebase_uid, u.email, u.first_name, u.last_name,
                   u.role, u.is_active, u.created_at,
                   fp.certification_status,
                   fp.farm_name, fp.location AS farmer_location, fp.county AS farmer_county, fp.national_id AS farmer_national_id,
                   bp.verification_status AS buyer_verification_status,
                   bp.company_name, bp.location AS buyer_location, bp.county AS buyer_county, bp.national_id AS buyer_national_id
            FROM users u
            LEFT JOIN farmer_profiles fp ON fp.user_id = u.id
            LEFT JOIN buyer_profiles bp ON bp.user_id = u.id
            ORDER BY u.created_at DESC
        """, fetch_all=True)

        users = []
        for r in rows:
            d = dict(r)
            farmer_db = str(d.get('certification_status') or 'pending').strip().lower()
            buyer_db = str(d.get('buyer_verification_status') or 'pending').strip().lower()
            d['certification_status_db'] = farmer_db
            d['buyer_verification_status_db'] = buyer_db
            # Admin screens must use exact DB values (no derived display badge).
            d['certification_status'] = farmer_db
            d['buyer_verification_status'] = buyer_db
            d.pop('farm_name', None)
            d.pop('farmer_location', None)
            d.pop('farmer_county', None)
            d.pop('farmer_national_id', None)
            d.pop('company_name', None)
            d.pop('buyer_location', None)
            d.pop('buyer_county', None)
            d.pop('buyer_national_id', None)
            d['id'] = str(d['id'])
            users.append(d)

        return jsonify(users), 200

    except Exception as e:
        logger.error(f"Admin users error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/admin/users/<user_id>/verification', methods=['PATCH'])
def admin_patch_verification(user_id):
    """Approve or reject verification; writes Neon profile + verification_audit."""
    try:
        decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        data = request.get_json() or {}
        action = data.get('action')
        reason = data.get('reason')
        admin_email = (data.get('admin_email') or decoded.get('email') or '').strip() or None

        result = apply_verification_change(
            user_id,
            action=action,
            reason=reason,
            actor_decoded=decoded,
            actor_email=admin_email,
        )
        try:
            from utils.twilio_service import send_verification_status_sms

            user_row = User.get_user_by_id(user_id)
            if user_row:
                send_verification_status_sms(
                    user_row,
                    result.get('new_status'),
                    reason if (action or '').lower() == 'reject' else None,
                )
        except Exception as sms_exc:
            logger.warning('Verification SMS notification failed (non-fatal): %s', sms_exc)

        # Email user on approval (best-effort)
        try:
            if (result.get('new_status') or '').lower() == 'verified':
                user_row = User.get_user_by_id(user_id)
                if user_row:
                    to_email = (user_row.get('email') or '').strip()
                    if to_email:
                        send_account_verified_email(
                            to_email,
                            first_name=user_row.get('first_name'),
                        )
        except Exception as e:
            logger.warning('Verification approval email skipped/failed (non-fatal): %s', e)

        return jsonify({'success': True, **result}), 200
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as e:
        logger.error(f"admin_patch_verification: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/admin/users/<user_id>/verification-history', methods=['GET'])
def admin_verification_history(user_id):
    """Audit trail for a user's verification changes."""
    try:
        _decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        rows = VerificationAudit.list_for_user(user_id)
        history = [dict(row) for row in rows]
        for h in history:
            if h.get('created_at'):
                h['created_at'] = str(h['created_at'])
            if h.get('id'):
                h['id'] = str(h['id'])
        return jsonify({'success': True, 'history': history}), 200
    except Exception as e:
        logger.error(f"admin_verification_history: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/admin/users/<user_id>/permanent-delete', methods=['DELETE'])
def admin_permanent_delete_user(user_id):
    """Admin-only hard delete of user + cascaded relational data."""
    try:
        _decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        target = User.get_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'User not found'}), 404

        cloudinary_summary = _purge_user_cloudinary_assets(user_id)
        deleted_row = execute_query(
            "DELETE FROM users WHERE id = %s::uuid RETURNING id, email",
            (str(user_id),),
            fetch_one=True,
        )
        if not deleted_row:
            return jsonify({'error': 'User delete failed'}), 500

        return jsonify({
            'success': True,
            'deleted_user_id': str(deleted_row.get('id')),
            'deleted_email': deleted_row.get('email'),
            'cloudinary': cloudinary_summary,
        }), 200
    except Exception as e:
        logger.error(f"admin_permanent_delete_user: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/admin/impersonation-log', methods=['POST'])
def admin_impersonation_log_post():
    """Record admin opening a client dashboard (impersonation / support view)."""
    try:
        decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        data = request.get_json() or {}
        target_user_id = (data.get('target_user_id') or '').strip()
        if not target_user_id:
            return jsonify({'error': 'target_user_id is required'}), 400

        admin_email = (data.get('admin_email') or decoded.get('email') or '').strip() or None
        row = AdminImpersonationLog.log(
            target_user_id,
            admin_firebase_uid=decoded.get('uid'),
            admin_email=admin_email,
        )
        out = dict(row) if row else {}
        if out.get('id'):
            out['id'] = str(out['id'])
        if out.get('created_at'):
            out['created_at'] = str(out['created_at'])
        return jsonify({'success': True, 'log': out}), 201
    except Exception as e:
        logger.error(f"admin_impersonation_log_post: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/admin/impersonation-log', methods=['GET'])
def admin_impersonation_log_list():
    try:
        _decoded, err = decode_token_if_admin()
        if err:
            resp, code = err
            return resp, code

        limit = request.args.get('limit', '50')
        try:
            lim = min(max(int(limit), 1), 200)
        except ValueError:
            lim = 50
        rows = AdminImpersonationLog.list_recent(lim)
        logs = []
        for r in rows or []:
            d = dict(r)
            if d.get('id'):
                d['id'] = str(d['id'])
            if d.get('target_user_id'):
                d['target_user_id'] = str(d['target_user_id'])
            if d.get('created_at'):
                d['created_at'] = str(d['created_at'])
            logs.append(d)
        return jsonify({'success': True, 'logs': logs}), 200
    except Exception as e:
        logger.error(f"admin_impersonation_log_list: {e}")
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/dashboard-route', methods=['POST'])
def get_dashboard_route():
    """
    Get the appropriate dashboard route based on user role
    Expects: { firebase_uid } or { role }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        role = data.get('role')
        
        if firebase_uid:
            user = User.get_user_by_firebase_uid(firebase_uid)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            role = user['role']
        
        if not role:
            return jsonify({'error': 'role or firebase_uid is required'}), 400
        
        # Determine dashboard route
        # Support multi-role: if user has multiple roles, prioritize farmer > buyer > admin
        roles_list = [r.strip() for r in role.split(',')] if ',' in role else [role]
        
        if 'admin' in roles_list:
            dashboard = '/admin-support'
        elif 'farmer' in roles_list:
            dashboard = '/farmer'
        elif 'agro-dealer' in roles_list:
            dashboard = '/agro-dealer'
        elif 'buyer' in roles_list:
            dashboard = '/buyer'
        else:
            dashboard = '/'
        
        return jsonify({
            'success': True,
            'dashboard': dashboard,
            'role': role,
            'roles': roles_list
        }), 200
        
    except Exception as e:
        logger.error(f"Dashboard route error: {str(e)}")
        return jsonify({'error': str(e)}), 500

