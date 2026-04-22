# Database Audit Report (Conservative)

This audit follows a conservative rule: only remove objects that are 100% confirmed unused.  
Result: no table or column qualifies for safe removal at this time.

## Scope

- Reviewed migration files under `backend/migrations/` (`001` through `012`).
- Cross-checked table and column usage against SQL in Python backend code under `backend/`.
- Focused extra attention on later migrations: `005`, `006`, `010`, `011`, `012`.

## Migration Inventory

- `001_create_users_table.sql`
- `002_create_profile_tables.sql`
- `003_fix_timestamp_trigger.sql`
- `004_add_name_columns.sql`
- `005_add_profile_fields.sql`
- `006_create_products_table.sql`
- `007_verification_audit.sql`
- `008_create_support_tickets.sql`
- `009_create_chat_tables.sql`
- `010_create_commerce_tables.sql`
- `011_add_featured_flag_to_products.sql`
- `012_normalize_profile_verification_statuses.sql`

## Tables Created By Migrations

### 001
- `users`
- `user_roles`

### 002
- `farmer_profiles`
- `buyer_profiles`

### 006
- `products`

### 007
- `verification_audit`
- `admin_impersonation_log`
- `auth_login_audit`

### 008
- `support_tickets`
- `support_ticket_messages`

### 009
- `conversations`
- `messages`

### 010
- `carts`
- `cart_items`
- `orders`
- `order_items`
- `tenders`
- `tender_bids`

## Reference Status Summary

All created tables above are referenced from backend Python code (models/routes/services).  
No table is currently a guaranteed-unused candidate for removal.

Representative reference locations:

- `users`, `user_roles`: `backend/models/user.py`, `backend/routes/auth.py`
- `farmer_profiles`, `buyer_profiles`: `backend/models/farmer_profile.py`, `backend/models/buyer_profile.py`, `backend/routes/profiles.py`
- `products`: `backend/models/product.py`, `backend/routes/products.py`, `backend/routes/auth.py`
- audit/security tables: `backend/routes/auth.py`, `backend/models/user.py`
- support tables: `backend/models/support_ticket.py`, `backend/routes/support.py`
- chat tables: `backend/models/chat.py`, `backend/routes/chat.py`
- commerce tables: `backend/routes/cart.py`, `backend/routes/orders.py`, `backend/routes/tenders.py`

## Column Audit (Late Migrations)

### 005 (`add_profile_fields`)
Added profile identity/address/extra fields on `farmer_profiles` and `buyer_profiles`.  
These columns are referenced by backend profile routes/models and remain in active use.

### 006 (`create_products_table`)
Core product columns are used by product listing, seller dashboards, and admin stats/routes.

### 010 (`create_commerce_tables`)
Commerce columns are used in cart/order/tender flows and associated SQL joins.

### 011 (`add_featured_flag_to_products`)
`products.is_featured` is actively used by featured product/admin logic.

### 012 (`normalize_profile_verification_statuses`)
No new tables/columns; status normalization and CHECK constraints only.

## Notes

- `carts.status` CHECK includes `'abandoned'`. The literal value appears not to be actively set/read in backend Python logic. This is an enum-value usage gap, not a removable table/column.

## Final Recommendation

- Do not drop any tables or columns now.
- Keep schema unchanged until a separate, staged cleanup confirms runtime behavior/telemetry and data retention needs.
