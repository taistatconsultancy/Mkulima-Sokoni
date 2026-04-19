-- Add admin-curated featured flag for marketplace top movers ticker.
ALTER TABLE products
ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_products_is_featured
ON products(is_featured);
