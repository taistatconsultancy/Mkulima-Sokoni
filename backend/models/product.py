"""
Product model and database operations
"""
from database import execute_query, get_db_connection
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Product:
    """Product model for storing farm products and livestock listings"""
    
    @staticmethod
    def create_product(farmer_profile_id, name, category, product_type, location,
                      measurement_metric, quantity, min_order, image_url=None,
                      description=None, county=None, price=None, price_min=None, price_max=None,
                      planting_time=None, fertilizer_used=None, harvest_time=None,
                      status='draft'):
        """
        Create a new product
        
        Args:
            farmer_profile_id: UUID of the farmer profile
            name: Product name
            category: Product category (Vegetables, Fruits, Livestock, etc.)
            product_type: 'farm' or 'livestock'
            location: Location/County
            measurement_metric: Unit of measurement (kg, crate, piece, head, etc.)
            quantity: Available quantity
            min_order: Minimum order quantity
            image_url: Cloudinary URL for product image
            description: Product description (optional)
            county: County name (optional)
            price: Single price for farm products
            price_min: Minimum price for livestock
            price_max: Maximum price for livestock
            planting_time: Planting time (farm products only)
            fertilizer_used: Fertilizer used (farm products only)
            harvest_time: Harvest time (farm products only)
            status: Product status (default: 'draft')
        
        Returns:
            dict: Created product record
            None: If creation fails
        """
        try:
            # Validate farmer_profile_id is a UUID
            if isinstance(farmer_profile_id, str) and 'T' in farmer_profile_id:
                logger.error(f"CRITICAL: create_product received timestamp '{farmer_profile_id}' instead of UUID!")
                raise ValueError(f"Invalid farmer_profile_id: expected UUID, got timestamp '{farmer_profile_id}'")
            
            # Validate product_type
            if product_type not in ['farm', 'livestock']:
                raise ValueError(f"Invalid product_type: must be 'farm' or 'livestock'")
            
            # Validate pricing based on product_type
            if product_type == 'farm' and price is None:
                raise ValueError("Farm products require a 'price' field")
            if product_type == 'livestock' and (price_min is None or price_max is None):
                raise ValueError("Livestock products require both 'price_min' and 'price_max' fields")
            
            query = """
                INSERT INTO products 
                (farmer_profile_id, name, category, product_type, location, county,
                 price, price_min, price_max, measurement_metric, quantity, min_order,
                 planting_time, fertilizer_used, harvest_time, image_url, description,
                 status, views, orders, created_at, updated_at)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING *
            """
            params = (farmer_profile_id, name, category, product_type, location, county,
                     price, price_min, price_max, measurement_metric, quantity, min_order,
                     planting_time, fertilizer_used, harvest_time, image_url, description,
                     status)
            result = execute_query(query, params, fetch_one=True)
            return result if result else None
        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            raise
    
    @staticmethod
    def get_product_by_id(product_id):
        """
        Get product by ID
        
        Args:
            product_id: UUID of the product
        
        Returns:
            dict: Product record
            None: If not found
        """
        try:
            query = "SELECT * FROM products WHERE id = %s::uuid"
            result = execute_query(query, (product_id,), fetch_one=True)
            return result if result else None
        except Exception as e:
            logger.error(f"Error getting product by id: {str(e)}")
            raise
    
    @staticmethod
    def get_products_by_farmer(farmer_profile_id, status=None):
        """
        Get all products for a farmer
        
        Args:
            farmer_profile_id: UUID of the farmer profile
            status: Optional status filter ('draft', 'active', 'sold_out', 'archived')
        
        Returns:
            list: List of product records
        """
        try:
            if status:
                query = """
                    SELECT * FROM products 
                    WHERE farmer_profile_id = %s::uuid AND status = %s
                    ORDER BY created_at DESC
                """
                result = execute_query(query, (farmer_profile_id, status), fetch_all=True)
            else:
                query = """
                    SELECT * FROM products 
                    WHERE farmer_profile_id = %s::uuid
                    ORDER BY created_at DESC
                """
                result = execute_query(query, (farmer_profile_id,), fetch_all=True)
            return result if result else []
        except Exception as e:
            logger.error(f"Error getting products by farmer: {str(e)}")
            raise
    
    @staticmethod
    def get_all_products(status='active', category=None, product_type=None, limit=100, offset=0):
        """
        Get all products with optional filters
        
        Args:
            status: Product status filter (default: 'active')
            category: Optional category filter
            product_type: Optional product type filter ('farm' or 'livestock')
            limit: Maximum number of results (default: 100)
            offset: Offset for pagination (default: 0)
        
        Returns:
            list: List of product records
        """
        try:
            conditions = ["p.status = %s"]
            params = [status]
            
            if category:
                conditions.append("p.category = %s")
                params.append(category)
            
            if product_type:
                conditions.append("p.product_type = %s")
                params.append(product_type)

            # Marketplace policy: only verified/approved sellers are visible in listings.
            conditions.append("COALESCE(fp.certification_status, 'pending') IN ('verified', 'approved')")
            # Incomplete profiles are always treated as pending (not market-visible).
            conditions.append("NULLIF(TRIM(COALESCE(fp.farm_name, '')), '') IS NOT NULL")
            conditions.append("NULLIF(TRIM(COALESCE(fp.location, '')), '') IS NOT NULL")
            conditions.append("NULLIF(TRIM(COALESCE(fp.county, '')), '') IS NOT NULL")
            conditions.append("NULLIF(TRIM(COALESCE(fp.national_id, '')), '') IS NOT NULL")
            
            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])
            
            query = f"""
                SELECT p.*,
                       COALESCE(
                         (SELECT ur.role FROM user_roles ur
                          JOIN farmer_profiles fp ON fp.user_id = ur.user_id
                          WHERE fp.id = p.farmer_profile_id
                          LIMIT 1),
                         'farmer'
                       ) AS seller_role
                FROM products p
                INNER JOIN farmer_profiles fp ON fp.id = p.farmer_profile_id
                WHERE {where_clause}
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
            """
            result = execute_query(query, params, fetch_all=True)
            return result if result else []
        except Exception as e:
            logger.error(f"Error getting all products: {str(e)}")
            raise

    @staticmethod
    def get_admin_product_catalog(status='active', limit=200, offset=0):
        """
        All listings for admin dashboard (no marketplace verification filter).
        Includes seller email and display names for management UI.
        """
        try:
            limit = max(1, min(int(limit), 500))
            offset = max(0, int(offset))
            query = """
                SELECT p.*,
                       fp.farm_name AS seller_farm_name,
                       u.email AS seller_email,
                       NULLIF(TRIM(CONCAT_WS(' ', NULLIF(TRIM(u.first_name), ''), NULLIF(TRIM(u.last_name), ''))), '') AS seller_account_name,
                       COALESCE(
                         (SELECT ur.role FROM user_roles ur
                          JOIN farmer_profiles fp2 ON fp2.user_id = ur.user_id
                          WHERE fp2.id = p.farmer_profile_id
                          LIMIT 1),
                         'farmer'
                       ) AS seller_role
                FROM products p
                INNER JOIN farmer_profiles fp ON fp.id = p.farmer_profile_id
                INNER JOIN users u ON u.id = fp.user_id
                WHERE p.status = %s
                ORDER BY p.created_at DESC
                LIMIT %s OFFSET %s
            """
            result = execute_query(query, (status, limit, offset), fetch_all=True)
            return result if result else []
        except Exception as e:
            logger.error(f"Error getting admin product catalog: {str(e)}")
            raise

    @staticmethod
    def get_marketplace_meta(status='active', category=None, product_type=None):
        """
        Cheap aggregate for polling: active listing count and latest updated_at.
        Filters mirror get_all_products (same WHERE, no pagination).
        """
        try:
            conditions = [
                'p.status = %s',
                "COALESCE(fp.certification_status, 'pending') IN ('verified', 'approved')",
                "NULLIF(TRIM(COALESCE(fp.farm_name, '')), '') IS NOT NULL",
                "NULLIF(TRIM(COALESCE(fp.location, '')), '') IS NOT NULL",
                "NULLIF(TRIM(COALESCE(fp.county, '')), '') IS NOT NULL",
                "NULLIF(TRIM(COALESCE(fp.national_id, '')), '') IS NOT NULL",
            ]
            params = [status]
            if category:
                conditions.append('p.category = %s')
                params.append(category)
            if product_type:
                conditions.append('p.product_type = %s')
                params.append(product_type)
            where_clause = ' AND '.join(conditions)
            query = f"""
                SELECT COUNT(*)::int AS count, MAX(p.updated_at) AS latest_updated_at
                FROM products p
                INNER JOIN farmer_profiles fp ON fp.id = p.farmer_profile_id
                WHERE {where_clause}
            """
            row = execute_query(query, tuple(params), fetch_one=True)
            if not row:
                return {'count': 0, 'latest_updated_at': None}
            d = dict(row)
            lu = d.get('latest_updated_at')
            if lu is not None:
                d['latest_updated_at'] = lu.isoformat() if hasattr(lu, 'isoformat') else str(lu)
            return d
        except Exception as e:
            logger.error(f'Error getting marketplace meta: {str(e)}')
            raise
    
    @staticmethod
    def update_product(product_id, **kwargs):
        """
        Update product fields
        
        Args:
            product_id: UUID of the product
            **kwargs: Fields to update
        
        Returns:
            dict: Updated product record
            None: If update fails
        """
        try:
            allowed_fields = [
                'name', 'category', 'product_type', 'description', 'location', 'county',
                'price', 'price_min', 'price_max', 'measurement_metric', 'quantity', 'min_order',
                'planting_time', 'fertilizer_used', 'harvest_time', 'image_url', 'status',
                'is_featured'
            ]
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = %s")
                    params.append(value)
            
            if not updates:
                return None
            
            params.append(product_id)
            query = f"""
                UPDATE products 
                SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
                RETURNING *
            """
            result = execute_query(query, params, fetch_one=True)
            return result if result else None
        except Exception as e:
            logger.error(f"Error updating product: {str(e)}")
            raise
    
    @staticmethod
    def delete_product(product_id):
        """
        Delete a product
        
        Args:
            product_id: UUID of the product
        
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            query = "DELETE FROM products WHERE id = %s::uuid RETURNING id"
            result = execute_query(query, (product_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            raise
    
    @staticmethod
    def increment_views(product_id):
        """
        Increment product views counter
        
        Args:
            product_id: UUID of the product
        
        Returns:
            bool: True if updated, False otherwise
        """
        try:
            query = """
                UPDATE products 
                SET views = views + 1 
                WHERE id = %s::uuid
                RETURNING views
            """
            result = execute_query(query, (product_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"Error incrementing views: {str(e)}")
            raise
    
    @staticmethod
    def increment_orders(product_id):
        """
        Increment product orders counter
        
        Args:
            product_id: UUID of the product
        
        Returns:
            bool: True if updated, False otherwise
        """
        try:
            query = """
                UPDATE products 
                SET orders = orders + 1 
                WHERE id = %s::uuid
                RETURNING orders
            """
            result = execute_query(query, (product_id,), fetch_one=True)
            return result is not None
        except Exception as e:
            logger.error(f"Error incrementing orders: {str(e)}")
            raise

    @staticmethod
    def get_featured_products(limit=20):
        """
        Admin-curated ticker: active listings explicitly marked is_featured.
        No extra seller-verification filter — the admin selection is authoritative for the ticker.
        """
        try:
            query = """
                SELECT p.*,
                       COALESCE(
                         (SELECT ur.role FROM user_roles ur
                          JOIN farmer_profiles fp2 ON fp2.user_id = ur.user_id
                          WHERE fp2.id = p.farmer_profile_id
                          LIMIT 1),
                         'farmer'
                       ) AS seller_role
                FROM products p
                INNER JOIN farmer_profiles fp ON fp.id = p.farmer_profile_id
                WHERE p.status = 'active'
                  AND COALESCE(p.is_featured, FALSE) = TRUE
                ORDER BY p.updated_at DESC, p.created_at DESC
                LIMIT %s
            """
            result = execute_query(query, (limit,), fetch_all=True)
            return result if result else []
        except Exception as e:
            logger.error(f"Error getting featured products: {str(e)}")
            raise

    @staticmethod
    def clear_all_featured_flags():
        """Remove featured flag from every product (admin ticker reset)."""
        try:
            execute_query(
                "UPDATE products SET is_featured = FALSE WHERE COALESCE(is_featured, FALSE) = TRUE",
                tuple(),
            )
            return True
        except Exception as e:
            logger.error(f"Error clearing featured flags: {str(e)}")
            raise

