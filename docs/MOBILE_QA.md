# Mobile QA Checklist

Viewport targets: `360px`, `414px`, `768px`  
Roles/pages: `buyer.html`, `farmer.html`, `agro-dealer.html`

## Checklist Used

- Topbar fits on small screens (hamburger visible, no badge/menu overlap).
- Main horizontal padding remains readable (>= 14px at mobile breakpoints).
- Product/inventory grids collapse correctly at mobile widths.
- Orders/Tenders/Cart tables scroll horizontally without page overflow.
- Touch targets remain usable (chat avatars and key controls at >= 40px where applicable).
- Chat inbox/thread behavior remains usable on mobile.
- Profile forms collapse to one column at mobile widths.

## Buyer (`frontend/buyer.html`)

- `360px`: Pass
  - Added compact topbar behavior and hides status text label.
  - Stats collapse to single column.
  - Cart, tenders, and orders tables use `.table-scroll`.
- `414px`: Pass
  - Two-column product cards preserved, no forced overflow from table content.
  - Chat avatars increased to 40px.
- `768px`: Pass
  - Mobile nav drawer behavior active.
  - Stats use two-column layout.
  - Forms/chat stack vertically.

## Farmer (`frontend/farmer.html`)

- `360px`: Pass
  - Added compact topbar behavior and hides status label text.
  - Agro-dealer dashboard strip collapses to one column.
  - Market listings force single-column layout.
- `414px`: Pass
  - Orders/tenders tables wrapped in `.table-scroll`.
  - Chat avatars increased to 40px.
- `768px`: Pass
  - Mobile nav drawer behavior active.
  - Form and chat shell stack correctly.
  - Stats remain two columns.

## Agro-dealer (`frontend/agro-dealer.html`)

- `360px`: Pass
  - Compact topbar behavior added (status text hidden, tighter spacing).
  - User menu condensed.
- `414px`: Pass
  - Orders/tenders tables wrapped with `.table-scroll`.
  - Chat avatar target increased to 40px.
- `768px`: Pass
  - `inv-grid` now responsive to two columns.
  - `mk-grid` stays two columns and chat stacks correctly.
  - Profile/add-product form is single-column.

## Notes

- This pass is based on the implemented responsive CSS/markup checks for the requested breakpoints.
- If you want a screenshot-backed regression gate next, the next step is adding Playwright mobile snapshots for these three pages.
