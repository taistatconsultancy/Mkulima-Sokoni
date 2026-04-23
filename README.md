# Mkulima Sokoni

**From Farm to Market.**

Mkulima Sokoni is a digital agricultural marketplace connecting Kenyan farmers to buyers, agro-dealers, and support services. The platform provides transparent pricing, real-time product listings, and direct deals across all 47 counties.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Pages & Navigation](#pages--navigation)
- [User Roles](#user-roles)
- [Admin Support Dashboard](#admin-support-dashboard)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)

---

## Features

- **Live Product Ticker** — Stock-style scrolling ticker showing active listings with images, prices, and locations
- **Product Marketplace** — Browse, filter, and search produce across categories (Vegetables, Fruits, Cereals, Livestock, Dairy, etc.)
- **Product Detail Pages** — Full product view with large image, pricing, seller/farmer info, view counts, share functionality, and similar products
- **Farmer Dashboard** — Add/manage products, view agro-dealers, browse marketplace listings with pagination, track orders and analytics
- **Buyer Dashboard** — Browse products, create tenders, manage orders, and maintain buyer profiles
- **Agro-Dealer Dashboard** — Inventory management, product listing, and order tracking for agro-dealers
- **Seller/Farmer Profiles** — Public profile pages showing farmer info, contact details, bio, and all listed products
- **Authentication** — Email/password and Google sign-in via Firebase, with role selection (Farmer, Buyer, Agro-Dealer)
- **Admin Support Dashboard** — Password-protected admin panel for user management, verification, support tickets, analytics, and super-user client account access
- **Dynamic View Counts** — Product views increment automatically when users visit product detail pages
- **Share Products & Profiles** — Share via WhatsApp, Facebook, X (Twitter), or copy link (requires sign-in)
- **Responsive Design** — Optimized for desktop, tablet, and mobile

---

## Tech Stack

| Layer      | Technology                                    |
|------------|-----------------------------------------------|
| Frontend   | HTML, CSS, Vanilla JavaScript                 |
| Backend    | Python, Flask, Flask-CORS                     |
| Database   | PostgreSQL (Neon)                              |
| Auth       | Firebase Authentication                        |
| Storage    | Cloudinary (product & profile images)          |
| Deployment | Vercel-ready (WSGI/ASGI support)              |
| Fonts      | Playfair Display, DM Sans (Google Fonts)      |

---

## Project Structure

```
Soko-Safi/
├── backend/
│   ├── app.py                  # Flask application entry point
│   ├── config.py               # Configuration settings
│   ├── database.py             # Database connection & query execution
│   ├── migrate.py              # Database migrations
│   ├── auth/
│   │   └── firebase_auth.py    # Firebase token verification
│   ├── models/
│   │   ├── user.py             # User model (auth, roles)
│   │   ├── product.py          # Product model (CRUD, views, orders)
│   │   ├── farmer_profile.py   # Farmer profile model
│   │   └── buyer_profile.py    # Buyer profile model
│   ├── routes/
│   │   ├── auth.py             # Auth routes (register, login, Google sign-in)
│   │   ├── products.py         # Product routes (CRUD, detail, farmer products)
│   │   ├── profiles.py         # Profile routes (farmer, buyer)
│   │   └── uploads.py          # File upload routes
│   └── utils/
│       └── cloudinary_service.py  # Cloudinary image upload utility
├── frontend/
│   ├── index.html              # Homepage (hero, ticker, marketplace, support)
│   ├── market.html             # Full marketplace page
│   ├── product-detail.html     # Product detail page (image, info, farmer card, similar)
│   ├── seller-profile.html     # Public farmer/seller profile page
│   ├── auth.html               # Authentication (sign in / sign up with role selection)
│   ├── farmer.html             # Farmer dashboard
│   ├── buyer.html              # Buyer dashboard
│   ├── agro-dealer.html        # Agro-Dealer dashboard
│   ├── admin-support.html      # Admin support dashboard (password-protected)
│   └── assets/
│       └── img/
│           └── sokosafi_logo.png
├── .env                        # Environment variables (not committed)
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- pip
- PostgreSQL database (or Neon account)
- Firebase project (for authentication)
- Cloudinary account (for image uploads)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd Soko-Safi

# Create virtual environment
python -m venv src
source src/bin/activate        # Linux/Mac
src\Scripts\Activate.ps1       # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Copy .env.example to .env and fill in your credentials
```

### Running Locally

```bash
# Start the backend server (serves both API and frontend)
cd backend
python app.py
```

The app runs at **http://localhost:5000**

- Frontend: `http://localhost:5000/index.html`
- API: `http://localhost:5000/api/...`

---

## Pages & Navigation

| Page                  | URL                          | Description                                            |
|-----------------------|------------------------------|--------------------------------------------------------|
| Homepage              | `/index.html`                | Hero section, product ticker, marketplace listings, support form |
| Marketplace           | `/market.html`               | Full product listings with filters and ticker          |
| Product Detail        | `/product-detail.html?id=…`  | Product image, pricing, farmer info, share, similar products |
| Farmer Profile        | `/seller-profile.html?uid=…` | Public farmer profile, contact info, all listed products |
| Authentication        | `/auth.html`                 | Sign in / Sign up with role selection                  |
| Farmer Dashboard      | `/farmer.html`               | Manage products, agro-dealers, marketplace, orders, analytics |
| Buyer Dashboard       | `/buyer.html`                | Browse products, tenders, orders, profile              |
| Agro-Dealer Dashboard | `/agro-dealer.html`          | Inventory, products, orders, profile                   |
| Admin Support         | `/admin-support.html`        | User management, verification, tickets, client access  |

---

## User Roles

| Role         | Description                                                          |
|--------------|----------------------------------------------------------------------|
| **Farmer**   | List produce, manage inventory, view orders, connect with buyers     |
| **Buyer**    | Browse/search products, create tenders, place orders                 |
| **Agro-Dealer** | List farming supplies, manage inventory, process orders          |
| **Admin**    | Manage users, verify accounts, handle support tickets, access client accounts |

---

## Admin Support Dashboard

The admin dashboard is protected by a login gate.

### Login Credentials

| Field    | Value                        |
|----------|------------------------------|
| Username | `TaiStat@sokosafi.com`       |
| Password | `Soko_Safi@2026`             |

### Admin Features

- **User Management** — View, edit, and verify all registered users
- **Verification** — Approve or reject user verification requests with document review
- **Support Tickets** — Manage and resolve support tickets from users
- **Client Account Access (Super User)** — Log in as any user by entering their email to see exactly what they see on their dashboard. A purple "SUPER USER" banner appears at the top of the client's dashboard. Access is logged per session.
- **Analytics** — Platform-wide stats (users, products, orders, revenue)

### Super User Access

1. Navigate to the **Client Access** tab
2. Enter the user's email address
3. Review the user's profile card (name, role, status, join date)
4. Click **Open Client Dashboard** — opens the user's actual dashboard in a new tab
5. A purple banner indicates you are viewing as admin
6. Click **Back to Admin** to exit

---

## API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint                  | Description                              |
|--------|---------------------------|------------------------------------------|
| POST   | `/api/auth/register`      | Register a new user                      |
| POST   | `/api/auth/login`         | Login with Firebase ID token             |
| POST   | `/api/auth/google-signin` | Google sign-in                           |
| POST   | `/api/auth/complete-registration` | Complete registration (role selection) |
| GET    | `/api/auth/user/<uid>`    | Get user by Firebase UID                 |
| GET    | `/api/auth/user-by-email?email=…` | Get user by email (admin use)   |
| POST   | `/api/auth/dashboard-route` | Get dashboard route for user role      |

### Products (`/api/products`)

| Method | Endpoint                          | Description                                 |
|--------|-----------------------------------|---------------------------------------------|
| GET    | `/api/products`                   | List products (filters: status, category, type, limit, offset) |
| POST   | `/api/products`                   | Create a product                            |
| GET    | `/api/products/<id>`              | Get product by ID (increments views)        |
| GET    | `/api/products/<id>/detail`       | Get product with seller info & similar products |
| PUT    | `/api/products/<id>`              | Update a product                            |
| DELETE | `/api/products/<id>`              | Delete a product                            |
| POST   | `/api/products/<id>/publish`      | Publish a draft product                     |
| GET    | `/api/products/farmer/<uid>`      | Get all products by a farmer                |

### Profiles (`/api/profiles`)

| Method | Endpoint                          | Description                              |
|--------|-----------------------------------|------------------------------------------|
| GET    | `/api/profiles/`                  | API info                                 |
| POST   | `/api/profiles/farmer`            | Create/update farmer profile             |
| GET    | `/api/profiles/farmer/<uid>`      | Get farmer profile by Firebase UID       |
| POST   | `/api/profiles/buyer`             | Create/update buyer profile              |
| GET    | `/api/profiles/buyer/<uid>`       | Get buyer profile by Firebase UID        |
| GET    | `/api/profiles/<uid>`             | Get all profiles for a user              |

---

## Environment Variables

Create a `.env` file in the project root with the following:

```env
# Database
DATABASE_URL=postgresql://...

# Cloudinary (image uploads)
CLOUD_NAME=your_cloud_name
API_KEY=your_api_key
API_SECRET=your_api_secret

# Firebase
FIREBASE_PROJECT_ID=your_project_id
FIREBASE_SERVICE_ACCOUNT_PATH=path/to/service-account.json
PUBLIC_APP_URL=Public link to access the app
```

---

## Design System

| Token       | Value     | Usage                          |
|-------------|-----------|--------------------------------|
| `--forest`  | `#1B4332` | Primary dark green             |
| `--leaf`    | `#40916C` | Secondary green                |
| `--lime`    | `#74C69D` | Accent green                   |
| `--gold`    | `#E9C46A` | Highlight / CTA                |
| `--cream`   | `#FAF6EF` | Page background                |
| `--ink`     | `#1A1A18` | Text color                     |
| `--muted`   | `#6B705C` | Secondary text                 |
| `--border`  | `#DDD8CE` | Card/input borders             |

Fonts: **Playfair Display** (headings), **DM Sans** (body)

---

*Powered by TaiStat Firm*
