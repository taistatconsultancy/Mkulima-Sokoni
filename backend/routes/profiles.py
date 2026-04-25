"""
Profile routes for Phase 2
"""
from flask import Blueprint, request, jsonify
from models.user import User
from models.farmer_profile import FarmerProfile
from models.buyer_profile import BuyerProfile
from auth.firebase_auth import verify_firebase_token
from utils.cloudinary_service import upload_image_from_url
from utils.mailer import resolve_support_team_emails, send_support_verification_request_email
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


def _user_submitted_verification_status(raw):
    """
    Non-admin profile saves may only set status to 'pending' (submit for review).
    Returns 'pending' or None (omit field — keep existing on update).
    """
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s == 'pending':
        return 'pending'
    return None


def _farmer_profile_complete(data):
    return bool(
        str(data.get('farm_name') or '').strip() and
        str(data.get('location') or '').strip() and
        str(data.get('county') or '').strip() and
        str(data.get('national_id') or '').strip()
    )


def _buyer_profile_complete(data):
    return bool(
        str(data.get('company_name') or '').strip() and
        str(data.get('location') or '').strip() and
        str(data.get('county') or '').strip() and
        str(data.get('national_id') or '').strip()
    )


def _maybe_notify_support_profile_submitted(
    *,
    firebase_uid: str,
    user_id: str,
    profile_kind: str,
    submitted_pending: bool,
    prev_status: Optional[str],
    new_status: Optional[str],
    profile_complete: bool,
) -> None:
    """
    Best-effort support email when a user submits a complete profile for review.
    Sends only on transition into 'pending' to avoid repeats.
    """
    try:
        if not submitted_pending:
            return
        if not profile_complete:
            return
        prev_s = (prev_status or "").strip().lower() or None
        new_s = (new_status or "").strip().lower() or None
        if new_s != "pending":
            return
        if prev_s == "pending":
            return

        recipients = resolve_support_team_emails()
        if not recipients:
            return

        user = User.get_user_by_firebase_uid(firebase_uid) or {}
        try:
            roles = User.get_user_roles(user_id) or []
        except Exception:
            roles = []
        user_summary = {
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "email": user.get("email"),
            "phone_number": user.get("phone_number"),
            "roles": roles or (user.get("role") or ""),
        }
        send_support_verification_request_email(recipients, user_summary, profile_kind=profile_kind)
    except Exception as e:
        logger.warning("Support verification email skipped/failed: %s", e)


def extract_user_id(user):
    """
    Safely extract user_id from user object, ensuring it's a UUID not a timestamp
    """
    if not user:
        logger.error("extract_user_id: user object is None")
        return None
    
    # Log all available keys for debugging
    if hasattr(user, 'keys'):
        all_keys = list(user.keys())
        logger.debug(f"extract_user_id: Available keys in user object: {all_keys}")
        # Log all values to see what we're working with
        for key in all_keys:
            val = user[key] if hasattr(user, '__getitem__') else getattr(user, key, None)
            logger.debug(f"  {key}: {val} (type: {type(val).__name__})")
    
    # First, try to find a valid UUID in the user object
    # Check all fields that might contain a UUID
    uuid_candidates = []
    
    if hasattr(user, 'keys'):
        for key in user.keys():
            try:
                val = user[key] if hasattr(user, '__getitem__') else getattr(user, key, None)
                if val:
                    # Check if it's a valid UUID format
                    if isinstance(val, str):
                        # UUIDs are 36 characters with exactly 4 dashes, no 'T'
                        if len(val) == 36 and val.count('-') == 4 and 'T' not in val:
                            try:
                                # Validate it's a valid UUID
                                uuid.UUID(val)
                                uuid_candidates.append((key, val))
                                logger.debug(f"Found UUID candidate in key '{key}': {val}")
                            except (ValueError, AttributeError):
                                pass
            except (KeyError, AttributeError):
                continue
    
    # If we found UUID candidates, prefer 'id' key, otherwise use the first one
    if uuid_candidates:
        # Prefer 'id' key if it exists
        for key, val in uuid_candidates:
            if key == 'id':
                logger.debug(f"Using UUID from 'id' key: {val}")
                return val
        # Otherwise use the first UUID found
        key, val = uuid_candidates[0]
        logger.warning(f"Using UUID from '{key}' key (not 'id'): {val}")
        return val
    
    # Fallback: Try to get 'id' using different methods
    user_id = None
    if hasattr(user, 'get'):
        user_id = user.get('id')
    elif hasattr(user, '__getitem__'):
        user_id = user['id'] if 'id' in user else None
    else:
        user_id = getattr(user, 'id', None)
    
    # Validate the extracted id
    if user_id:
        # Check if it's a timestamp (ISO format with 'T')
        if isinstance(user_id, str) and 'T' in user_id:
            logger.error(f"CRITICAL: user_id from 'id' key is a timestamp '{user_id}' instead of UUID!")
            logger.error(f"User object type: {type(user)}")
            logger.error(f"User object keys: {list(user.keys()) if hasattr(user, 'keys') else 'N/A'}")
            logger.error(f"User object: {user}")
            return None
        
        # Validate it's a valid UUID format
        if isinstance(user_id, str):
            # UUIDs are 36 characters with exactly 4 dashes
            if len(user_id) == 36 and user_id.count('-') == 4 and 'T' not in user_id:
                try:
                    uuid.UUID(user_id)
                    return user_id
                except (ValueError, AttributeError) as e:
                    logger.error(f"user_id '{user_id}' looks like UUID but failed validation: {e}")
                    return None
    
    logger.error(f"Failed to extract valid UUID from user object. user_id: {user_id}")
    return None

profiles_bp = Blueprint('profiles', __name__, url_prefix='/api/profiles')

@profiles_bp.route('/farmers/nearby', methods=['GET'])
def list_nearby_farmers():
    """
    List farmers near the user (hybrid):
    - If lat/lng are provided, return farmers within radius_km ordered by distance.
    - Else if county is provided, return farmers in that county.

    Query params:
      lat, lng, radius_km (default 25), limit (default 24)
      county (fallback)
    """
    try:
        lat = request.args.get('lat', None)
        lng = request.args.get('lng', None)
        county = request.args.get('county', None)
        radius_km = request.args.get('radius_km', 25)
        limit = request.args.get('limit', 24)

        # Prefer GPS if present
        use_gps = lat is not None and lng is not None and str(lat).strip() and str(lng).strip()
        farmers = FarmerProfile.list_nearby(
            lat=lat if use_gps else None,
            lng=lng if use_gps else None,
            radius_km=radius_km,
            limit=limit,
            county=None if use_gps else county,
        )

        return jsonify({'success': True, 'farmers': farmers}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error listing nearby farmers: {str(e)}")
        return jsonify({'error': 'Failed to load nearby farmers'}), 500

@profiles_bp.route('/', methods=['GET'])
def profiles_info():
    """
    Get information about available profile endpoints
    """
    return jsonify({
        'success': True,
        'message': 'Profile API endpoints',
        'endpoints': {
            'farmer': {
                'create_update': 'POST /api/profiles/farmer',
                'get': 'GET /api/profiles/farmer/<firebase_uid>'
            },
            'buyer': {
                'create_update': 'POST /api/profiles/buyer',
                'get': 'GET /api/profiles/buyer/<firebase_uid>'
            },
            'all_profiles': 'GET /api/profiles/<firebase_uid>'
        }
    }), 200

@profiles_bp.route('/farmer', methods=['POST'])
def create_farmer_profile():
    """
    Create or update farmer profile
    Expects: { firebase_uid, farm_name, location, county, ... }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        
        # Get user_id directly from farmer_profiles table (avoids timestamp issue)
        logger.info(f"Getting user_id from farmer_profiles for firebase_uid: {firebase_uid}")
        user_id = FarmerProfile.get_user_id_by_firebase_uid(firebase_uid)
        
        if not user_id:
            # Profile doesn't exist yet, get user_id directly from users table (avoids extraction issues)
            logger.info("Profile doesn't exist, getting user_id directly from users table...")
            user_id = User.get_user_id_by_firebase_uid(firebase_uid)
            if not user_id:
                return jsonify({'error': 'User not found'}), 404
            
            # Validate user_id is a UUID
            import uuid
            if isinstance(user_id, str) and ('T' in user_id or len(user_id) != 36 or user_id.count('-') != 4):
                logger.error(f"Invalid user_id format from get_user_id_by_firebase_uid: {user_id}")
                return jsonify({'error': f'Invalid user ID format: {user_id}'}), 500
            
            # Get user object to check role (farmer + agro-dealer share farmer_profiles)
            user = User.get_user_by_firebase_uid(firebase_uid)
            if user:
                user_roles = User.get_user_roles(user_id)
                role_text = str(user.get('role') or '').lower().replace(' ', '')
                has_farmer_slot = (
                    'farmer' in user_roles
                    or 'agro-dealer' in user_roles
                    or 'farmer' in role_text
                    or 'agro-dealer' in role_text
                    or 'agrodealer' in role_text
                )
                if not has_farmer_slot:
                    return jsonify({'error': 'User does not have farmer or agro-dealer role'}), 403
        else:
            # Validate the user_id we got from profile table
            import uuid
            if isinstance(user_id, str) and ('T' in user_id or len(user_id) != 36 or user_id.count('-') != 4):
                logger.error(f"Invalid user_id from profile table: {user_id}")
                return jsonify({'error': f'Invalid user ID from profile: {user_id}'}), 500
            logger.info(f"✅ Got user_id from farmer_profiles: {user_id}")
        
        # Handle profile image URL - upload to Cloudinary if it's a new URL
        profile_image_url = data.get('profile_image_url')
        if profile_image_url and profile_image_url.startswith('http') and 'cloudinary.com' not in profile_image_url:
            # Upload external URL to Cloudinary
            try:
                upload_result = upload_image_from_url(profile_image_url, folder='mkulima-bora/profiles/farmer')
                if upload_result:
                    profile_image_url = upload_result['secure_url']
            except Exception as e:
                logger.warning(f"Could not upload image to Cloudinary: {str(e)}")
                # Continue with original URL if upload fails
        
        # Check if profile exists - log the user_id being passed
        logger.info(f"Calling FarmerProfile.profile_exists with user_id: {user_id} (type: {type(user_id).__name__})")
        
        # ONE MORE SAFETY CHECK - ensure user_id is definitely a UUID before calling profile_exists
        if isinstance(user_id, str):
            if 'T' in user_id or len(user_id) != 36 or user_id.count('-') != 4:
                logger.error(f"FINAL SAFETY CHECK FAILED: user_id '{user_id}' is not a valid UUID!")
                logger.error(f"  Has 'T': {'T' in user_id}, Length: {len(user_id)}, Dashes: {user_id.count('-')}")
                return jsonify({'error': f'Invalid user ID format detected: {user_id}'}), 500
            try:
                uuid.UUID(user_id)
            except (ValueError, AttributeError) as e:
                logger.error(f"FINAL SAFETY CHECK FAILED: user_id '{user_id}' failed UUID parsing: {e}")
                return jsonify({'error': f'Invalid user ID: {user_id}'}), 500
        
        # Handle file uploads - convert base64 to Cloudinary URLs
        from utils.cloudinary_service import upload_base64_image
        
        id_front_url = data.get('id_front_url')
        id_back_url = data.get('id_back_url')
        profile_selfie_url = data.get('profile_selfie_url')
        
        # Upload base64 images to Cloudinary if provided
        if data.get('id_front') and not id_front_url:
            upload_result = upload_base64_image(
                data.get('id_front'),
                folder='mkulima-bora/profiles/farmer/id-documents'
            )
            if upload_result:
                id_front_url = upload_result['secure_url']
                logger.info(f"Uploaded ID front to Cloudinary: {id_front_url}")
        
        if data.get('id_back') and not id_back_url:
            upload_result = upload_base64_image(
                data.get('id_back'),
                folder='mkulima-bora/profiles/farmer/id-documents'
            )
            if upload_result:
                id_back_url = upload_result['secure_url']
                logger.info(f"Uploaded ID back to Cloudinary: {id_back_url}")
        
        if data.get('profile_selfie') and not profile_selfie_url:
            upload_result = upload_base64_image(
                data.get('profile_selfie'),
                folder='mkulima-bora/profiles/farmer/selfies'
            )
            if upload_result:
                profile_selfie_url = upload_result['secure_url']
                logger.info(f"Uploaded profile selfie to Cloudinary: {profile_selfie_url}")
        
        cert_status = _user_submitted_verification_status(data.get('certification_status'))
        if not _farmer_profile_complete(data):
            cert_status = 'pending'

        # Optional geo coordinates (validated). These are privacy-rounded client-side.
        latitude = data.get('latitude', None)
        longitude = data.get('longitude', None)
        if latitude is not None or longitude is not None:
            try:
                lat_f = float(latitude) if latitude is not None and str(latitude).strip() != '' else None
                lng_f = float(longitude) if longitude is not None and str(longitude).strip() != '' else None
            except Exception:
                return jsonify({'error': 'Invalid latitude/longitude (must be numbers)'}), 400
            if lat_f is None or lng_f is None:
                return jsonify({'error': 'Both latitude and longitude are required together'}), 400
            if not (-90.0 <= lat_f <= 90.0):
                return jsonify({'error': 'Invalid latitude (must be between -90 and 90)'}), 400
            if not (-180.0 <= lng_f <= 180.0):
                return jsonify({'error': 'Invalid longitude (must be between -180 and 180)'}), 400
        else:
            lat_f = None
            lng_f = None
        if FarmerProfile.profile_exists(user_id):
            prev_profile = FarmerProfile.get_profile_by_user_id(user_id)
            prev_status = (prev_profile or {}).get('certification_status')
            # Update existing profile (omit certification_status unless submitting pending)
            fp_kwargs = dict(
                farm_name=data.get('farm_name'),
                location=data.get('location'),
                county=data.get('county'),
                latitude=lat_f,
                longitude=lng_f,
                farm_size_acres=data.get('farm_size_acres'),
                farming_experience_years=data.get('farming_experience_years'),
                bio=data.get('bio'),
                profile_image_url=profile_image_url,
                national_id=data.get('national_id'),
                id_front_url=id_front_url,
                id_back_url=id_back_url,
                profile_selfie_url=profile_selfie_url,
                ward=data.get('ward'),
                crops=data.get('crops'),
                livestock=data.get('livestock'),
                referral_source=data.get('referral_source'),
                referral_other=data.get('referral_other'),
            )
            if cert_status is not None:
                fp_kwargs['certification_status'] = cert_status
            profile = FarmerProfile.update_profile(user_id, **fp_kwargs)
        else:
            prev_status = None
            # Create new profile
            profile = FarmerProfile.create_profile(
                user_id,
                farm_name=data.get('farm_name'),
                location=data.get('location'),
                county=data.get('county'),
                latitude=lat_f,
                longitude=lng_f,
                farm_size_acres=data.get('farm_size_acres'),
                farming_experience_years=data.get('farming_experience_years'),
                certification_status=cert_status or 'pending',
                bio=data.get('bio'),
                profile_image_url=profile_image_url,
                national_id=data.get('national_id'),
                id_front_url=id_front_url,
                id_back_url=id_back_url,
                profile_selfie_url=profile_selfie_url,
                ward=data.get('ward'),
                crops=data.get('crops'),  # JSON string from frontend
                livestock=data.get('livestock'),  # JSON string from frontend
                referral_source=data.get('referral_source'),
                referral_other=data.get('referral_other')
            )

        # Support notification when user submits for verification (best-effort)
        submitted_pending = str(data.get('certification_status') or '').strip().lower() == 'pending'
        new_status = None
        try:
            new_status = (profile or {}).get('certification_status')
        except Exception:
            new_status = None
        _maybe_notify_support_profile_submitted(
            firebase_uid=firebase_uid,
            user_id=str(user_id),
            profile_kind='farmer',
            submitted_pending=submitted_pending,
            prev_status=prev_status,
            new_status=new_status,
            profile_complete=_farmer_profile_complete(data),
        )
        
        return jsonify({
            'success': True,
            'profile': profile,
            'message': 'Farmer profile saved successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating/updating farmer profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@profiles_bp.route('/farmer/<firebase_uid>', methods=['GET'])
def get_farmer_profile(firebase_uid):
    """
    Get farmer profile by Firebase UID
    Uses join to get profile directly, avoiding user_id extraction issues
    """
    try:
        # Get profile directly using join (includes user email and phone)
        profile = FarmerProfile.get_profile_by_firebase_uid(firebase_uid)
        if not profile:
            return jsonify({'error': 'Farmer profile not found'}), 404
        
        # Format response
        profile_dict = dict(profile) if hasattr(profile, 'keys') else profile
        profile_dict['user'] = {
            'email': profile_dict.get('email'),
            # Do not expose phone numbers on public profile endpoints.
            'phone_number': None
        }
        # Remove email and phone_number from main profile (they're in user object)
        profile_dict.pop('email', None)
        profile_dict.pop('phone_number', None)
        db_cert = str(profile_dict.get('certification_status') or 'pending').strip().lower()
        profile_dict['certification_status_db'] = db_cert
        profile_dict['certification_status'] = db_cert
        
        return jsonify({
            'success': True,
            'profile': profile_dict
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting farmer profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@profiles_bp.route('/buyer', methods=['POST'])
def create_buyer_profile():
    """
    Create or update buyer profile
    Expects: { firebase_uid, company_name, location, county, ... }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        
        # Get user_id directly from buyer_profiles table (avoids timestamp issue)
        logger.info(f"Getting user_id from buyer_profiles for firebase_uid: {firebase_uid}")
        user_id = BuyerProfile.get_user_id_by_firebase_uid(firebase_uid)
        
        if not user_id:
            # Profile doesn't exist yet, get user_id directly from users table (avoids extraction issues)
            logger.info("Profile doesn't exist, getting user_id directly from users table...")
            user_id = User.get_user_id_by_firebase_uid(firebase_uid)
            if not user_id:
                return jsonify({'error': 'User not found'}), 404
            
            # Validate user_id is a UUID
            import uuid
            if isinstance(user_id, str) and ('T' in user_id or len(user_id) != 36 or user_id.count('-') != 4):
                logger.error(f"Invalid user_id format from get_user_id_by_firebase_uid: {user_id}")
                return jsonify({'error': f'Invalid user ID format: {user_id}'}), 500
            
            # Get user object to check role
            user = User.get_user_by_firebase_uid(firebase_uid)
            if user:
                # Check if user has buyer role
                user_roles = User.get_user_roles(user_id)
                if 'buyer' not in user_roles and user.get('role') != 'buyer' and 'buyer' not in user.get('role', ''):
                    return jsonify({'error': 'User does not have buyer role'}), 403
        else:
            # Validate the user_id we got from profile table
            import uuid
            if isinstance(user_id, str) and ('T' in user_id or len(user_id) != 36 or user_id.count('-') != 4):
                logger.error(f"Invalid user_id from profile table: {user_id}")
                return jsonify({'error': f'Invalid user ID from profile: {user_id}'}), 500
            logger.info(f"✅ Got user_id from buyer_profiles: {user_id}")
        
        # Handle profile image URL - upload to Cloudinary if it's a new URL
        profile_image_url = data.get('profile_image_url')
        if profile_image_url and profile_image_url.startswith('http') and 'cloudinary.com' not in profile_image_url:
            # Upload external URL to Cloudinary
            try:
                upload_result = upload_image_from_url(profile_image_url, folder='mkulima-bora/profiles/buyer')
                if upload_result:
                    profile_image_url = upload_result['secure_url']
            except Exception as e:
                logger.warning(f"Could not upload image to Cloudinary: {str(e)}")
                # Continue with original URL if upload fails
        
        # Handle file uploads - convert base64 to Cloudinary URLs
        from utils.cloudinary_service import upload_base64_image
        
        id_front_url = data.get('id_front_url')
        id_back_url = data.get('id_back_url')
        
        # Upload base64 images to Cloudinary if provided
        if data.get('id_front') and not id_front_url:
            upload_result = upload_base64_image(
                data.get('id_front'),
                folder='mkulima-bora/profiles/buyer/id-documents'
            )
            if upload_result:
                id_front_url = upload_result['secure_url']
                logger.info(f"Uploaded ID front to Cloudinary: {id_front_url}")
        
        if data.get('id_back') and not id_back_url:
            upload_result = upload_base64_image(
                data.get('id_back'),
                folder='mkulima-bora/profiles/buyer/id-documents'
            )
            if upload_result:
                id_back_url = upload_result['secure_url']
                logger.info(f"Uploaded ID back to Cloudinary: {id_back_url}")
        
        buyer_vstatus = _user_submitted_verification_status(data.get('verification_status'))
        if not _buyer_profile_complete(data):
            buyer_vstatus = 'pending'
        # Check if profile exists
        if BuyerProfile.profile_exists(user_id):
            prev_profile = BuyerProfile.get_profile_by_user_id(user_id)
            prev_status = (prev_profile or {}).get('verification_status')
            # Update existing profile
            bp_kwargs = dict(
                company_name=data.get('company_name'),
                location=data.get('location'),
                county=data.get('county'),
                business_type=data.get('business_type'),
                business_registration_number=data.get('business_registration_number'),
                bio=data.get('bio'),
                profile_image_url=profile_image_url,
                national_id=data.get('national_id'),
                id_front_url=id_front_url,
                id_back_url=id_back_url,
                referral_source=data.get('referral_source'),
                referral_other=data.get('referral_other'),
            )
            if buyer_vstatus is not None:
                bp_kwargs['verification_status'] = buyer_vstatus
            profile = BuyerProfile.update_profile(user_id, **bp_kwargs)
        else:
            prev_status = None
            # Create new profile
            profile = BuyerProfile.create_profile(
                user_id,
                company_name=data.get('company_name'),
                location=data.get('location'),
                county=data.get('county'),
                business_type=data.get('business_type'),
                business_registration_number=data.get('business_registration_number'),
                verification_status=buyer_vstatus or 'pending',
                bio=data.get('bio'),
                profile_image_url=profile_image_url,
                national_id=data.get('national_id'),
                id_front_url=id_front_url,
                id_back_url=id_back_url,
                referral_source=data.get('referral_source'),
                referral_other=data.get('referral_other')
            )

        # Support notification when user submits for verification (best-effort)
        submitted_pending = str(data.get('verification_status') or '').strip().lower() == 'pending'
        new_status = None
        try:
            new_status = (profile or {}).get('verification_status')
        except Exception:
            new_status = None
        _maybe_notify_support_profile_submitted(
            firebase_uid=firebase_uid,
            user_id=str(user_id),
            profile_kind='buyer',
            submitted_pending=submitted_pending,
            prev_status=prev_status,
            new_status=new_status,
            profile_complete=_buyer_profile_complete(data),
        )
        
        return jsonify({
            'success': True,
            'profile': profile,
            'message': 'Buyer profile saved successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating/updating buyer profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@profiles_bp.route('/buyer/<firebase_uid>', methods=['GET'])
def get_buyer_profile(firebase_uid):
    """
    Get buyer profile by Firebase UID
    Uses join to get profile directly, avoiding user_id extraction issues
    """
    try:
        # Get profile directly using join (includes user email and phone)
        profile = BuyerProfile.get_profile_by_firebase_uid(firebase_uid)
        if not profile:
            return jsonify({'error': 'Buyer profile not found'}), 404
        
        # Format response
        profile_dict = dict(profile) if hasattr(profile, 'keys') else profile
        profile_dict['user'] = {
            'email': profile_dict.get('email'),
            # Do not expose phone numbers on public profile endpoints.
            'phone_number': None
        }
        # Remove email and phone_number from main profile (they're in user object)
        profile_dict.pop('email', None)
        profile_dict.pop('phone_number', None)
        db_vs = str(profile_dict.get('verification_status') or 'pending').strip().lower()
        profile_dict['verification_status_db'] = db_vs
        profile_dict['verification_status'] = db_vs
        
        return jsonify({
            'success': True,
            'profile': profile_dict
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting buyer profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@profiles_bp.route('/<firebase_uid>', methods=['GET'])
def get_user_profiles(firebase_uid):
    """
    Get all profiles for a user (farmer and/or buyer)
    """
    try:
        user = User.get_user_by_firebase_uid(firebase_uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Extract and validate user_id
        user_id = extract_user_id(user)
        if not user_id:
            return jsonify({'error': 'Invalid user data'}), 500
        
        user_roles = User.get_user_roles(user_id)
        profiles = {}
        
        # Get farmer profile if user has farmer role
        if 'farmer' in user_roles or 'farmer' in user.get('role', ''):
            farmer_profile = FarmerProfile.get_profile_by_user_id(user_id)
            if farmer_profile:
                profiles['farmer'] = farmer_profile
        
        # Get buyer profile if user has buyer role
        if 'buyer' in user_roles or 'buyer' in user.get('role', ''):
            buyer_profile = BuyerProfile.get_profile_by_user_id(user_id)
            if buyer_profile:
                profiles['buyer'] = buyer_profile
        
        return jsonify({
            'success': True,
            'profiles': profiles,
            'user': {
                'email': user['email'],
                # Do not expose phone numbers on public endpoints.
                'phone_number': None
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user profiles: {str(e)}")
        return jsonify({'error': str(e)}), 500

