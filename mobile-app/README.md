# Mobile App (PWA-First)

This folder contains a phone-focused Progressive Web App that reuses the current backend APIs and core marketplace/commerce/messaging flows.

## Scope

- Mobile-first shell for Buyer, Farmer, and Agro-dealer roles
- Responsive card-based layouts for commerce sections
- Installable PWA (`manifest.json` + `service worker`)
- Offline-friendly app shell and graceful network retry states

## Run Locally

You can serve the project using your existing Flask backend static serving, or any simple static server.

### Option A: Existing backend

1. Start backend: `python .\\backend\\app.py`
2. Open: `http://localhost:5000/mobile-app/index.html`

### Option B: Static preview only

If using a static server, API calls still require backend running on localhost.

## File Layout

- `index.html` - mobile app entry shell
- `css/mobile.css` - mobile-first styles and responsive behavior
- `js/mobile-shell.js` - role routing, UI rendering, install/offline behavior
- `js/api-client.js` - shared API client and role-centric API wrappers
- `manifest.json` - PWA metadata
- `sw.js` - app shell service worker
- `assets/icons/` - install icons

## Notes

- Backend APIs are unchanged and reused from `/api/*`.
- This app does not modify existing desktop pages under `frontend/`.
- Capacitor wrapping can be added later if store packaging is required.
