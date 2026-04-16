"""
Product routes for Phase 3
"""
from flask import Blueprint, request, jsonify
from models.product import Product
from models.farmer_profile import FarmerProfile
from utils.cloudinary_service import upload_base64_image
import logging

logger = logging.getLogger(__name__)

products_bp = Blueprint('products', __name__, url_prefix='/api/products')

def get_farmer_profile_id(firebase_uid):
    """
    Get farmer_profile_id from firebase_uid
    """
    try:
        # Get user_id first
        user_id = FarmerProfile.get_user_id_by_firebase_uid(firebase_uid)
        if not user_id:
            return None
        
        # Get farmer profile to get farmer_profile_id
        profile = FarmerProfile.get_profile_by_user_id(user_id)
        if profile:
            return profile.get('id')
        return None
    except Exception as e:
        logger.error(f"Error getting farmer_profile_id: {str(e)}")
        return None

@products_bp.route('', methods=['POST'])
def create_product():
    """
    Create a new product
    Expects: { firebase_uid, name, category, product_type, location, ... }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        
        # Get farmer_profile_id (also auto-creates for agro-dealers)
        farmer_profile_id = get_farmer_profile_id(firebase_uid)
        if not farmer_profile_id:
            try:
                from models.user import User
                user = User.get_user_by_firebase_uid(firebase_uid)
                if user:
                    user_id = str(user.get('id'))
                    if not FarmerProfile.profile_exists(user_id):
                        FarmerProfile.create_profile(user_id, farm_name=None, location=None, county=None)
                    farmer_profile_id = get_farmer_profile_id(firebase_uid)
            except Exception as e:
                logger.warning(f"Auto-create profile failed: {e}")
        if not farmer_profile_id:
            return jsonify({'error': 'Profile not found. Please update your profile first.'}), 404
        
        # Extract product data
        name = data.get('name')
        category = data.get('category')
        product_type = data.get('product_type')  # 'farm' or 'livestock'
        location = data.get('location')
        measurement_metric = data.get('measurement_metric')
        quantity = data.get('quantity')
        min_order = data.get('min_order', 1)
        
        # Validate required fields
        if not all([name, category, product_type, location, measurement_metric, quantity]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Handle image upload (base64 to Cloudinary)
        image_url = None
        if data.get('image'):
            upload_result = upload_base64_image(
                data.get('image'),
                folder='mkulima-bora/products'
            )
            if upload_result:
                image_url = upload_result['secure_url']
                logger.info(f"Uploaded product image to Cloudinary: {image_url}")
        
        # Handle pricing based on product_type
        price = None
        price_min = None
        price_max = None
        
        if product_type == 'farm':
            price = data.get('price')
            if price is None:
                return jsonify({'error': 'Price is required for farm products'}), 400
        elif product_type == 'livestock':
            price_min = data.get('price_min')
            price_max = data.get('price_max')
            if price_min is None or price_max is None:
                return jsonify({'error': 'price_min and price_max are required for livestock'}), 400
        else:
            return jsonify({'error': 'Invalid product_type. Must be "farm" or "livestock"'}), 400
        
        # Farm-specific fields
        planting_time = data.get('planting_time') if product_type == 'farm' else None
        fertilizer_used = data.get('fertilizer_used') if product_type == 'farm' else None
        harvest_time = data.get('harvest_time') if product_type == 'farm' else None
        
        # Create product
        product = Product.create_product(
            farmer_profile_id=farmer_profile_id,
            name=name,
            category=category,
            product_type=product_type,
            location=location,
            county=data.get('county'),
            measurement_metric=measurement_metric,
            quantity=int(quantity),
            min_order=int(min_order),
            image_url=image_url,
            description=data.get('description'),
            price=float(price) if price else None,
            price_min=float(price_min) if price_min else None,
            price_max=float(price_max) if price_max else None,
            planting_time=planting_time,
            fertilizer_used=fertilizer_used,
            harvest_time=harvest_time,
            status=data.get('status', 'draft')
        )
        
        if product:
            # Convert UUID to string for JSON serialization
            product_dict = dict(product)
            product_dict['id'] = str(product_dict['id'])
            product_dict['farmer_profile_id'] = str(product_dict['farmer_profile_id'])
            return jsonify(product_dict), 201
        else:
            return jsonify({'error': 'Failed to create product'}), 500
            
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        return jsonify({'error': str(e)}), 500


def _normalize_product_status(raw):
    """Map API aliases to DB check constraint: draft, active, sold_out, archived."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    aliases = {
        'sold': 'sold_out',
        'paused': 'archived',
    }
    s = aliases.get(s, s)
    if s not in ('draft', 'active', 'sold_out', 'archived'):
        return None
    return s


@products_bp.route('/meta', methods=['GET'])
def get_products_meta():
    """Aggregate count + max(updated_at) for marketplace polling (no full listing body)."""
    try:
        status = request.args.get('status', 'active')
        category = request.args.get('category')
        product_type = request.args.get('product_type')
        meta = Product.get_marketplace_meta(
            status=status, category=category, product_type=product_type
        )
        return jsonify(meta), 200
    except Exception as e:
        logger.error(f'get_products_meta: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@products_bp.route('/<product_id>/status', methods=['PUT'])
def update_product_status(product_id):
    """Update a product's status; requires firebase_uid and seller ownership."""
    try:
        data = request.get_json() or {}
        firebase_uid = data.get('firebase_uid')
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400

        new_status = _normalize_product_status(data.get('status'))
        if not new_status:
            return jsonify({
                'error': 'Invalid status. Use draft, active, sold_out, archived '
                         '(aliases: sold -> sold_out, paused -> archived)',
            }), 400

        farmer_profile_id = get_farmer_profile_id(firebase_uid)
        if not farmer_profile_id:
            return jsonify({'error': 'Farmer profile not found'}), 404

        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        if str(product['farmer_profile_id']) != str(farmer_profile_id):
            return jsonify({'error': 'Unauthorized'}), 403

        updated = Product.update_product(product_id, status=new_status)
        if updated:
            return jsonify({
                'success': True,
                'id': str(updated['id']),
                'status': updated['status'],
            }), 200
        return jsonify({'error': 'Failed to update status'}), 500
    except Exception as e:
        logger.error(f"Update product status error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@products_bp.route('', methods=['GET'])
def get_products():
    """
    Get all products with optional filters
    Query params: status, category, product_type, limit, offset
    """
    try:
        status = request.args.get('status', 'active')
        category = request.args.get('category')
        product_type = request.args.get('product_type')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        products = Product.get_all_products(
            status=status,
            category=category,
            product_type=product_type,
            limit=limit,
            offset=offset
        )
        
        products_list = []
        for product in products:
            product_dict = dict(product)
            product_dict['id'] = str(product_dict['id'])
            product_dict['farmer_profile_id'] = str(product_dict['farmer_profile_id'])
            if 'seller_role' not in product_dict:
                product_dict['seller_role'] = 'farmer'
            products_list.append(product_dict)
        
        return jsonify(products_list), 200
        
    except ValueError as e:
        logger.error(f"Validation error getting products: {str(e)}")
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error getting products: {str(e)}", exc_info=True)
        error_msg = str(e)
        if 'DATABASE_URL' in error_msg or 'connection' in error_msg.lower():
            error_msg = 'Database connection error. Please check configuration.'
        return jsonify({'error': error_msg}), 500

@products_bp.route('/<product_id>', methods=['GET'])
def get_product(product_id):
    """
    Get a single product by ID
    """
    try:
        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Increment views
        Product.increment_views(product_id)
        
        # Convert UUIDs to strings for JSON serialization
        product_dict = dict(product)
        product_dict['id'] = str(product_dict['id'])
        product_dict['farmer_profile_id'] = str(product_dict['farmer_profile_id'])
        
        return jsonify(product_dict), 200
        
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}")
        return jsonify({'error': str(e)}), 500

@products_bp.route('/<product_id>/detail', methods=['GET'])
def get_product_detail(product_id):
    """
    Get product with seller details (profile + user info) for the public detail page.
    Increments view count. Returns product + seller object.
    """
    try:
        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404

        Product.increment_views(product_id)

        product_dict = dict(product)
        product_dict['id'] = str(product_dict['id'])
        farmer_profile_id = str(product_dict['farmer_profile_id'])
        product_dict['farmer_profile_id'] = farmer_profile_id

        seller = {}
        try:
            from database import execute_query
            q = """
                SELECT fp.id AS profile_id,
                       fp.farm_name,
                       fp.location AS seller_location,
                       fp.county AS seller_county,
                       fp.bio,
                       fp.profile_image_url,
                       fp.certification_status,
                       fp.farming_experience_years,
                       u.first_name,
                       u.last_name,
                       u.email,
                       u.phone_number,
                       u.firebase_uid,
                       u.created_at AS member_since
                FROM farmer_profiles fp
                INNER JOIN users u ON fp.user_id = u.id
                WHERE fp.id = %s::uuid
            """
            result = execute_query(q, (farmer_profile_id,), fetch_one=True)
            if result:
                seller = dict(result)
                seller['profile_id'] = str(seller['profile_id'])
                # Standardized verification flag for frontend badge
                cert = (seller.get('certification_status') or '').lower()
                seller['is_verified'] = cert not in ('', 'pending', 'rejected')
        except Exception as e:
            logger.warning(f"Could not fetch seller info: {e}")

        similar = []
        try:
            sims = Product.get_all_products(
                status='active', category=product_dict.get('category'), limit=8
            )
            for s in sims:
                sd = dict(s)
                if str(sd['id']) == product_id:
                    continue
                sd['id'] = str(sd['id'])
                sd['farmer_profile_id'] = str(sd['farmer_profile_id'])
                similar.append(sd)
            similar = similar[:6]
        except Exception as e:
            logger.warning(f"Could not fetch similar products: {e}")

        return jsonify({
            'success': True,
            'product': product_dict,
            'seller': seller,
            'similar': similar
        }), 200

    except Exception as e:
        logger.error(f"Error getting product detail: {str(e)}")
        return jsonify({'error': str(e)}), 500

@products_bp.route('/farmer/<firebase_uid>', methods=['GET'])
def get_farmer_products(firebase_uid):
    """
    Get all products for a specific farmer
    Query params: status (optional filter)
    """
    try:
        farmer_profile_id = get_farmer_profile_id(firebase_uid)
        if not farmer_profile_id:
            return jsonify({'error': 'Farmer profile not found'}), 404
        
        status = request.args.get('status')
        products = Product.get_products_by_farmer(farmer_profile_id, status=status)
        
        # Convert UUIDs to strings for JSON serialization
        products_list = []
        for product in products:
            product_dict = dict(product)
            product_dict['id'] = str(product_dict['id'])
            product_dict['farmer_profile_id'] = str(product_dict['farmer_profile_id'])
            products_list.append(product_dict)
        
        return jsonify(products_list), 200
        
    except Exception as e:
        logger.error(f"Error getting farmer products: {str(e)}")
        return jsonify({'error': str(e)}), 500

@products_bp.route('/<product_id>', methods=['PUT'])
def update_product(product_id):
    """
    Update a product
    Expects: { firebase_uid, ...fields to update }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        
        # Verify ownership
        farmer_profile_id = get_farmer_profile_id(firebase_uid)
        if not farmer_profile_id:
            return jsonify({'error': 'Farmer profile not found'}), 404
        
        # Check if product exists and belongs to farmer
        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if str(product['farmer_profile_id']) != str(farmer_profile_id):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Handle image update if provided
        if data.get('image'):
            upload_result = upload_base64_image(
                data.get('image'),
                folder='mkulima-bora/products'
            )
            if upload_result:
                data['image_url'] = upload_result['secure_url']
        
        # Remove firebase_uid from update data
        update_data = {k: v for k, v in data.items() if k != 'firebase_uid' and k != 'image'}
        
        # Update product
        updated_product = Product.update_product(product_id, **update_data)
        
        if updated_product:
            product_dict = dict(updated_product)
            product_dict['id'] = str(product_dict['id'])
            product_dict['farmer_profile_id'] = str(product_dict['farmer_profile_id'])
            return jsonify(product_dict), 200
        else:
            return jsonify({'error': 'Failed to update product'}), 500
            
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        return jsonify({'error': str(e)}), 500

@products_bp.route('/<product_id>', methods=['DELETE'])
def delete_product(product_id):
    """
    Delete a product
    Expects: { firebase_uid }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        
        # Verify ownership
        farmer_profile_id = get_farmer_profile_id(firebase_uid)
        if not farmer_profile_id:
            return jsonify({'error': 'Farmer profile not found'}), 404
        
        # Check if product exists and belongs to farmer
        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if str(product['farmer_profile_id']) != str(farmer_profile_id):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete product
        success = Product.delete_product(product_id)
        
        if success:
            return jsonify({'message': 'Product deleted successfully'}), 200
        else:
            return jsonify({'error': 'Failed to delete product'}), 500
            
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        return jsonify({'error': str(e)}), 500

@products_bp.route('/<product_id>/publish', methods=['POST'])
def publish_product(product_id):
    """
    Publish a product (change status from draft to active)
    Expects: { firebase_uid }
    """
    try:
        data = request.get_json()
        firebase_uid = data.get('firebase_uid')
        
        if not firebase_uid:
            return jsonify({'error': 'firebase_uid is required'}), 400
        
        # Verify ownership
        farmer_profile_id = get_farmer_profile_id(firebase_uid)
        if not farmer_profile_id:
            return jsonify({'error': 'Farmer profile not found'}), 404
        
        # Check if product exists and belongs to farmer
        product = Product.get_product_by_id(product_id)
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        if str(product['farmer_profile_id']) != str(farmer_profile_id):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update status to active
        updated_product = Product.update_product(product_id, status='active')
        
        if updated_product:
            product_dict = dict(updated_product)
            product_dict['id'] = str(product_dict['id'])
            product_dict['farmer_profile_id'] = str(product_dict['farmer_profile_id'])
            return jsonify(product_dict), 200
        else:
            return jsonify({'error': 'Failed to publish product'}), 500
            
    except Exception as e:
        logger.error(f"Error publishing product: {str(e)}")
        return jsonify({'error': str(e)}), 500
