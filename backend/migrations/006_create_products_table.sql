-- Migration: Create products table for Phase 3
-- Products table for storing farm products and livestock listings

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_profile_id UUID NOT NULL REFERENCES farmer_profiles(id) ON DELETE CASCADE,
    
    -- Basic Information
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL, -- Vegetables, Fruits, Livestock, etc.
    product_type VARCHAR(20) NOT NULL CHECK (product_type IN ('farm', 'livestock')),
    description TEXT,
    
    -- Location
    location VARCHAR(255) NOT NULL, -- County/Area
    county VARCHAR(100),
    
    -- Pricing (flexible for both farm products and livestock)
    price DECIMAL(10, 2), -- Single price for farm products
    price_min DECIMAL(10, 2), -- Min price for livestock
    price_max DECIMAL(10, 2), -- Max price for livestock
    measurement_metric VARCHAR(50) NOT NULL, -- kg, crate, sack, piece, head, etc.
    
    -- Inventory
    quantity INTEGER NOT NULL DEFAULT 0,
    min_order INTEGER NOT NULL DEFAULT 1,
    
    -- Farm Product Specific Fields (nullable, only for farm products)
    planting_time VARCHAR(255),
    fertilizer_used VARCHAR(255),
    harvest_time VARCHAR(255),
    
    -- Media
    image_url VARCHAR(500), -- Cloudinary URL
    
    -- Status & Analytics
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'sold_out', 'archived')),
    is_featured BOOLEAN NOT NULL DEFAULT FALSE,
    views INTEGER DEFAULT 0,
    orders INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backfill for existing deployments that created products before is_featured existed.
ALTER TABLE products
ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_products_farmer_profile_id ON products(farmer_profile_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_product_type ON products(product_type);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_is_featured ON products(is_featured);
CREATE INDEX IF NOT EXISTS idx_products_county ON products(county);
CREATE INDEX IF NOT EXISTS idx_products_location ON products(location);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at DESC);

-- Create trigger to automatically update updated_at timestamp (idempotent re-runs)
DROP TRIGGER IF EXISTS trigger_update_products_updated_at ON products;
CREATE TRIGGER trigger_update_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

