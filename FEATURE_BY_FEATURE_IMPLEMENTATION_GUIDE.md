# Vendly.lk Ã¢â‚¬â€ Feature-by-Feature Coding Handbook

This handbook rebuilds the current Vendly system in the same order that the
features were requested and implemented. Work through one feature at a time.
Do not begin the next feature until the current feature passes its checklist.

The complete contents of every current source file are included later in this
document, grouped by the feature they primarily implement. Secret `.env` files,
Firebase Admin credentials, dependencies, build output and binary assets are
never included.

## How to use this handbook

For each feature:

1. read **What this feature does**;
2. create the listed files in the given order;
3. copy the exact source from that feature's source section;
4. add only placeholder values to environment files;
5. start Flask and React;
6. complete the verification checklist;
7. commit the working feature before continuing.

Useful commands:

```powershell
# Backend terminal
cd D:\Documents\orderflow\vendly-lk-web\backend
.\.venv\Scripts\Activate.ps1
python run.py

# Frontend terminal
cd D:\Documents\orderflow\vendly-lk-web\frontend
npm run dev

# Verification
cd D:\Documents\orderflow\vendly-lk-web\backend
.\.venv\Scripts\python.exe -m pytest

cd D:\Documents\orderflow\vendly-lk-web\frontend
npm run lint
npm run build
```

## Feature 1 Ã¢â‚¬â€ Create the React and Flask foundation

### What this feature does

Creates the three-tier application: React renders the interface, Flask owns
business rules, and Firestore stores persistent data.

### Build order

1. Create `frontend` using Vite React.
2. Create `backend` and its virtual environment.
3. Install the dependencies from `package.json` and `requirements.txt`.
4. Create the Flask application factory and `/api/v1/health` endpoint.
5. Configure CORS for `http://localhost:5173`.
6. Create the React router and API client.

### Data and API

```text
GET /api/v1/health
```

The API client converts JavaScript objects to JSON, reads JSON responses and
turns non-success responses into JavaScript errors.

### Verify

- Flask starts on port 5000.
- Vite starts on port 5173.
- `/api/v1/health` returns a successful JSON response.
- No secret is present in React source.

## Feature 2 Ã¢â‚¬â€ Configure Firebase Authentication

### What this feature does

Adds seller email/password and Google login. Firebase authenticates identity;
Flask verifies the Firebase ID token before accessing protected data.

### Firebase Console

1. Create a Firebase project.
2. Add a Web application.
3. Enable Email/Password and Google providers.
4. Download a Firebase Admin service-account file outside the repository.
5. Add the web values to `frontend/.env.local` using `VITE_FIREBASE_*` names.
6. Add the Admin file path and project ID to `backend/.env`.

### Request flow

```text
React login -> Firebase Auth -> ID token
ID token -> Authorization: Bearer TOKEN -> Flask
Flask verify_id_token() -> g.current_user
```

Email/password accounts must verify their email. Google accounts are already
provider-verified.

### Verify

- Registration sends a verification email.
- Unverified email login is rejected.
- Google login works.
- Flask rejects missing, expired or invalid tokens.

## Feature 3 Ã¢â‚¬â€ Seller onboarding and business creation

### What this feature does

Collects owner name and business name once, creates the business, owner
membership, seller profile and public short link.

### Firestore writes

```text
users/{uid}
businesses/{businessId}
businesses/{businessId}/members/{uid}
shortLinks/{storeShortCode}
```

The owner user stores `defaultBusinessId` and `businessIds`. The membership
stores role `owner`, status `active` and unrestricted permissions.

### API

```text
GET  /api/v1/me
POST /api/v1/businesses
```

### Verify

- Business setup appears only when no business exists.
- Logging out and back in does not ask for the business name again.
- Business name appears in Overview, Header and Sidebar.

## Feature 4 Ã¢â‚¬â€ Dashboard shell, routing and dark mode

### What this feature does

Builds the reusable sidebar, header, protected pages, responsive layout,
collapse button, theme persistence and profile menu.

### React concepts

- `useState` stores collapse, theme and menu state.
- `useEffect` writes the theme to `localStorage` and the HTML dataset.
- `NavLink` applies the active-page class.
- `ProtectedRoute` redirects logged-out users.
- `lazy` and `Suspense` split large pages into separate bundles.

### Verify

- Sidebar navigation changes routes without refreshing.
- Collapse state changes the layout correctly.
- Dark theme remains after refreshing.
- Mobile menu and profile dropdown are keyboard accessible.

## Feature 5 Ã¢â‚¬â€ Profile, email and password management

### What this feature does

Adds My Profile, logout, verified email changes, password changes and password
reset. Firebase requires recent authentication for sensitive changes.

### Security

Never accept a password in Flask or store it in Firestore. Password operations
remain inside Firebase Authentication. Reauthenticate with the current password
or Google popup before changing sensitive account details.

### Verify

- Profile modal fits within the viewport and scrolls internally.
- New email is applied only after verification.
- Wrong current password is rejected.
- Google accounts are not shown password-only controls.

## Feature 6 Ã¢â‚¬â€ Staff assignment and permissions

### What this feature does

Lets an owner/admin add an existing Vendly account to a business and assign a
role. Both frontend navigation and backend endpoints enforce permissions.

### Roles

```text
admin             broad management access
order_manager     orders, customers, courier reading, inventory reading
inventory_manager inventory management, order reading, review moderation
support           order/customer reading and messages
viewer            read-only orders, inventory and analytics
```

### Permission format

```text
orders:read
orders:manage
orders:*
*
```

Backend permission checks are the security boundary. Hiding a sidebar item is
only a usability improvement.

### Verify

- Staff must first create a Vendly Firebase account.
- Adding staff sets their `defaultBusinessId` and `businessIds`.
- Disabled staff receive HTTP 403.
- Typing a forbidden dashboard URL redirects safely.
- Typing a forbidden API URL returns HTTP 403.

## Feature 7 Ã¢â‚¬â€ Categories

### What this feature does

Adds category creation, editing, expansion, product grouping and safe archival.
Category totals are calculated from products rather than typed manually.

### API

```text
GET    /api/v1/businesses/{businessId}/categories
POST   /api/v1/businesses/{businessId}/categories
PATCH  /api/v1/businesses/{businessId}/categories/{categoryId}
DELETE /api/v1/businesses/{businessId}/categories/{categoryId}
```

### Verify

- Duplicate category names are rejected appropriately.
- Expanding a category shows its products.
- Removing a category asks for confirmation.
- Historical product/order data is not physically destroyed.

## Feature 8 Ã¢â‚¬â€ Products, one variant layer, SKU and barcode

### What this feature does

Each colour is stored as a separate product. A product optionally has one
variant layer, currently size. Every variant owns SKU, barcode, stock, selling
price and cost price. Simple products still receive one default variant.

### Firestore documents

```text
businesses/{businessId}/products/{productId}
businesses/{businessId}/productVariants/{variantId}
```

Product documents keep `variantSummaries` for efficient inventory-table reads.
The complete variant document remains the authoritative stock record.

### API

```text
GET    /api/v1/businesses/{businessId}/products
POST   /api/v1/businesses/{businessId}/products
GET    /api/v1/businesses/{businessId}/products/{productId}
PATCH  /api/v1/businesses/{businessId}/products/{productId}
DELETE /api/v1/businesses/{businessId}/products/{productId}
```

### Verify

- Variant fields appear only when the checkbox is selected.
- SKU and barcode generators avoid collisions.
- Edit Product loads the complete existing product into the same form.
- Product totals equal the sum of active variants.

## Feature 9 Ã¢â‚¬â€ Product media and AI descriptions

### What this feature does

Uploads product/variant images to Cloudinary and stores only returned URLs in
Firestore. AI description generation receives trusted product facts and never
writes stock or pricing.

### API

```text
POST /api/v1/businesses/{businessId}/products/{productId}/media
POST /api/v1/businesses/{businessId}/products/{productId}/variants/{variantId}/image
POST /api/v1/businesses/{businessId}/products/generate-description
```

### Verify

- Cloudinary secrets exist only in Flask `.env`.
- Upload validates type and size.
- Primary image appears in inventory, storefront, chatbot, order and receipt.
- AI failure leaves the form usable and never invents unsupported facts.

## Feature 10 Ã¢â‚¬â€ Inventory and stock transactions

### What this feature does

Adds stock adjustment, low/out-of-stock state, bulk actions, barcode search and
an immutable transaction history.

### Firestore

```text
businesses/{businessId}/inventoryTransactions/{transactionId}
```

Never change stock without also writing the reason, before/after quantity,
actor and timestamp.

### Verify

- Negative available stock is rejected.
- Variant and product summary totals update together.
- Bulk adjust/status/export actions use selected IDs.
- Reset filters restores all rows without a page refresh.

## Feature 11 Ã¢â‚¬â€ Customers and fraud risk

### What this feature does

Stores seller-specific customer records, normalized Sri Lankan phone numbers,
addresses, tags, private notes, return counts and risk level.

### Verify

- Invalid phone/address input is rejected.
- Existing customers can be found by normalized phone.
- Returned/fake-order events update risk without exposing private notes.

## Feature 12 Ã¢â‚¬â€ Couriers, delivery fees and waybill ranges

### What this feature does

Stores first-kilogram price, extra-kilogram price, location overrides,
performance history and an assignable waybill range.

### Server calculations

```text
chargeable kilograms = ceiling(total grams / 1000)
fee = first kg price + extra kg count Ãƒâ€” extra kg price
```

Waybill assignment occurs inside the same Firestore transaction as order
creation. This prevents two simultaneous orders receiving the same number.

### Verify

- District and total weight affect delivery fee.
- Exhausted waybill ranges return HTTP 409.
- Duplicate manual waybill numbers return an error popup.
- Courier issue reports influence performance data.

## Feature 13 Ã¢â‚¬â€ Manual multi-item order creation

### What this feature does

Adds the seller Add Order modal with customer details, product search, variants,
multiple order items, quantities, delivery, discount, payment and confirmation.

### Trusted order workflow

1. Validate customer and items.
2. Load variants and product prices from Firestore.
3. Check stock inside a transaction.
4. Calculate weight and delivery fee.
5. Assign courier, order number and waybill.
6. Reserve stock.
7. Write order, waybill, inventory transactions and notification atomically.

React never submits a trusted price or total.

### Verify

- Multiple items become one order document.
- The same variant rows merge quantities.
- Stock is reserved exactly once.
- Order and waybill sequences remain unique.

## Feature 14 Ã¢â‚¬â€ Order table, editing and status workflow

### What this feature does

Adds expandable rows, photos, filters, stat-card filtering, action menus, edit
order, bulk actions and controlled fulfilment transitions.

```text
needs-confirmation -> confirmed -> packed -> shipped -> delivered
                  \-> cancelled
shipped -> returned
```

Cancellation/return releases reserved stock. Delivery converts reservation to
a completed sale. Invalid jumps return HTTP 409.

### Verify

- Stat values do not change when filtering.
- Clearing search/reset restores the complete table.
- Edit Order updates permitted fields without recreating the order.
- Deletion uses safe cancellation rather than destroying history.

## Feature 15 Ã¢â‚¬â€ Excel export, notifications, receipts and waybills

### What this feature does

Exports filtered order/inventory data, creates notifications, prints waybills
and generates a customer PDF receipt instead of a text file.

### Verify

- Exported amounts and rows match the selected filter.
- Clicking a notification opens the relevant record.
- PDF contains business, customer, items, totals, courier and order number.
- Notification permission is requested only after a user action.

## Feature 16 Ã¢â‚¬â€ Seller and product short links

### What this feature does

Creates public links without exposing Firestore business IDs:

```text
https://vendly.lk/s/V7k92M
https://vendly.lk/p/P8x43K
```

`shortLinks/{code}` resolves the business/product. Product links restrict
checkout to that linked product.

### Verify

- Inactive/unknown links return 404.
- A store link returns only that seller's active products.
- A product link cannot order another product.

## Feature 17 Ã¢â‚¬â€ Storefront catalogue, cart and checkout

### What this feature does

Builds the public responsive catalogue, category/search filters, variant
selection, multi-product cart, contact form, calculated checkout and receipt.

### Verify

- Cart quantity never exceeds available stock.
- Mobile sidebar/cart layouts fit the viewport.
- Checkout uses Flask-calculated subtotal, delivery and total.
- Confirmation clears only the completed cart.

## Feature 18 Ã¢â‚¬â€ Product-information and ordering chatbot

### What this feature does

The chatbot shows product cards, answers product facts, lists categories,
suggests alternatives, handles multiple items, validates contact information,
asks for confirmation and creates one trusted order.

### Chat security

Each session gets a random secret. The raw secret stays in the browser; only a
SHA-256 hash is stored. Message and order requests send:

```http
X-Chat-Session-Token: secret-session-token
```

### Verify

- Product/category questions show the correct seller's items.
- Unknown specifications are not invented.
- Multiple cart items remain one order.
- After selecting a size, minus, direct number input and plus controls appear
  inside the product-detail reply.
- Direct input is limited to the variant's available stock; zero removes the
  item from the live order draft.
- Order is not created before explicit confirmation.

## Feature 19 Ã¢â‚¬â€ Customer login, guest login and private history

### What this feature does

Adds storefront email, Google and anonymous guest authentication. Chats and
new orders store the verified Firebase `customerUid`, allowing the account
panel to show saved chats, orders, status, courier and waybill details.

### Firebase Console

Enable Email/Password, Google and Anonymous providers.

### Identity model

```text
customerId  -> seller's CRM customer document
customerUid -> Firebase account allowed to read storefront history
```

### API

```text
POST /api/v1/public/chat/sessions/{sessionId}/claim
GET  /api/v1/public/stores/{storeCode}/customer/orders
GET  /api/v1/public/stores/{storeCode}/customer/orders/{orderId}
GET  /api/v1/public/stores/{storeCode}/customer/chats
```

The backend derives UID from the Firebase token. Never accept customer UID from
a URL or ordinary request body. Public responses remove costs, private notes,
fraud information and staff fields.

### Verify

- Guest history persists in the same browser.
- Email/Google history works across devices.
- One account cannot claim another account's chat.
- One account cannot read another account's order ID.
- Orders created before `customerUid` are not exposed by insecure phone lookup.

## Feature 20 Ã¢â‚¬â€ Reviews

### What this feature does

Accepts order-verified seller/product reviews, queues moderation and shows only
approved reviews in the catalogue and chatbot.

### Verify

- Invalid order/phone combinations cannot review.
- Staff without review permission cannot moderate.
- Private/unapproved reviews never appear publicly.

## Feature 21 Ã¢â‚¬â€ Analytics and global search

### What this feature does

Calculates dashboard summaries, daily/monthly orders, revenue and product
performance. Global search finds order, customer, product, SKU, barcode,
waybill and tracking data permitted to the staff role.

### Verify

- Analytics are calculated from authoritative order status/data.
- Search is seller-scoped.
- A staff member cannot search inaccessible business data.

## Feature 22 Ã¢â‚¬â€ Final security and deployment checks

### Required checks

```powershell
.\.venv\Scripts\python.exe -m pytest
npm run lint
npm run build
```

Before deployment:

- configure production frontend origins;
- configure Firebase authorized domains;
- keep Admin/Cloudinary/AI secrets only in backend environment variables;
- use HTTPS;
- use persistent rate-limit storage in multi-instance production;
- deploy Firestore indexes;
- test all roles and customer ownership with two separate accounts;
- never commit `.env`, `.env.local` or service-account JSON.

## Exact current code grouped by feature

The sections below contain the exact current local source files. A file appears
under the feature it primarily implements. Some shared files participate in
several features; read their imports to follow those connections.

## Feature 1 source — React, Flask and configuration foundation

Files in this feature: 28

### `frontend/package.json`

````json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "oxlint",
    "preview": "vite preview"
  },
  "dependencies": {
    "@fontsource-variable/inter": "^5.3.0",
    "firebase": "^12.17.1",
    "jspdf": "^4.2.1",
    "lucide-react": "^1.28.0",
    "react": "^19.2.8",
    "react-dom": "^19.2.8",
    "react-router-dom": "^7.18.2"
  },
  "devDependencies": {
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.4",
    "oxlint": "^1.75.0",
    "vite": "^8.2.0"
  },
  "allowScripts": {
    "@firebase/util@1.15.2": true,
    "protobufjs@7.6.5": true
  }
}
````

### `frontend/vite.config.js`

````javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "firebase-firestore",
              test: /node_modules[\\/]@firebase[\\/]firestore/,
            },
            {
              name: "firebase-auth",
              test: /node_modules[\\/]@firebase[\\/]auth/,
            },
            {
              name: "firebase-core",
              test: /node_modules[\\/](?:@firebase|firebase)[\\/]/,
            },
            {
              name: "react-vendor",
              test: /node_modules[\\/](?:react|react-dom|react-router-dom)[\\/]/,
            },
          ],
        },
      },
    },
  },
})
````

### `frontend/index.html`

````html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Vendly.lk</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
````

### `backend/requirements.txt`

````text
Flask>=3.1,<4
flask-cors>=6,<7
Flask-Limiter>=4,<5
firebase-admin>=7,<8
google-genai>=1,<2
httpx>=0.28,<1
openpyxl>=3.1,<4
python-dotenv>=1.1,<2
gunicorn>=23,<24
pytest>=8,<10
````

### `backend/run.py`

````python
import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=app.config["DEBUG"],
    )

````

### `firebase.json`

````json
{
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  },
  "storage": {
    "rules": "storage.rules"
  }
}
````

### `firestore.rules`

````javascript
rules_version = '2';

service cloud.firestore {
  match /databases/{database}/documents {
    function signedIn() {
      return request.auth != null;
    }

    // Legacy seller records are migrated by the trusted Flask backend.
    match /sellers/{sellerId} {
      allow read, write: if false;
    }

    // Users may read their own backend-managed profile.
    match /users/{userId} {
      allow read: if signedIn() && request.auth.uid == userId;
      allow write: if false;
    }

    // Authoritative business data is accessed through the authenticated Flask API.
    match /businesses/{businessId}/{document=**} {
      allow read, write: if false;
    }

    match /shortLinks/{shortCode} {
      allow read, write: if false;
    }

    match /publicChatSessions/{sessionId}/{document=**} {
      allow read, write: if false;
    }

    match /{document=**} {
      allow read, write: if false;
    }
  }
}
````

### `firestore.indexes.json`

````json
{
  "indexes": [],
  "fieldOverrides": []
}
````

### `storage.rules`

````javascript
rules_version = '2';

service firebase.storage {
  match /b/{bucket}/o {
    // Media uploads and downloads will use backend-authorised URLs.
    match /{allPaths=**} {
      allow read, write: if false;
    }
  }
}
````

### `backend/app/__init__.py`

````python
from flask import Flask, jsonify
from flask_cors import CORS

from app.api.businesses import businesses_blueprint
from app.api.analytics import analytics_blueprint
from app.api.categories import categories_blueprint
from app.api.customers import customers_blueprint
from app.api.couriers import couriers_blueprint
from app.api.health import health_blueprint
from app.api.me import me_blueprint
from app.api.members import members_blueprint
from app.api.orders import orders_blueprint
from app.api.operations import operations_blueprint
from app.api.products import products_blueprint
from app.api.public import public_blueprint
from app.api.reviews import reviews_blueprint
from app.api.search import search_blueprint
from app.core.config import Settings
from app.core.errors import ApiError, api_error_payload
from app.core.firebase import initialize_firebase
from app.core.rate_limit import limiter


def create_app(test_config=None):
    """Create and configure one Vendly Flask application instance."""
    settings = Settings.from_environment()

    app = Flask(__name__)
    app.config.from_mapping(
        DEBUG=settings.debug,
        JSON_SORT_KEYS=False,
        FIREBASE_PROJECT_ID=settings.firebase_project_id,
        FIREBASE_STORAGE_BUCKET=settings.firebase_storage_bucket,
        CLOUDINARY_CLOUD_NAME=settings.cloudinary_cloud_name,
        CLOUDINARY_API_KEY=settings.cloudinary_api_key,
        CLOUDINARY_API_SECRET=settings.cloudinary_api_secret,
        MAX_CONTENT_LENGTH=60 * 1024 * 1024,
        AI_PROVIDER=settings.ai_provider,
        AI_API_KEY=settings.ai_api_key,
        AI_MODEL=settings.ai_model,
        AI_API_BASE_URL=settings.ai_api_base_url,
        AI_TIMEOUT_SECONDS=settings.ai_timeout_seconds,
        RATELIMIT_STORAGE_URI=settings.rate_limit_storage_uri,
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_ENABLED=True,
    )

    if test_config:
        app.config.update(test_config)

    if app.config.get("TESTING"):
        app.config["RATELIMIT_ENABLED"] = False

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": settings.frontend_origins,
                "allow_headers": [
                    "Authorization",
                    "Content-Type",
                    "X-Chat-Session-Token",
                ],
                "methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                "expose_headers": [
                    "Content-Disposition",
                    "X-RateLimit-Limit",
                    "X-RateLimit-Remaining",
                    "X-RateLimit-Reset",
                ],
            },
        },
    )

    initialize_firebase(settings)
    limiter.init_app(app)

    app.register_blueprint(health_blueprint)
    app.register_blueprint(analytics_blueprint)
    app.register_blueprint(me_blueprint)
    app.register_blueprint(members_blueprint)
    app.register_blueprint(businesses_blueprint)
    app.register_blueprint(categories_blueprint)
    app.register_blueprint(customers_blueprint)
    app.register_blueprint(couriers_blueprint)
    app.register_blueprint(products_blueprint)
    app.register_blueprint(orders_blueprint)
    app.register_blueprint(operations_blueprint)
    app.register_blueprint(public_blueprint)
    app.register_blueprint(reviews_blueprint)
    app.register_blueprint(search_blueprint)

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(api_error_payload(error)), error.status_code

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Route not found."}}), 404

    @app.errorhandler(413)
    def handle_payload_too_large(_error):
        return jsonify(
            {
                "error": {
                    "code": "payload_too_large",
                    "message": "The uploaded request is too large.",
                },
            },
        ), 413

    @app.errorhandler(429)
    def handle_rate_limit(_error):
        return jsonify(
            {
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests. Please wait and try again.",
                },
            },
        ), 429

    @app.errorhandler(500)
    def handle_server_error(_error):
        return jsonify(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected server error occurred.",
                },
            },
        ), 500

    return app
````

### `backend/app/api/__init__.py`

````python
"""HTTP API blueprints for Vendly."""
````

### `backend/app/api/categories.py`

````python
from flask import Blueprint, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.category_service import (
    create_category,
    list_categories,
    update_category,
)


categories_blueprint = Blueprint("categories", __name__, url_prefix="/api/v1")


@categories_blueprint.get("/businesses/<business_id>/categories")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_categories(business_id):
    categories = list_categories(get_firestore_client(), business_id)
    return jsonify({"categories": categories})


@categories_blueprint.post("/businesses/<business_id>/categories")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_category(business_id):
    payload = get_json_object()

    category = create_category(
        get_firestore_client(),
        business_id,
        payload,
    )
    return jsonify({"category": category}), 201


@categories_blueprint.patch("/businesses/<business_id>/categories/<category_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def edit_category(business_id, category_id):
    payload = get_json_object()

    category = update_category(
        get_firestore_client(),
        business_id,
        category_id,
        payload,
    )
    return jsonify({"category": category})


@categories_blueprint.delete("/businesses/<business_id>/categories/<category_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def remove_category(business_id, category_id):
    category = update_category(
        get_firestore_client(),
        business_id,
        category_id,
        {"status": "archived"},
    )
    return jsonify({"category": category})
````

### `backend/app/api/health.py`

````python
from flask import Blueprint, jsonify


health_blueprint = Blueprint("health", __name__, url_prefix="/api/v1")


@health_blueprint.get("/health")
def health_check():
    """Public liveness endpoint used by local development and hosting."""
    return jsonify({"status": "ok", "service": "vendly-api"})
````

### `backend/app/api/public.py`

````python
from flask import Blueprint, g, jsonify, request

from app.core.auth import optional_firebase_user, require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.core.rate_limit import limiter, public_chat_key
from app.services.public_catalog_service import get_public_product, get_public_store
from app.services.public_chat_service import (
    answer_public_message,
    create_public_chat_order,
    create_public_chat_session,
    claim_public_chat_session,
)
from app.services.customer_portal_service import (
    get_customer_order,
    list_customer_chats,
    list_customer_orders,
)


public_blueprint = Blueprint("public", __name__, url_prefix="/api/v1/public")


@public_blueprint.get("/stores/<short_code>")
@limiter.limit("120 per minute")
def public_store(short_code):
    return jsonify(get_public_store(get_firestore_client(), short_code))


@public_blueprint.get("/products/<short_code>")
@limiter.limit("120 per minute")
def public_product(short_code):
    return jsonify(get_public_product(get_firestore_client(), short_code))


@public_blueprint.post("/chat/sessions")
@limiter.limit("20 per minute")
@optional_firebase_user
def start_public_chat():
    session = create_public_chat_session(
        get_firestore_client(),
        get_json_object(),
        (g.current_user or {}).get("uid"),
    )
    return jsonify(session), 201


@public_blueprint.post("/chat/sessions/<session_id>/messages")
@limiter.limit("60 per minute", key_func=public_chat_key)
def public_chat_message(session_id):
    response = answer_public_message(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        get_json_object(),
    )
    return jsonify(response)


@public_blueprint.post("/chat/sessions/<session_id>/orders")
@limiter.limit("6 per minute", key_func=public_chat_key)
@optional_firebase_user
def public_chat_order(session_id):
    session_token = request.headers.get("X-Chat-Session-Token", "")
    if g.current_user:
        claim_public_chat_session(
            get_firestore_client(),
            session_id,
            session_token,
            g.current_user["uid"],
        )
    order = create_public_chat_order(
        get_firestore_client(),
        session_id,
        session_token,
        get_json_object(),
    )
    return jsonify({"order": order}), 201


@public_blueprint.post("/chat/sessions/<session_id>/claim")
@require_firebase_user
def claim_public_chat(session_id):
    result = claim_public_chat_session(
        get_firestore_client(),
        session_id,
        request.headers.get("X-Chat-Session-Token", ""),
        g.current_user["uid"],
    )
    return jsonify(result)


@public_blueprint.get("/stores/<store_code>/customer/orders")
@require_firebase_user
def customer_orders(store_code):
    return jsonify(
        {"orders": list_customer_orders(get_firestore_client(), store_code, g.current_user["uid"])}
    )


@public_blueprint.get("/stores/<store_code>/customer/orders/<order_id>")
@require_firebase_user
def customer_order(store_code, order_id):
    return jsonify(
        {"order": get_customer_order(get_firestore_client(), store_code, g.current_user["uid"], order_id)}
    )


@public_blueprint.get("/stores/<store_code>/customer/chats")
@require_firebase_user
def customer_chats(store_code):
    return jsonify(
        {"chats": list_customer_chats(get_firestore_client(), store_code, g.current_user["uid"])}
    )
````

### `backend/app/core/__init__.py`

````python
"""Configuration, authentication, and Firebase infrastructure."""
````

### `backend/app/core/config.py`

````python
import os
from dataclasses import dataclass

from dotenv import load_dotenv


def parse_boolean(value, default=False):
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_positive_float(value, default):
    try:
        parsed_value = float(value)
    except (TypeError, ValueError):
        return default

    return parsed_value if parsed_value > 0 else default


@dataclass(frozen=True)
class Settings:
    debug: bool
    frontend_origins: list[str]
    firebase_project_id: str | None
    firebase_storage_bucket: str | None
    firebase_service_account_path: str | None
    cloudinary_cloud_name: str | None
    cloudinary_api_key: str | None
    cloudinary_api_secret: str | None
    ai_provider: str
    ai_api_key: str | None
    ai_model: str | None
    ai_api_base_url: str | None
    ai_timeout_seconds: float
    rate_limit_storage_uri: str

    @classmethod
    def from_environment(cls):
        load_dotenv()

        origins = [
            origin.strip()
            for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ]

        return cls(
            debug=parse_boolean(os.getenv("FLASK_DEBUG"), default=False),
            frontend_origins=origins,
            firebase_project_id=os.getenv("FIREBASE_PROJECT_ID") or None,
            firebase_storage_bucket=os.getenv("FIREBASE_STORAGE_BUCKET") or None,
            firebase_service_account_path=(
                os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or None
            ),
            cloudinary_cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME") or None,
            cloudinary_api_key=os.getenv("CLOUDINARY_API_KEY") or None,
            cloudinary_api_secret=os.getenv("CLOUDINARY_API_SECRET") or None,
            ai_provider=os.getenv("AI_PROVIDER", "none").strip().lower(),
            ai_api_key=os.getenv("AI_API_KEY") or None,
            ai_model=os.getenv("AI_MODEL") or None,
            ai_api_base_url=os.getenv("AI_API_BASE_URL") or None,
            ai_timeout_seconds=parse_positive_float(
                os.getenv("AI_TIMEOUT_SECONDS"),
                15.0,
            ),
            rate_limit_storage_uri=(
                os.getenv("RATE_LIMIT_STORAGE_URI", "memory://").strip()
                or "memory://"
            ),
        )
````

### `backend/app/core/errors.py`

````python
class ApiError(Exception):
    """An expected API error that can be safely returned to the client."""

    def __init__(self, code, message, status_code=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def api_error_payload(error):
    payload = {
        "error": {
            "code": error.code,
            "message": error.message,
        },
    }

    if error.details is not None:
        payload["error"]["details"] = error.details

    return payload
````

### `backend/app/core/firebase.py`

````python
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore


def initialize_firebase(settings):
    """Initialize the default Firebase Admin application exactly once."""
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    options = {}

    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id

    if settings.firebase_storage_bucket:
        options["storageBucket"] = settings.firebase_storage_bucket

    if settings.firebase_service_account_path:
        credential_path = Path(settings.firebase_service_account_path).expanduser().resolve()

        if not credential_path.is_file():
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_PATH does not point to an existing file.",
            )

        credential = credentials.Certificate(str(credential_path))
        return firebase_admin.initialize_app(credential, options)

    return firebase_admin.initialize_app(options=options)


def get_firestore_client():
    """Return the Firestore Admin client for repository and service code."""
    return firestore.client()
````

### `backend/app/core/rate_limit.py`

````python
import hashlib

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def public_chat_key():
    """Limit an active chat by its secret token without storing the raw token."""
    token = request.headers.get("X-Chat-Session-Token", "").strip()

    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return f"chat:{digest}"

    return f"ip:{get_remote_address()}"


limiter = Limiter(key_func=get_remote_address)
````

### `backend/app/core/requests.py`

````python
from flask import request

from app.core.errors import ApiError


def get_json_object():
    """Return a JSON object request body or raise a consistent API error."""
    payload = request.get_json(silent=True)

    if payload is None:
        return {}

    if not isinstance(payload, dict):
        raise ApiError(
            "validation_error",
            "The request body must be a JSON object.",
            422,
        )

    return payload
````

### `backend/app/core/serialization.py`

````python
from datetime import date, datetime


def serialize_value(value):
    """Convert Firestore values into JSON-compatible response values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}

    return value


def serialize_snapshot(snapshot):
    return {
        "id": snapshot.id,
        **serialize_value(snapshot.to_dict()),
    }
````

### `backend/app/services/__init__.py`

````python
"""Application services that implement Vendly business workflows."""
````

### `backend/app/services/numbers.py`

````python
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def money_to_minor_units(value, field_name, allow_zero=True):
    """Convert a decimal money value to integer cents for safe storage."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid number.") from error

    minimum = Decimal("0") if allow_zero else Decimal("0.01")

    if amount < minimum:
        requirement = "zero or greater" if allow_zero else "greater than zero"
        raise ValueError(f"{field_name} must be {requirement}.")

    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def kilograms_to_grams(value, field_name="Product weight"):
    """Convert kilograms to integer grams so delivery calculations stay stable."""
    try:
        kilograms = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a valid number.") from error

    if kilograms <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return int((kilograms * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def non_negative_integer(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive whole number or zero.")

    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{field_name} must be a positive whole number or zero.",
        ) from error

    if number < 0 or str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError(f"{field_name} must be a positive whole number or zero.")

    return number


def integer_value(value, field_name):
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a whole number.")

    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a whole number.") from error

    if str(value).strip() not in {str(number), f"{number}.0"}:
        raise ValueError(f"{field_name} must be a whole number.")

    return number
````

### `backend/app/services/text.py`

````python
import re
import unicodedata


def required_text(value, field_name, maximum_length=120):
    text = str(value or "").strip()

    if not text:
        raise ValueError(f"{field_name} is required.")

    if len(text) > maximum_length:
        raise ValueError(
            f"{field_name} must be {maximum_length} characters or fewer.",
        )

    return text


def optional_text(value, maximum_length=500):
    text = str(value or "").strip()

    if len(text) > maximum_length:
        raise ValueError(f"Text must be {maximum_length} characters or fewer.")

    return text


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
````

### `frontend/src/index.css`

````css
/* Global light-theme design tokens reused by every component stylesheet. */
:root {
 font-family:
  "Inter Variable",
  "Inter",
  "Noto Sans Sinhala",
  "Noto Sans Tamil",
  "Segoe UI",
  sans-serif;

  font-optical-sizing: auto;
  font-synthesis: none;

  --color-primary: #0b3b6e;
  --color-accent: #168cf5;

  --color-background: #f8fafc;
  --color-background-gradient:
    linear-gradient(
      135deg,
      #f8fafc 0%,
      #f5f9ff 50%,
      #edf5ff 100%
    );

  --color-surface: #ffffff;
  --color-surface-soft: #f1f5f9;

  --color-text-strong: #08213f;
  --color-text: #102f50;
  --color-muted: #526b87;
  --color-subtle: #71849a;
  --color-border: #dbe4ee;

  --color-header: rgba(245, 247, 250, 0.88);
  --color-control: #ffffff;

  --card-background: #ffffff;
  --card-shadow: 0 3px 8px rgba(15, 23, 42, 0.08);

  color: var(--color-text);
  background-color: var(--color-background);
  color-scheme: light;
}

/* Dark-theme token values replace the light values when data-theme is dark. */
html[data-theme="dark"] {
  --color-primary: #0d477d;
  --color-accent: #2997ff;

  --color-background: #07111c;

  --color-background-gradient:
    radial-gradient(
      circle at 85% 0%,
      rgba(27, 112, 197, 0.2) 0%,
      transparent 34%
    ),
    radial-gradient(
      circle at 10% 100%,
      rgba(0, 82, 145, 0.16) 0%,
      transparent 36%
    ),
    linear-gradient(
      135deg,
      #050b12 0%,
      #08131f 48%,
      #0a1c2d 100%
    );

  --color-surface: #101b28;
  --color-surface-soft: #172536;

  --color-text: #f4f7fb;
  --color-text-strong: #f8fbff;
  --color-muted: #b0c0d2;
  --color-subtle: #8ea1b6;
  --color-border: #25374a;

  --color-header: rgba(7, 15, 25, 0.82);
  --color-control: #111e2d;

  --card-background:
    linear-gradient(
      145deg,
      rgba(18, 31, 46, 0.96),
      rgba(10, 20, 32, 0.96)
    );

  --card-shadow:
    0 12px 30px rgba(0, 0, 0, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.025);

  color-scheme: dark;
}

* {
  box-sizing: border-box;
}

html,
body,
#root {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
}

/* Browser-wide defaults and page background. */
body {
  min-height: 100vh;
  line-height: 1.45;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  cursor: pointer;
}

/* Smooth visual transition when changing between light and dark themes. */
.app__content {
  flex: 1;
  min-width: 0;
}
````

### `frontend/src/main.jsx`

````jsx
// React and router tools used to start the Vendly application.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/inter";
import './index.css'
import App from './App.jsx'
import { AuthProvider } from "./context/AuthContext.jsx";

// Mount the React application inside the <div id="root"> from index.html.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
  <AuthProvider>
    <App />
  </AuthProvider>
</BrowserRouter>
  </StrictMode>,
);
````

### `frontend/src/services/apiClient.js`

````javascript
import { getCurrentUserToken } from "./authService";

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:5000/api/v1"
).replace(/\/$/, "");

/**
 * Send one request to the Vendly Flask API.
 *
 * Firebase owns the login session. This helper reads its current ID token and
 * sends that token to Flask, where it is verified before business data is read
 * or changed.
 */
export async function apiRequest(
  path,
  {
    method = "GET",
    body,
    headers = {},
    requiresAuthentication = true,
    signal,
  } = {},
) {
  const requestHeaders = new Headers(headers);

  if (requiresAuthentication) {
    const idToken = await getCurrentUserToken();

    if (!idToken && requiresAuthentication !== "optional") {
      throw new Error("You must be logged in to complete this request.");
    }

    if (idToken) requestHeaders.set("Authorization", `Bearer ${idToken}`);
  }

  let requestBody = body;

  if (body !== undefined && !(body instanceof FormData)) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  const response = await fetch(
    `${apiBaseUrl}/${path.replace(/^\//, "")}`,
    {
      method,
      headers: requestHeaders,
      body: requestBody,
      signal,
    },
  );

  const responseType = response.headers.get("content-type") ?? "";
  const responseData = responseType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok) {
    const error = new Error(
      responseData?.error?.message ??
        `The API request failed with status ${response.status}.`,
    );

    error.status = response.status;
    error.code = responseData?.error?.code ?? "api_request_failed";
    error.details = responseData?.error?.details;

    throw error;
  }

  return responseData;
}

/** Download an authenticated file from the API without treating it as JSON. */
export async function apiFileRequest(path) {
  const idToken = await getCurrentUserToken();

  if (!idToken) {
    throw new Error("You must be logged in to complete this request.");
  }

  const response = await fetch(`${apiBaseUrl}/${path.replace(/^\//, "")}`, {
    headers: { Authorization: `Bearer ${idToken}` },
  });

  if (!response.ok) {
    const responseType = response.headers.get("content-type") ?? "";
    const responseData = responseType.includes("application/json")
      ? await response.json()
      : null;
    throw new Error(
      responseData?.error?.message ??
        `The file download failed with status ${response.status}.`,
    );
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const filenameMatch = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);

  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] ?? "vendly-download",
  };
}
````

### `frontend/src/services/publicService.js`

````javascript
import { apiRequest } from "./apiClient";

export function getPublicStore(storeCode) {
  return apiRequest(`/public/stores/${storeCode}`, {
    requiresAuthentication: false,
  });
}

export function getPublicProduct(productCode) {
  return apiRequest(`/public/products/${productCode}`, {
    requiresAuthentication: false,
  });
}

export function createPublicChatSession({ storeCode, productCode }) {
  return apiRequest("/public/chat/sessions", {
    method: "POST",
    body: { storeCode, productCode },
    requiresAuthentication: "optional",
  });
}

export function claimPublicChatSession(sessionId, sessionToken) {
  return apiRequest(`/public/chat/sessions/${sessionId}/claim`, {
    method: "POST",
    headers: { "X-Chat-Session-Token": sessionToken },
  });
}

export function getCustomerOrders(storeCode) {
  return apiRequest(`/public/stores/${storeCode}/customer/orders`);
}

export function getCustomerChats(storeCode) {
  return apiRequest(`/public/stores/${storeCode}/customer/chats`);
}

export function sendPublicChatMessage(sessionId, sessionToken, message, orderDraft = {}) {
  return apiRequest(`/public/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    body: { message, ...orderDraft },
    headers: { "X-Chat-Session-Token": sessionToken },
    requiresAuthentication: false,
  });
}

export function createPublicChatOrder(sessionId, sessionToken, orderData) {
  return apiRequest(`/public/chat/sessions/${sessionId}/orders`, {
    method: "POST",
    body: orderData,
    headers: { "X-Chat-Session-Token": sessionToken },
    requiresAuthentication: "optional",
  });
}

export function getPublicProductReviews(productCode) {
  return apiRequest(`/public/products/${productCode}/reviews`, {
    requiresAuthentication: false,
  });
}

export function submitPublicReview(storeCode, reviewData) {
  return apiRequest(`/public/stores/${storeCode}/reviews`, {
    method: "POST",
    body: reviewData,
    requiresAuthentication: false,
  });
}
````

## Feature 2 source — Firebase authentication

Files in this feature: 7

### `backend/app/core/auth.py`

````python
from functools import wraps

from firebase_admin import auth as firebase_auth
from flask import g, jsonify, request


def authentication_error(
    message,
    status_code=401,
    code="authentication_required",
):
    return jsonify(
        {
            "error": {
                "code": code,
                "message": message,
            },
        },
    ), status_code


def require_firebase_user(view_function):
    """Verify a Firebase ID token from the Authorization header."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")

        if not authorization.startswith("Bearer "):
            return authentication_error("A Firebase bearer token is required.")

        id_token = authorization.removeprefix("Bearer ").strip()

        if not id_token:
            return authentication_error("A Firebase bearer token is required.")

        try:
            g.current_user = firebase_auth.verify_id_token(id_token)
        except (
            firebase_auth.InvalidIdTokenError,
            firebase_auth.ExpiredIdTokenError,
            firebase_auth.RevokedIdTokenError,
            firebase_auth.UserDisabledError,
            ValueError,
        ):
            return authentication_error(
                "The Firebase token is invalid or expired.",
                code="invalid_authentication_token",
            )

        sign_in_provider = g.current_user.get("firebase", {}).get(
            "sign_in_provider",
        )

        if (
            sign_in_provider == "password"
            and not g.current_user.get("email_verified", False)
        ):
            return authentication_error(
                "Verify your email address before using Vendly.",
                status_code=403,
                code="email_not_verified",
            )

        return view_function(*args, **kwargs)

    return wrapped_view


def optional_firebase_user(view_function):
    """Load a Firebase identity when supplied, while allowing public guests."""

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        g.current_user = None

        if authorization.startswith("Bearer "):
            id_token = authorization.removeprefix("Bearer ").strip()
            try:
                g.current_user = firebase_auth.verify_id_token(id_token)
            except (
                firebase_auth.InvalidIdTokenError,
                firebase_auth.ExpiredIdTokenError,
                firebase_auth.RevokedIdTokenError,
                firebase_auth.UserDisabledError,
                ValueError,
            ):
                return authentication_error(
                    "The Firebase token is invalid or expired.",
                    code="invalid_authentication_token",
                )

        return view_function(*args, **kwargs)

    return wrapped_view
````

### `frontend/src/context/AuthContext.jsx`

````jsx
import {
  useEffect,
  useState,
} from "react";

import { onAuthStateChanged } from "firebase/auth";

import { auth } from "../firebase/firebase";
import { getCurrentAccount } from "../services/accountService";
import { createBusiness } from "../services/businessService";
import {
  clearPendingSellerProfile,
  getSellerProfile,
} from "../services/sellerService";
import { AuthContext } from "./authContextValue";

function AuthProvider({ children }) {
  // Firebase user currently logged into Vendly.
  const [user, setUser] = useState(null);

  // Vendly-specific details stored separately from the Firebase user.
  const [sellerProfile, setSellerProfile] = useState(null);

  // Account data returned by Flask: user profile, business and membership.
  const [account, setAccount] = useState(null);

  // A backend error does not destroy the Firebase login session.
  const [accountError, setAccountError] = useState(null);

  // Prevent pages from loading before Firebase checks the session.
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  async function loadAccount(currentUser) {
    let legacyProfile = await getSellerProfile(currentUser);

    try {
      let currentAccount = await getCurrentAccount();

      if (
        !legacyProfile &&
        currentAccount.profile?.businessName &&
        !currentAccount.business
      ) {
        legacyProfile = {
          ownerName: currentAccount.profile.ownerName,
          businessName: currentAccount.profile.businessName,
        };
      }

      // Upgrade profiles created by the earlier direct-Firestore onboarding.
      if (!currentAccount.business && legacyProfile) {
        await createBusiness({
          ownerName:
            legacyProfile.ownerName ??
            currentUser.displayName ??
            "Business owner",
          businessName: legacyProfile.businessName,
        });

        currentAccount = await getCurrentAccount();
      }

      setAccount(currentAccount);
      setAccountError(null);

      if (currentAccount.business) {
        clearPendingSellerProfile(currentUser);
        setSellerProfile({
          ...legacyProfile,
          ownerName:
            currentAccount.profile?.displayName ??
            legacyProfile?.ownerName ??
            currentUser.displayName ??
            "",
          businessName: currentAccount.business.name,
        });
        return;
      }
    } catch (error) {
      console.error("Vendly account could not be loaded:", error);
      setAccount(null);
      setAccountError(error);
    }

    // Compatibility fallback while an older account is being migrated.
    setSellerProfile(legacyProfile);
  }

  useEffect(() => {
    // Firebase calls this whenever the login session changes.
    const unsubscribe = onAuthStateChanged(
      auth,
      async (currentUser) => {
        setIsAuthLoading(true);
        setUser(currentUser);

        try {
          if (currentUser) {
            await loadAccount(currentUser);
          } else {
            setSellerProfile(null);
            setAccount(null);
            setAccountError(null);
          }
        } catch (error) {
          console.error("Seller profile could not be loaded:", error);
          setSellerProfile(null);
        } finally {
          setIsAuthLoading(false);
        }
      },
    );

    // Stop the Firebase listener when this component is removed.
    return unsubscribe;
  }, []);

  // Refresh profile data after the seller finishes business setup.
  async function refreshSellerProfile() {
    if (!auth.currentUser) {
      setSellerProfile(null);
      setAccount(null);
      return;
    }

    await loadAccount(auth.currentUser);
  }

  const authValue = {
    user,
    sellerProfile,
    account,
    business: account?.business ?? null,
    membership: account?.membership ?? null,
    accountError,
    refreshSellerProfile,
    isAuthLoading,
    isAuthenticated: Boolean(user),
  };

  return (
    <AuthContext.Provider value={authValue}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthProvider };
````

### `frontend/src/context/authContextValue.js`

````javascript
import { createContext, useContext } from "react";

// Shared authentication storage used by AuthProvider and dashboard components.
export const AuthContext = createContext(null);

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}
````

### `frontend/src/firebase/firebase.js`

````javascript
// Firebase application setup.
import { initializeApp } from "firebase/app";

// Firebase Authentication tools.
import {
  getAuth,
  GoogleAuthProvider,
} from "firebase/auth";

// Read Firebase settings from .env.local.
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId:
    import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Initialize the Firebase application.
const firebaseApp = initializeApp(firebaseConfig);

// Initialize Firebase Authentication.
const auth = getAuth(firebaseApp);

// Configure the Google login provider.
const googleProvider = new GoogleAuthProvider();

googleProvider.setCustomParameters({
  prompt: "select_account",
});

// Export these objects so authentication components can use them.
export {
  firebaseApp,
  auth,
  googleProvider,
};
````

### `frontend/src/pages/LoginPage.css`

````css
/* Full-page authentication background. */
.login-page {
  display: grid;
  place-items: center;

  min-height: 100vh;
  padding: 24px;

  background:
    radial-gradient(
      circle at top right,
      rgba(34, 145, 255, 0.35),
      transparent 34%
    ),
    linear-gradient(
      145deg,
      #002d52,
      #063b6a 50%,
      #001e38
    );
}

/* Main login and registration card. */
.login-card {
  width: min(100%, 440px);
  padding: 30px;

  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 18px;

  background: rgba(255, 255, 255, 0.97);

  box-shadow:
    0 24px 60px rgba(0, 15, 35, 0.35);

  animation: login-card-open 300ms ease-out;
}

/* Page heading and supporting text. */
.login-card__heading {
  margin-bottom: 24px;
  text-align: center;
}

.login-card__heading h1 {
  margin: 0 0 8px;

  color: #08233f;
  font-size: 26px;
}

.login-card__heading p {
  margin: 0;
  color: #64748b;
}

/* Login and Register selector. */
.login-card__tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);

  margin-bottom: 22px;
  padding: 4px;

  border-radius: 10px;
  background: #edf4fb;
}

.login-card__tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;

  min-height: 42px;
  padding: 8px 14px;

  border: 0;
  border-radius: 8px;

  color: #64748b;
  background: transparent;

  font: inherit;
  font-weight: 700;

  cursor: pointer;
}

.login-card__tab:hover {
  color: #087fee;
}

.login-card__tab--active {
  color: white;
  background: #087fee;

  box-shadow:
    0 6px 16px rgba(8, 127, 238, 0.25);
}

.login-card__tab--active:hover {
  color: white;
}

/* Email and password form. */
.login-card__form {
  display: grid;
  gap: 16px;
}

/* Individual label and input group. */
.login-card__field {
  display: grid;
  gap: 7px;
}

.login-card__field label {
  color: #16314d;

  font-size: 13px;
  font-weight: 700;
}

.login-card__field input {
  width: 100%;
  min-height: 46px;
  padding: 0 13px;

  border: 1px solid #cbd9e7;
  border-radius: 9px;
  outline: 0;

  color: #102a43;
  background: white;

  font: inherit;
  font-size: 14px;

  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.login-card__field input::placeholder {
  color: #94a3b8;
}

.login-card__field input:focus {
  border-color: #168cf5;

  box-shadow:
    0 0 0 3px rgba(22, 140, 245, 0.14);
}

/* Firebase authentication error message. */
.login-card__error {
  margin: 0;
  padding: 10px 12px;

  border: 1px solid #fca5a5;
  border-radius: 8px;

  color: #b42323;
  background: #fff1f1;

  font-size: 13px;
}

/* Successful registration and email-verification instructions. */
.login-card__success {
  margin: 0;
  padding: 10px 12px;

  border: 1px solid #86efac;
  border-radius: 8px;

  color: #166534;
  background: #f0fdf4;

  font-size: 13px;
}

/* Primary email login or registration button. */
.login-card__submit {
  min-height: 46px;
  margin-top: 2px;
  padding: 0 16px;

  border: 1px solid #087fee;
  border-radius: 9px;

  color: white;
  background: linear-gradient(
    135deg,
    #168cf5,
    #0873d4
  );

  font: inherit;
  font-weight: 700;

  cursor: pointer;

  box-shadow:
    0 8px 20px rgba(8, 127, 238, 0.24);
}

.login-card__submit:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    #087fee,
    #0567bd
  );

  transform: translateY(-1px);
}

.login-card__submit:disabled,
.login-card__google:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

/* Separator between email and Google login. */
.login-card__divider {
  display: flex;
  align-items: center;
  gap: 12px;

  margin: 20px 0;
  color: #94a3b8;

  font-size: 12px;
}

.login-card__divider::before,
.login-card__divider::after {
  content: "";

  flex: 1;
  height: 1px;

  background: #dbe5ef;
}

/* Google authentication button. */
.login-card__google {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;

  width: 100%;
  min-height: 46px;
  padding: 0 16px;

margin: 5px;

  border: 1px solid #cbd9e7;
  border-radius: 9px;

  color: #16314d;
  background: white;

  font: inherit;
  font-weight: 700;

  cursor: pointer;
}

.login-card__google:hover:not(:disabled) {
  color: #087fee;
  border-color: #168cf5;
  background: #f7fbff;
}

/* Simple Google letter icon. */
.login-card__google > span {
  display: grid;
  place-items: center;

  width: 25px;
  height: 25px;

  border-radius: 50%;

  color: white;
  background:
    linear-gradient(
      135deg,
      #4285f4,
      #34a853
    );

  font-weight: 800;
}

/* Login-card opening animation. */
@keyframes login-card-open {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Smaller spacing for mobile devices. */
@media (max-width: 520px) {
  .login-page {
    padding: 14px;
  }

  .login-card {
    padding: 22px 18px;
    border-radius: 14px;
  }

  .login-card__heading h1 {
    font-size: 23px;
  }
}

/* Disable animation when requested by the device. */
@media (prefers-reduced-motion: reduce) {
  .login-card {
    animation: none;
  }

  .login-card__submit:hover:not(:disabled) {
    transform: none;
  }
}
````

### `frontend/src/pages/LoginPage.jsx`

````jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  LogIn,
  UserPlus,
} from "lucide-react";

import {
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import { saveSellerProfile } from "../services/sellerService";
import { useAuth } from "../context/authContextValue";
import vendlyLoginLogo from "../assets/logo.png";
import googleLogo from "../assets/g.webp";

import "./LoginPage.css";

// Convert Firebase error codes into understandable messages.
function getAuthErrorMessage(error) {
  switch (error.code) {
    case "auth/email-already-in-use":
      return "An account already exists with this email.";

    case "auth/invalid-email":
      return "Please enter a valid email address.";

    case "auth/invalid-credential":
      return "The email or password is incorrect.";

    case "auth/weak-password":
      return "Please use a stronger password.";

    case "auth/popup-closed-by-user":
      return "Google login was cancelled.";

    case "auth/email-not-verified":
      return "Please verify your email address before logging in.";

    default:
      return "Authentication failed. Please try again.";
  }
}

function LoginPage() {
  const navigate = useNavigate();
  const { refreshSellerProfile } = useAuth();

  // The same page handles both login and registration.
  const [formMode, setFormMode] = useState("login");

  const [formData, setFormData] = useState({
    ownerName: "",
    businessName: "",
    email: "",
    password: "",
  });

  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegisterMode = formMode === "register";

  // Update the field that the seller changes.
  function handleInputChange(event) {
    const fieldName = event.target.name;
    const fieldValue = event.target.value;

    setFormData((currentData) => ({
      ...currentData,
      [fieldName]: fieldValue,
    }));
  }

  // Login or register using the submitted form.
  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      if (isRegisterMode) {
        const registeredUser = await registerWithEmail(
          formData.ownerName,
          formData.email,
          formData.password,
        );

        await saveSellerProfile(registeredUser, {
          ownerName: formData.ownerName,
          businessName: formData.businessName,
        });

        // Keep the new account out of the dashboard until email verification.
        await logoutUser();

        setSuccessMessage(
          "Verification email sent. Please check your inbox before logging in.",
        );

        return;
      } else {
        await loginWithEmail(
          formData.email,
          formData.password,
        );
        await refreshSellerProfile();
      }

      navigate("/", {
        replace: true,
      });
    } catch (error) {
      setErrorMessage(getAuthErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  // Login or register using a Google account.
  async function handleGoogleLogin() {
    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      await loginWithGoogle();
      await refreshSellerProfile();

      navigate("/", {
        replace: true,
      });
    } catch (error) {
      setErrorMessage(getAuthErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  // Change between Login and Register modes.
  function changeFormMode(newMode) {
    setFormMode(newMode);
    setErrorMessage("");
    setSuccessMessage("");

    setFormData({
      ownerName: "",
      businessName: "",
      email: "",
      password: "",
    });
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-card__heading">
        <img height="90" src={vendlyLoginLogo} alt="Vendly.lk" />

          <p>
            {isRegisterMode
              ? "Create your seller account."
              : "Login to manage your business."}
          </p>
        </div>

        {/* Login and registration selector */}
        <div className="login-card__tabs">
          <button
            className={
              formMode === "login"
                ? "login-card__tab login-card__tab--active"
                : "login-card__tab"
            }
            type="button"
            onClick={() => changeFormMode("login")}
          >
            <LogIn size={17} aria-hidden="true" />
            Login
          </button>

          <button
            className={
              formMode === "register"
                ? "login-card__tab login-card__tab--active"
                : "login-card__tab"
            }
            type="button"
            onClick={() => changeFormMode("register")}
          >
            <UserPlus size={17} aria-hidden="true" />
            Register
          </button>
        </div>

        {/* Email and password form */}
        <form
          className="login-card__form"
          onSubmit={handleSubmit}
        >
          {isRegisterMode && (
            <div className="login-card__field">
              <label htmlFor="owner-name">
                Owner name
              </label>

              <input
                id="owner-name"
                name="ownerName"
                type="text"
                value={formData.ownerName}
                onChange={handleInputChange}
                placeholder="Enter your name"
                autoComplete="name"
                required
              />
            </div>
          )}

          {isRegisterMode && (
            <div className="login-card__field">
              <label htmlFor="business-name">
                Business name
              </label>

              <input
                id="business-name"
                name="businessName"
                type="text"
                value={formData.businessName}
                onChange={handleInputChange}
                placeholder="Example: VS Tech Store"
                autoComplete="organization"
                required
              />
            </div>
          )}

          <div className="login-card__field">
            <label htmlFor="seller-email">
              Email address
            </label>

            <input
              id="seller-email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleInputChange}
              placeholder="seller@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div className="login-card__field">
            <label htmlFor="seller-password">
              Password
            </label>

            <input
              id="seller-password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleInputChange}
              placeholder="Enter your password"
              autoComplete={
                isRegisterMode
                  ? "new-password"
                  : "current-password"
              }
              minLength={6}
              required
            />
          </div>

          {errorMessage && (
            <p className="login-card__error" role="alert">
              {errorMessage}
            </p>
          )}

          {successMessage && (
            <p className="login-card__success" role="status">
              {successMessage}
            </p>
          )}

          <button
            className="login-card__submit"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Please wait..."
              : isRegisterMode
                ? "Create account"
                : "Login"}
          </button>
        </form>

        <div className="login-card__divider">
          <span>or</span>
        </div>

{/* Google login button */}
        <button
          className="login-card__google"
          type="button"
          onClick={handleGoogleLogin}
          disabled={isSubmitting}
        >
          <img width="25" src={googleLogo} alt="" aria-hidden="true" />
          Sign in with Google
        </button>


      </section>
    </main>
  );
}

export default LoginPage;
````

### `frontend/src/services/authService.js`

````javascript
// Firebase Authentication functions.
import {
  createUserWithEmailAndPassword,
  EmailAuthProvider,
  getIdToken,
  reauthenticateWithCredential,
  reauthenticateWithPopup,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInAnonymously,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updatePassword,
  updateProfile,
  verifyBeforeUpdateEmail,
} from "firebase/auth";

// Firebase objects configured in firebase.js.
import {
  auth,
  googleProvider,
} from "../firebase/firebase";

// Register a seller using an email address and password.
export async function registerWithEmail(
  name,
  email,
  password,
) {
  const userCredential =
    await createUserWithEmailAndPassword(
      auth,
      email,
      password,
    );

  // Save the seller's name in their Firebase profile.
  await updateProfile(userCredential.user, {
    displayName: name,
  });

  // Send an email-verification message.
  await sendEmailVerification(userCredential.user);

  return userCredential.user;
}

// Login using email and password.
export async function loginWithEmail(email, password) {
  const userCredential =
    await signInWithEmailAndPassword(
      auth,
      email,
      password,
    );

  const loggedInUser = userCredential.user;

  // Retrieve the latest email-verification status from Firebase.
  await reload(loggedInUser);

  // Email/password accounts must verify their address before continuing.
  if (!loggedInUser.emailVerified) {
    await signOut(auth);

    const verificationError = new Error(
      "Email address has not been verified.",
    );

    verificationError.code = "auth/email-not-verified";

    throw verificationError;
  }

  return loggedInUser;
}

// Login or register using a Google account.
export async function loginWithGoogle() {
  const userCredential = await signInWithPopup(
    auth,
    googleProvider,
  );

  return userCredential.user;
  
}

// Logout the currently authenticated seller.
export async function logoutUser() {
  await signOut(auth);
}

// Generate a token that can be sent to the Flask backend.
export async function getCurrentUserToken() {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    return null;
  }

  return getIdToken(currentUser);
}

export async function loginAsGuest() {
  const userCredential = await signInAnonymously(auth);
  return userCredential.user;
}

// Return true when the current account can sign in with an email and password.
export function currentUserHasPasswordProvider() {
  return Boolean(
    auth.currentUser?.providerData.some(
      (provider) => provider.providerId === "password",
    ),
  );
}

// Firebase requires a recent login before changing sensitive account details.
async function reauthenticateCurrentUser(currentPassword = "") {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    throw new Error("Please sign in again before changing your profile.");
  }

  if (currentUserHasPasswordProvider()) {
    if (!currentPassword) {
      const passwordError = new Error("Enter your current password to continue.");
      passwordError.code = "auth/current-password-required";
      throw passwordError;
    }

    const credential = EmailAuthProvider.credential(
      currentUser.email,
      currentPassword,
    );
    await reauthenticateWithCredential(currentUser, credential);
    return;
  }

  const usesGoogle = currentUser.providerData.some(
    (provider) => provider.providerId === "google.com",
  );

  if (usesGoogle) {
    await reauthenticateWithPopup(currentUser, googleProvider);
    return;
  }

  const providerError = new Error(
    "This sign-in provider cannot be re-authenticated from this screen.",
  );
  providerError.code = "auth/provider-not-supported";
  throw providerError;
}

// Send verification to the new address. Firebase changes the address only
// after the user opens that verification link.
export async function requestAccountEmailChange(newEmail, currentPassword = "") {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    throw new Error("Please sign in again before changing your email.");
  }

  await reauthenticateCurrentUser(currentPassword);
  await verifyBeforeUpdateEmail(currentUser, newEmail);
}

// Password accounts must prove their current password before setting a new one.
export async function changeAccountPassword(currentPassword, newPassword) {
  const currentUser = auth.currentUser;

  if (!currentUser || !currentUserHasPasswordProvider()) {
    const providerError = new Error(
      "This account uses Google sign-in and does not have a Vendly password.",
    );
    providerError.code = "auth/password-provider-missing";
    throw providerError;
  }

  await reauthenticateCurrentUser(currentPassword);
  await updatePassword(currentUser, newPassword);
}

export async function sendCurrentUserPasswordReset() {
  const currentUser = auth.currentUser;

  if (!currentUser?.email) {
    throw new Error("No email address is available for this account.");
  }

  await sendPasswordResetEmail(auth, currentUser.email);
}
````

## Feature 3 source — Business onboarding

Files in this feature: 7

### `backend/app/api/businesses.py`

````python
from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.business_service import create_or_get_business


businesses_blueprint = Blueprint("businesses", __name__, url_prefix="/api/v1")


@businesses_blueprint.post("/businesses")
@require_firebase_user
def create_business():
    payload = get_json_object()

    business, was_created = create_or_get_business(
        get_firestore_client(),
        g.current_user,
        payload,
    )

    return jsonify({"business": business}), 201 if was_created else 200
````

### `backend/app/api/me.py`

````python
from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.firebase import get_firestore_client
from app.core.serialization import serialize_snapshot


me_blueprint = Blueprint("me", __name__, url_prefix="/api/v1")


@me_blueprint.get("/me")
@require_firebase_user
def get_current_user():
    """Return the verified Firebase identity and current legacy seller profile."""
    uid = g.current_user["uid"]
    database = get_firestore_client()

    user_snapshot = database.collection("users").document(uid).get()
    seller_snapshot = database.collection("sellers").document(uid).get()

    profile = None
    business = None
    membership = None

    if user_snapshot.exists:
        profile = serialize_snapshot(user_snapshot)
        business_ids = profile.get("businessIds") or []
        business_id = profile.get("defaultBusinessId") or (
            business_ids[0] if business_ids else None
        )

        if business_id:
            business_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .get()
            )
            membership_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .collection("members")
                .document(uid)
                .get()
            )

            if business_snapshot.exists:
                business = serialize_snapshot(business_snapshot)

            if membership_snapshot.exists:
                membership = serialize_snapshot(membership_snapshot)
    elif seller_snapshot.exists:
        profile = serialize_snapshot(seller_snapshot)

    return jsonify(
        {
            "user": {
                "uid": uid,
                "email": g.current_user.get("email"),
                "emailVerified": g.current_user.get("email_verified", False),
                "name": g.current_user.get("name"),
                "picture": g.current_user.get("picture"),
            },
            "profile": profile,
            "business": business,
            "membership": membership,
        },
    )
````

### `backend/app/services/business_service.py`

````python
import secrets
import string

from firebase_admin import firestore
from google.cloud import firestore as google_firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import required_text


SHORT_CODE_ALPHABET = string.ascii_letters + string.digits


def generate_short_code(length=7):
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(length))


def create_or_get_business(database, firebase_user, payload):
    """Create the first business for a Firebase user, or return the existing one."""
    uid = firebase_user["uid"]
    user_reference = database.collection("users").document(uid)
    existing_user = user_reference.get()

    if existing_user.exists:
        default_business_id = existing_user.to_dict().get("defaultBusinessId")

        if default_business_id:
            existing_business = (
                database.collection("businesses")
                .document(default_business_id)
                .get()
            )

            if existing_business.exists:
                return serialize_snapshot(existing_business), False

    try:
        owner_name = required_text(
            payload.get("ownerName") or firebase_user.get("name"),
            "Owner name",
        )
        business_name = required_text(payload.get("businessName"), "Business name")
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    business_reference = database.collection("businesses").document()
    membership_reference = business_reference.collection("members").document(uid)
    short_code = generate_short_code()
    short_link_reference = database.collection("shortLinks").document(short_code)
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        short_link_snapshot = short_link_reference.get(transaction=current_transaction)

        if short_link_snapshot.exists:
            raise ApiError(
                "short_code_conflict",
                "A public code conflict occurred. Please try again.",
                409,
            )

        timestamp = firestore.SERVER_TIMESTAMP

        current_transaction.set(
            business_reference,
            {
                "name": business_name,
                "ownerUid": uid,
                "shortCode": short_code,
                "logoPath": "",
                "phone": "",
                "email": firebase_user.get("email") or "",
                "address": {},
                "currency": "LKR",
                "timezone": "Asia/Colombo",
                "status": "active",
                "nextOrderSequence": 1,
                "nextWaybillSequence": 1,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            membership_reference,
            {
                "uid": uid,
                "role": "owner",
                "permissions": ["*"],
                "status": "active",
                "joinedAt": timestamp,
            },
        )
        current_transaction.set(
            user_reference,
            {
                "uid": uid,
                "displayName": owner_name,
                "email": firebase_user.get("email") or "",
                "photoUrl": firebase_user.get("picture") or "",
                "defaultBusinessId": business_reference.id,
                "businessIds": firestore.ArrayUnion([business_reference.id]),
                "status": "active",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
            merge=True,
        )
        current_transaction.set(
            short_link_reference,
            {
                "type": "store",
                "businessId": business_reference.id,
                "status": "active",
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)

    return serialize_snapshot(business_reference.get()), True
````

### `frontend/src/pages/BusinessSetupPage.jsx`

````jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import { createBusiness } from "../services/businessService";

import "./LoginPage.css";

function BusinessSetupPage() {
  const navigate = useNavigate();
  const {
    user,
    refreshSellerProfile,
  } = useAuth();

  const [ownerName, setOwnerName] = useState(
    user?.displayName ?? "",
  );
  const [businessName, setBusinessName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      await createBusiness({
        ownerName,
        businessName,
      });

      await refreshSellerProfile();
      navigate("/", { replace: true });
    } catch (error) {
      console.error(error);
      setErrorMessage(
        "Business details could not be saved. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-card__heading">
          <h1>Set up your business</h1>
          <p>This information will appear on your Vendly dashboard.</p>
        </div>

        <form className="login-card__form" onSubmit={handleSubmit}>
          <div className="login-card__field">
            <label htmlFor="setup-owner-name">Owner name</label>
            <input
              id="setup-owner-name"
              type="text"
              value={ownerName}
              onChange={(event) => setOwnerName(event.target.value)}
              placeholder="Enter your name"
              autoComplete="name"
              required
            />
          </div>

          <div className="login-card__field">
            <label htmlFor="setup-business-name">Business name</label>
            <input
              id="setup-business-name"
              type="text"
              value={businessName}
              onChange={(event) => setBusinessName(event.target.value)}
              placeholder="Example: VS Tech Store"
              autoComplete="organization"
              required
            />
          </div>

          {errorMessage && (
            <p className="login-card__error" role="alert">
              {errorMessage}
            </p>
          )}

          <button
            className="login-card__submit"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Saving..." : "Continue to dashboard"}
          </button>
        </form>
      </section>
    </main>
  );
}

export default BusinessSetupPage;
````

### `frontend/src/services/accountService.js`

````javascript
import { apiRequest } from "./apiClient";

// Load the authenticated Firebase identity and its Vendly profile from Flask.
export function getCurrentAccount() {
  return apiRequest("/me");
}
````

### `frontend/src/services/businessService.js`

````javascript
import { apiRequest } from "./apiClient";

// Create the seller's first business. Repeating the request returns the same one.
export function createBusiness({ ownerName, businessName }) {
  return apiRequest("/businesses", {
    method: "POST",
    body: {
      ownerName,
      businessName,
    },
  });
}
````

### `frontend/src/services/sellerService.js`

````javascript
function pendingProfileKey(email) {
  return `vendly-pending-profile:${String(email ?? "").trim().toLowerCase()}`;
}


// Read onboarding details kept locally until an email address is verified.
export async function getSellerProfile(user) {
  if (!user?.email) return null;

  const storedValue = localStorage.getItem(pendingProfileKey(user.email));

  if (!storedValue) return null;

  try {
    return JSON.parse(storedValue);
  } catch {
    localStorage.removeItem(pendingProfileKey(user.email));
    return null;
  }
}


// Unverified accounts cannot use Flask yet, so remember only the non-sensitive
// onboarding names in this browser until the first verified login.
export async function saveSellerProfile(user, profileData) {
  localStorage.setItem(
    pendingProfileKey(user.email),
    JSON.stringify({
      ownerName: profileData.ownerName.trim(),
      businessName: profileData.businessName.trim(),
      email: user.email ?? "",
    }),
  );
}


export function clearPendingSellerProfile(user) {
  if (user?.email) localStorage.removeItem(pendingProfileKey(user.email));
}
````

## Feature 4 source — Dashboard shell and shared UI

Files in this feature: 12

### `frontend/src/App.css`

````css
/* Main application shell containing the sidebar and routed content. */
.app {
  display: flex;
  min-height: 100vh;

  color: var(--color-text);
  background-color: var(--color-background);
  background-image: var(--color-background-gradient);
  background-attachment: fixed;

  transition:
    color 250ms ease,
    background-color 250ms ease;
}

/* Shared content spacing used by every dashboard page. */
.dashboard {
  flex: 1;
  padding: 1px 32px;
}

.dashboard h2 {
  flex: 1;
  min-width: 0;
}

.dashboard p {
  margin: 0;
  color: var(--color-muted);
}

/* Main content column positioned beside the fixed-width sidebar. */
.app__content {
  flex: 1;
  min-width: 0;
}

/* Shared page introduction and section heading spacing. */
.dashboard__intro {
  margin-bottom: 10px;
  padding: 0px
}

.dashboard__intro h2 {
  margin-bottom: 6px;
}

.dashboard section > h2 {
  margin: 0 0 18px;
  color: var(--color-text);
  font-size: 26px;
}

/* Responsive grid used by overview and inventory statistic cards. */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 18px;
}
.app-loading {
  display: grid;
  place-items: center;
  min-height: 100vh;
  color: var(--color-text);
  background: var(--color-background);
  font-weight: 700;
}
````

### `frontend/src/App.jsx`

````jsx
// React state and effect hooks manage the sidebar and colour theme.
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

// Shared layout components and the individual dashboard pages.
import "./App.css";
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage.jsx"));
const CouriersPage = lazy(() => import("./pages/CouriersPage.jsx"));
const CustomersPage = lazy(() => import("./pages/CustomersPage.jsx"));
const InventoryPage = lazy(() => import("./pages/InventoryPage.jsx"));
const OrdersPage = lazy(() => import("./pages/OrdersPage.jsx"));
const OverviewPage = lazy(() => import("./pages/OverviewPage.jsx"));
const BusinessSetupPage = lazy(() => import("./pages/BusinessSetupPage.jsx"));
const StorefrontPage = lazy(() => import("./pages/StorefrontPage.jsx"));

// Choose a starting theme from local storage or the user's device preference.
function getInitialTheme() {
  const savedTheme = localStorage.getItem("vendly-theme");

  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme;
  }

  const deviceUsesDarkMode = window.matchMedia(
    "(prefers-color-scheme: dark)",
  ).matches;

  if (deviceUsesDarkMode === true) {
    return "dark";
  }

  return "light";
}

function App() {  
  // Application-wide UI state shared by the sidebar and header.
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState(getInitialTheme);

  // Apply the selected theme to the HTML element and remember the choice.
  useEffect(() => {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("vendly-theme", theme);
}, [theme]);

  // Expand or collapse the left sidebar.
  function toggleSidebar() {
    setIsSidebarCollapsed((currentValue) => !currentValue);
  }

  // Change between the light and dark themes.
  function toggleTheme() {
  setTheme((currentTheme) => {
    if (currentTheme === "light") {
      return "dark";
    }

    return "light";
  });
}

  return (
  <Suspense fallback={<main className="app-loading">Loading Vendly...</main>}>
  <Routes>
    {/* Login remains publicly accessible. */}
    <Route
      path="/login"
      element={<LoginPage />}
    />

    <Route
      path="/s/:storeCode"
      element={<StorefrontPage linkType="store" />}
    />

    <Route
      path="/p/:productCode"
      element={<StorefrontPage linkType="product" />}
    />

    {/* Google users enter their business name after their first login. */}
    <Route
      path="/setup-business"
      element={
        <ProtectedRoute requireSellerProfile={false}>
          <BusinessSetupPage />
        </ProtectedRoute>
      }
    />

    {/* Every dashboard route requires authentication. */}
    <Route
      path="/*"
      element={
        <ProtectedRoute>
          <div className="app">
            <Sidebar
              isCollapsed={isSidebarCollapsed}
              onToggleSidebar={toggleSidebar}
            />

            <div className="app__content">
              <Routes>
                <Route
                  path="/"
                  element={
                    <>
                      <Header
                        title="Overview"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                      />

                      <OverviewPage />
                    </>
                  }
                />

                <Route
                  path="/orders"
                  element={
                    <ProtectedRoute permission="orders:read">
                      <Header
                        title="Orders"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                      />

                      <OrdersPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/inventory"
                  element={
                    <ProtectedRoute permission="inventory:read">
                      <Header
                        title="Inventory"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                      />

                      <InventoryPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/couriers"
                  element={
                    <ProtectedRoute permission="couriers:read">
                      <Header
                        title="Couriers"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                      />

                      <CouriersPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/customers"
                  element={
                    <ProtectedRoute permission="customers:read">
                      <Header
                        title="Customers"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                      />

                      <CustomersPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/analytics"
                  element={
                    <ProtectedRoute permission="analytics:read">
                      <Header
                        title="Analytics"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                      />

                      <AnalyticsPage />
                    </ProtectedRoute>
                  }
                />

                {/* Unknown dashboard links return to Overview. */}
                <Route
                  path="*"
                  element={<Navigate to="/" replace />}
                />
              </Routes>
            </div>
          </div>
        </ProtectedRoute>
      }
    />
  </Routes>
  </Suspense>
);
}

export default App;
````

### `frontend/src/components/ActionMenu.css`

````css
.action-menu { position: relative; display: inline-flex; }
.action-menu__list { position: fixed; z-index: 1000; min-width: 170px; padding: 6px; border: 1px solid var(--color-border); border-radius: 10px; background: var(--color-surface); box-shadow: 0 14px 30px rgba(0, 30, 60, .18); }
.action-menu__item { display: flex; align-items: center; gap: 8px; width: 100%; border: 0; border-radius: 7px; padding: 9px 10px; background: transparent; color: var(--color-text); text-align: left; cursor: pointer; font-size: .86rem; }
.action-menu__item:hover { background: var(--color-surface-muted); }
.action-menu__item--danger { color: #dc2626; }
````

### `frontend/src/components/ActionMenu.jsx`

````jsx
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreVertical } from "lucide-react";

import "./ActionMenu.css";

function ActionMenu({ label = "More actions", items = [] }) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, right: 0 });
  const buttonReference = useRef(null);
  const menuReference = useRef(null);

  function openMenu() {
    const rectangle = buttonReference.current?.getBoundingClientRect();
    if (rectangle) {
      setPosition({
        top: Math.min(rectangle.bottom + 6, window.innerHeight - 120),
        right: Math.max(8, window.innerWidth - rectangle.right),
      });
    }
    setIsOpen((open) => !open);
  }

  useEffect(() => {
    if (!isOpen) return undefined;

    function closeOnOutsideClick(event) {
      if (
        !buttonReference.current?.contains(event.target) &&
        !menuReference.current?.contains(event.target)
      ) setIsOpen(false);
    }

    function closeMenu() {
      setIsOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
    };
  }, [isOpen]);

  return (
    <div className="action-menu">
      <button ref={buttonReference} className="orders-table__more-button" type="button" aria-label={label} aria-expanded={isOpen} onClick={openMenu}>
        <MoreVertical size={19} aria-hidden="true" />
      </button>
      {isOpen && createPortal(
        <div ref={menuReference} className="action-menu__list" style={position} role="menu">
          {items.map((item) => (
            <button key={item.label} type="button" className={item.danger ? "action-menu__item action-menu__item--danger" : "action-menu__item"} onClick={() => { setIsOpen(false); item.onClick?.(); }} role="menuitem" disabled={item.disabled}>
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}

export default ActionMenu;
````

### `frontend/src/components/Header.css`

````css
/* Top application header layout. */
.header {
  position: relative;
  z-index: 20;

  display: grid;
  grid-template-columns: minmax(150px, 1fr) minmax(260px, 430px) auto;
  align-items: center;
  gap: 24px;

  min-height: 70px;
  padding: 0 28px;

  background-color: var(--color-header);
  border-bottom: 1px solid var(--color-border);

  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);

  transition:
    background-color 250ms ease,
    border-color 250ms ease;
}

.header__title {
  margin: 0;
  color: var(--color-text);
  font-size: 28px;
  font-weight: 700;
}

/* Global search input and keyboard-shortcut badge. */
.header__search {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;

  height: 40px;
  padding: 0 10px;

  border: 1px solid var(--color-border);
  border-radius: 8px;

  color: var(--color-muted);
  background-color: var(--color-control);

  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease;
}

.header__search:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(41, 151, 255, 0.13);
}

.header__search input {
  flex: 1;
  min-width: 0;

  border: 0;
  outline: 0;

  color: var(--color-text);
  background-color: transparent;

  font-size: 13px;
}

.header__search input::placeholder {
  color: var(--color-muted);
}

.header__search kbd {
  padding: 3px 6px;

  border: 1px solid var(--color-border);
  border-radius: 5px;

  color: var(--color-muted);
  background-color: var(--color-surface-soft);

  font-family: inherit;
  font-size: 10px;
  white-space: nowrap;
}

/* Theme, settings, notifications, and business-profile controls. */
.header__actions {
  display: flex;
  align-items: center;
  gap: 7px;
}

/* Shared circular style for small header icon buttons. */
.header__icon-button {
  position: relative;

  display: grid;
  place-items: center;

  width: 38px;
  height: 38px;
  padding: 0;

  border: 0;
  border-radius: 8px;

  color: var(--color-text);
  background-color: transparent;

  transition:
    color 180ms ease,
    background-color 180ms ease,
    transform 180ms ease;
}

.header__icon-button:hover {
  color: var(--color-accent);
  background-color: var(--color-surface-soft);
  transform: translateY(-1px);
}

.header__divider {
  width: 1px;
  height: 24px;
  margin: 0 3px;
  background-color: var(--color-border);
}

/* Red unread-notification number positioned over the bell. */
.header__notification-count {
  position: absolute;
  top: 3px;
  right: 2px;

  display: grid;
  place-items: center;

  min-width: 16px;
  height: 16px;
  padding: 0 4px;

  border: 2px solid var(--color-header);
  border-radius: 10px;

  color: white;
  background-color: #ef4444;

  font-size: 9px;
  font-weight: 700;
}

/* Current business avatar and text menu. */
.header__business {
  display: flex;
  align-items: center;
  gap: 9px;

  margin-left: 5px;
  padding: 4px 7px 4px 4px;

  border: 0;
  border-radius: 10px;

  color: var(--color-text);
  background-color: transparent;

  text-align: left;

  transition: background-color 180ms ease;
}

.header__business:hover {
  background-color: var(--color-surface-soft);
}

.header__avatar {
  display: grid;
  place-items: center;
  flex-shrink: 0;

  width: 38px;
  height: 38px;

  border-radius: 50%;

  color: white;
  background:
    linear-gradient(
      145deg,
      #0d5fa9,
      #073665
    );

  font-size: 12px;
  font-weight: 700;
}

.header__business-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header__business-details strong {
  font-size: 12px;
  white-space: nowrap;
}

.header__business-details small {
  color: var(--color-muted);
  font-size: 10px;
}

/* Theme-specific colour adjustments. */
html[data-theme="dark"] .header__search {
  background-color: rgba(9, 23, 37, 0.8);
}

html[data-theme="dark"] .header__avatar {
  box-shadow: 0 0 16px rgba(41, 151, 255, 0.16);
}

/* Hide less important header information as available width decreases. */
@media (max-width: 1050px) {
  .header {
    grid-template-columns: 1fr auto;
  }

  .header__search {
    display: none;
  }
}

/* Compact mobile header layout. */
@media (max-width: 700px) {
  .header {
    padding: 0 16px;
  }

  .header__business-details,
  .header__business > svg,
  .header__divider {
    display: none;
  }
}


.header__profile-menu {
  position: relative;
}

.header__profile-dropdown {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  z-index: 100;

  width: 180px;
  padding: 7px;

  border: 1px solid var(--color-border);
  border-radius: 10px;

  background: var(--color-surface);

  box-shadow:
    0 12px 30px rgba(0, 20, 45, 0.18);
}

.header__dropdown-item {
  display: flex;
  align-items: center;
  gap: 9px;

  width: 100%;
  padding: 10px 12px;

  border: 0;
  border-radius: 7px;

  color: #dc2626;
  background: transparent;

  font: inherit;
  font-size: 14px;
  font-weight: 600;
  text-align: left;

  cursor: pointer;
}

.header__dropdown-item:hover {
  background: rgba(220, 38, 38, 0.1);
}

.header__notification-menu {
  position: relative;
}

.header__notification-dropdown {
  position: absolute;

  top: calc(100% + 10px);
  right: 0;
  z-index: 100;

  width: min(360px, calc(100vw - 32px));
  padding: 12px;

  border: 1px solid var(--color-border);
  border-radius: 10px;

  background: var(--color-surface);

  box-shadow:
    0 12px 30px rgba(0, 20, 45, 0.18);
}

.header__search-results {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  left: 0;
  z-index: 120;
  display: grid;
  gap: 3px;
  max-height: 430px;
  padding: 9px;
  overflow-y: auto;
  border: 1px solid var(--color-border);
  border-radius: 11px;
  color: var(--color-text);
  background: var(--color-surface);
  box-shadow: 0 18px 45px rgba(0, 20, 45, 0.2);
}

.header__search-results > strong {
  padding: 8px 9px 4px;
  color: var(--color-muted);
  font-size: 10px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.header__search-results button {
  display: grid;
  gap: 3px;
  width: 100%;
  padding: 9px;
  border: 0;
  border-radius: 8px;
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.header__search-results button:hover {
  background: var(--color-surface-soft);
}

.header__search-results span {
  font-size: 12px;
  font-weight: 700;
}

.header__search-results small,
.header__search-results p {
  margin: 0;
  color: var(--color-muted);
  font-size: 10px;
}

.header__search-results p {
  padding: 18px 10px;
  text-align: center;
}

.header__notification-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 5px 11px;
  border-bottom: 1px solid var(--color-border);
}

.header__notification-heading span {
  color: var(--color-muted);
  font-size: 11px;
}

.header__notification-list {
  display: grid;
  gap: 4px;
  max-height: 360px;
  margin-top: 7px;
  overflow-y: auto;
}

.header__notification-item {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 10px;
  border: 0;
  border-radius: 8px;
  color: var(--color-text);
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.header__notification-item:hover,
.header__notification-item--unread {
  background: var(--color-surface-soft);
}

.header__notification-item--unread {
  box-shadow: inset 3px 0 var(--color-accent);
}

.header__notification-item strong {
  font-size: 12px;
}

.header__notification-item span,
.header__notification-empty {
  color: var(--color-muted);
  font-size: 11px;
  line-height: 1.45;
}

.header__notification-empty {
  margin: 0;
  padding: 18px 10px;
  text-align: center;
}

.header__settings-menu {
  position: relative;
}

.header__settings-dropdown {
  position: absolute;

  top: calc(100% + 20px);
  right: 0;
  z-index: 100;

  width: 700px;
  max-width: calc(100vw - 32px);
  max-height: min(540px, calc(100vh - 100px));
  overflow-y: auto;
  padding: 12px;

  border: 1px solid var(--color-border);
  border-radius: 10px;

  background: var(--color-surface);

  box-shadow:
    0 12px 30px rgba(0, 20, 45, 0.18);
}

.header__profile-dropdown,
.header__notification-dropdown, 
.header__settings-dropdown{
  transform-origin: top right;

  animation:
    dropdown-open 200ms
    cubic-bezier(0.22, 1, 0.36, 1)
    both;
}

@keyframes dropdown-open {
  from {
    opacity: 0;
    transform:
      translateY(-8px)
      scale(0.96);
  }

  to {
    opacity: 1;
    transform:
      translateY(0)
      scale(1);
  }
}

.header__dropdown-item{
  animation:
    dropdown-item-open 240ms ease-out both;
}

@keyframes dropdown-item-open {
  from {
    opacity: 0;
    transform: translateX(-6px);
  }

  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .header__profile-dropdown,
  .header__notification-dropdown,
  .header__dropdown-item {
    animation: none;
  }
}
````

### `frontend/src/components/Header.jsx`

````jsx
// Icons used by global search, theme controls, notifications, and the profile.
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { logoutUser } from "../services/authService";

import {
  Bell,
  ChevronDown,
  Moon,
  Search,
  Settings,
  Sun,
  LogOut,
  UserRound,
} from "lucide-react";

import "./Header.css";
import { useAuth } from "../context/authContextValue";
import {
  getNotifications,
  markNotificationRead,
} from "../services/notificationService";
import StaffSettings from "./StaffSettings";
import { searchBusiness } from "../services/searchService";
import ProfileModal from "./ProfileModal";

function getNotificationPath(notification) {
  if (notification.orderId || ["new-order", "fraud-report"].includes(notification.type)) {
    const orderNumber =
      notification.orderNumber ||
      notification.title?.match(/[A-Z]{2,}-\d+/)?.[0] ||
      "";
    return orderNumber
      ? `/orders?search=${encodeURIComponent(orderNumber)}`
      : "/orders";
  }
  if (notification.productId || notification.type?.includes("stock")) {
    const productSearch = notification.productName || notification.sku || "";
    return productSearch
      ? `/inventory?search=${encodeURIComponent(productSearch)}`
      : "/inventory";
  }
  if (notification.customerId) return "/customers";
  if (notification.courierId || notification.type?.includes("courier")) return "/couriers";
  return "/";
}

function Header({ title, theme, onToggleTheme }) {
  const navigate = useNavigate();
  const location = useLocation();
  const searchInputReference = useRef(null);
  const knownNotificationIdsReference = useRef(new Set());
  const notificationsLoadedReference = useRef(false);
  const { user, sellerProfile, business, membership } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";
  const businessInitials = businessName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
  const roleLabel = (membership?.role ?? "viewer")
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  // profile menu
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  //Notification panel
  const [isNotiPanelOpen, setIsNotiPanelOpen] = useState(false);
  //Settongs Panel
  const [isSettingsPanelOpen, setIsSettingsPanelOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState({
    orders: [],
    products: [],
    customers: [],
  });
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  useEffect(() => {
    let requestIsCurrent = true;
    let refreshTimer;

    if (!business?.id) {
      setNotifications([]);
      return undefined;
    }

    function showDeviceNotification(notification) {
      if (!("Notification" in window) || window.Notification.permission !== "granted") return;

      const deviceNotification = new window.Notification(notification.title || "Vendly notification", {
        body: notification.message || "Open Vendly to view the update.",
        tag: `vendly-${notification.id}`,
      });
      deviceNotification.onclick = () => {
        window.focus();
        navigate(getNotificationPath(notification));
        deviceNotification.close();
      };
    }

    async function refreshNotifications() {
      try {
        const records = await getNotifications(business.id);
        if (!requestIsCurrent) return;

        if (notificationsLoadedReference.current) {
          records
            .filter(
              (notification) =>
                !notification.isRead &&
                !knownNotificationIdsReference.current.has(notification.id),
            )
            .forEach(showDeviceNotification);
        }

        knownNotificationIdsReference.current = new Set(
          records.map((notification) => notification.id),
        );
        notificationsLoadedReference.current = true;
        setNotifications(records);
      } catch (error) {
        console.error("Notifications could not be loaded:", error);
      }
    }

    refreshNotifications();
    refreshTimer = window.setInterval(refreshNotifications, 30000);

    return () => {
      requestIsCurrent = false;
      window.clearInterval(refreshTimer);
    };
  }, [business?.id, navigate]);

  async function requestDeviceNotificationPermission() {
    if ("Notification" in window && window.Notification.permission === "default") {
      await window.Notification.requestPermission();
    }
  }

  useEffect(() => {
    function focusGlobalSearch(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInputReference.current?.focus();
      }
    }

    window.addEventListener("keydown", focusGlobalSearch);
    return () => window.removeEventListener("keydown", focusGlobalSearch);
  }, []);

  useEffect(() => {
    const cleanSearch = searchText.trim();

    if (!business?.id || cleanSearch.length < 2) {
      setSearchResults({ orders: [], products: [], customers: [] });
      setIsSearchOpen(false);
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchBusiness(business.id, cleanSearch, controller.signal)
        .then((results) => {
          setSearchResults(results);
          setIsSearchOpen(true);
        })
        .catch((error) => {
          if (error.name !== "AbortError") {
            console.error("Global search failed:", error);
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [business?.id, searchText]);

  function openSearchResult(path) {
    setIsSearchOpen(false);
    navigate(path);
  }

  const unreadNotificationCount = notifications.filter(
    (notification) => !notification.isRead,
  ).length;

  async function handleNotificationClick(notification) {
    if (!business?.id) return;

    try {
      if (!notification.isRead) {
        await markNotificationRead(business.id, notification.id);
        setNotifications((current) =>
          current.map((item) =>
            item.id === notification.id ? { ...item, isRead: true } : item,
          ),
        );
      }
    } catch (error) {
      console.error("Notification could not be marked as read:", error);
    } finally {
      setIsNotiPanelOpen(false);
      navigate(getNotificationPath(notification));
    }
  }
 

  // Accessible text changes to describe the action the theme button will perform.
  const themeButtonLabel =
    theme === "dark" ? "Switch to light mode" : "Switch to dark mode";

  return (
    <header className="header">
      {/* The title is supplied by the page route in App.jsx. */}
      <h1 className="header__title">{title}</h1>

      {/* Global search layout; the search behaviour will be connected later. */}
      <div className="header__search">
        <Search size={17} aria-hidden="true" />

        <input
          ref={searchInputReference}
          type="search"
          value={searchText}
          onChange={(event) => {
            const value = event.target.value;
            setSearchText(value);
            if (!value && location.search) navigate(location.pathname, { replace: true });
          }}
          onFocus={() => {
            if (searchText.trim().length >= 2) setIsSearchOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setIsSearchOpen(false);
          }}
          placeholder="Search orders, customers, products..."
          aria-label="Global search"
        />

        <kbd>Ctrl + K</kbd>

        {isSearchOpen && (
          <div className="header__search-results">
            {searchResults.orders.length > 0 && <strong>Orders</strong>}
            {searchResults.orders.map((order) => (
              <button
                key={order.id}
                type="button"
                onClick={() => openSearchResult(`/orders?search=${encodeURIComponent(order.orderNumber)}`)}
              >
                <span>{order.orderNumber}</span>
                <small>{order.customerName} Â· {order.status}</small>
              </button>
            ))}

            {searchResults.products.length > 0 && <strong>Products</strong>}
            {searchResults.products.map((product) => (
              <button
                key={product.id}
                type="button"
                onClick={() => openSearchResult(`/inventory?search=${encodeURIComponent(product.name)}`)}
              >
                <span>{product.name}</span>
                <small>{product.sku || "Product"} Â· {product.availableStock} available</small>
              </button>
            ))}

            {searchResults.customers.length > 0 && <strong>Customers</strong>}
            {searchResults.customers.map((customer) => (
              <button
                key={customer.id}
                type="button"
                onClick={() => openSearchResult(`/customers?search=${encodeURIComponent(customer.name)}`)}
              >
                <span>{customer.name}</span>
                <small>+{customer.phone} Â· {customer.riskLevel} risk</small>
              </button>
            ))}

            {Object.values(searchResults).every((items) => items.length === 0) && (
              <p>No matching orders, products or customers.</p>
            )}
          </div>
        )}
      </div>

      {/* Header controls for theme, settings, notifications, and business profile. */}
      <div className="header__actions">
        {/* Light/dark theme switch. */}
        <button
          className="header__icon-button"
          type="button"
          onClick={onToggleTheme}
          aria-label={themeButtonLabel}
          title={themeButtonLabel}
        >
          {theme === "dark" ? (
            <Sun size={20} aria-hidden="true" />
          ) : (
            <Moon size={20} aria-hidden="true" />
          )}
        </button>

        <span className="header__divider" aria-hidden="true" />

        {/* Application settings shortcut. */}
        <div className="header__settings-menu">
        <button
          className="header__icon-button"
          type="button"
          onClick={() => setIsSettingsPanelOpen((currentValue) => !currentValue)}
          aria-label="Open settings"
          title="Settings"
        >
          <Settings size={20} aria-hidden="true" />
        </button>

        {isSettingsPanelOpen && (
            <div className="header__settings-dropdown" role="menu">
              <StaffSettings
                businessId={business?.id}
                currentRole={membership?.role}
              />
            </div>
          )}
        </div>

        {/* Notification bell and unread notification count. */}
        <div className="header__notification-menu">
          <button
            className="header__icon-button header__notification"
            type="button"
            onClick={() => {
              requestDeviceNotificationPermission();
              setIsNotiPanelOpen((currentValue) => !currentValue);
            }}
            aria-label="View notifications"
            title="Notifications"
            aria-haspopup="menu"
            aria-expanded={isNotiPanelOpen}
          >
            <Bell size={20} aria-hidden="true" />
            {unreadNotificationCount > 0 && (
              <span className="header__notification-count">
                {unreadNotificationCount > 99 ? "99+" : unreadNotificationCount}
              </span>
            )}
          </button>

          {isNotiPanelOpen && (
            <div className="header__notification-dropdown" role="menu">
              <div className="header__notification-heading">
                <strong>Notifications</strong>
                <span>{unreadNotificationCount} unread</span>
              </div>

              <div className="header__notification-list">
                {notifications.length === 0 ? (
                  <p className="header__notification-empty">No notifications yet.</p>
                ) : (
                  notifications.slice(0, 8).map((notification) => (
                    <button
                      className={`header__notification-item ${
                        notification.isRead
                          ? ""
                          : "header__notification-item--unread"
                      }`}
                      key={notification.id}
                      type="button"
                      role="menuitem"
                      onClick={() => handleNotificationClick(notification)}
                    >
                      <strong>{notification.title}</strong>
                      <span>{notification.message}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Current business profile menu. */}

        <div className="header__profile-menu">
          <button
            className="header__business"
            type="button"
            onClick={() =>
              setIsProfileMenuOpen((currentValue) => !currentValue)
            }
            aria-label="Open business profile"
            aria-haspopup="menu"
            aria-expanded={isProfileMenuOpen}
          >
            <span className="header__avatar">{businessInitials}</span>

            <span className="header__business-details">
              <strong>{businessName}</strong>
              <small>{roleLabel}</small>
            </span>

            <ChevronDown size={16} aria-hidden="true" />
          </button>

          {isProfileMenuOpen && (
            <div className="header__profile-dropdown" role="menu">
              <button
                className="header__dropdown-item"
                type="button"
                onClick={() => {
                  setIsProfileMenuOpen(false);
                  setIsProfileModalOpen(true);
                }}
                role="menuitem"
              >
                <UserRound size={17} aria-hidden="true" />
                My Profile
              </button>
              <button
                className="header__dropdown-item"
                type="button"
                onClick={handleLogout}
                role="menuitem"
              >
                <LogOut size={17} aria-hidden="true" />
                Log out
              </button>
            </div>
          )}
        </div>
      </div>

      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        user={user}
      />
    </header>
  );
}

async function handleLogout() {
  try {
    await logoutUser();
  } catch (error) {
    console.error("Logout failed:", error);
  }
}

export default Header;
````

### `frontend/src/components/ModalShell.css`

````css
.modal-is-open {
  overflow: hidden;
}

.modal-shell__backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(4, 19, 37, 0.68);
  backdrop-filter: blur(4px);
  animation: modal-backdrop-in 160ms ease-out;
}

.modal-shell {
  width: min(100%, 620px);
  max-height: calc(100vh - 48px);
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  color: var(--color-text);
  background: var(--color-surface);
  box-shadow: 0 26px 70px rgba(0, 17, 38, 0.34);
  animation: modal-panel-in 190ms cubic-bezier(0.22, 1, 0.36, 1);
}

.modal-shell--large {
  width: min(100%, 1120px);
}

.modal-shell--wide {
  width: min(100%, 1320px);
}

.modal-shell__header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 22px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.modal-shell__header h2,
.modal-shell__header p {
  margin: 0;
}

.modal-shell__header p {
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}

.modal-shell__header button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 9px;
  color: inherit;
  background: transparent;
  cursor: pointer;
}

.modal-shell__header button:hover {
  background: var(--color-surface-muted);
}

.modal-shell__content {
  padding: 22px;
}

@keyframes modal-backdrop-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-panel-in {
  from { opacity: 0; transform: translateY(14px) scale(0.985); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .modal-shell__backdrop,
  .modal-shell {
    animation: none;
  }
}
````

### `frontend/src/components/ModalShell.jsx`

````jsx
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import "./ModalShell.css";

function ModalShell({ isOpen, title, description, onClose, children, size = "medium" }) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function closeWithEscape(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", closeWithEscape);
    document.body.classList.add("modal-is-open");

    return () => {
      document.removeEventListener("keydown", closeWithEscape);
      document.body.classList.remove("modal-is-open");
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return createPortal(
    <div className="modal-shell__backdrop" role="presentation">
      <section
        className={`modal-shell modal-shell--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-shell-title"
      >
        <header className="modal-shell__header">
          <div>
            <h2 id="modal-shell-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>

          <button type="button" onClick={onClose} aria-label={`Close ${title}`}>
            <X size={21} aria-hidden="true" />
          </button>
        </header>

        <div className="modal-shell__content">{children}</div>
      </section>
    </div>,
    document.body,
  );
}

export default ModalShell;
````

### `frontend/src/components/ProtectedRoute.jsx`

````jsx
import {
  Navigate,
  useLocation,
} from "react-router-dom";

import { useAuth } from "../context/authContextValue";

function hasPermission(membership, requiredPermission) {
  if (!requiredPermission || membership?.role === "owner") {
    return true;
  }

  const permissions = membership?.permissions ?? [];
  const resource = requiredPermission.split(":", 1)[0];

  return (
    permissions.includes("*")
    || permissions.includes(requiredPermission)
    || permissions.includes(`${resource}:*`)
  );
}

function ProtectedRoute({
  children,
  requireSellerProfile = true,
  permission = null,
}) {
  const {
    isAuthenticated,
    isAuthLoading,
    sellerProfile,
    membership,
  } = useAuth();

  const location = useLocation();

  // Wait until Firebase finishes checking the saved login session.
  if (isAuthLoading) {
    return null;
  }

  // Send logged-out users to the login page.
  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location.pathname,
        }}
      />
    );
  }

  // Google users and older accounts complete their business profile once.
  if (requireSellerProfile && !sellerProfile) {
    return <Navigate to="/setup-business" replace />;
  }

  // Keep staff away from dashboard pages their assigned role cannot access.
  if (permission && !hasPermission(membership, permission)) {
    return <Navigate to="/" replace />;
  }

  // Logged-in users can view the protected page.
  return children;
}

export default ProtectedRoute;
````

### `frontend/src/components/Sidebar.css`

````css
/* Full-width sidebar with the Vendly blue gradient. */
.sidebar {
  display: flex;
  flex-direction: column;
  width: 200px;
  min-height: 100vh;
  padding: 4px 14px 24px;
  color: white;
  background: linear-gradient(
  to bottom right,
  #002d52 0%,
  #063b6a 50%,
  #00315c 100%
);
  overflow: hidden;
  transition:
    width 240ms cubic-bezier(0.22, 1, 0.36, 1),
    padding 240ms cubic-bezier(0.22, 1, 0.36, 1);
}

/* Narrow sidebar state used after pressing the toggle button. */
.sidebar--collapsed {
  width: 76px;
  padding-right: 10px;
  padding-left: 10px;
}

.sidebar--collapsed .sidebar__logo {
  height: 72px;
  margin-bottom: 12px;
}

.sidebar--collapsed .sidebar__logo-image {
  opacity: 0;
}

.sidebar--collapsed .sidebar__link,
.sidebar--collapsed .sidebar__assistant {
  justify-content: center;
  gap: 0;
}

.sidebar--collapsed .sidebar__label {
  display: none;
}

/* Logo sizing in expanded and collapsed states. */
.sidebar__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  margin-bottom: 4px;
  padding: 0;
  overflow: hidden;
}

.sidebar__logo-image {
  display: block;
  width: 140px;
  max-width: none;
  height: auto;
  object-fit: contain;
}

/* Main navigation link layout and spacing. */
.sidebar__navigation {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar__link,
.sidebar__assistant {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  border: 0;
  border-radius: 8px;
  padding: 12px;
  color: white;
  background: transparent;
  text-align: left;
  text-decoration: none;
}

/* Hover and active-page link styles. */
.sidebar__link:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.sidebar__link--active {
  background:
    linear-gradient(
      135deg,
      #0879dd 0%,
      #075da9 100%
    );


}

.sidebar__assistant {
  margin-top: 0;
  border: 1px solid var(--color-accent);
  justify-content: center;
}
/* Bottom area containing the assistant and current business. */
.sidebar__footer {
  display: flex;
  flex-direction: column;
  gap: 12px;

  margin-top: auto;
}

/* Current business/store button. */
.sidebar__business {
  display: flex;
  align-items: center;
  gap: 9px;

  width: 100%;
  padding: 12px 6px 0;

  border: 0;
  border-top: 1px solid rgba(255, 255, 255, 0.14);

  color: white;
  background-color: transparent;

  text-align: left;
}

.sidebar__business-icon {
  display: grid;
  place-items: center;
  flex-shrink: 0;

  width: 32px;
  height: 32px;

  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 9px;

  background-color: rgba(255, 255, 255, 0.08);
}

.sidebar__business-details {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.sidebar__business-details strong {
  overflow: hidden;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar__business-details small {
  color: rgba(255, 255, 255, 0.7);
  font-size: 9px;
}

.sidebar__business-arrow {
  flex-shrink: 0;
}

.sidebar__business:hover {
  color: #7fc5ff;
}

.sidebar--collapsed .sidebar__business {
  justify-content: center;
  padding-right: 0;
  padding-left: 0;
}

.sidebar--collapsed .sidebar__business-arrow {
  display: none;
}

/* Top logo-and-toggle row. */
.sidebar__top {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 60px;
  margin-bottom: 12px;
}

.sidebar__top .sidebar__logo {
  flex: 1;
  height: auto;
  margin: 0;
}

/* Button used to expand or collapse the sidebar. */
.sidebar__toggle {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  color: white;
  background-color: rgba(59, 138, 202, 0);
  transition:
    background-color 180ms ease,
    transform 180ms ease;
}

.Panel_icon{
border-radius: 7px;
}

.sidebar__toggle:hover {
  background-color: #0879dd;
  transform: scale(1.06);
}

.sidebar--collapsed .sidebar__top {
  justify-content: center;
  min-height: 60px;
}

.sidebar--collapsed .sidebar__logo {
  display: none;
}

/* Dark-theme sidebar background and active-link adjustment. */
html[data-theme="dark"] .sidebar {
  background:
    radial-gradient(
      circle at 100% 0%,
      rgba(20, 126, 220, 0.25),
      transparent 38%
    ),
    linear-gradient(
      145deg,
      #052d50 0%,
      #073d6d 52%,
      #031e37 100%
    );

  box-shadow: 8px 0 28px rgba(0, 0, 0, 0.22);
}

html[data-theme="dark"] .sidebar__link--active {
  background:
    linear-gradient(
      135deg,
      #075fae 0%,
      #064b89 100%
    );
}
````

### `frontend/src/components/Sidebar.jsx`

````jsx
// Sidebar styles, Vendly logo, and React Router navigation component.
import "./Sidebar.css";
import vendlyLogo from "../assets/vendly-logo.png";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/authContextValue";

// Icons paired with sidebar links and footer actions.
import {
  LayoutDashboard,
  ClipboardList,
  Truck,
  Users,
  ChartNoAxesCombined,
  Sparkles,
  Box,
  ChevronsRight,
  SquareMenu,
  ChevronRight,
  Store,
} from "lucide-react";

// Central list of sidebar pages; map() below turns each item into a link.
const navigationItems = [
  { label: "Overview", path: "/", icon: LayoutDashboard },
  { label: "Orders", path: "/orders", icon: ClipboardList, permission: "orders:read" },
  { label: "Inventory", path: "/inventory", icon: Box, permission: "inventory:read" },
  { label: "Couriers", path: "/couriers", icon: Truck, permission: "couriers:read" },
  { label: "Customers", path: "/customers", icon: Users, permission: "customers:read" },
  { label: "Analytics", path: "/analytics", icon: ChartNoAxesCombined, permission: "analytics:read" },
];

function hasPermission(membership, requiredPermission) {
  if (!requiredPermission || membership?.role === "owner") return true;
  const permissions = membership?.permissions ?? [];
  const resource = requiredPermission.split(":", 1)[0];
  return permissions.includes("*") || permissions.includes(requiredPermission) || permissions.includes(`${resource}:*`);
}

function readableRole(role = "viewer") {
  return role.split("_").map((word) => word[0].toUpperCase() + word.slice(1)).join(" ");
}

function Sidebar({ isCollapsed, onToggleSidebar }) {
  const { sellerProfile, membership } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";

  return (
    <aside id="sidebar-navigation" className={`sidebar ${isCollapsed ? "sidebar--collapsed" : ""}`} >
{/* Logo and button that expands or collapses the sidebar. */}
<div className="sidebar__top">
  <div className="sidebar__logo">
    <img
      className="sidebar__logo-image"
      src={vendlyLogo}
      alt="Vendly.lk"
    />
  </div>

  <button
    className="sidebar__toggle"
    type="button"
    onClick={onToggleSidebar}
    aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
    aria-expanded={!isCollapsed}
    title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
  >
    {isCollapsed ? <ChevronsRight size={25} /> : <SquareMenu className="Panel_icon" size={20} />}
  </button>
</div>
      {/* Main navigation links. NavLink reports which route is active. */}
      <nav className="sidebar__navigation">
        {navigationItems.filter((item) => hasPermission(membership, item.permission)).map((item) => {
          // Store the selected icon component in a capitalized variable for JSX.
          const Icon = item.icon;

          return (
 <NavLink
  className={({ isActive }) =>
    `sidebar__link ${isActive ? "sidebar__link--active" : ""}`
  }
  end={item.path === "/"}
  key={item.path}
  to={item.path}
  title={isCollapsed ? item.label : undefined}
>
  <Icon size={22} />
  <span className="sidebar__label">{item.label}</span>
</NavLink>
          );
        })}
      </nav>

     {/* Business assistant and current-store controls stay at the bottom. */}
     <div className="sidebar__footer">
  <button className="sidebar__assistant" type="button">
    <Sparkles size={20} aria-hidden="true" />
    <span className="sidebar__label">Business Assistant</span>
  </button>

  <button
    className="sidebar__business"
    type="button"
    title={isCollapsed ? businessName : undefined}
  >
    <span className="sidebar__business-icon">
      <Store size={18} aria-hidden="true" />
    </span>

    <span className="sidebar__business-details sidebar__label">
      <strong>{businessName}</strong>
      <small>{readableRole(membership?.role)}</small>
    </span>

    <ChevronRight
      className="sidebar__business-arrow"
      size={16}
      aria-hidden="true"
    />
  </button>
</div>
    </aside>
  );
}

export default Sidebar;
````

### `frontend/src/pages/ManagementPage.css`

````css
.management-page__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.management-page__primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid #087cf0;
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(135deg, #178ff8, #066ce1);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}

.management-page__notice {
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  color: var(--color-text-muted);
  background: var(--color-surface);
}

.management-table {
  width: 100%;
  margin-top: 18px;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  color: var(--color-text);
  background: var(--color-surface);
}

.management-table th,
.management-table td {
  padding: 13px 14px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  font-size: 0.88rem;
}

.management-table th {
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.management-table tr:last-child td {
  border-bottom: 0;
}

.management-table__badge {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  color: #087443;
  background: rgba(16, 185, 129, 0.13);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: capitalize;
}

.management-table__badge--medium {
  color: #a15c00;
  background: rgba(245, 158, 11, 0.15);
}

.management-table__badge--high {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.14);
}

@media (max-width: 760px) {
  .management-page__heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .management-table {
    display: block;
    overflow-x: auto;
  }
}
````

## Feature 5 source — Profile and account management

Files in this feature: 2

### `frontend/src/components/ProfileModal.css`

````css
.profile-modal {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.profile-modal__identity {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface-soft);
  grid-column: 1 / -1;
}

.profile-modal__identity-icon {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  border-radius: 50%;
  color: #fff;
  background: linear-gradient(145deg, #087cf0, #0759ba);
}

.profile-modal__identity > div { display: grid; gap: 2px; min-width: 0; }
.profile-modal__identity span, .profile-modal__identity small { color: var(--color-text-muted); }
.profile-modal__verified { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; color: #13865d !important; font-size: 0.78rem; font-weight: 700; }

.profile-modal__section { display: grid; gap: 12px; padding: 16px; border: 1px solid var(--color-border); border-radius: 12px; }
.profile-modal__section-title { display: flex; align-items: flex-start; gap: 10px; }
.profile-modal__section-title svg { margin-top: 2px; color: var(--color-accent); }
.profile-modal__section-title h3, .profile-modal__section-title p { margin: 0; }
.profile-modal__section-title h3 { font-size: 0.96rem; }
.profile-modal__section-title p { margin-top: 3px; color: var(--color-text-muted); font-size: 0.78rem; }

.profile-modal label { display: grid; gap: 6px; color: var(--color-text); font-size: 0.8rem; font-weight: 650; }
.profile-modal input { width: 100%; min-height: 40px; padding: 0 11px; border: 1px solid var(--color-border); border-radius: 8px; color: var(--color-text); background: var(--color-surface); font: inherit; box-sizing: border-box; }
.profile-modal input:focus { border-color: var(--color-accent); outline: 3px solid color-mix(in srgb, var(--color-accent) 15%, transparent); }
.profile-modal__password-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; }
.profile-modal__password-grid label:first-child { grid-column: 1 / -1; }
.profile-modal__hint, .profile-modal__provider-note { margin: 0; padding: 10px 12px; border-radius: 8px; color: var(--color-text-muted); background: var(--color-surface-soft); font-size: 0.78rem; line-height: 1.5; }
.profile-modal__message { margin: 0; padding: 9px 11px; border-radius: 8px; font-size: 0.78rem; line-height: 1.45; }
.profile-modal__message--success { color: #08734f; background: #e7f8f1; }
.profile-modal__message--error { color: #b42318; background: #fff0ef; }
.profile-modal__button-row { display: flex; justify-content: flex-end; gap: 8px; }
.profile-modal button { min-height: 38px; padding: 0 14px; border-radius: 8px; font: inherit; font-size: 0.8rem; font-weight: 700; cursor: pointer; }
.profile-modal button:disabled { cursor: wait; opacity: 0.62; }
.profile-modal__primary { justify-self: end; border: 1px solid var(--color-accent); color: #fff; background: var(--color-accent); }
.profile-modal__secondary { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--color-border); color: var(--color-text); background: var(--color-surface); }

html[data-theme="dark"] .profile-modal__message--success { color: #75e1ba; background: rgba(18, 134, 93, 0.18); }
html[data-theme="dark"] .profile-modal__message--error { color: #ffaaa3; background: rgba(180, 35, 24, 0.2); }

@media (max-width: 800px) {
  .profile-modal { grid-template-columns: 1fr; }
  .profile-modal__identity { grid-column: auto; }
}

@media (max-width: 620px) {
  .profile-modal__password-grid { grid-template-columns: 1fr; }
  .profile-modal__password-grid label:first-child { grid-column: auto; }
  .profile-modal__identity { align-items: flex-start; flex-wrap: wrap; }
  .profile-modal__verified { margin-left: 59px; }
  .profile-modal__button-row { flex-direction: column-reverse; }
  .profile-modal__button-row button, .profile-modal__primary { width: 100%; justify-self: stretch; justify-content: center; }
}
````

### `frontend/src/components/ProfileModal.jsx`

````jsx
import { KeyRound, Mail, RotateCcw, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import {
  changeAccountPassword,
  currentUserHasPasswordProvider,
  requestAccountEmailChange,
  sendCurrentUserPasswordReset,
} from "../services/authService";
import ModalShell from "./ModalShell";

import "./ProfileModal.css";

function readableAuthError(error) {
  const messages = {
    "auth/email-already-in-use": "That email address is already used by another account.",
    "auth/invalid-email": "Enter a valid email address.",
    "auth/invalid-credential": "The current password is incorrect.",
    "auth/wrong-password": "The current password is incorrect.",
    "auth/weak-password": "Use a stronger password with at least 6 characters.",
    "auth/too-many-requests": "Too many attempts. Please wait and try again.",
    "auth/popup-closed-by-user": "Google verification was cancelled.",
    "auth/popup-blocked": "Allow popups and try Google verification again.",
    "auth/requires-recent-login": "For security, sign out and sign in again before trying this change.",
  };

  return messages[error?.code] ?? error?.message ?? "The account could not be updated.";
}

function ProfileModal({ isOpen, onClose, user }) {
  const [newEmail, setNewEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [emailMessage, setEmailMessage] = useState(null);
  const [passwordMessage, setPasswordMessage] = useState(null);
  const [workingAction, setWorkingAction] = useState("");
  const hasPasswordProvider = currentUserHasPasswordProvider();
  const providerNames = (user?.providerData ?? []).map((provider) =>
    provider.providerId === "google.com" ? "Google" :
      provider.providerId === "password" ? "Email and password" : provider.providerId,
  );

  useEffect(() => {
    if (!isOpen) return;
    setNewEmail("");
    setEmailPassword("");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setEmailMessage(null);
    setPasswordMessage(null);
  }, [isOpen]);

  async function handleEmailChange(event) {
    event.preventDefault();
    const cleanEmail = newEmail.trim().toLowerCase();
    setEmailMessage(null);

    if (!cleanEmail || cleanEmail === user?.email?.toLowerCase()) {
      setEmailMessage({ type: "error", text: "Enter a different email address." });
      return;
    }

    setWorkingAction("email");
    try {
      await requestAccountEmailChange(cleanEmail, emailPassword);
      setEmailMessage({
        type: "success",
        text: `Verification was sent to ${cleanEmail}. Your email changes after you open that link.`,
      });
      setNewEmail("");
      setEmailPassword("");
    } catch (error) {
      setEmailMessage({ type: "error", text: readableAuthError(error) });
    } finally {
      setWorkingAction("");
    }
  }

  async function handlePasswordChange(event) {
    event.preventDefault();
    setPasswordMessage(null);

    if (newPassword.length < 6) {
      setPasswordMessage({ type: "error", text: "The new password needs at least 6 characters." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: "error", text: "The new passwords do not match." });
      return;
    }

    setWorkingAction("password");
    try {
      await changeAccountPassword(currentPassword, newPassword);
      setPasswordMessage({ type: "success", text: "Your password was changed successfully." });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      setPasswordMessage({ type: "error", text: readableAuthError(error) });
    } finally {
      setWorkingAction("");
    }
  }

  async function handlePasswordReset() {
    setPasswordMessage(null);
    setWorkingAction("reset");
    try {
      await sendCurrentUserPasswordReset();
      setPasswordMessage({ type: "success", text: `Password-reset email sent to ${user?.email}.` });
    } catch (error) {
      setPasswordMessage({ type: "error", text: readableAuthError(error) });
    } finally {
      setWorkingAction("");
    }
  }

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title="My Profile"
      description="Manage your Firebase sign-in details securely."
      size="large"
    >
      <div className="profile-modal">
        <section className="profile-modal__identity">
          <span className="profile-modal__identity-icon"><UserRound size={24} /></span>
          <div>
            <strong>{user?.displayName || "Vendly user"}</strong>
            <span>{user?.email}</span>
            <small>Sign-in method: {providerNames.join(", ") || "Unknown"}</small>
          </div>
          {user?.emailVerified && (
            <span className="profile-modal__verified"><ShieldCheck size={15} /> Verified</span>
          )}
        </section>

        <form className="profile-modal__section" onSubmit={handleEmailChange}>
          <div className="profile-modal__section-title">
            <Mail size={19} />
            <div><h3>Change email</h3><p>A verification link will be sent to the new address.</p></div>
          </div>
          <label>
            New email address
            <input type="email" value={newEmail} onChange={(event) => setNewEmail(event.target.value)} placeholder="new-email@example.com" required />
          </label>
          {hasPasswordProvider && (
            <label>
              Current password
              <input type="password" value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} autoComplete="current-password" required />
            </label>
          )}
          {!hasPasswordProvider && <p className="profile-modal__hint">Google will open a popup to confirm your identity.</p>}
          {emailMessage && <p className={`profile-modal__message profile-modal__message--${emailMessage.type}`} role="status">{emailMessage.text}</p>}
          <button className="profile-modal__primary" type="submit" disabled={Boolean(workingAction)}>
            {workingAction === "email" ? "Sending verification..." : "Verify new email"}
          </button>
        </form>

        <form className="profile-modal__section" onSubmit={handlePasswordChange}>
          <div className="profile-modal__section-title">
            <KeyRound size={19} />
            <div><h3>Change password</h3><p>Use a password you do not use on another website.</p></div>
          </div>

          {hasPasswordProvider ? (
            <>
              <div className="profile-modal__password-grid">
                <label>Current password<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required /></label>
                <label>New password<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={6} required /></label>
                <label>Confirm new password<input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={6} required /></label>
              </div>
              {passwordMessage && <p className={`profile-modal__message profile-modal__message--${passwordMessage.type}`} role="status">{passwordMessage.text}</p>}
              <div className="profile-modal__button-row">
                <button className="profile-modal__secondary" type="button" onClick={handlePasswordReset} disabled={Boolean(workingAction)}><RotateCcw size={16} /> Send reset email</button>
                <button className="profile-modal__primary" type="submit" disabled={Boolean(workingAction)}>{workingAction === "password" ? "Changing..." : "Change password"}</button>
              </div>
            </>
          ) : (
            <p className="profile-modal__provider-note">This account signs in with Google, so it does not have a separate Vendly password. Manage your Google password from your Google Account.</p>
          )}
        </form>
      </div>
    </ModalShell>
  );
}

export default ProfileModal;
````

## Feature 6 source — Staff permissions

Files in this feature: 6

### `backend/app/api/members.py`

````python
from flask import Blueprint, g, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.member_service import add_member, list_members, update_member


members_blueprint = Blueprint("members", __name__, url_prefix="/api/v1")


@members_blueprint.get("/businesses/<business_id>/members")
@require_firebase_user
@require_business_member("owner", "admin", permission="staff:manage")
def get_members(business_id):
    return jsonify(
        {"members": list_members(get_firestore_client(), business_id)},
    )


@members_blueprint.post("/businesses/<business_id>/members")
@require_firebase_user
@require_business_member("owner", "admin", permission="staff:manage")
def create_member(business_id):
    member = add_member(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"member": member}), 201


@members_blueprint.patch("/businesses/<business_id>/members/<member_uid>")
@require_firebase_user
@require_business_member("owner", "admin", permission="staff:manage")
def edit_member(business_id, member_uid):
    member = update_member(
        get_firestore_client(),
        business_id,
        member_uid,
        get_json_object(),
    )
    return jsonify({"member": member})
````

### `backend/app/core/authorization.py`

````python
from functools import wraps

from flask import g

from app.core.errors import ApiError
from app.core.firebase import get_firestore_client


def membership_has_permission(membership, required_permission):
    """Return whether a membership grants one exact or wildcard permission."""
    if not required_permission:
        return True
    if membership.get("role") == "owner":
        return True

    permissions = set(membership.get("permissions") or [])
    if "*" in permissions or required_permission in permissions:
        return True

    resource = required_permission.split(":", 1)[0]
    return f"{resource}:*" in permissions


def require_business_member(*allowed_roles, permission=None):
    """Require the authenticated user to belong to the requested business."""

    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            business_id = kwargs.get("business_id")

            if not business_id:
                raise ApiError(
                    "business_required",
                    "A business ID is required.",
                    400,
                )

            uid = g.current_user["uid"]
            database = get_firestore_client()
            membership_snapshot = (
                database.collection("businesses")
                .document(business_id)
                .collection("members")
                .document(uid)
                .get()
            )

            if not membership_snapshot.exists:
                raise ApiError(
                    "business_access_denied",
                    "You do not have access to this business.",
                    403,
                )

            membership = membership_snapshot.to_dict()

            if membership.get("status") != "active":
                raise ApiError(
                    "business_access_denied",
                    "Your business membership is not active.",
                    403,
                )

            if allowed_roles and membership.get("role") not in allowed_roles:
                raise ApiError(
                    "permission_denied",
                    "You do not have permission to complete this action.",
                    403,
                )

            if permission and not membership_has_permission(membership, permission):
                raise ApiError(
                    "permission_denied",
                    "You do not have permission to complete this action.",
                    403,
                    {"requiredPermission": permission},
                )

            g.business_id = business_id
            g.membership = membership

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator
````

### `backend/app/services/member_service.py`

````python
from firebase_admin import auth, firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import required_text


ROLE_PERMISSIONS = {
    "admin": [
        "orders:*",
        "inventory:*",
        "customers:*",
        "couriers:*",
        "analytics:read",
        "staff:manage",
    ],
    "order_manager": [
        "orders:*",
        "customers:*",
        "couriers:read",
        "inventory:read",
    ],
    "inventory_manager": ["inventory:*", "orders:read", "reviews:manage"],
    "support": ["orders:read", "customers:*", "messages:*"],
    "viewer": ["orders:read", "inventory:read", "analytics:read"],
}


def validate_member_payload(payload, require_email=True):
    try:
        email = (
            required_text(payload.get("email"), "Email", 254).lower()
            if require_email
            else ""
        )
        role = required_text(payload.get("role"), "Role", 40).lower()
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if role not in ROLE_PERMISSIONS:
        raise ApiError(
            "validation_error",
            "Choose a valid staff role.",
            422,
            {"allowedRoles": sorted(ROLE_PERMISSIONS)},
        )

    return {"email": email, "role": role, "permissions": ROLE_PERMISSIONS[role]}


def list_members(database, business_id):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("members")
        .stream()
    )
    members = []

    for snapshot in snapshots:
        member = serialize_snapshot(snapshot)
        user_reference = database.collection("users").document(snapshot.id)
        user_snapshot = user_reference.get()
        user = user_snapshot.to_dict() if user_snapshot.exists else {}

        # Repair staff assignments created before users stored their business link.
        # Existing users keep their current default business; this business is added
        # to the account and becomes the default only when no default exists yet.
        user_business_ids = user.get("businessIds") or []
        user_changes = {}
        if business_id not in user_business_ids:
            user_changes["businessIds"] = firestore.ArrayUnion([business_id])
        if not user.get("defaultBusinessId"):
            user_changes["defaultBusinessId"] = business_id
        if user_changes:
            user_changes["updatedAt"] = firestore.SERVER_TIMESTAMP
            user_reference.set(user_changes, merge=True)

        members.append(
            {
                **member,
                "displayName": user.get("displayName", "Staff member"),
                "email": user.get("email", ""),
                "photoUrl": user.get("photoUrl", ""),
            },
        )

    return sorted(members, key=lambda item: item.get("displayName", "").casefold())


def add_member(database, business_id, invited_by, payload):
    member_data = validate_member_payload(payload)

    try:
        firebase_user = auth.get_user_by_email(member_data["email"])
    except auth.UserNotFoundError as error:
        raise ApiError(
            "staff_account_not_found",
            "This person must create a Vendly account before being added as staff.",
            404,
        ) from error

    business_reference = database.collection("businesses").document(business_id)
    member_reference = business_reference.collection("members").document(
        firebase_user.uid,
    )

    if member_reference.get().exists:
        raise ApiError(
            "staff_member_exists",
            "This account already belongs to the business.",
            409,
        )

    timestamp = firestore.SERVER_TIMESTAMP
    member_reference.set(
        {
            "uid": firebase_user.uid,
            "role": member_data["role"],
            "permissions": member_data["permissions"],
            "status": "active",
            "invitedBy": invited_by,
            "joinedAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    database.collection("users").document(firebase_user.uid).set(
        {
            "uid": firebase_user.uid,
            "displayName": firebase_user.display_name or member_data["email"],
            "email": member_data["email"],
            "photoUrl": firebase_user.photo_url or "",
            "defaultBusinessId": business_id,
            "businessIds": firestore.ArrayUnion([business_id]),
            "status": "active",
            "updatedAt": timestamp,
        },
        merge=True,
    )
    return next(
        member
        for member in list_members(database, business_id)
        if member["id"] == firebase_user.uid
    )


def update_member(database, business_id, member_uid, payload):
    business_reference = database.collection("businesses").document(business_id)
    business_snapshot = business_reference.get()

    if business_snapshot.exists and business_snapshot.to_dict().get("ownerUid") == member_uid:
        raise ApiError(
            "owner_membership_protected",
            "The business owner role cannot be changed or disabled.",
            409,
        )

    member_reference = business_reference.collection("members").document(member_uid)

    if not member_reference.get().exists:
        raise ApiError("staff_member_not_found", "Staff member not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    if "role" in payload:
        validated = validate_member_payload({"role": payload.get("role")}, False)
        changes.update(
            {"role": validated["role"], "permissions": validated["permissions"]},
        )
    if "status" in payload:
        status = str(payload.get("status", "")).strip().lower()
        if status not in {"active", "inactive"}:
            raise ApiError(
                "validation_error",
                "Staff status must be active or inactive.",
                422,
            )
        changes["status"] = status

    member_reference.update(changes)
    return next(
        member
        for member in list_members(database, business_id)
        if member["id"] == member_uid
    )
````

### `frontend/src/components/StaffSettings.css`

````css
.staff-settings {
  display: grid;
  gap: 14px;
}

.staff-settings h2,
.staff-settings p {
  margin: 0;
}

.staff-settings header p,
.staff-settings__members span {
  color: var(--color-muted);
  font-size: 12px;
}

.staff-settings form {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 170px auto;
  gap: 8px;
}

.staff-settings input,
.staff-settings select,
.staff-settings button {
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  background: var(--color-control);
  font: inherit;
}

.staff-settings form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-color: var(--color-accent);
  color: white;
  background: var(--color-accent);
  cursor: pointer;
  font-weight: 700;
}

.staff-settings__members {
  display: grid;
  gap: 7px;
  max-height: 280px;
  overflow-y: auto;
}

.staff-settings__members article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px 80px;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
}

.staff-settings__members article > div {
  display: grid;
  gap: 2px;
}

.staff-settings__members button {
  cursor: pointer;
}

.staff-settings__owner {
  grid-column: span 2;
  color: var(--color-accent);
  text-align: right;
}

.staff-settings__notice {
  padding: 11px;
  border-radius: 8px;
  color: var(--color-muted);
  background: var(--color-surface-soft);
}

.staff-settings__notice--error {
  color: #b42318;
  background: rgba(239, 68, 68, 0.12);
}

.staff-settings__role-description {
  margin-top: -7px !important;
  color: var(--color-muted);
  font-size: 11px;
}

.staff-settings__member-permissions {
  grid-column: 1 / -1;
  color: var(--color-muted);
  font-size: 10px;
}

@media (max-width: 700px) {
  .staff-settings form,
  .staff-settings__members article {
    grid-template-columns: 1fr;
  }
}
````

### `frontend/src/components/StaffSettings.jsx`

````jsx
import { UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import {
  addBusinessMember,
  getBusinessMembers,
  updateBusinessMember,
} from "../services/memberService";
import "./StaffSettings.css";


const staffRoles = [
  ["admin", "Admin"],
  ["order_manager", "Order manager"],
  ["inventory_manager", "Inventory manager"],
  ["support", "Support"],
  ["viewer", "Viewer"],
];

const roleDescriptions = {
  admin: "Full business access, including staff management.",
  order_manager: "Manage orders and customers; view stock and couriers.",
  inventory_manager: "Manage products, stock and reviews; view orders.",
  support: "View orders and manage customer support details.",
  viewer: "Read-only access to orders, inventory and analytics.",
};


function StaffSettings({ businessId, currentRole }) {
  const [members, setMembers] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("order_manager");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const canManageStaff = ["owner", "admin"].includes(currentRole);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!businessId || !canManageStaff) return undefined;

    getBusinessMembers(businessId)
      .then((records) => {
        if (requestIsCurrent) setMembers(records);
      })
      .catch((error) => {
        if (requestIsCurrent) setErrorMessage(error.message);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [businessId, canManageStaff]);

  async function addMember(event) {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage("");

    try {
      const member = await addBusinessMember(businessId, { email, role });
      setMembers((current) => [...current, member]);
      setEmail("");
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function changeMember(member, changes) {
    setErrorMessage("");

    try {
      const updated = await updateBusinessMember(businessId, member.id, changes);
      setMembers((current) =>
        current.map((item) => (item.id === member.id ? updated : item)),
      );
    } catch (error) {
      setErrorMessage(error.message);
    }
  }

  return (
    <section className="staff-settings">
      <header>
        <div><h2>Staff & permissions</h2><p>Control who can access this business.</p></div>
      </header>

      {!canManageStaff ? (
        <p className="staff-settings__notice">Only the owner or an admin can manage staff accounts.</p>
      ) : (
        <>
          <form onSubmit={addMember}>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Existing Vendly account email"
              required
            />
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              {staffRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <button type="submit" disabled={isSaving}>
              <UserPlus size={16} /> {isSaving ? "Adding..." : "Add staff"}
            </button>
          </form>
          <p className="staff-settings__role-description">{roleDescriptions[role]}</p>

          {errorMessage && <p className="staff-settings__notice staff-settings__notice--error" role="alert">{errorMessage}</p>}

          <div className="staff-settings__members">
            {members.map((member) => (
              <article key={member.id}>
                <div><strong>{member.displayName}</strong><span>{member.email}</span></div>
                {member.role === "owner" ? (
                  <strong className="staff-settings__owner">Owner</strong>
                ) : (
                  <>
                    <select
                      value={member.role}
                      onChange={(event) => changeMember(member, { role: event.target.value })}
                    >
                      {staffRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <small className="staff-settings__member-permissions">
                      {roleDescriptions[member.role]}
                    </small>
                    <button
                      type="button"
                      onClick={() => changeMember(member, {
                        status: member.status === "active" ? "inactive" : "active",
                      })}
                    >
                      {member.status === "active" ? "Disable" : "Enable"}
                    </button>
                  </>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export default StaffSettings;
````

### `frontend/src/services/memberService.js`

````javascript
import { apiRequest } from "./apiClient";


export async function getBusinessMembers(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/members`);
  return response.members;
}


export async function addBusinessMember(businessId, memberData) {
  const response = await apiRequest(`/businesses/${businessId}/members`, {
    method: "POST",
    body: memberData,
  });
  return response.member;
}


export async function updateBusinessMember(businessId, memberUid, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/members/${memberUid}`,
    { method: "PATCH", body: changes },
  );
  return response.member;
}
````

## Feature 7 source — Categories

Files in this feature: 6

### `backend/app/services/category_service.py`

````python
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import optional_text, required_text, slugify


def list_categories(database, business_id):
    query = (
        database.collection("businesses")
        .document(business_id)
        .collection("categories")
        .order_by("sortOrder")
    )

    return [serialize_snapshot(snapshot) for snapshot in query.stream()]


def create_category(database, business_id, payload):
    try:
        name = required_text(payload.get("name"), "Category name")
        description = optional_text(payload.get("description"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    category_collection = (
        database.collection("businesses")
        .document(business_id)
        .collection("categories")
    )
    slug = slugify(name)

    if slug:
        duplicate_query = category_collection.where(
            filter=FieldFilter("slug", "==", slug),
        ).limit(1)

        if next(duplicate_query.stream(), None) is not None:
            raise ApiError(
                "category_already_exists",
                "A category with this name already exists.",
                409,
            )

    category_reference = category_collection.document()
    sort_order = payload.get("sortOrder", 0)

    if not isinstance(sort_order, int) or sort_order < 0:
        raise ApiError(
            "validation_error",
            "Sort order must be a positive whole number or zero.",
            422,
        )

    category_reference.set(
        {
            "name": name,
            "slug": slug or category_reference.id.lower(),
            "description": description,
            "status": "active",
            "sortOrder": sort_order,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    return serialize_snapshot(category_reference.get())


def update_category(database, business_id, category_id, payload):
    category_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("categories")
        .document(category_id)
    )
    category_snapshot = category_reference.get()

    if not category_snapshot.exists:
        raise ApiError("category_not_found", "Category not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    try:
        if "name" in payload:
            changes["name"] = required_text(payload.get("name"), "Category name")
            changes["slug"] = slugify(changes["name"]) or category_id.lower()

        if "description" in payload:
            changes["description"] = optional_text(payload.get("description"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if "status" in payload:
        status = payload.get("status")

        if status not in {"active", "archived"}:
            raise ApiError(
                "validation_error",
                "Status must be active or archived.",
                422,
            )

        changes["status"] = status

    if "sortOrder" in payload:
        sort_order = payload.get("sortOrder")

        if not isinstance(sort_order, int) or sort_order < 0:
            raise ApiError(
                "validation_error",
                "Sort order must be a positive whole number or zero.",
                422,
            )

        changes["sortOrder"] = sort_order

    category_reference.update(changes)

    return serialize_snapshot(category_reference.get())
````

### `frontend/src/components/AddCategoryModal.jsx`

````jsx
import { useEffect, useState } from "react";

import { createCategory, updateCategory } from "../services/categoryService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";

function AddCategoryModal({ isOpen, businessId, category = null, onClose, onCreated, onUpdated }) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    sortOrder: "0",
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData(category ? { name: category.name ?? "", description: category.description ?? "", sortOrder: String(category.sortOrder ?? 0) } : { name: "", description: "", sortOrder: "0" });
      setErrorMessage("");
    }
  }, [isOpen, category]);

  function updateField(event) {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");
    setIsSaving(true);

    try {
      const response = category ? await updateCategory(businessId, category.id, {
        ...formData,
        sortOrder: Number(formData.sortOrder),
      }) : await createCategory(businessId, {
        ...formData,
        sortOrder: Number(formData.sortOrder),
      });
      if (category) onUpdated?.(response.category);
      else onCreated?.(response.category);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell
      isOpen={isOpen}
      title={category ? "Edit Category" : "Add Category"}
      description="Create a category used to organise your catalogue."
      onClose={onClose}
    >
      <form className="inventory-form" onSubmit={handleSubmit}>
        <label>
          Category name
          <input
            name="name"
            value={formData.name}
            onChange={updateField}
            placeholder="Example: Footwear"
            maxLength={120}
            autoFocus
            required
          />
        </label>

        <label>
          Description
          <textarea
            name="description"
            value={formData.description}
            onChange={updateField}
            placeholder="What kind of products belong here?"
            maxLength={500}
            rows={4}
          />
        </label>

        <label>
          Display order
          <input
            name="sortOrder"
            type="number"
            value={formData.sortOrder}
            onChange={updateField}
            min="0"
            step="1"
          />
        </label>

        {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}

        <footer className="inventory-form__footer">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="inventory-form__primary" type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : category ? "Save changes" : "Add Category"}
          </button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default AddCategoryModal;
````

### `frontend/src/components/CategoryTable.css`

````css
/* Category table column sizing. */
.category-table th:nth-child(2) {
  min-width: 180px;
}

.category-table th:nth-child(3) {
  min-width: 280px;
}

.category-table th:nth-child(4),
.category-table th:nth-child(5) {
  min-width: 110px;
}

/* Category status badge. */
.category-table__status {
  display: inline-flex;
  align-items: center;

  padding: 5px 9px;

  border: 1px solid;
  border-radius: 7px;

  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

/* Active category status. */
.category-table__status--active {
  color: #14835a;
  border-color: #54c99b;
  background: rgba(34, 164, 116, 0.1);
}

/* Uncategorized or incomplete category status. */
.category-table__status--needs-attention {
  color: #c77700;
  border-color: #f7b84b;
  background: rgba(245, 158, 11, 0.1);
}

/* Prevent the expanded row from receiving a hover colour. */
.orders-table tbody .category-table__details-row:hover {
  background: transparent;
}

/* Table cell containing the expanded product list. */
.category-table__details-cell {
  padding: 0 10px 12px !important;
  background: var(--color-surface-soft);
}

/* Expanded category container. */
.category-table__products {
  padding: 14px;

  border: 1px solid var(--color-border);
  border-radius: 10px;

  background: var(--color-surface);

  animation: category-products-open 220ms ease-out;
}

.category-table__products h3 {
  margin: 0 0 12px;
  font-size: 13px;
}

/* Allow the nested product table to scroll on small screens. */
.category-table__products-scroll {
  overflow-x: auto;
}

/* Nested products table. */
.category-table__products-table {
  width: 100%;
  min-width: 750px;

  border-collapse: collapse;
}

/* Nested table headings and cells. */
.category-table__products-table th,
.category-table__products-table td {
  padding: 10px 12px;

  border-bottom: 1px solid var(--color-border);

  text-align: left;
  white-space: nowrap;
}

.category-table__products-table th {
  color: var(--color-muted);

  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.category-table__products-table td {
  color: var(--color-text);
  font-size: 12px;
}

/* Remove the final unnecessary border. */
.category-table__products-table tbody tr:last-child td {
  border-bottom: 0;
}

/* Product image frame. */
.category-table__product-image {
  display: grid;
  place-items: center;

  width: 44px;
  height: 44px;

  overflow: hidden;

  border: 1px solid var(--color-border);
  border-radius: 8px;

  color: var(--color-accent);
  background: var(--color-surface-soft);
}

/* Keep the complete product visible inside its frame. */
.category-table__product-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Expanded-row opening animation. */
@keyframes category-products-open {
  from {
    opacity: 0;
    transform: translateY(-7px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Dark-theme adjustments. */
html[data-theme="dark"] .category-table__details-cell {
  background: rgba(7, 17, 28, 0.72);
}

html[data-theme="dark"] .category-table__products {
  border-color: #2b4055;

  background: linear-gradient(
    145deg,
    rgba(18, 34, 51, 0.98),
    rgba(10, 22, 35, 0.98)
  );
}

html[data-theme="dark"] .category-table__status--active {
  color: #5cdaa8;
}

html[data-theme="dark"]
  .category-table__status--needs-attention {
  color: #ffbd4a;
}

/* Remove animations for users who disable motion. */
@media (prefers-reduced-motion: reduce) {
  .category-table__products {
    animation: none;
  }
}
````

### `frontend/src/components/CategoryTable.jsx`

````jsx
import { Fragment, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Pencil,
  Trash2,
  Package,
} from "lucide-react";

import { getProductStock } from "../utils/inventory";
import ActionMenu from "./ActionMenu";

import "./OrderTable.css";
import "./CategoryTable.css";

// Display the product's first image.
// A package icon appears when the image cannot be loaded.
function CategoryProductImage({ product }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageSource = product.images?.[0];

  return (
    <span className="category-table__product-image">
      {imageSource && !imageFailed ? (
        <img
          src={imageSource}
          alt={product.name}
          onError={() => setImageFailed(true)}
        />
      ) : (
        <Package size={21} aria-hidden="true" />
      )}
    </span>
  );
}

// Find all products belonging to one category.
function getProductsForCategory(category, products) {
  if (category.name === "Uncategorized") {
    return products.filter(
      (product) => !product.categoryId && !product.category,
    );
  }

  return products.filter(
    (product) =>
      product.categoryId === category.id ||
      product.category === category.name,
  );
}

function CategoryTable({ categories: categoryRecords = [], products = [], onEditCategory, onRemoveCategory }) {
  // Only one category is expanded at a time.
  const [expandedCategoryId, setExpandedCategoryId] =
    useState("category-footwear");

  // Add product count, product records and total stock to every category.
  const categories = categoryRecords.map((category) => {
    const categoryProducts = getProductsForCategory(category, products);

    const totalStock = categoryProducts.reduce(
      (stockTotal, product) =>
        stockTotal + getProductStock(product),
      0,
    );

    return {
      ...category,
      products: categoryProducts,
      totalStock,
    };
  });

  // Open the selected category or close it when clicked again.
  function toggleCategory(categoryId) {
    setExpandedCategoryId((currentCategoryId) =>
      currentCategoryId === categoryId ? null : categoryId,
    );
  }

  return (
    <section
      className="orders-table-section category-table-section"
      aria-label="Product categories"
    >
      <div className="orders-table__scroll">
        <table className="orders-table category-table">
          <thead>
            <tr>
              <th className="orders-table__expand-column"></th>
              <th>Category</th>
              <th>Description</th>
              <th>Products</th>
              <th>Total Stock</th>
              <th>Status</th>
              <th className="orders-table__actions-heading">
                Actions
              </th>
            </tr>
          </thead>

          <tbody>
            {categories.map((category) => {
              const isExpanded =
                expandedCategoryId === category.id;

              return (
                <Fragment key={category.id}>
                  {/* Main category row */}
                  <tr>
                    <td>
                      <button
                        className="orders-table__expand-button"
                        type="button"
                        onClick={() => toggleCategory(category.id)}
                        aria-expanded={isExpanded}
                        aria-label={
                          isExpanded
                            ? `Collapse ${category.name}`
                            : `Expand ${category.name}`
                        }
                      >
                        {isExpanded ? (
                          <ChevronDown
                            size={18}
                            aria-hidden="true"
                          />
                        ) : (
                          <ChevronRight
                            size={18}
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    </td>

                    <td>
                      <strong>{category.name}</strong>
                    </td>

                    <td>{category.description}</td>

                    <td>
                      <strong>{category.products.length}</strong>
                    </td>

                    <td>
                      <strong>{category.totalStock}</strong>
                    </td>

                    <td>
                      <span
                        className={`category-table__status category-table__status--${category.status}`}
                      >
                        {category.status === "active"
                          ? "Active"
                          : "Needs attention"}
                      </span>
                    </td>

                    <td>
                      <ActionMenu label={`More actions for ${category.name}`} items={[
                        { label: "Edit category", icon: <Pencil size={16} />, onClick: () => onEditCategory?.(category) },
                        { label: "Remove category", icon: <Trash2 size={16} />, danger: true, onClick: () => onRemoveCategory?.(category) },
                      ]} />
                    </td>
                  </tr>

                  {/* Products belonging to the expanded category */}
                  {isExpanded && (
                    <tr className="category-table__details-row">
                      <td
                        className="category-table__details-cell"
                        colSpan={7}
                      >
                        <div className="category-table__products">
                          <h3>
                            Products in {category.name}
                          </h3>

                          {category.products.length === 0 ? (
                            <p>
                              No products belong to this category.
                            </p>
                          ) : (
                            <div className="category-table__products-scroll">
                              <table className="category-table__products-table">
                                <thead>
                                  <tr>
                                    <th>Product Image</th>
                                    <th>Product Name</th>
                                    <th>SKU ID</th>
                                    <th>Barcode</th>
                                    <th>Available Stock</th>
                                  </tr>
                                </thead>

                                <tbody>
                                  {category.products.map((product) => (
                                    <tr key={product.id}>
                                      <td>
                                        <CategoryProductImage
                                          product={product}
                                        />
                                      </td>

                                      <td>
                                        <strong>{product.name}</strong>
                                      </td>

                                      <td>
                                        {product.hasSizes
                                          ? "Multiple SKUs"
                                          : product.sku}
                                      </td>

                                      <td>
                                        {product.hasSizes
                                          ? "Multiple barcodes"
                                          : product.barcode}
                                      </td>

                                      <td>
                                        <strong>
                                          {getProductStock(product)}
                                        </strong>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <footer className="orders-table__footer">
        <span>
          Showing 1 to {categories.length} of{" "}
          {categories.length} categories
        </span>
      </footer>
    </section>
  );
}

export default CategoryTable;
````

### `frontend/src/data/sampleCategories.js`

````javascript
// Temporary category records used until Firestore is connected.
const sampleCategories = [
  {
    id: "category-footwear",
    name: "Footwear",
    description: "Shoes, sandals and other footwear.",
    status: "active",
  },
  {
    id: "category-audio",
    name: "Audio",
    description: "Earbuds, headphones and speakers.",
    status: "active",
  },
  {
    id: "category-wearables",
    name: "Wearables",
    description: "Smart watches and fitness devices.",
    status: "active",
  },
  {
    id: "category-bags",
    name: "Bags",
    description: "Handbags, backpacks and travel bags.",
    status: "active",
  },
  {
    id: "category-appliances",
    name: "Appliances",
    description: "Small home and kitchen appliances.",
    status: "active",
  },
  {
    id: "category-uncategorized",
    name: "Uncategorized",
    description: "Products waiting for a category.",
    status: "needs-attention",
  },
];

export default sampleCategories;
````

### `frontend/src/services/categoryService.js`

````javascript
import { apiRequest } from "./apiClient";

export function getCategories(businessId) {
  return apiRequest(`/businesses/${businessId}/categories`);
}

export function createCategory(businessId, categoryData) {
  return apiRequest(`/businesses/${businessId}/categories`, {
    method: "POST",
    body: categoryData,
  });
}

export function updateCategory(businessId, categoryId, changes) {
  return apiRequest(
    `/businesses/${businessId}/categories/${categoryId}`,
    {
      method: "PATCH",
      body: changes,
    },
  );
}

export function removeCategory(businessId, categoryId) {
  return apiRequest(`/businesses/${businessId}/categories/${categoryId}`, {
    method: "DELETE",
  });
}
````

## Feature 8 source — Products and variants

Files in this feature: 7

### `backend/app/api/products.py`

````python
from flask import Blueprint, current_app, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.product_service import (
    adjust_variant_stock,
    create_product,
    get_product,
    list_products,
    update_product,
)
from app.services.media_service import upload_product_media, upload_variant_image
from app.services.ai_service import generate_product_description


products_blueprint = Blueprint("products", __name__, url_prefix="/api/v1")


@products_blueprint.get("/businesses/<business_id>/products")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_products(business_id):
    products = list_products(
        get_firestore_client(),
        business_id,
        category_id=request.args.get("categoryId"),
        status=request.args.get("status"),
    )
    return jsonify({"products": products})


@products_blueprint.post("/businesses/<business_id>/products")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_product(business_id):
    payload = get_json_object()

    product = create_product(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        payload,
    )
    return jsonify({"product": product}), 201


@products_blueprint.post("/businesses/<business_id>/products/generate-description")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def generate_description(business_id):
    payload = get_json_object()
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"error": {"code": "validation_error", "message": "Enter a product name first."}}), 422

    description = generate_product_description(payload)
    generated_by = "ai"
    if not description:
        description = (
            f"{name} is available from this seller. Add the product's key features, "
            "materials, compatibility, usage details and important limitations here "
            "so customers can make an informed purchase."
        )
        generated_by = "template"

    return jsonify({"description": description, "generatedBy": generated_by})


@products_blueprint.get("/businesses/<business_id>/products/<product_id>")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_product_by_id(business_id, product_id):
    product = get_product(get_firestore_client(), business_id, product_id)
    return jsonify({"product": product})


@products_blueprint.patch("/businesses/<business_id>/products/<product_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def edit_product(business_id, product_id):
    product = update_product(
        get_firestore_client(),
        business_id,
        product_id,
        get_json_object(),
    )
    return jsonify({"product": product})


@products_blueprint.delete("/businesses/<business_id>/products/<product_id>")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def remove_product(business_id, product_id):
    product = update_product(
        get_firestore_client(),
        business_id,
        product_id,
        {"status": "archived"},
    )
    return jsonify({"product": product})


@products_blueprint.post(
    "/businesses/<business_id>/products/<product_id>/variants/<variant_id>/adjust-stock",
)
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def adjust_stock(business_id, product_id, variant_id):
    product = adjust_variant_stock(
        get_firestore_client(),
        business_id,
        product_id,
        variant_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"product": product})


@products_blueprint.post(
    "/businesses/<business_id>/products/<product_id>/media",
)
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_product_media(business_id, product_id):
    product = upload_product_media(
        get_firestore_client(),
        business_id,
        product_id,
        g.current_user["uid"],
        request.files.getlist("files"),
        cloudinary_config={
            "cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"),
            "api_key": current_app.config.get("CLOUDINARY_API_KEY"),
            "api_secret": current_app.config.get("CLOUDINARY_API_SECRET"),
        },
    )
    return jsonify({"product": product}), 201


@products_blueprint.post("/businesses/<business_id>/products/<product_id>/variants/<variant_id>/image")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager", permission="inventory:manage")
def add_variant_image(business_id, product_id, variant_id):
    upload = request.files.get("file")
    if upload is None:
        return jsonify({"error": {"code": "media_required", "message": "Choose a variant image."}}), 422
    product = upload_variant_image(
        get_firestore_client(), business_id, product_id, variant_id, upload,
        cloudinary_config={"cloud_name": current_app.config.get("CLOUDINARY_CLOUD_NAME"), "api_key": current_app.config.get("CLOUDINARY_API_KEY"), "api_secret": current_app.config.get("CLOUDINARY_API_SECRET")},
    )
    return jsonify({"product": product}), 201
````

### `backend/app/services/product_service.py`

````python
from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.business_service import generate_short_code
from app.services.numbers import (
    kilograms_to_grams,
    integer_value,
    money_to_minor_units,
    non_negative_integer,
)
from app.services.text import optional_text, required_text, slugify


def stock_status(stock, threshold):
    if stock == 0:
        return "out-of-stock"
    if stock <= threshold:
        return "low-stock"
    return "in-stock"


def normalize_registry_key(value):
    return value.strip().upper()


def validate_product(payload):
    """Validate an Add Product request and return normalized server values."""
    try:
        name = required_text(payload.get("name"), "Product name", 160)
        colour_name = optional_text(payload.get("colourName"), 80)
        product_type = optional_text(payload.get("productType"), 100)
        product_size = optional_text(payload.get("productSize"), 80)
        brand = optional_text(payload.get("brand"), 100)
        supplier_id = optional_text(payload.get("supplierId"), 120)
        description = optional_text(payload.get("description"), 4000)
        ai_description = optional_text(payload.get("aiDescription"), 4000)
        sku_prefix = optional_text(payload.get("skuPrefix"), 60).upper()
        colour_hex = optional_text(payload.get("colourHex"), 20)
        category_id = required_text(payload.get("categoryId"), "Category", 120)
        cost_price_minor = money_to_minor_units(
            payload.get("costPrice"),
            "Cost price",
        )
        selling_price_minor = money_to_minor_units(
            payload.get("sellingPrice"),
            "Selling price",
            allow_zero=False,
        )
        compare_at_price_minor = money_to_minor_units(
            payload.get("compareAtPrice", 0),
            "Compare-at price",
        )
        weight_grams = kilograms_to_grams(payload.get("weightKg"))
        low_stock_threshold = non_negative_integer(
            payload.get("lowStockThreshold", 5),
            "Low-stock threshold",
        )
        warranty_period_months = non_negative_integer(
            payload.get("warrantyPeriodMonths", 0),
            "Warranty period",
        )
        warranty_notes = optional_text(payload.get("warrantyNotes"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    has_sizes = payload.get("hasSizes") is True
    raw_variants = payload.get("variants")

    if not isinstance(raw_variants, list) or not raw_variants:
        raise ApiError(
            "validation_error",
            "At least one stock row is required.",
            422,
        )

    if len(raw_variants) > 100:
        raise ApiError(
            "too_many_variants",
            "A product can contain no more than 100 size rows.",
            422,
        )

    variants = []
    seen_sizes = set()
    seen_skus = set()
    seen_barcodes = set()

    for index, raw_variant in enumerate(raw_variants, start=1):
        try:
            size = optional_text(raw_variant.get("size"), 40)
            sku = required_text(raw_variant.get("sku"), f"SKU in row {index}", 80).upper()
            barcode = required_text(
                raw_variant.get("barcode"),
                f"Barcode in row {index}",
                80,
            )
            initial_stock = non_negative_integer(
                raw_variant.get("stock", 0),
                f"Stock in row {index}",
            )
            variant_cost_price_minor = money_to_minor_units(
                raw_variant.get("costPrice", payload.get("costPrice")),
                f"Cost price in row {index}",
            )
            variant_selling_price_minor = money_to_minor_units(
                raw_variant.get("sellingPrice", payload.get("sellingPrice")),
                f"Selling price in row {index}",
                allow_zero=False,
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

        if has_sizes and not size:
            raise ApiError(
                "validation_error",
                f"Size is required in row {index}.",
                422,
            )

        if not has_sizes and len(raw_variants) != 1:
            raise ApiError(
                "validation_error",
                "A product without sizes must have exactly one stock row.",
                422,
            )

        normalized_size = size.casefold()
        normalized_sku = normalize_registry_key(sku)
        normalized_barcode = normalize_registry_key(barcode)

        if has_sizes and normalized_size in seen_sizes:
            raise ApiError("duplicate_size", f"Size {size} is repeated.", 422)
        if normalized_sku in seen_skus:
            raise ApiError("duplicate_sku", f"SKU {sku} is repeated.", 422)
        if normalized_barcode in seen_barcodes:
            raise ApiError(
                "duplicate_barcode",
                f"Barcode {barcode} is repeated.",
                422,
            )

        seen_sizes.add(normalized_size)
        seen_skus.add(normalized_sku)
        seen_barcodes.add(normalized_barcode)
        variants.append(
            {
                "size": size,
                "sku": sku,
                "barcode": barcode,
                "initialStock": initial_stock,
                "costPriceMinor": variant_cost_price_minor,
                "sellingPriceMinor": variant_selling_price_minor,
            },
        )

    raw_media = payload.get("media", [])

    if not isinstance(raw_media, list):
        raise ApiError("validation_error", "Media must be a list.", 422)

    media = []

    for media_item in raw_media[:12]:
        if not isinstance(media_item, dict):
            raise ApiError(
                "validation_error",
                "Each media item must be an object.",
                422,
            )

        try:
            path = optional_text(media_item.get("path"), 500)
            url = optional_text(media_item.get("url"), 2000)
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error
        media_type = media_item.get("type", "image")

        if media_type not in {"image", "video"}:
            raise ApiError(
                "validation_error",
                "Media type must be image or video.",
                422,
            )

        if not path and not url:
            raise ApiError(
                "validation_error",
                "Each media item requires a storage path or URL.",
                422,
            )

        media.append({"path": path, "url": url, "type": media_type})

    return {
        "name": name,
        "colourName": colour_name,
        "colourHex": colour_hex,
        "productType": product_type,
        "productSize": product_size,
        "categoryId": category_id,
        "brand": brand,
        "supplierId": supplier_id,
        "description": description,
        "aiDescription": ai_description,
        "taxCategory": optional_text(payload.get("taxCategory"), 60) or "standard",
        "hasSizes": has_sizes,
        "skuPrefix": sku_prefix,
        "costPriceMinor": cost_price_minor,
        "sellingPriceMinor": selling_price_minor,
        "compareAtPriceMinor": compare_at_price_minor,
        "weightGrams": weight_grams,
        "lowStockThreshold": low_stock_threshold,
        "warrantyPeriodMonths": warranty_period_months,
        "warrantyNotes": warranty_notes,
        "media": media,
        "variants": variants,
    }


def list_products(database, business_id, category_id=None, status=None):
    query = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
    )

    if category_id:
        query = query.where(filter=FieldFilter("categoryId", "==", category_id))
    if status:
        query = query.where(filter=FieldFilter("status", "==", status))

    return [serialize_snapshot(snapshot) for snapshot in query.limit(200).stream()]


def get_product(database, business_id, product_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
        .document(product_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("product_not_found", "Product not found.", 404)

    return serialize_snapshot(snapshot)


def create_product(database, business_id, uid, payload):
    product = validate_product(payload)
    business_reference = database.collection("businesses").document(business_id)
    category_reference = business_reference.collection("categories").document(
        product["categoryId"],
    )
    category_snapshot = category_reference.get()

    if not category_snapshot.exists or category_snapshot.to_dict().get("status") != "active":
        raise ApiError(
            "invalid_category",
            "Choose an active product category.",
            422,
        )

    product_reference = business_reference.collection("products").document()
    variant_collection = business_reference.collection("productVariants")
    inventory_collection = business_reference.collection("inventoryTransactions")
    variant_entries = []
    registry_references = []

    for variant in product["variants"]:
        variant_reference = variant_collection.document()
        sku_registry = business_reference.collection("skuRegistry").document(
            normalize_registry_key(variant["sku"]),
        )
        barcode_registry = business_reference.collection("barcodeRegistry").document(
            normalize_registry_key(variant["barcode"]),
        )
        registry_references.extend(
            [
                (sku_registry, "sku", variant["sku"]),
                (barcode_registry, "barcode", variant["barcode"]),
            ],
        )
        variant_entries.append((variant_reference, variant))

    short_code = generate_short_code()
    short_link_reference = database.collection("shortLinks").document(short_code)
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        for registry_reference, registry_type, registry_value in registry_references:
            if registry_reference.get(transaction=current_transaction).exists:
                raise ApiError(
                    f"{registry_type}_already_exists",
                    f"{registry_type.upper()} {registry_value} is already in use.",
                    409,
                )

        if short_link_reference.get(transaction=current_transaction).exists:
            raise ApiError(
                "short_code_conflict",
                "A public code conflict occurred. Please try again.",
                409,
            )

        timestamp = firestore.SERVER_TIMESTAMP
        total_stock = sum(item["initialStock"] for item in product["variants"])
        overall_status = stock_status(total_stock, product["lowStockThreshold"])
        variant_summaries = []

        for variant_reference, variant in variant_entries:
            initial_stock = variant["initialStock"]
            variant_status = stock_status(initial_stock, product["lowStockThreshold"])
            variant_data = {
                "productId": product_reference.id,
                "size": variant["size"],
                "sku": variant["sku"],
                "barcode": variant["barcode"],
                "costPriceMinor": variant["costPriceMinor"],
                "sellingPriceMinor": variant["sellingPriceMinor"],
                "weightGrams": product["weightGrams"],
                "stockOnHand": initial_stock,
                "stockReserved": 0,
                "stockAvailable": initial_stock,
                "stockStatus": variant_status,
                "status": "active",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
            current_transaction.set(variant_reference, variant_data)
            variant_summaries.append(
                {
                    "id": variant_reference.id,
                    "size": variant["size"],
                    "sku": variant["sku"],
                    "barcode": variant["barcode"],
                    "stockOnHand": initial_stock,
                    "stockReserved": 0,
                    "stockAvailable": initial_stock,
                    "stockStatus": variant_status,
                    "costPriceMinor": variant["costPriceMinor"],
                    "sellingPriceMinor": variant["sellingPriceMinor"],
                    "imageUrl": "",
                },
            )

            if initial_stock > 0:
                current_transaction.set(
                    inventory_collection.document(),
                    {
                        "productId": product_reference.id,
                        "variantId": variant_reference.id,
                        "type": "receive",
                        "quantity": initial_stock,
                        "stockBefore": 0,
                        "stockAfter": initial_stock,
                        "orderId": None,
                        "reference": "Initial product stock",
                        "reason": "Product created",
                        "performedBy": uid,
                        "createdAt": timestamp,
                    },
                )

        category = category_snapshot.to_dict()
        current_transaction.set(
            product_reference,
            {
                "name": product["name"],
                "slug": slugify(product["name"]) or product_reference.id.lower(),
                "colourName": product["colourName"],
                "colourHex": product["colourHex"],
                "productType": product["productType"],
                "productSize": product["productSize"],
                "categoryId": product["categoryId"],
                "categoryName": category.get("name", ""),
                "brand": product["brand"],
                "supplierId": product["supplierId"],
                "description": product["description"],
                "aiDescription": product["aiDescription"],
                "taxCategory": product["taxCategory"],
                "hasSizes": product["hasSizes"],
                "skuPrefix": product["skuPrefix"],
                "costPriceMinor": product["costPriceMinor"],
                "sellingPriceMinor": product["sellingPriceMinor"],
                "compareAtPriceMinor": product["compareAtPriceMinor"],
                "weightGrams": product["weightGrams"],
                "lowStockThreshold": product["lowStockThreshold"],
                "warrantyPeriodMonths": product["warrantyPeriodMonths"],
                "warrantyNotes": product["warrantyNotes"],
                "totalStock": total_stock,
                "reservedStock": 0,
                "availableStock": total_stock,
                "stockStatus": overall_status,
                "approvedReviewCount": 0,
                "media": product["media"],
                "primaryMediaPath": (
                    product["media"][0].get("path", "") if product["media"] else ""
                ),
                "variantSummaries": variant_summaries,
                "status": "active",
                "shortCode": short_code,
                "createdBy": uid,
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )

        for registry_reference, registry_type, registry_value in registry_references:
            current_transaction.set(
                registry_reference,
                {
                    "type": registry_type,
                    "value": registry_value,
                    "productId": product_reference.id,
                    "createdAt": timestamp,
                },
            )

        current_transaction.set(
            short_link_reference,
            {
                "type": "product",
                "businessId": business_id,
                "productId": product_reference.id,
                "status": "active",
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return get_product(database, business_id, product_reference.id)


def update_product(database, business_id, product_id, payload):
    """Update shared product information without changing SKU or stock history."""
    business_reference = database.collection("businesses").document(business_id)
    product_reference = business_reference.collection("products").document(product_id)
    product_snapshot = product_reference.get()

    if not product_snapshot.exists:
        raise ApiError("product_not_found", "Product not found.", 404)

    current_product = product_snapshot.to_dict()
    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    try:
        if "name" in payload:
            changes["name"] = required_text(payload.get("name"), "Product name", 160)
            changes["slug"] = slugify(changes["name"]) or product_id.lower()
        if "colourName" in payload:
            changes["colourName"] = optional_text(payload.get("colourName"), 80)
        if "colourHex" in payload:
            changes["colourHex"] = optional_text(payload.get("colourHex"), 20)
        if "productType" in payload:
            changes["productType"] = optional_text(payload.get("productType"), 100)
        if "productSize" in payload:
            changes["productSize"] = optional_text(payload.get("productSize"), 80)
        if "brand" in payload:
            changes["brand"] = optional_text(payload.get("brand"), 100)
        if "supplierId" in payload:
            changes["supplierId"] = optional_text(payload.get("supplierId"), 120)
        if "description" in payload:
            changes["description"] = optional_text(payload.get("description"), 4000)
        if "aiDescription" in payload:
            changes["aiDescription"] = optional_text(payload.get("aiDescription"), 4000)
        if "taxCategory" in payload:
            changes["taxCategory"] = optional_text(payload.get("taxCategory"), 60)
        if "costPrice" in payload:
            changes["costPriceMinor"] = money_to_minor_units(
                payload.get("costPrice"),
                "Cost price",
            )
        if "sellingPrice" in payload:
            changes["sellingPriceMinor"] = money_to_minor_units(
                payload.get("sellingPrice"),
                "Selling price",
                allow_zero=False,
            )
        if "compareAtPrice" in payload:
            changes["compareAtPriceMinor"] = money_to_minor_units(
                payload.get("compareAtPrice"),
                "Compare-at price",
            )
        if "weightKg" in payload:
            changes["weightGrams"] = kilograms_to_grams(payload.get("weightKg"))
        if "lowStockThreshold" in payload:
            changes["lowStockThreshold"] = non_negative_integer(
                payload.get("lowStockThreshold"),
                "Low-stock threshold",
            )
        if "warrantyPeriodMonths" in payload:
            changes["warrantyPeriodMonths"] = non_negative_integer(payload.get("warrantyPeriodMonths"), "Warranty period")
        if "warrantyNotes" in payload:
            changes["warrantyNotes"] = optional_text(payload.get("warrantyNotes"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if "status" in payload:
        if payload.get("status") not in {"active", "archived", "draft"}:
            raise ApiError(
                "validation_error",
                "Product status must be active, draft or archived.",
                422,
            )
        changes["status"] = payload["status"]

    if "categoryId" in payload:
        try:
            category_id = required_text(payload.get("categoryId"), "Category", 120)
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error
        category_snapshot = business_reference.collection("categories").document(
            category_id,
        ).get()

        if (
            not category_snapshot.exists
            or category_snapshot.to_dict().get("status") != "active"
        ):
            raise ApiError("invalid_category", "Choose an active category.", 422)

        changes["categoryId"] = category_id
        changes["categoryName"] = category_snapshot.to_dict().get("name", "")

    variants = list(
        business_reference.collection("productVariants")
        .where(filter=FieldFilter("productId", "==", product_id))
        .stream(),
    )
    batch = database.batch()

    if "variants" in payload:
        raw_variants = payload.get("variants")
        if not isinstance(raw_variants, list) or not raw_variants:
            raise ApiError("validation_error", "At least one variant is required.", 422)
        existing_by_id = {snapshot.id: snapshot for snapshot in variants}
        retained_ids = set()
        seen_skus = set()
        seen_barcodes = set()
        summaries = []
        total_stock = 0
        total_reserved = 0
        for index, raw_variant in enumerate(raw_variants, start=1):
            try:
                variant_id = optional_text(raw_variant.get("id"), 120)
                size = optional_text(raw_variant.get("size"), 40)
                sku = required_text(raw_variant.get("sku"), f"SKU in row {index}", 80).upper()
                barcode = required_text(raw_variant.get("barcode"), f"Barcode in row {index}", 80)
                stock_on_hand = non_negative_integer(raw_variant.get("stock", 0), f"Stock in row {index}")
                cost_minor = money_to_minor_units(raw_variant.get("costPrice", payload.get("costPrice")), f"Cost price in row {index}")
                selling_minor = money_to_minor_units(raw_variant.get("sellingPrice", payload.get("sellingPrice")), f"Selling price in row {index}", allow_zero=False)
            except ValueError as error:
                raise ApiError("validation_error", str(error), 422) from error
            normalized_sku = normalize_registry_key(sku)
            normalized_barcode = normalize_registry_key(barcode)
            if normalized_sku in seen_skus or normalized_barcode in seen_barcodes:
                raise ApiError("duplicate_variant_identifier", "Variant SKUs and barcodes must be unique.", 422)
            seen_skus.add(normalized_sku)
            seen_barcodes.add(normalized_barcode)

            snapshot = existing_by_id.get(variant_id)
            if snapshot:
                current = snapshot.to_dict()
                reserved = current.get("stockReserved", 0)
                if stock_on_hand < reserved:
                    raise ApiError("insufficient_adjustable_stock", "Variant stock cannot be below reserved stock.", 409)
                reference = snapshot.reference
                retained_ids.add(snapshot.id)
                image_url = current.get("imageUrl", "")
                created_at = current.get("createdAt")
            else:
                current = {}
                reserved = 0
                reference = business_reference.collection("productVariants").document()
                variant_id = reference.id
                image_url = raw_variant.get("imageUrl", "")
                created_at = firestore.SERVER_TIMESTAMP
            sku_registry = business_reference.collection("skuRegistry").document(normalize_registry_key(sku))
            barcode_registry = business_reference.collection("barcodeRegistry").document(normalize_registry_key(barcode))
            for registry, registry_type, value in ((sku_registry, "sku", sku), (barcode_registry, "barcode", barcode)):
                registry_snapshot = registry.get()
                if registry_snapshot.exists and registry_snapshot.to_dict().get("productId") != product_id:
                    raise ApiError(f"{registry_type}_already_exists", f"{registry_type.upper()} {value} is already in use.", 409)
                batch.set(registry, {"type": registry_type, "value": value, "productId": product_id, "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
            if current.get("sku") and normalize_registry_key(current["sku"]) != normalize_registry_key(sku):
                batch.delete(business_reference.collection("skuRegistry").document(normalize_registry_key(current["sku"])))
            if current.get("barcode") and normalize_registry_key(current["barcode"]) != normalize_registry_key(barcode):
                batch.delete(business_reference.collection("barcodeRegistry").document(normalize_registry_key(current["barcode"])))
            available = stock_on_hand - reserved
            status = stock_status(available, changes.get("lowStockThreshold", current_product.get("lowStockThreshold", 5)))
            variant_data = {"productId": product_id, "size": size, "sku": sku, "barcode": barcode, "costPriceMinor": cost_minor, "sellingPriceMinor": selling_minor, "weightGrams": changes.get("weightGrams", current_product.get("weightGrams", 0)), "stockOnHand": stock_on_hand, "stockReserved": reserved, "stockAvailable": available, "stockStatus": status, "status": "active", "imageUrl": image_url, "createdAt": created_at, "updatedAt": firestore.SERVER_TIMESTAMP}
            batch.set(reference, variant_data, merge=True)
            summaries.append({"id": variant_id, "size": size, "sku": sku, "barcode": barcode, "stockOnHand": stock_on_hand, "stockReserved": reserved, "stockAvailable": available, "stockStatus": status, "costPriceMinor": cost_minor, "sellingPriceMinor": selling_minor, "imageUrl": image_url})
            total_stock += stock_on_hand
            total_reserved += reserved

        for variant_id, snapshot in existing_by_id.items():
            if variant_id not in retained_ids and snapshot.to_dict().get("stockReserved", 0) > 0:
                raise ApiError("variant_in_use", "A variant reserved by an order cannot be removed.", 409)
            if variant_id not in retained_ids:
                old = snapshot.to_dict()
                if old.get("sku"):
                    batch.delete(business_reference.collection("skuRegistry").document(normalize_registry_key(old["sku"])))
                if old.get("barcode"):
                    batch.delete(business_reference.collection("barcodeRegistry").document(normalize_registry_key(old["barcode"])))
                batch.delete(snapshot.reference)
        available_stock = total_stock - total_reserved
        changes.update({"hasSizes": payload.get("hasSizes") is True, "variantSummaries": summaries, "totalStock": total_stock, "reservedStock": total_reserved, "availableStock": available_stock, "stockStatus": stock_status(available_stock, changes.get("lowStockThreshold", current_product.get("lowStockThreshold", 5)))})
    shared_variant_changes = {
        field: changes[field]
        for field in ("costPriceMinor", "sellingPriceMinor", "weightGrams")
        if field in changes and (field == "weightGrams" or "variants" not in payload)
    }

    if "lowStockThreshold" in changes:
        threshold = changes["lowStockThreshold"]
        changes["stockStatus"] = stock_status(
            current_product.get("availableStock", 0),
            threshold,
        )
        if "variants" not in payload:
            changes["variantSummaries"] = [
            {
                **summary,
                "stockStatus": stock_status(
                    summary.get("stockAvailable", 0),
                    threshold,
                ),
            }
            for summary in current_product.get("variantSummaries", [])
            ]

    batch.update(product_reference, changes)

    if shared_variant_changes or "lowStockThreshold" in changes:
        timestamp = firestore.SERVER_TIMESTAMP

        for variant in variants:
            variant_changes = {
                **shared_variant_changes,
                "updatedAt": timestamp,
            }

            if "lowStockThreshold" in changes:
                variant_changes["stockStatus"] = stock_status(
                    variant.to_dict().get("stockAvailable", 0),
                    changes["lowStockThreshold"],
                )

            batch.update(variant.reference, variant_changes)

    batch.commit()
    return get_product(database, business_id, product_id)


def adjust_variant_stock(
    database,
    business_id,
    product_id,
    variant_id,
    uid,
    payload,
):
    """Adjust one variant's stock and record the complete audit transaction."""
    try:
        quantity_change = integer_value(payload.get("quantityChange"), "Quantity change")
        reason = required_text(payload.get("reason"), "Adjustment reason", 300)
        reference = optional_text(payload.get("reference"), 200)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if quantity_change == 0:
        raise ApiError(
            "validation_error",
            "Quantity change cannot be zero.",
            422,
        )

    business_reference = database.collection("businesses").document(business_id)
    product_reference = business_reference.collection("products").document(product_id)
    variant_reference = business_reference.collection("productVariants").document(
        variant_id,
    )
    transaction_reference = business_reference.collection(
        "inventoryTransactions",
    ).document()
    transaction = database.transaction()

    @google_firestore.transactional
    def adjust_in_transaction(current_transaction):
        product_snapshot = product_reference.get(transaction=current_transaction)
        variant_snapshot = variant_reference.get(transaction=current_transaction)

        if not product_snapshot.exists:
            raise ApiError("product_not_found", "Product not found.", 404)
        if not variant_snapshot.exists:
            raise ApiError("variant_not_found", "Product size/SKU not found.", 404)

        product = product_snapshot.to_dict()
        variant = variant_snapshot.to_dict()

        if variant.get("productId") != product_id:
            raise ApiError("variant_not_found", "Product size/SKU not found.", 404)

        stock_before = variant.get("stockOnHand", 0)
        stock_after = stock_before + quantity_change
        reserved = variant.get("stockReserved", 0)

        if stock_after < reserved:
            raise ApiError(
                "insufficient_adjustable_stock",
                "Stock cannot be reduced below the quantity reserved by orders.",
                409,
            )

        available_after = stock_after - reserved
        threshold = product.get("lowStockThreshold", 0)
        new_variant_status = stock_status(available_after, threshold)
        product_stock_after = product.get("totalStock", 0) + quantity_change
        product_available_after = product.get("availableStock", 0) + quantity_change
        summaries = []

        for summary in product.get("variantSummaries", []):
            if summary.get("id") == variant_id:
                summaries.append(
                    {
                        **summary,
                        "stockOnHand": stock_after,
                        "stockAvailable": available_after,
                        "stockStatus": new_variant_status,
                    },
                )
            else:
                summaries.append(summary)

        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.update(
            variant_reference,
            {
                "stockOnHand": stock_after,
                "stockAvailable": available_after,
                "stockStatus": new_variant_status,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            product_reference,
            {
                "totalStock": product_stock_after,
                "availableStock": product_available_after,
                "stockStatus": stock_status(product_available_after, threshold),
                "variantSummaries": summaries,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            transaction_reference,
            {
                "productId": product_id,
                "variantId": variant_id,
                "type": "adjust",
                "quantity": quantity_change,
                "stockBefore": stock_before,
                "stockAfter": stock_after,
                "orderId": None,
                "reference": reference,
                "reason": reason,
                "performedBy": uid,
                "createdAt": timestamp,
            },
        )

    adjust_in_transaction(transaction)
    return get_product(database, business_id, product_id)
````

### `frontend/src/components/AddProductModal.jsx`

````jsx
import { useEffect, useMemo, useState } from "react";
import { Image as ImageIcon, Plus, Trash2, Upload, WandSparkles } from "lucide-react";

import {
  createProduct,
  generateProductDescription,
  updateProduct,
  uploadProductMedia,
  uploadVariantImage,
} from "../services/productService";
import ModalShell from "./ModalShell";
import "./InventoryForm.css";

function randomCode(length = 5) {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({ length }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join("");
}

function skuPart(value, fallback = "ITEM") {
  const cleaned = String(value || "").toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return cleaned.slice(0, 12) || fallback;
}

function generateSku(name, option = "") {
  return [skuPart(name), option && skuPart(option), randomCode(4)].filter(Boolean).join("-");
}

function generateBarcode() {
  const body = Array.from({ length: 12 }, () => Math.floor(Math.random() * 10)).join("");
  const weightedTotal = [...body].reduce(
    (total, digit, index) => total + Number(digit) * (index % 2 === 0 ? 1 : 3),
    0,
  );
  return `${body}${(10 - (weightedTotal % 10)) % 10}`;
}

function newVariant(prices = {}, existing = {}) {
  return {
    id: existing.id || crypto.randomUUID(),
    size: existing.size || "",
    sku: existing.sku || "",
    barcode: existing.barcode || "",
    stock: String(existing.stock ?? 0),
    sellingPrice: String(existing.sellingPrice ?? prices.sellingPrice ?? ""),
    costPrice: String(existing.costPrice ?? prices.costPrice ?? ""),
    imageUrl: existing.imageUrl || "",
    imageFile: null,
  };
}

function initialFormData(product = null) {
  return {
    name: product?.name || "",
    colourName: product?.colourName || product?.colour || "",
    productSize: product?.productSize || "",
    categoryId: product?.categoryId || "",
    brand: product?.brand || "",
    warrantyPeriodMonths: String(product?.warrantyPeriodMonths ?? 0),
    baseSku: product?.sku || "",
    baseBarcode: product?.barcode || "",
    stock: String(product?.stock ?? 0),
    costPrice: String(product?.costPrice ?? ""),
    sellingPrice: String(product?.sellingPrice ?? ""),
    weightKg: String(product?.weightKg ?? ""),
    description: product?.description || "",
    hasSizes: Boolean(product?.hasSizes),
    variants: (product?.sizes || []).map((variant) => newVariant(product, variant)),
  };
}

function AddProductModal({ isOpen, businessId, categories, product = null, onClose, onCreated, onUpdated }) {
  const [formData, setFormData] = useState(initialFormData);
  const [mediaFiles, setMediaFiles] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData(initialFormData(product));
      setMediaFiles([]);
      setErrorMessage("");
    }
  }, [isOpen, product]);

  const activeCategories = categories.filter((category) => category.status === "active");
  const selectedCategory = activeCategories.find((category) => category.id === formData.categoryId);
  const previews = useMemo(
    () => mediaFiles.map((file) => ({ file, url: file.type.startsWith("image/") ? URL.createObjectURL(file) : null })),
    [mediaFiles],
  );

  useEffect(() => () => previews.forEach(({ url }) => url && URL.revokeObjectURL(url)), [previews]);

  function updateField(event) {
    const { name, value, type, checked } = event.target;
    setFormData((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  function updateVariant(id, field, value) {
    setFormData((current) => ({
      ...current,
      variants: current.variants.map((variant) => variant.id === id ? { ...variant, [field]: value } : variant),
    }));
  }

  function addVariant() {
    setFormData((current) => ({
      ...current,
      variants: [...current.variants, newVariant(current)],
    }));
  }

  function toggleVariants(event) {
    const checked = event.target.checked;
    setFormData((current) => ({
      ...current,
      hasSizes: checked,
      variants: checked && current.variants.length === 0 ? [newVariant(current)] : current.variants,
    }));
  }

  function fillBaseIdentifier(field) {
    setFormData((current) => ({
      ...current,
      [field]: field === "baseSku" ? generateSku(current.name, current.productSize) : generateBarcode(),
    }));
  }

  function fillVariantIdentifier(id, field) {
    setFormData((current) => ({
      ...current,
      variants: current.variants.map((variant) => variant.id === id ? {
        ...variant,
        [field]: field === "sku" ? generateSku(current.name, variant.size) : generateBarcode(),
      } : variant),
    }));
  }

  async function handleGenerateDescription() {
    if (!formData.name.trim()) {
      setErrorMessage("Enter the product name before generating a description.");
      return;
    }
    setErrorMessage("");
    setIsGenerating(true);
    try {
      const description = await generateProductDescription(businessId, {
        name: formData.name,
        brand: formData.brand,
        colourName: formData.colourName,
        productSize: formData.productSize,
        categoryName: selectedCategory?.name || "",
        warrantyPeriodMonths: Number(formData.warrantyPeriodMonths),
        weightKg: formData.weightKg,
        costPrice: formData.hasSizes ? undefined : formData.costPrice,
        sellingPrice: formData.hasSizes ? undefined : formData.sellingPrice,
        variants: formData.hasSizes ? formData.variants.map(({ size, sku, barcode, stock, costPrice, sellingPrice }) => ({ size, sku, barcode, stock, costPrice, sellingPrice })) : [],
      });
      setFormData((current) => ({ ...current, description }));
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");
    setIsSaving(true);

    const variants = formData.hasSizes
      ? formData.variants
      : [{
          size: formData.productSize,
          sku: formData.baseSku,
          barcode: formData.baseBarcode,
          stock: formData.stock,
          sellingPrice: formData.sellingPrice,
          costPrice: formData.costPrice,
        }];

    try {
      const baseCost = formData.hasSizes ? formData.variants[0]?.costPrice : formData.costPrice;
      const baseSelling = formData.hasSizes ? formData.variants[0]?.sellingPrice : formData.sellingPrice;
      const payload = {
        ...formData,
        productType: "",
        colourHex: "",
        supplierId: "",
        skuPrefix: formData.baseSku,
        compareAtPrice: "0",
        lowStockThreshold: "5",
        taxCategory: "standard",
        warrantyNotes: "",
        costPrice: baseCost,
        sellingPrice: baseSelling,
        variants: variants.map(({ imageFile: _imageFile, ...variant }) => variant),
        media: [],
      };
      let savedProduct = product
        ? await updateProduct(businessId, product.id, payload)
        : await createProduct(businessId, payload);
      if (mediaFiles.length) savedProduct = await uploadProductMedia(businessId, savedProduct.id, mediaFiles);
      for (const [index, variant] of formData.variants.entries()) {
        if (!variant.imageFile) continue;
        const savedVariant = savedProduct.sizes.find((item) => item.id === variant.id) || savedProduct.sizes[index];
        if (savedVariant) savedProduct = await uploadVariantImage(businessId, savedProduct.id, savedVariant.id, variant.imageFile);
      }
      if (product) onUpdated?.(savedProduct); else onCreated?.(savedProduct);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell isOpen={isOpen} title={product ? "Edit Product" : "Add Product"} onClose={onClose} size="wide">
      <form className="stitch-product-form" onSubmit={handleSubmit}>
        <div className="stitch-product__top">
          <div className="stitch-product__details">
            <label className="stitch-product__full">Product Name
              <input name="name" value={formData.name} onChange={updateField} placeholder="Enter product name" required />
            </label>
            <label>Product color
              <input name="colourName" value={formData.colourName} onChange={updateField} placeholder="Select color..." />
            </label>
            <label>Product Size
              <input name="productSize" value={formData.productSize} onChange={updateField} placeholder="Select size..." />
            </label>
            <label>Category
              <select name="categoryId" value={formData.categoryId} onChange={updateField} required>
                <option value="">None</option>
                {activeCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </label>
            <label>Brand
              <input name="brand" value={formData.brand} onChange={updateField} placeholder="Select brand..." />
            </label>
            <label>Warranty
              <select name="warrantyPeriodMonths" value={formData.warrantyPeriodMonths} onChange={updateField}>
                <option value="0">None</option><option value="1">1 month</option><option value="3">3 months</option>
                <option value="6">6 months</option><option value="12">1 year</option><option value="24">2 years</option>
              </select>
            </label>
          </div>

          <section className="stitch-product__photos">
            <strong>Product Photos</strong>
            <label className="stitch-product__upload"><Upload size={15} /> Upload
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple onChange={(event) => setMediaFiles(Array.from(event.target.files).slice(0, 12))} />
            </label>
            <div className="stitch-product__photo-grid">
              {previews.slice(0, 3).map((preview, index) => (
                <span key={`${preview.file.name}-${index}`}>{preview.url ? <img src={preview.url} alt="" /> : <ImageIcon size={19} />}</span>
              ))}
              {Array.from({ length: Math.max(0, 3 - previews.length) }, (_, index) => <span key={`empty-${index}`}><ImageIcon size={19} /></span>)}
              <label className="stitch-product__photo-add"><Plus size={22} />
                <input type="file" accept="image/*" multiple onChange={(event) => setMediaFiles((current) => [...current, ...Array.from(event.target.files)].slice(0, 12))} />
              </label>
            </div>
          </section>
        </div>

        <div className="stitch-product__identifiers">
          <IdentifierField label="SKU ID" name="baseSku" value={formData.baseSku} placeholder="Generate or enter SKU" onChange={updateField} onGenerate={() => fillBaseIdentifier("baseSku")} disabled={formData.hasSizes} />
          <IdentifierField label="Barcode" name="baseBarcode" value={formData.baseBarcode} placeholder="Scan or enter barcode" onChange={updateField} onGenerate={() => fillBaseIdentifier("baseBarcode")} disabled={formData.hasSizes} />
        </div>

        <section className={`stitch-product__panel ${formData.hasSizes ? "stitch-product__panel--weight-only" : ""}`}>
          <strong>{formData.hasSizes ? "Product Weight" : "Pricing"}</strong>
          <div className="stitch-product__pricing">
            {!formData.hasSizes && <label>Cost price<input name="costPrice" type="number" min="0" step="0.01" value={formData.costPrice} onChange={updateField} placeholder="LKR 0.00" required /></label>}
            {!formData.hasSizes && <label>Selling price<input name="sellingPrice" type="number" min="0.01" step="0.01" value={formData.sellingPrice} onChange={updateField} placeholder="LKR 0.00" required /></label>}
            <label>Weight<input name="weightKg" type="number" min="0.001" step="0.001" value={formData.weightKg} onChange={updateField} placeholder="0.00 kg" required /></label>
            {!formData.hasSizes && <label>Stock<input name="stock" type="number" min="0" step="1" value={formData.stock} onChange={updateField} required /></label>}
          </div>
        </section>

        <section className="stitch-product__panel stitch-product__variants">
          <div className="stitch-product__section-title"><strong>Variants</strong><label><input type="checkbox" checked={formData.hasSizes} onChange={toggleVariants} /> This product has variants</label></div>
          {formData.hasSizes && <>
            <div className="stitch-product__variant-head"><span>Variant</span><span>Image</span><span>SKU</span><span>Barcode</span><span>Stock</span><span>Selling price</span><span>Cost price</span><span /></div>
            {formData.variants.map((variant, index) => (
              <div className="stitch-product__variant-row" key={variant.id}>
                <input value={variant.size} onChange={(event) => updateVariant(variant.id, "size", event.target.value)} placeholder="e.g. Red, Small" aria-label={`Variant ${index + 1}`} required />
                <label className="stitch-product__variant-image">{variant.imageFile ? <img src={URL.createObjectURL(variant.imageFile)} alt="" /> : variant.imageUrl ? <img src={variant.imageUrl} alt="" /> : <ImageIcon size={16} />}<input type="file" accept="image/*" onChange={(event) => updateVariant(variant.id, "imageFile", event.target.files[0] || null)} /></label>
                <GeneratedInput value={variant.sku} onChange={(value) => updateVariant(variant.id, "sku", value)} onGenerate={() => fillVariantIdentifier(variant.id, "sku")} label={`SKU ${index + 1}`} />
                <GeneratedInput value={variant.barcode} onChange={(value) => updateVariant(variant.id, "barcode", value)} onGenerate={() => fillVariantIdentifier(variant.id, "barcode")} label={`Barcode ${index + 1}`} />
                <input type="number" min="0" value={variant.stock} onChange={(event) => updateVariant(variant.id, "stock", event.target.value)} aria-label={`Stock ${index + 1}`} required />
                <input type="number" min="0.01" step="0.01" value={variant.sellingPrice} onChange={(event) => updateVariant(variant.id, "sellingPrice", event.target.value)} aria-label={`Selling price ${index + 1}`} required />
                <input type="number" min="0" step="0.01" value={variant.costPrice} onChange={(event) => updateVariant(variant.id, "costPrice", event.target.value)} aria-label={`Cost price ${index + 1}`} required />
                <button type="button" onClick={() => setFormData((current) => ({ ...current, variants: current.variants.filter(({ id }) => id !== variant.id) }))} aria-label={`Remove variant ${index + 1}`}><Trash2 size={15} /></button>
              </div>
            ))}
            <button className="stitch-product__add-variant" type="button" onClick={addVariant}><Plus size={15} /> Add variant</button>
          </>}
        </section>

        <section className="stitch-product__description">
          <div><strong>Description</strong><button type="button" onClick={handleGenerateDescription} disabled={isGenerating}><WandSparkles size={14} /> {isGenerating ? "Generating..." : "Generate"}</button></div>
          <textarea name="description" value={formData.description} onChange={updateField} placeholder="Write a detailed product description..." rows="4" />
        </section>

        {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}
        <footer className="stitch-product__footer"><button type="button" onClick={onClose}>Cancel</button><button className="stitch-product__save" type="submit" disabled={isSaving || activeCategories.length === 0}>{isSaving ? "Saving..." : product ? "Save Product" : "Add Product"}</button></footer>
      </form>
    </ModalShell>
  );
}

function IdentifierField({ label, onGenerate, disabled, ...inputProps }) {
  return <label>{label}<span className="stitch-product__generated"><input {...inputProps} disabled={disabled} required={!disabled} /><button type="button" onClick={onGenerate} disabled={disabled} aria-label={`Generate ${label}`}><WandSparkles size={15} /></button></span></label>;
}

function GeneratedInput({ value, onChange, onGenerate, label }) {
  return <span className="stitch-product__generated"><input value={value} onChange={(event) => onChange(event.target.value)} aria-label={label} required /><button type="button" onClick={onGenerate} aria-label={`Generate ${label}`}><WandSparkles size={14} /></button></span>;
}

export default AddProductModal;
````

### `frontend/src/components/EditProductModal.jsx`

````jsx
import { useEffect, useState } from "react";
import { updateProduct, uploadProductMedia } from "../services/productService";
import ModalShell from "./ModalShell";
import "./InventoryForm.css";

const emptyForm = {
  name: "",
  colourName: "",
  colourHex: "#f36f8d",
  productType: "",
  categoryId: "",
  brand: "",
  supplierId: "",
  description: "",
  aiDescription: "",
  costPrice: "",
  sellingPrice: "",
  compareAtPrice: "0",
  weightKg: "",
  lowStockThreshold: "5",
  taxCategory: "standard",
};

function EditProductModal({ isOpen, businessId, product, categories = [], onClose, onUpdated }) {
  const [form, setForm] = useState(emptyForm);
  const [mediaFiles, setMediaFiles] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen || !product) return;
    setForm({
      ...emptyForm,
      name: product.name ?? "",
      colourName: product.colourName ?? product.colour ?? "",
      colourHex: product.colourHex ?? "#f36f8d",
      productType: product.productType ?? "",
      categoryId: product.categoryId ?? "",
      brand: product.brand ?? "",
      supplierId: product.supplierId ?? "",
      description: product.description ?? "",
      aiDescription: product.aiDescription ?? "",
      costPrice: product.costPrice ?? "",
      sellingPrice: product.sellingPrice ?? "",
      compareAtPrice: product.compareAtPrice ?? "0",
      weightKg: product.weightKg ?? "",
      lowStockThreshold: product.lowStockThreshold ?? "5",
      taxCategory: product.taxCategory ?? "standard",
    });
    setMediaFiles([]);
    setError("");
  }, [isOpen, product]);

  function change(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!product) return;
    setSaving(true);
    setError("");
    try {
      let updated = await updateProduct(businessId, product.id, form);
      if (mediaFiles.length) updated = await uploadProductMedia(businessId, product.id, mediaFiles);
      onUpdated?.(updated);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalShell isOpen={isOpen} title="Edit Product" description="Update every catalogue field. Stock quantities remain in Adjust stock so each change is audited." onClose={onClose} size="wide">
      <form className="inventory-form" onSubmit={submit}>
        <div className="inventory-form__two-columns">
          <label>Product name<input name="name" value={form.name} onChange={change} required /></label>
          <label>Product type<input name="productType" value={form.productType} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Colour name<input name="colourName" value={form.colourName} onChange={change} /></label>
          <label>Colour<input className="inventory-form__colour" name="colourHex" type="color" value={form.colourHex} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Category<select name="categoryId" value={form.categoryId} onChange={change} required><option value="">Choose category</option>{categories.filter((category) => category.status === "active").map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label>Brand<input name="brand" value={form.brand} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Supplier ID<input name="supplierId" value={form.supplierId} onChange={change} /></label>
          <label>Tax category<select name="taxCategory" value={form.taxCategory} onChange={change}><option value="standard">Standard</option><option value="zero-rated">Zero rated</option><option value="exempt">Exempt</option></select></label>
        </div>
        <label>Description for chatbot<textarea name="description" value={form.description} onChange={change} rows={4} /></label>
        <label>AI description<textarea name="aiDescription" value={form.aiDescription} onChange={change} rows={3} /></label>
        <div className="inventory-form__three-columns">
          <label>Cost price (LKR)<input name="costPrice" type="number" min="0" step="0.01" value={form.costPrice} onChange={change} required /></label>
          <label>Selling price (LKR)<input name="sellingPrice" type="number" min="0.01" step="0.01" value={form.sellingPrice} onChange={change} required /></label>
          <label>Compare-at price<input name="compareAtPrice" type="number" min="0" step="0.01" value={form.compareAtPrice} onChange={change} /></label>
        </div>
        <div className="inventory-form__three-columns">
          <label>Weight (kg)<input name="weightKg" type="number" min="0.001" step="0.001" value={form.weightKg} onChange={change} required /></label>
          <label>Low-stock alert<input name="lowStockThreshold" type="number" min="0" step="1" value={form.lowStockThreshold} onChange={change} required /></label>
          <label>Replace/add media<input type="file" accept="image/*,video/*" multiple onChange={(event) => setMediaFiles(Array.from(event.target.files).slice(0, 12))} /></label>
        </div>
        {error && <p className="inventory-form__error" role="alert">{error}</p>}
        <footer className="inventory-form__footer"><button type="button" onClick={onClose}>Cancel</button><button className="inventory-form__primary" type="submit" disabled={saving}>{saving ? "Saving..." : "Save product"}</button></footer>
      </form>
    </ModalShell>
  );
}

export default EditProductModal;
````

### `frontend/src/components/InventoryForm.css`

````css
.inventory-form {
  display: grid;
  gap: 16px;
}

/* Add Product modal: compact layout based on the approved reference. */
.modal-shell:has(.stitch-product-form) {
  width: min(940px, calc(100vw - 32px));
  max-height: calc(100vh - 28px);
  border-radius: 3px;
}

.modal-shell:has(.stitch-product-form) .modal-shell__header {
  padding: 13px 20px;
  background: #f8fafc;
}

.modal-shell:has(.stitch-product-form) .modal-shell__header h2 { font-size: 1.05rem; }
.modal-shell:has(.stitch-product-form) .modal-shell__header p { display: none; }
.modal-shell:has(.stitch-product-form) .modal-shell__content { padding: 18px 20px 14px; }

.stitch-product-form {
  display: grid;
  gap: 14px;
  color: #344054;
  font-size: 12px;
}

.stitch-product-form label {
  display: grid;
  gap: 5px;
  min-width: 0;
  font-weight: 650;
}

.stitch-product-form input,
.stitch-product-form select,
.stitch-product-form textarea {
  width: 100%;
  min-width: 0;
  min-height: 35px;
  padding: 7px 10px;
  border: 1px solid #d5dbe3;
  border-radius: 6px;
  color: #344054;
  background: #fff;
  font: inherit;
  outline: none;
}

.stitch-product-form input:focus,
.stitch-product-form select:focus,
.stitch-product-form textarea:focus {
  border-color: #2589dc;
  box-shadow: 0 0 0 2px rgba(37, 137, 220, 0.12);
}

.stitch-product-form input:disabled { background: #f2f4f7; }

.stitch-product__top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 275px;
  gap: 28px;
}

.stitch-product__details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  align-content: start;
  gap: 14px;
}

.stitch-product__full { grid-column: 1 / -1; }

.stitch-product__photos,
.stitch-product__panel {
  border: 1px solid #e0e4ea;
  border-radius: 7px;
  background: #f8fafc;
}

.stitch-product__photos { padding: 18px; }
.stitch-product__photos > strong,
.stitch-product__panel > strong { display: block; margin-bottom: 13px; }

.stitch-product__upload {
  display: flex !important;
  grid-template-columns: none !important;
  align-items: center;
  justify-content: center;
  gap: 7px !important;
  height: 36px;
  border: 1px solid #d5dbe3;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}

.stitch-product__upload input,
.stitch-product__photo-add input { position: absolute; width: 1px; height: 1px; opacity: 0; }

.stitch-product__photo-grid {
  display: grid;
  grid-template-columns: repeat(3, 55px);
  gap: 8px;
  margin-top: 12px;
}

.stitch-product__photo-grid > span,
.stitch-product__photo-add {
  display: grid !important;
  place-items: center;
  width: 55px;
  height: 55px;
  overflow: hidden;
  border: 1px dashed #ccd4df;
  border-radius: 4px;
  color: #98a2b3;
  background: #fff;
  cursor: pointer;
}

.stitch-product__photo-grid img { width: 100%; height: 100%; object-fit: cover; }

.stitch-product__identifiers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22px;
}

.stitch-product__generated { position: relative; display: block; }
.stitch-product__generated input { padding-right: 35px; }
.stitch-product__generated button {
  position: absolute;
  top: 50%;
  right: 5px;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  color: #98a2b3;
  background: transparent;
  transform: translateY(-50%);
  cursor: pointer;
}

.stitch-product__panel { padding: 16px 18px; }
.stitch-product__pricing { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.stitch-product__panel--weight-only .stitch-product__pricing { grid-template-columns: minmax(180px, 260px); }

.stitch-product__section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
}

.stitch-product__section-title label {
  display: flex;
  grid-template-columns: none;
  align-items: center;
  gap: 7px;
  font-weight: 500;
}

.stitch-product__section-title input { width: 16px; min-height: 16px; accent-color: #168bd1; }

.stitch-product__variant-head,
.stitch-product__variant-row {
  display: grid;
  grid-template-columns: 1.05fr 52px .95fr 1.05fr .58fr .82fr .82fr 28px;
  align-items: center;
  gap: 10px;
}

.stitch-product__variant-head {
  padding: 8px 10px;
  color: #667085;
  background: #f1f4f7;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.stitch-product__variant-row { padding: 7px 10px; border-bottom: 1px solid #eaecf0; }
.stitch-product__variant-row input { min-height: 34px; padding: 6px 8px; }
.stitch-product__variant-row > button {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  color: #98a2b3;
  background: transparent;
  cursor: pointer;
}
.stitch-product__variant-image { display: grid !important; place-items: center; width: 42px; height: 34px; overflow: hidden; border: 1px dashed #cbd5e1; border-radius: 5px; color: #94a3b8; background: #fff; cursor: pointer; }
.stitch-product__variant-image img { width: 100%; height: 100%; object-fit: cover; }
.stitch-product__variant-image input { position: absolute; width: 1px; height: 1px; opacity: 0; }

.stitch-product__add-variant,
.stitch-product__description button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 0 0;
  border: 0;
  color: #168bd1;
  background: transparent;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.stitch-product__description > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.stitch-product__description button {
  padding: 5px 8px;
  border-radius: 4px;
  background: #dff2fc;
}

.stitch-product__description textarea { min-height: 88px; resize: vertical; }
.stitch-product__footer { display: flex; justify-content: flex-end; gap: 9px; padding-top: 3px; }
.stitch-product__footer button { min-height: 36px; padding: 0 18px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; cursor: pointer; }
.stitch-product__footer .stitch-product__save { border-color: #087cf0; color: #fff; background: #087cf0; }

html[data-theme="dark"] .modal-shell:has(.stitch-product-form) .modal-shell__header,
html[data-theme="dark"] .stitch-product__photos,
html[data-theme="dark"] .stitch-product__panel { background: var(--color-surface-soft); }
html[data-theme="dark"] .stitch-product-form { color: var(--color-text); }
html[data-theme="dark"] .stitch-product-form input,
html[data-theme="dark"] .stitch-product-form select,
html[data-theme="dark"] .stitch-product-form textarea,
html[data-theme="dark"] .stitch-product__upload,
html[data-theme="dark"] .stitch-product__photo-grid > span,
html[data-theme="dark"] .stitch-product__photo-add { color: var(--color-text); background: var(--color-surface); border-color: var(--color-border); }

@media (max-width: 760px) {
  .stitch-product__top { grid-template-columns: 1fr; gap: 14px; }
  .stitch-product__photos { order: 2; }
  .stitch-product__identifiers,
  .stitch-product__pricing { grid-template-columns: 1fr 1fr; }
  .stitch-product__variants { overflow-x: auto; }
  .stitch-product__variant-head,
  .stitch-product__variant-row { min-width: 790px; }
}

.inventory-form__columns {
  display: grid;
  grid-template-columns: minmax(280px, 0.8fr) minmax(460px, 1.35fr);
  gap: 14px;
}

.inventory-form__panel {
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
}

.inventory-form__panel h3,
.inventory-form__panel p {
  margin: 0;
}

.inventory-form__two-columns,
.inventory-form__three-columns {
  display: grid;
  gap: 12px;
}

.inventory-form__two-columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.inventory-form__three-columns {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.inventory-form input.inventory-form__colour {
  min-height: 42px;
  padding: 5px;
}

.inventory-form__checkbox {
  display: flex !important;
  grid-template-columns: none;
  align-items: center;
  gap: 9px !important;
}

.inventory-form__checkbox input {
  width: 18px;
  min-height: 18px;
  margin: 0;
}

.inventory-form__hint,
.inventory-form__variants-heading p {
  color: var(--color-text-muted);
  font-size: 0.8rem;
  font-weight: 450;
}

.inventory-form__variants-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 14px;
  padding-top: 4px;
}

.inventory-form__button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
}

.inventory-form__variants {
  display: grid;
  gap: 9px;
}

.inventory-form__variant-row {
  display: grid;
  grid-template-columns: 0.6fr 1fr 1.15fr 0.6fr auto;
  align-items: end;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: var(--color-surface-muted);
}

.inventory-form__variant-row:has(label:nth-child(3):last-of-type) {
  grid-template-columns: 1fr 1.15fr 0.6fr;
}

.inventory-form__remove {
  display: grid;
  place-items: center;
  width: 38px;
  height: 42px;
  border: 1px solid rgba(220, 38, 38, 0.3);
  border-radius: 8px;
  color: #dc2626;
  background: transparent;
  cursor: pointer;
}

@media (max-width: 900px) {
  .inventory-form__columns,
  .inventory-form__two-columns,
  .inventory-form__three-columns {
    grid-template-columns: 1fr;
  }

  .inventory-form__variant-row,
  .inventory-form__variant-row:has(label:nth-child(3):last-of-type) {
    grid-template-columns: 1fr;
  }
}

.inventory-form label,
.inventory-form__field-group {
  display: grid;
  gap: 7px;
  color: var(--color-text);
  font-size: 0.86rem;
  font-weight: 650;
}

.inventory-form input,
.inventory-form select,
.inventory-form textarea {
  width: 100%;
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  color: var(--color-text);
  background: var(--color-surface);
  font: inherit;
  font-weight: 450;
}

.inventory-form textarea {
  resize: vertical;
}

.inventory-form input:focus,
.inventory-form select:focus,
.inventory-form textarea:focus {
  border-color: #1686f7;
  outline: 3px solid rgba(22, 134, 247, 0.13);
}

.inventory-form__error {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.72);
}

.inventory-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.inventory-form__footer button,
.inventory-form__button {
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  color: var(--color-text);
  background: var(--color-surface);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}

.inventory-form__footer .inventory-form__primary,
.inventory-form__primary {
  border-color: #087cf0;
  color: #fff;
  background: linear-gradient(135deg, #178ff8, #066ce1);
}

.inventory-form button:disabled {
  cursor: wait;
  opacity: 0.65;
}

[data-theme="dark"] .inventory-form__error {
  color: #fca5a5;
  background: rgba(127, 29, 29, 0.22);
}

/* Add Product modal ------------------------------------------------------ */
.product-modal {
  gap: 12px;
}

.product-modal__steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 26px;
  margin: -4px auto 4px;
  padding: 0;
  width: min(100%, 760px);
  list-style: none;
}

.product-modal__steps li {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 650;
}

.product-modal__steps li:not(:last-child)::after {
  position: absolute;
  top: 50%;
  left: calc(100% - 8px);
  width: 34px;
  height: 1px;
  background: var(--color-border);
  content: "";
}

.product-modal__steps li span {
  display: grid;
  place-items: center;
  width: 25px;
  height: 25px;
  border: 1px solid var(--color-border-strong, var(--color-border));
  border-radius: 50%;
  background: var(--color-surface);
}

.product-modal__steps .product-modal__step--active {
  color: #087cf0;
}

.product-modal__steps .product-modal__step--active span {
  border-color: #087cf0;
  color: #fff;
  background: #087cf0;
}

.product-modal__summary {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  min-height: 72px;
  padding: 10px 14px;
  border: 1px solid var(--color-border);
  border-radius: 11px;
  background: var(--color-surface-muted);
}

.product-modal__summary-media {
  display: grid;
  place-items: center;
  width: 70px;
  height: 52px;
  overflow: hidden;
  border-radius: 9px;
  color: #1686f7;
  background: var(--color-surface);
}

.product-modal__summary-media img,
.product-modal__media-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-modal__summary > div:nth-child(2) {
  display: grid;
  gap: 4px;
}

.product-modal__summary span {
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.product-modal__summary-price {
  font-size: 1.05rem;
}

.product-modal__layout {
  display: grid;
  grid-template-columns: minmax(310px, 0.72fr) minmax(550px, 1.48fr);
  gap: 12px;
}

.product-modal__left-column,
.product-modal__right-column {
  display: grid;
  align-content: start;
  gap: 12px;
}

.product-modal__colour-field {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 7px;
}

.product-modal__colour-field input.inventory-form__colour {
  min-height: 42px;
  padding: 6px;
}

.product-modal__upload {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  border: 1px dashed #7faee0;
  border-radius: 9px;
  color: #087cf0;
  cursor: pointer;
}

.product-modal__upload input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.product-modal__media-list {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 64px;
}

.product-modal__media-list > p {
  width: 100%;
  text-align: center;
}

.product-modal__media-item {
  position: relative;
  display: grid;
  place-items: center;
  width: 65px;
  height: 58px;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
}

.product-modal__media-item:first-child {
  border-color: #1686f7;
  box-shadow: 0 0 0 1px #1686f7;
}

.product-modal__media-item span {
  position: absolute;
  top: 0;
  left: 0;
  padding: 2px 5px;
  color: #fff;
  background: #1686f7;
  font-size: 0.62rem;
}

.product-modal__pricing-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.product-modal__stock-heading,
.product-modal__stock-tools,
.product-modal__stock-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.product-modal__stock-heading p {
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.product-modal__toggle {
  display: flex !important;
  grid-template-columns: none !important;
  align-items: center;
  flex-direction: row !important;
  white-space: nowrap;
}

.product-modal__toggle input {
  width: 40px;
  min-height: 22px;
  accent-color: #087cf0;
}

.product-modal__stock-tools > label {
  width: min(260px, 100%);
}

.product-modal__variant-table {
  overflow-x: auto;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}

.product-modal__variant-head,
.product-modal__variant-row {
  display: grid;
  grid-template-columns: 0.55fr 1fr 1.25fr 0.6fr 42px;
  align-items: center;
  gap: 8px;
  min-width: 650px;
}

.product-modal__variant-head--single,
.product-modal__variant-row--single {
  grid-template-columns: 1fr 1.25fr 0.6fr 42px;
}

.product-modal__variant-head {
  padding: 8px 6px;
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-weight: 700;
}

.product-modal__variant-row {
  padding: 7px 6px;
  border-top: 1px solid var(--color-border);
}

.product-modal__variant-row input {
  min-height: 36px;
  padding: 7px 9px;
}

.product-modal__variant-row .inventory-form__remove {
  width: 36px;
  height: 36px;
}

.product-modal__stock-total {
  justify-content: flex-start;
  padding-top: 2px;
}

.product-modal__stock-total span {
  color: var(--color-text-muted);
}

.product-modal__footer {
  position: sticky;
  bottom: -22px;
  z-index: 3;
  align-items: center;
  justify-content: space-between;
  margin: 0 -22px -22px;
  padding: 14px 22px;
  background: var(--color-surface);
}

.product-modal__footer > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.product-modal__ready {
  color: #16855b;
  font-size: 0.86rem;
}

@media (max-width: 1050px) {
  .product-modal__layout {
    grid-template-columns: 1fr;
  }

  .product-modal__pricing-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .product-modal__steps {
    gap: 8px;
  }

  .product-modal__steps li {
    font-size: 0.7rem;
  }

  .product-modal__steps li::after {
    display: none;
  }

  .product-modal__summary {
    grid-template-columns: auto 1fr;
  }

  .product-modal__summary-price {
    grid-column: 2;
  }

  .product-modal__pricing-grid {
    grid-template-columns: 1fr 1fr;
  }

  .product-modal__stock-heading,
  .product-modal__stock-tools,
  .product-modal__footer {
    align-items: stretch;
    flex-direction: column;
  }

  .product-modal__footer > div {
    width: 100%;
  }

  .product-modal__footer > div:last-child button {
    flex: 1;
  }
}

/* Compact Stitch-inspired Add Product layout --------------------------- */
@media (min-width: 1051px) and (min-height: 760px) {
  .modal-shell:has(.product-modal) {
    width: min(96vw, 1080px);
    max-height: 96vh;
    overflow: hidden;
    border-radius: 12px;
  }

  .modal-shell:has(.product-modal) .modal-shell__header {
    padding: 11px 18px;
    background: var(--color-surface-soft);
  }

  .modal-shell:has(.product-modal) .modal-shell__header h2 {
    font-size: 1.05rem;
  }

  .modal-shell:has(.product-modal) .modal-shell__header p {
    display: none;
  }

  .modal-shell:has(.product-modal) .modal-shell__header button {
    width: 30px;
    height: 30px;
  }

  .modal-shell:has(.product-modal) .modal-shell__content {
    max-height: calc(96vh - 53px);
    overflow: auto;
    padding: 12px 16px 0;
  }

  .product-modal {
    gap: 9px;
    font-size: 12px;
  }

  .product-modal__steps,
  .product-modal__summary {
    display: none;
  }

  .product-modal__layout {
    grid-template-columns: minmax(330px, 0.88fr) minmax(520px, 1.35fr);
    gap: 10px;
  }

  .product-modal__left-column,
  .product-modal__right-column {
    gap: 9px;
  }

  .product-modal .inventory-form__panel {
    gap: 8px;
    padding: 11px 12px;
    border-radius: 9px;
    background: var(--color-surface-soft);
  }

  .product-modal .inventory-form__panel h3 {
    font-size: 0.82rem;
  }

  .product-modal label,
  .product-modal .inventory-form__field-group {
    gap: 4px;
    font-size: 0.7rem;
    font-weight: 650;
  }

  .product-modal .inventory-form__two-columns,
  .product-modal .inventory-form__three-columns {
    gap: 8px;
  }

  .product-modal input,
  .product-modal select,
  .product-modal textarea {
    min-height: 31px;
    padding: 6px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
  }

  .product-modal textarea {
    min-height: 64px;
    max-height: 78px;
  }

  .product-modal__colour-field {
    grid-template-columns: 35px 1fr;
    gap: 5px;
  }

  .product-modal__colour-field input.inventory-form__colour {
    min-height: 31px;
    padding: 3px;
  }

  .product-modal__upload {
    min-height: 34px;
    border-radius: 6px;
  }

  .product-modal__media-list {
    min-height: 48px;
    gap: 6px;
  }

  .product-modal__media-item {
    width: 52px;
    height: 46px;
    border-radius: 6px;
  }

  .product-modal__pricing-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 7px;
  }

  .product-modal__stock-heading p,
  .product-modal__stock-tools,
  .product-modal__stock-total {
    font-size: 0.7rem;
  }

  .product-modal__variant-head,
  .product-modal__variant-row {
    min-width: 0;
    gap: 5px;
  }

  .product-modal__variant-head {
    padding: 5px 4px;
    font-size: 0.64rem;
  }

  .product-modal__variant-row {
    padding: 5px 4px;
  }

  .product-modal__variant-row input {
    min-height: 30px;
    padding: 5px 6px;
  }

  .product-modal__variant-row .inventory-form__remove {
    width: 30px;
    height: 30px;
  }

  .product-modal__footer {
    bottom: 0;
    margin: 0 -16px;
    padding: 9px 16px;
    font-size: 0.72rem;
  }

  .product-modal__footer button,
  .product-modal .inventory-form__button {
    min-height: 33px;
    padding: 0 13px;
    border-radius: 7px;
    font-size: 0.72rem;
  }
}
````

### `frontend/src/components/ProductVariantsTable.jsx`

````jsx
// Row action icon and shared stock-status helper.
import { PackagePlus } from "lucide-react";

import { getStockStatus } from "../utils/inventory";

// Convert a value such as "low-stock" into the readable text "Low Stock".
function formatStatus(status) {
  return status
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Display the size-level SKU, barcode, stock, and status for a sized product.
function ProductSizesTable({ sizes, onAdjustStock }) {
  return (
    <section className="product-variants">
      <div className="product-variants__scroll">
        <table className="product-variants__table">
          <thead>
            <tr>
              <th>Size</th>
              <th>SKU</th>
              <th>Barcode</th>
              <th>Available</th>
              <th>Status</th>
              <th aria-label="Size actions"></th>
            </tr>
          </thead>

          <tbody>
            {sizes.map((sizeOption) => {
              // Size variants use a smaller low-stock threshold than products.
              const stockStatus = getStockStatus(sizeOption.stock, 2);

              return (
                <tr key={sizeOption.id}>
                  <td>
                    <strong>EU {sizeOption.size}</strong>
                  </td>
                  <td>{sizeOption.sku}</td>
                  <td>{sizeOption.barcode}</td>
                  <td>
                    <strong>{sizeOption.stock}</strong>
                  </td>

                  <td>
                    <span
                      className={`inventory-table__status inventory-table__status--${stockStatus}`}
                    >
                      {formatStatus(stockStatus)}
                    </span>
                  </td>

                  <td className="product-variants__actions-cell">
                    <button
                      className="product-variants__adjust-button"
                      type="button"
                      onClick={() => onAdjustStock?.(sizeOption.id)}
                      aria-label={`Adjust stock for size ${sizeOption.size}`}
                    >
                      <PackagePlus size={15} aria-hidden="true" />
                      Adjust
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default ProductSizesTable;
````

### `frontend/src/services/productService.js`

````javascript
import { apiRequest } from "./apiClient";

function minorUnitsToAmount(value = 0) {
  return value / 100;
}

// Convert the backend's safe storage fields into the existing inventory UI shape.
export function mapProductForInventory(product) {
  const variants = product.variantSummaries ?? [];
  const firstVariant = variants[0] ?? {};

  return {
    ...product,
    colour: product.colourName,
    category: product.categoryName,
    sku: firstVariant.sku ?? product.skuPrefix,
    barcode: firstVariant.barcode ?? "",
    costPrice: minorUnitsToAmount(product.costPriceMinor),
    sellingPrice: minorUnitsToAmount(product.sellingPriceMinor),
    compareAtPrice: minorUnitsToAmount(product.compareAtPriceMinor),
    weightKg: (product.weightGrams ?? 0) / 1000,
    lowStockThreshold: product.lowStockThreshold ?? 5,
    stock: product.availableStock ?? 0,
    approvedReviews: product.approvedReviewCount ?? 0,
    images: (product.media ?? [])
      .map((mediaItem) => mediaItem.url)
      .filter(Boolean),
    sizes: variants.map((variant) => ({
      id: variant.id,
      size: variant.size,
      sku: variant.sku,
      barcode: variant.barcode,
      stock: variant.stockAvailable,
      costPrice: minorUnitsToAmount(variant.costPriceMinor ?? product.costPriceMinor),
      sellingPrice: minorUnitsToAmount(variant.sellingPriceMinor ?? product.sellingPriceMinor),
      imageUrl: variant.imageUrl ?? "",
    })),
  };
}

export async function getProducts(businessId, filters = {}) {
  const searchParameters = new URLSearchParams();

  if (filters.categoryId) {
    searchParameters.set("categoryId", filters.categoryId);
  }
  if (filters.status) {
    searchParameters.set("status", filters.status);
  }

  const query = searchParameters.toString();
  const response = await apiRequest(
    `/businesses/${businessId}/products${query ? `?${query}` : ""}`,
  );

  return response.products.map(mapProductForInventory);
}

export async function createProduct(businessId, productData) {
  const response = await apiRequest(`/businesses/${businessId}/products`, {
    method: "POST",
    body: productData,
  });

  return mapProductForInventory(response.product);
}

export async function generateProductDescription(businessId, productDetails) {
  const response = await apiRequest(
    `/businesses/${businessId}/products/generate-description`,
    {
      method: "POST",
      body: productDetails,
    },
  );

  return response.description;
}

export async function uploadProductMedia(businessId, productId, files) {
  const formData = new FormData();

  files.forEach((file) => formData.append("files", file));

  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}/media`,
    {
      method: "POST",
      body: formData,
    },
  );

  return mapProductForInventory(response.product);
}

export async function uploadVariantImage(businessId, productId, variantId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}/variants/${variantId}/image`,
    { method: "POST", body: formData },
  );
  return mapProductForInventory(response.product);
}

export async function updateProduct(businessId, productId, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}`,
    {
      method: "PATCH",
      body: changes,
    },
  );

  return mapProductForInventory(response.product);
}

export async function removeProduct(businessId, productId) {
  const response = await apiRequest(`/businesses/${businessId}/products/${productId}`, {
    method: "DELETE",
  });
  return mapProductForInventory(response.product);
}

export async function updateProductStatus(businessId, productId, status) {
  return updateProduct(businessId, productId, { status });
}

// Export the currently loaded inventory without requiring a second server endpoint.
export function downloadInventoryCsv(products = []) {
  const columns = ["Product", "SKU", "Barcode", "Category", "Selling price", "Weight (kg)", "Stock", "Status"];
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const rows = products.map((product) => [
    product.name,
    product.sku,
    product.barcode,
    product.category,
    product.sellingPrice,
    product.weightKg,
    product.stock,
    product.stockStatus,
  ]);
  const csv = [columns, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `vendly-inventory-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function adjustProductStock(
  businessId,
  productId,
  variantId,
  adjustment,
) {
  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}/variants/${variantId}/adjust-stock`,
    {
      method: "POST",
      body: adjustment,
    },
  );

  return mapProductForInventory(response.product);
}
````

## Feature 9 source — Media and AI descriptions

Files in this feature: 2

### `backend/app/services/ai_service.py`

````python
import json

import httpx
from flask import current_app


OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}


def product_prompt(question, product):
    context = {
        "name": product.get("name"),
        "brand": product.get("brand"),
        "colour": product.get("colourName"),
        "category": product.get("categoryName"),
        "description": product.get("description"),
        "sellerAiDescription": product.get("aiDescription"),
        "priceLkr": product.get("sellingPriceMinor", 0) / 100,
        "availableSizes": [
            variant.get("size")
            for variant in product.get("variants", [])
            if variant.get("size")
        ],
        "approvedReviewCount": product.get("approvedReviewCount", 0),
        "approvedReviewSnippets": product.get("approvedReviewSnippets", []),
    }
    return (
        "You are Vendly's product assistant. Answer in the customer's language. "
        "Use only the seller-provided JSON facts below. Never invent features, "
        "warranties, waterproof ratings, SIM support, video support, reviews, or "
        "availability. If the facts do not answer the question, say the seller has "
        "not provided that information yet. Mention that delivery is calculated "
        "from district and total order weight when relevant. Keep the answer concise.\n\n"
        f"PRODUCT FACTS:\n{json.dumps(context, ensure_ascii=False)}\n\n"
        f"CUSTOMER QUESTION:\n{question}"
    )


def generate_openai_compatible_answer(prompt, provider, settings):
    base_url = settings.get("AI_API_BASE_URL") or OPENAI_COMPATIBLE_BASE_URLS.get(
        provider,
    )

    if not base_url:
        return None

    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings['AI_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings["AI_MODEL"],
            "messages": [
                {"role": "system", "content": "Follow the supplied product facts exactly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 350,
        },
        timeout=settings["AI_TIMEOUT_SECONDS"],
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_gemini_answer(prompt, settings):
    from google import genai

    client = genai.Client(api_key=settings["AI_API_KEY"])
    interaction = client.interactions.create(
        model=settings["AI_MODEL"],
        input=prompt,
    )
    return interaction.output_text.strip()


def generate_product_answer(question, product):
    """Return an optional AI answer; failures safely fall back to deterministic chat."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    prompt = product_prompt(question, product)

    try:
        if provider == "gemini":
            return generate_gemini_answer(prompt, settings)
        if provider in {"groq", "cerebras", "openai-compatible"}:
            return generate_openai_compatible_answer(prompt, provider, settings)
    except Exception:  # External SDKs use provider-specific exception classes.
        current_app.logger.exception("The configured AI provider request failed.")
        return None

    current_app.logger.warning("Unsupported AI_PROVIDER value: %s", provider)
    return None


def generate_product_description(product_details):
    """Generate seller-editable catalogue copy from the supplied product facts."""
    settings = current_app.config
    provider = settings.get("AI_PROVIDER", "none")
    name = str(product_details.get("name", "")).strip()

    if not name:
        return None

    facts = {
        "name": name,
        "brand": product_details.get("brand"),
        "colour": product_details.get("colourName"),
        "category": product_details.get("categoryName"),
        "size": product_details.get("productSize"),
        "warrantyMonths": product_details.get("warrantyPeriodMonths"),
        "weightKg": product_details.get("weightKg"),
        "costPriceLkr": product_details.get("costPrice"),
        "sellingPriceLkr": product_details.get("sellingPrice"),
        "variants": product_details.get("variants", []),
    }
    prompt = (
        "Write a clear e-commerce product description using every non-empty specification "
        "in the supplied facts, including brand, colour, size, weight, warranty and variant "
        "options when provided. Use only the supplied facts; do not invent specifications, materials, "
        "compatibility, waterproof ratings, warranty terms, or benefits. Do not "
        "Include prices only when supplied. Do not include a heading. Return only the description.\n\n"
        f"PRODUCT FACTS:\n{json.dumps(facts, ensure_ascii=False)}"
    )

    if provider == "none" or not settings.get("AI_API_KEY") or not settings.get("AI_MODEL"):
        return None

    try:
        if provider == "gemini":
            return generate_gemini_answer(prompt, settings)
        if provider in {"groq", "cerebras", "openai-compatible"}:
            return generate_openai_compatible_answer(prompt, provider, settings)
    except Exception:
        current_app.logger.exception("Product description generation failed.")
        return None

    return None
````

### `backend/app/services/media_service.py`

````python
import hashlib
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import httpx
from firebase_admin import firestore
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.core.errors import ApiError
from app.services.product_service import get_product


ALLOWED_MEDIA_TYPES = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
CLOUDINARY_UPLOAD_URL = "https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/upload"


def file_size(upload: FileStorage):
    current_position = upload.stream.tell()
    upload.stream.seek(0, 2)
    size = upload.stream.tell()
    upload.stream.seek(current_position)
    return size


def validate_media(upload: FileStorage):
    media_type = ALLOWED_MEDIA_TYPES.get(upload.mimetype)

    if not media_type:
        raise ApiError(
            "unsupported_media_type",
            f"{upload.filename or 'File'} is not a supported image or video.",
            422,
        )

    size = file_size(upload)
    maximum_size = MAX_IMAGE_BYTES if media_type == "image" else MAX_VIDEO_BYTES

    if size == 0:
        raise ApiError("empty_media_file", "An uploaded media file is empty.", 422)

    if size > maximum_size:
        maximum_megabytes = maximum_size // (1024 * 1024)
        raise ApiError(
            "media_file_too_large",
            f"{upload.filename} must be {maximum_megabytes} MB or smaller.",
            413,
        )

    return media_type, size


def firebase_download_url(bucket_name, object_path, download_token):
    encoded_path = quote(object_path, safe="")
    return (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/"
        f"{encoded_path}?alt=media&token={download_token}"
    )


def cloudinary_signature(parameters, api_secret):
    """Create Cloudinary's SHA-1 signature without exposing the API secret."""
    signed_values = "&".join(
        f"{key}={parameters[key]}" for key in sorted(parameters) if parameters[key] is not None
    )
    return hashlib.sha1(f"{signed_values}{api_secret}".encode("utf-8")).hexdigest()


def upload_to_cloudinary(upload, business_id, product_id, cloudinary_config):
    """Upload one file to Cloudinary and return safe metadata for Firestore."""
    cloud_name = cloudinary_config.get("cloud_name")
    api_key = cloudinary_config.get("api_key")
    api_secret = cloudinary_config.get("api_secret")

    if not all((cloud_name, api_key, api_secret)):
        raise ApiError(
            "media_storage_not_configured",
            "Media storage is not configured. Add the Cloudinary credentials to the backend .env file.",
            503,
        )

    media_type, size = validate_media(upload)
    resource_type = "video" if media_type == "video" else "image"
    safe_name = secure_filename(upload.filename or "media")
    public_id = (
        f"businesses/{business_id}/products/{product_id}/"
        f"{uuid4().hex}_{Path(safe_name).stem}"
    )
    timestamp = int(time.time())
    parameters = {"public_id": public_id, "timestamp": timestamp}
    signature = cloudinary_signature(parameters, api_secret)

    upload.stream.seek(0)
    try:
        response = httpx.post(
            CLOUDINARY_UPLOAD_URL.format(
                cloud_name=cloud_name,
                resource_type=resource_type,
            ),
            data={
                "api_key": api_key,
                "public_id": public_id,
                "timestamp": timestamp,
                "signature": signature,
            },
            files={
                "file": (
                    safe_name,
                    upload.stream,
                    upload.mimetype,
                ),
            },
            timeout=60.0,
        )
        response_data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise ApiError(
            "cloudinary_upload_failed",
            "The media upload service could not be reached. Please try again.",
            502,
        ) from error

    if response.status_code >= 400:
        message = response_data.get("error", {}).get("message")
        raise ApiError(
            "cloudinary_upload_failed",
            message or "Cloudinary rejected this media file.",
            422 if response.status_code < 500 else 502,
        )

    return {
        "id": response_data.get("asset_id") or response_data.get("public_id"),
        "type": media_type,
        "path": response_data.get("public_id", public_id),
        "url": response_data.get("secure_url") or response_data.get("url", ""),
        "fileName": safe_name,
        "contentType": upload.mimetype,
        "sizeBytes": size,
        "provider": "cloudinary",
    }


def upload_product_media(
    database,
    business_id,
    product_id,
    uid,
    uploads,
    cloudinary_config=None,
):
    """Upload product media and append safe Cloudinary metadata to Firestore."""
    if not uploads:
        raise ApiError("media_required", "Choose at least one image or video.", 422)
    if len(uploads) > 12:
        raise ApiError("too_many_media_files", "Upload no more than 12 files.", 422)

    product = get_product(database, business_id, product_id)
    existing_media = product.get("media", [])

    if len(existing_media) + len(uploads) > 12:
        raise ApiError(
            "too_many_media_files",
            "A product can contain no more than 12 media files.",
            422,
        )

    uploaded_media = []

    for upload in uploads:
        uploaded_media.append(
            upload_to_cloudinary(
                upload,
                business_id,
                product_id,
                cloudinary_config or {},
            ),
        )

    product_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
        .document(product_id)
    )
    changes = {
        "media": firestore.ArrayUnion(uploaded_media),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }

    if not existing_media and uploaded_media:
        changes["primaryMediaPath"] = uploaded_media[0]["path"]

    product_reference.update(changes)
    return get_product(database, business_id, product_id)


def upload_variant_image(database, business_id, product_id, variant_id, upload, cloudinary_config=None):
    """Upload one variant image and keep its product summary in sync."""
    product = get_product(database, business_id, product_id)
    variant_reference = database.collection("businesses").document(business_id).collection("productVariants").document(variant_id)
    variant_snapshot = variant_reference.get()
    if not variant_snapshot.exists or variant_snapshot.to_dict().get("productId") != product_id:
        raise ApiError("variant_not_found", "Product variant not found.", 404)
    media = upload_to_cloudinary(upload, business_id, product_id, cloudinary_config or {})
    variant_reference.update({"imageUrl": media["url"], "imagePath": media["path"], "updatedAt": firestore.SERVER_TIMESTAMP})
    summaries = [{**summary, "imageUrl": media["url"]} if summary.get("id") == variant_id else summary for summary in product.get("variantSummaries", [])]
    database.collection("businesses").document(business_id).collection("products").document(product_id).update({"variantSummaries": summaries, "updatedAt": firestore.SERVER_TIMESTAMP})
    return get_product(database, business_id, product_id)
````

## Feature 10 source — Inventory and stock

Files in this feature: 10

### `frontend/src/components/AdjustStockModal.css`

````css
.adjust-stock__product {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 11px;
  background: var(--color-surface-muted);
}

.adjust-stock__product > span {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 9px;
  color: #087cf0;
  background: rgba(8, 124, 240, 0.1);
}

.adjust-stock__product > div {
  display: grid;
  gap: 3px;
}

.adjust-stock__product small {
  color: var(--color-text-muted);
}

.adjust-stock__operation {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 0;
  padding: 0;
  border: 0;
}

.adjust-stock__operation legend {
  grid-column: 1 / -1;
  margin-bottom: 7px;
  color: var(--color-text);
  font-size: 0.86rem;
  font-weight: 650;
}

.adjust-stock__operation button {
  min-height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  background: var(--color-surface);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}

.adjust-stock__operation .adjust-stock__operation--active {
  border-color: #16865a;
  color: #13754f;
  background: rgba(22, 134, 90, 0.1);
}

.adjust-stock__operation .adjust-stock__operation--remove {
  border-color: #ef4444;
  color: #c62828;
  background: rgba(239, 68, 68, 0.09);
}

.adjust-stock__preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 8px;
  color: #13754f;
  background: rgba(22, 134, 90, 0.09);
}

.adjust-stock__preview strong {
  font-size: 1.05rem;
}

.adjust-stock__preview--error {
  justify-content: flex-start;
  color: #c62828;
  background: rgba(239, 68, 68, 0.09);
}

.adjust-stock__preview--error strong {
  margin-left: auto;
}
````

### `frontend/src/components/AdjustStockModal.jsx`

````jsx
import { useEffect, useMemo, useState } from "react";
import { PackagePlus, TriangleAlert } from "lucide-react";

import { adjustProductStock } from "../services/productService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";
import "./AdjustStockModal.css";

function AdjustStockModal({ businessId, product, initialVariantId, onClose, onUpdated }) {
  const [variantId, setVariantId] = useState("");
  const [operation, setOperation] = useState("add");
  const [quantity, setQuantity] = useState("1");
  const [reason, setReason] = useState("New stock received");
  const [reference, setReference] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!product) return;

    setVariantId(initialVariantId || product.sizes?.[0]?.id || "");
    setOperation("add");
    setQuantity("1");
    setReason("New stock received");
    setReference("");
    setErrorMessage("");
  }, [initialVariantId, product]);

  const selectedVariant = useMemo(
    () => product?.sizes?.find((variant) => variant.id === variantId),
    [product, variantId],
  );

  async function handleSubmit(event) {
    event.preventDefault();

    const cleanQuantity = Number(quantity);

    if (!selectedVariant || !Number.isInteger(cleanQuantity) || cleanQuantity < 1) {
      setErrorMessage("Choose a SKU and enter a positive whole quantity.");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      const updatedProduct = await adjustProductStock(
        businessId,
        product.id,
        selectedVariant.id,
        {
          quantityChange: operation === "add" ? cleanQuantity : -cleanQuantity,
          reason,
          reference,
        },
      );
      onUpdated(updatedProduct);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  const projectedStock = selectedVariant
    ? selectedVariant.stock + (operation === "add" ? Number(quantity) || 0 : -(Number(quantity) || 0))
    : 0;

  return (
    <ModalShell
      isOpen={Boolean(product)}
      title="Adjust Stock"
      description="Record a stock change and keep a complete inventory audit trail."
      onClose={onClose}
    >
      {product && (
        <form className="inventory-form adjust-stock" onSubmit={handleSubmit}>
          <div className="adjust-stock__product">
            <span><PackagePlus size={22} aria-hidden="true" /></span>
            <div><strong>{product.name}</strong><small>{product.category}</small></div>
            <b>{product.stock} total units</b>
          </div>

          <section className="inventory-form__panel">
            <label>
              Product size / SKU
              <select value={variantId} onChange={(event) => setVariantId(event.target.value)} required>
                {(product.sizes ?? []).map((variant) => (
                  <option key={variant.id} value={variant.id}>
                    {variant.size ? `Size ${variant.size} Â· ` : ""}{variant.sku} Â· {variant.stock} available
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="adjust-stock__operation">
              <legend>Adjustment type</legend>
              <button className={operation === "add" ? "adjust-stock__operation--active" : ""} type="button" onClick={() => { setOperation("add"); setReason("New stock received"); }}>Add stock</button>
              <button className={operation === "remove" ? "adjust-stock__operation--remove" : ""} type="button" onClick={() => { setOperation("remove"); setReason("Damaged, lost or corrected stock"); }}>Remove stock</button>
            </fieldset>

            <div className="inventory-form__two-columns">
              <label>
                Quantity
                <input type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
              </label>
              <label>
                Reference (optional)
                <input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Supplier invoice or note" />
              </label>
            </div>

            <label>
              Reason
              <textarea rows={3} maxLength={300} value={reason} onChange={(event) => setReason(event.target.value)} required />
            </label>

            <div className={`adjust-stock__preview ${projectedStock < 0 ? "adjust-stock__preview--error" : ""}`}>
              {projectedStock < 0 && <TriangleAlert size={18} aria-hidden="true" />}
              <span>Available stock after adjustment</span>
              <strong>{projectedStock}</strong>
            </div>
          </section>

          {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}

          <footer className="inventory-form__footer">
            <button type="button" onClick={onClose}>Cancel</button>
            <button className="inventory-form__primary" type="submit" disabled={isSaving || projectedStock < 0}>
              {isSaving ? "Updating stock..." : "Update Stock"}
            </button>
          </footer>
        </form>
      )}
    </ModalShell>
  );
}

export default AdjustStockModal;
````

### `frontend/src/components/InventoryFilters.css`

````css
/* Outer card containing all inventory filter controls. */
.inventory-filters {
  margin-top: 10px;
  padding: 10px;
  padding-left: 10px;
  padding-right: 10px;

  border: 1px solid var(--color-border);
  border-radius: 12px;

  background: var(--color-surface);

  box-shadow: 0 4px 14px rgba(15, 59, 110, 0.06);

  transition:
    background 250ms ease,
    border-color 250ms ease,
    box-shadow 250ms ease;
}

/* Responsive grid that arranges search, selects, and buttons. */
.inventory-filters__form {
  display: grid;

grid-template-columns:
  minmax(220px, 1.6fr)
  repeat(2, minmax(105px, 1fr))
  auto
  auto;

  align-items: end;
  gap: 10px;
}

/* Shared label and control layout for each inventory filter. */
.inventory-filters__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.inventory-filters__field label {
  color: var(--color-text-strong);
  font-size: 12px;
  font-weight: 650;
}

.inventory-filters__field > input,
/* Select and input visual states. */
.inventory-filters__field > select {
  width: 100%;
  min-width: 0;
  height: 40px;
  padding: 0 11px;

  border: 1px solid var(--color-border);
  border-radius: 7px;
  outline: none;

  color: var(--color-text);
  background-color: var(--color-control);

  font-size: 13px;
  font-weight: 450;

  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease,
    color 180ms ease;
}

.inventory-filters__field > input::placeholder {
  color: var(--color-subtle);
}

.inventory-filters__field > input:focus,
.inventory-filters__field > select:focus {
  border-color: var(--color-accent);
  background-color: var(--color-control);
  box-shadow: 0 0 0 3px rgba(41, 151, 255, 0.14);
}

.inventory-filters__apply,
/* Reset and primary Filter buttons. */
.inventory-filters__reset {
  display: inline-flex;
  align-items: center;
  justify-content: center;

  height: 40px;
  border-radius: 7px;

  font-weight: 700;

  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    color 180ms ease,
    transform 180ms ease,
    box-shadow 180ms ease;
}

.inventory-filters__apply {
  gap: 8px;
  min-width: 104px;
  padding: 0 16px;

  border: 1px solid var(--color-accent);
  color: white;
  background-color: var(--color-accent);

  font-size: 13px;
  box-shadow: 0 4px 10px rgba(22, 140, 245, 0.2);
}

.inventory-filters__apply:hover {
  border-color: #0879dd;
  background-color: #0879dd;
  box-shadow: 0 6px 14px rgba(22, 140, 245, 0.28);
  transform: translateY(-1px);
}

.inventory-filters__reset {
  width: 42px;
  padding: 0;

  border: 1px solid var(--color-border);
  color: var(--color-accent);
  background-color: var(--color-control);
}

.inventory-filters__reset:hover {
  border-color: var(--color-accent);
  color: white;
  background-color: var(--color-accent);
}

.inventory-filters__resetbt{
  transform: rotate(45deg);
}

.inventory-filters__apply:active,
.inventory-filters__reset:active {
  transform: translateY(0);
}

/* Tablet filter layout. */
@media (max-width: 1050px) {
  .inventory-filters__form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .inventory-filters__date-field {
    grid-column: auto;
  }

  .inventory-filters__apply {
    width: 100%;
  }
}

/* Mobile filter layout. */
@media (max-width: 620px) {
  .inventory-filters {
    padding: 12px;
  }

  .inventory-filters__form {
    grid-template-columns: 1fr;
  }

  .inventory-filters__date-field {
    grid-column: auto;
  }

  .inventory-filters__reset {
    width: 100%;
  }
}

/* Dark-theme filter card, inputs, selects, and reset button. */
html[data-theme="dark"] .inventory-filters {
  border-color: rgba(78, 111, 145, 0.45);

  background:
    radial-gradient(
      circle at 10% 0%,
      rgba(41, 151, 255, 0.09),
      transparent 35%
    ),
    linear-gradient(
      145deg,
      rgba(17, 31, 46, 0.96),
      rgba(10, 21, 34, 0.96)
    );

  box-shadow:
    0 12px 28px rgba(0, 0, 0, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.025);
}

html[data-theme="dark"] .inventory-filters__field label {
  color: #bed0e3;
}

html[data-theme="dark"] .inventory-filters__field > input,
html[data-theme="dark"] .inventory-filters__field > select {
  border-color: #2b4055;
  color: var(--color-text);
  background-color: rgba(7, 18, 30, 0.72);

  box-shadow:
    inset 0 1px 2px rgba(0, 0, 0, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.015);
}

html[data-theme="dark"]
  .inventory-filters__field
  > input::placeholder {
  color: #74879b;
}

html[data-theme="dark"] .inventory-filters__field select option {
  color: var(--color-text);
  background-color: #111e2d;
}

html[data-theme="dark"] .inventory-filters__field > input:focus,
html[data-theme="dark"] .inventory-filters__field > select:focus {
  border-color: #2997ff;
  background-color: rgba(10, 25, 41, 0.95);

  box-shadow:
    0 0 0 3px rgba(41, 151, 255, 0.14),
    0 5px 14px rgba(0, 0, 0, 0.15);
}


html[data-theme="dark"] .inventory-filters__reset {
  border-color: #31506d;
  color: #54aaff;
  background-color: rgba(13, 31, 48, 0.9);
}

html[data-theme="dark"] .inventory-filters__reset:hover {
  border-color: #2997ff;
  color: white;
  background-color: #176bb7;
}
.inventory-filters__field { position: relative; }
.inventory-filters__clear { position: absolute; right: 8px; bottom: 8px; display: grid; place-items: center; width: 24px; height: 24px; border: 0; border-radius: 50%; background: var(--color-surface-muted); color: var(--color-text-muted); cursor: pointer; }
````

### `frontend/src/components/InventoryFilters.jsx`

````jsx
// React state stores the current filter values entered by the user.
import { useState } from "react";
import {
  Funnel,
  RotateCcw,
  X,
} from "lucide-react";

import "./InventoryFilters.css";

// Empty values used when the form first loads or is reset.
const initialFilters = {
  searchProduct: "",
  category: "",
  stockStatus: "",
};

function InventoryFilters({ categories = [], onApply, onReset }) {
  // All inventory filter fields are stored together in one state object.
  const [filters, setFilters] = useState(initialFilters);

  // Update the field whose name matches the changed input or select element.
  function handleInputChange(event) {
    const fieldName = event.target.name;
    const fieldValue = event.target.value;

    const nextFilters = {
      ...filters,
      [fieldName]: fieldValue,
    };
    setFilters((currentFilters) => ({
      ...currentFilters,
      [fieldName]: fieldValue,
    }));
    if (fieldName === "searchProduct" && !fieldValue) onApply?.(nextFilters);
  }

  // Prevent a page reload and send the selected values to InventoryPage.
  function handleSubmit(event) {
    event.preventDefault();
    onApply?.(filters);
  }

  // Restore every filter to its original empty value.
  function handleReset() {
    setFilters(initialFilters);
    onReset?.();
  }

  return (
    <section className="inventory-filters" aria-label="inventory filters">
      {/* Controlled form: every value comes from the filters state object. */}
      <form className="inventory-filters__form" onSubmit={handleSubmit}>
    


        {/* Product name, SKU, or barcode search. */}
        <div className="inventory-filters__field">

          <input
            id="searchProduct"
            name="searchProduct"
            type="search"
            aria-label="Search product by name or SKU"
            placeholder="Search product name, SKU, or barcode"
            value={filters.searchProduct}
            onChange={handleInputChange}
          />
          {filters.searchProduct && <button type="button" className="inventory-filters__clear" onClick={() => handleInputChange({ target: { name: "searchProduct", value: "" } })} aria-label="Clear product search"><X size={15} /></button>}
        </div>


        {/* Category selector. */}
        <div className="inventory-filters__field">
          <label htmlFor="category">Category</label>

          <select
            id="category"
            name="category"
            value={filters.category}
            onChange={handleInputChange}
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </select>
        </div>



        {/* Stock-status selector. */}
        <div className="inventory-filters__field">
          <label htmlFor="stockStatus">Stock Status</label>

          <select
            id="stockStatus"
            name="stockStatus"
            value={filters.stockStatus}
            onChange={handleInputChange}
          >
            <option value="">All statuses</option>
            <option value="in-stock">In Stock</option>
            <option value="low-stock">Low Stock</option>
            <option value="out-of-stock">Out of Stock</option>
          </select>
        </div>

        {/* Submit and reset controls. */}
        <button className="inventory-filters__apply" type="submit">
          <Funnel size={18} aria-hidden="true" />
          <span>Filter</span>
        </button>

        <button
          className="inventory-filters__reset"
          type="button"
          onClick={handleReset}
          aria-label="Reset inventory filters"
          title="Reset filters"
        >
          <RotateCcw className="inventory-filters__resetbt" size={21} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}

export default InventoryFilters;
````

### `frontend/src/components/InventoryTable.css`

````css
/* Product image and text arrangement inside a main inventory row. */
.inventory-table__product {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 190px;
}

/* Actions displayed when inventory rows are checkbox-selected. */
.inventory-table__bulk-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  padding: 9px 14px;
  border-bottom: 1px solid var(--color-border);
  background: rgba(22, 140, 245, 0.06);
}

.inventory-table__bulk-status {
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--color-primary, #1683f5);
  border-radius: 8px;
  color: var(--color-primary-dark, #064e9b);
  background: var(--color-surface, #fff);
  font: inherit;
  cursor: pointer;
}

.inventory-table__bulk-actions strong {
  margin-right: 8px;
  color: var(--color-text-strong);
  font-size: 12.5px;
  font-weight: 650;
}

.inventory-table__bulk-actions button,
.inventory-table__size-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid var(--color-accent);
  border-radius: 7px;
  color: var(--color-accent);
  background: var(--color-control);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.inventory-table__bulk-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

/* Shared product-photo frame and fallback icon area. */
.inventory-table__product-image {
  display: grid;
  place-items: center;
  flex-shrink: 0;

  width: 42px;
  height: 42px;

  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;

  color: var(--color-accent);
  background: var(--color-surface-soft);
}

.inventory-table__product-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Stock badge base style followed by its three status colours. */
.inventory-table__status {
  display: inline-flex;
  align-items: center;

  padding: 5px 9px;
  border: 1px solid;
  border-radius: 7px;

  font-size: 10.5px;
  font-weight: 650;
  white-space: nowrap;
}

.inventory-table__status--in-stock {
  color: #14835a;
  border-color: #54c99b;
  background: rgba(34, 164, 116, 0.1);
}

.inventory-table__status--low-stock {
  color: #c77700;
  border-color: #f7b84b;
  background: rgba(245, 158, 11, 0.1);
}

.inventory-table__status--out-of-stock {
  color: #dc3030;
  border-color: #ff7777;
  background: rgba(239, 68, 68, 0.1);
}

.inventory-table__details-cell {
  padding: 0 10px 12px !important;
  background: var(--color-surface-soft);
}

/* Expanded panel used by products with size variants. */
.inventory-table__size-details {
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface);
  animation: inventory-details-open 220ms ease-out;
}

/* Size summary header and its seller action buttons. */
.inventory-table__size-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.inventory-table__size-header h3 {
  margin: 0 0 4px;
  color: var(--color-text-strong);
  font-size: 13.5px;
  font-weight: 650;
}

.inventory-table__size-header span {
  color: var(--color-subtle);
  font-size: 11.5px;
}

.inventory-table__size-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.inventory-table__size-actions button:first-child {
  color: white;
  background: var(--color-accent);
}

/* Description and photos displayed above the size rows. */
.inventory-table__size-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(220px, 0.8fr);
  gap: 18px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}

.inventory-table__size-overview section {
  min-width: 0;
}

.inventory-table__size-overview h4 {
  margin: 0 0 7px;
  color: var(--color-text-strong);
  font-size: 12.5px;
  font-weight: 650;
}

.inventory-table__size-overview p {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}

.orders-table tbody .inventory-table__details-row:hover {
  background: transparent;
}

/* Expanded four-column layout used by simple products. */
.inventory-table__details {
  display: grid;
  grid-template-columns:
    minmax(300px, 1.5fr)
    minmax(210px, 1fr)
    minmax(180px, 0.8fr)
    minmax(170px, 0.7fr);

  gap: 16px;
  padding: 16px;

  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface);

  animation: inventory-details-open 220ms ease-out;
}

.inventory-table__details section {
  padding-right: 16px;
  border-right: 1px solid var(--color-border);
}

.inventory-table__details section:last-child {
  padding-right: 0;
  border-right: 0;
}

.inventory-table__details h3 {
  margin: 0 0 8px;
  color: var(--color-text-strong);
  font-size: 12.5px;
  font-weight: 650;
}

.inventory-table__description p {
  margin: 0 0 14px;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}

/* Product images, information lists, reviews, and actions. */
.inventory-table__images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.inventory-table__information {
  display: grid;
  align-content: start;
}

.inventory-table__information > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;

  padding: 9px 0;
  border-bottom: 1px solid var(--color-border);
}

.inventory-table__information > div:last-child {
  border-bottom: 0;
}

.inventory-table__information span {
  color: var(--color-subtle);
  font-size: 12px;
}

.inventory-table__information strong {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-strong);
  font-weight: 650;
}

.inventory-table__star {
  color: #f59e0b;
}

.inventory-table__actions {
  display: grid;
  align-content: start;
  gap: 9px;
}

.inventory-table__actions button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;

  min-height: 36px;
  padding: 8px 12px;

  border: 1px solid var(--color-accent);
  border-radius: 7px;

  color: var(--color-accent);
  background: transparent;

  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.inventory-table__actions button:first-child {
  color: white;
  background: var(--color-accent);
}

/* Dark-theme simple-product details. */
html[data-theme="dark"] .inventory-table__details-cell {
  background: rgba(7, 17, 28, 0.72);
}

html[data-theme="dark"] .inventory-table__details {
  border-color: #2b4055;
  background: linear-gradient(
    145deg,
    rgba(18, 34, 51, 0.98),
    rgba(10, 22, 35, 0.98)
  );
}

html[data-theme="dark"]
  .inventory-table__status--in-stock {
  color: #5cdaa8;
}

html[data-theme="dark"]
  .inventory-table__status--low-stock {
  color: #ffbd4a;
}

html[data-theme="dark"]
  .inventory-table__status--out-of-stock {
  color: #ff7777;
}

/* Opening animation shared by expanded inventory content. */
@keyframes inventory-details-open {
  from {
    opacity: 0;
    transform: translateY(-7px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Collapse the simple-product detail grid on medium screens. */
@media (max-width: 1100px) {
  .inventory-table__details {
    grid-template-columns: repeat(2, minmax(250px, 1fr));
  }

  .inventory-table__details section:nth-child(2) {
    border-right: 0;
  }
}

/* Label showing how many sizes belong to a product. */
.inventory-table__variant-count {
  display: block;
  margin-top: 3px;
  color: var(--color-accent);
  font-size: 10px;
  font-weight: 700;
}

/* Nested table containing size-level SKUs, barcodes, and stock. */
.product-variants {
  grid-column: 1 / -1;
  padding: 0 !important;
  border: 0 !important;
}

.product-variants__scroll {
  overflow-x: auto;
}

.product-variants__table {
  width: 100%;
  border-collapse: collapse;
}

.product-variants__table th,
.product-variants__table td {
  padding: 10px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  white-space: nowrap;
}

.product-variants__table th {
  color: var(--color-text-strong);
  font-size: 10.5px;
  font-weight: 650;
  text-transform: uppercase;
}

.product-variants__actions-cell {
  width: 92px;
  text-align: right !important;
}

.product-variants__adjust-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-height: 30px;
  padding: 0 9px;
  border: 1px solid var(--color-accent);
  border-radius: 7px;
  color: var(--color-accent);
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 10.5px;
  font-weight: 700;
}

/* Dark-theme size details and bulk selection bar. */
html[data-theme="dark"] .inventory-table__size-details {
  border-color: #2b4055;
  background: linear-gradient(
    145deg,
    rgba(18, 34, 51, 0.98),
    rgba(10, 22, 35, 0.98)
  );
}

html[data-theme="dark"] .inventory-table__bulk-actions {
  background: rgba(41, 151, 255, 0.08);
}

/* Stack size details and actions on small screens. */
@media (max-width: 760px) {
  .inventory-table__size-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .inventory-table__size-overview {
    grid-template-columns: 1fr;
  }

  .inventory-table__size-actions {
    justify-content: flex-start;
  }
}
````

### `frontend/src/components/InventoryTable.jsx`

````jsx
// React tools manage repeated table rows and interactive component state.
import { Fragment, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Download,
  Package,
  PackagePlus,
  Pencil,
  Star,
  Trash2,
} from "lucide-react";
import ActionMenu from "./ActionMenu";

// Product data, stock calculation helpers, and the nested size table.
import {
  getProductStock,
  getProductStockStatus,
} from "../utils/inventory";
import ProductSizesTable from "./ProductVariantsTable";

import "./OrderTable.css";
import "./InventoryTable.css";

// Convert a number into Sri Lankan Rupee text for table prices.
function formatCurrency(amount) {
  return `LKR ${amount.toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// Convert "in-stock" style values into readable labels such as "In Stock".
function formatStatus(status) {
  return status
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Show a product photo and fall back to a package icon if the image fails.
function ProductImage({ product, imageNumber = 0 }) {
  // Each photo component remembers whether its own image failed to load.
  const [imageFailed, setImageFailed] = useState(false);
  const imageSource = product.images?.[imageNumber];

  return (
    <span
      className="inventory-table__product-image"
      style={product.colourHex ? { color: product.colourHex } : undefined}
    >
      {imageSource && !imageFailed ? (
        <img
          src={imageSource}
          alt={product.name}
          onError={() => setImageFailed(true)}
        />
      ) : (
        <Package size={21} aria-hidden="true" />
      )}
    </span>
  );
}

// Expanded content used only by products that have size variants.
function SizeStockDetails({ product, onViewReviews, onAdjustStock, onEditProduct, onRemoveProduct }) {
  return (
    <div className="inventory-table__size-details">
      {/* Size summary and seller actions. */}
      <header className="inventory-table__size-header">
        <div>
          <h3>Sizes &amp; Stock</h3>
          <span>
            {product.sizes.length} sizes â€¢ {getProductStock(product)} total units
          </span>
        </div>

        <div className="inventory-table__size-actions">
          <button type="button" onClick={() => onAdjustStock?.(product)}>
            <PackagePlus size={16} aria-hidden="true" />
            Adjust Stock
          </button>
          <button type="button" onClick={() => onEditProduct?.(product)}>
            <Pencil size={16} aria-hidden="true" />
            Edit Product
          </button>
          <button type="button" className="inventory-table__danger-button" onClick={() => onRemoveProduct?.(product)}>
            <Trash2 size={16} aria-hidden="true" />
            Remove Product
          </button>
          <button type="button" onClick={() => onViewReviews?.(product)}>
            <Star size={16} aria-hidden="true" />
            View Reviews
          </button>
        </div>
      </header>

      {/* Shared description and photos for every size of this product. */}
      <div className="inventory-table__size-overview">
        <section>
          <h4>Product Description</h4>
          <p>{product.description}</p>
        </section>

        <section>
          <h4>Product Photos</h4>
          <div className="inventory-table__images">
            {(product.images ?? []).map((image, index) => (
              <ProductImage
                key={image}
                product={product}
                imageNumber={index}
              />
            ))}
          </div>
        </section>
      </div>

      {/* Size-level SKU, barcode, stock, and status rows. */}
      <ProductSizesTable
        sizes={product.sizes}
        onAdjustStock={(variantId) => onAdjustStock?.(product, variantId)}
      />
    </div>
  );
}

// Expanded content for a simple product that does not have sizes.
function SimpleProductDetails({ product, onViewReviews, onAdjustStock, onEditProduct, onRemoveProduct }) {
  return (
    <div className="inventory-table__details">
      {/* Product description and photo gallery. */}
      <section className="inventory-table__description">
        <h3>Product Description</h3>
        <p>{product.description}</p>

        <h3>Product Images</h3>
        <div className="inventory-table__images">
          {(product.images ?? []).map((image, index) => (
            <ProductImage
              key={image}
              product={product}
              imageNumber={index}
            />
          ))}
        </div>
      </section>

      {/* Pricing, barcode, and weight information. */}
      <section className="inventory-table__information">
        <div>
          <span>Barcode</span>
          <strong>{product.barcode}</strong>
        </div>
        <div>
          <span>Cost Price</span>
          <strong>{formatCurrency(product.costPrice)}</strong>
        </div>
        <div>
          <span>Selling Price</span>
          <strong>{formatCurrency(product.sellingPrice)}</strong>
        </div>
        <div>
          <span>Weight</span>
          <strong>{product.weightKg.toFixed(2)} kg</strong>
        </div>
      </section>

      {/* Current stock and approved review count. */}
      <section className="inventory-table__information">
        <div>
          <span>Available Stock</span>
          <strong>{getProductStock(product)}</strong>
        </div>
        <div>
          <span>Approved Reviews</span>
          <strong>
            {product.approvedReviews}
            <Star
              className="inventory-table__star"
              size={15}
              fill="currentColor"
              aria-hidden="true"
            />
          </strong>
        </div>
      </section>

      {/* Actions available to the seller for this product. */}
      <section className="inventory-table__actions">
        <button type="button" onClick={() => onEditProduct?.(product)}>
          <Pencil size={17} aria-hidden="true" />
          Edit Product
        </button>
        <button type="button" className="inventory-table__danger-button" onClick={() => onRemoveProduct?.(product)}>
          <Trash2 size={17} aria-hidden="true" />
          Remove Product
        </button>
        <button type="button" onClick={() => onAdjustStock?.(product)}>
          <PackagePlus size={17} aria-hidden="true" />
          Adjust Stock
        </button>
        <button type="button" onClick={() => onViewReviews?.(product)}>
          <Star size={17} aria-hidden="true" />
          View Reviews
        </button>
      </section>
    </div>
  );
}

function InventoryTable({ products = [], categories = [], onViewReviews, onAdjustStock, onEditProduct, onRemoveProduct, onChangeStatus, onChangeCategory, onExportSelected }) {
  // Track the one expanded row and all checkbox-selected products.
  const [expandedProductId, setExpandedProductId] = useState(
    null,
  );
  const [selectedProductIds, setSelectedProductIds] = useState([]);

  // True when every visible product checkbox is selected.
  const allProductsSelected =
    products.length > 0 && selectedProductIds.length === products.length;

  // Open the clicked product, or close it if it is already open.
  function toggleExpandedProduct(productId) {
    setExpandedProductId((currentProductId) =>
      currentProductId === productId ? null : productId,
    );
  }

  // Add or remove one product ID from the selected ID array.
  function toggleSelectedProduct(productId) {
    setSelectedProductIds((currentIds) => {
      if (currentIds.includes(productId)) {
        return currentIds.filter((id) => id !== productId);
      }

      return [...currentIds, productId];
    });
  }

  // Select every product or clear the complete selection.
  function toggleAllProducts() {
    if (allProductsSelected) {
      setSelectedProductIds([]);
      return;
    }

    setSelectedProductIds(products.map((product) => product.id));
  }

  return (
    <section
      className="orders-table-section inventory-table-section"
      aria-label="Inventory products"
    >
      {/* Bulk actions appear only after one or more products are selected. */}
      {selectedProductIds.length > 0 && (
        <div className="inventory-table__bulk-actions">
          <strong>{selectedProductIds.length} products selected</strong>
          <button
            type="button"
            onClick={() => {
              if (selectedProductIds.length === 1) {
                onAdjustStock?.(
                  products.find((product) => product.id === selectedProductIds[0]),
                );
              }
            }}
            disabled={selectedProductIds.length !== 1}
            title={selectedProductIds.length === 1 ? "Adjust selected product" : "Select one product to adjust stock"}
          >
            <PackagePlus size={16} aria-hidden="true" />
            Adjust stock
          </button>
          <select
            className="inventory-table__bulk-status"
            defaultValue=""
            aria-label="Change status for selected products"
            onChange={(event) => {
              if (event.target.value) {
                onChangeStatus?.(selectedProductIds, event.target.value);
                event.target.value = "";
              }
            }}
          >
            <option value="" disabled>Change status</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
          <select
            className="inventory-table__bulk-status"
            defaultValue=""
            aria-label="Add selected products to a category"
            onChange={(event) => {
              if (event.target.value) {
                onChangeCategory?.(selectedProductIds, event.target.value);
                event.target.value = "";
              }
            }}
          >
            <option value="" disabled>Add to category</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <button type="button" onClick={() => onChangeStatus?.(selectedProductIds, "archived")}>
            Delete selected
          </button>
          <button type="button" onClick={() => onExportSelected?.(selectedProductIds)}>
            <Download size={16} aria-hidden="true" />
            Export selected
          </button>
        </div>
      )}

      {/* Scroll wrapper keeps the wide inventory table usable on small screens. */}
      <div className="orders-table__scroll">
        <table className="orders-table inventory-table">
          <thead>
            <tr>
              <th className="orders-table__checkbox-column">
                <input
                  type="checkbox"
                  checked={allProductsSelected}
                  onChange={toggleAllProducts}
                  aria-label="Select all products"
                />
              </th>
              <th className="orders-table__expand-column"></th>
              <th>Product</th>
              <th>SKU / Barcode</th>
              <th>Category</th>
              <th>Price</th>
              <th>Weight</th>
              <th>Stock</th>
              <th>Status</th>
              <th className="orders-table__actions-heading">Actions</th>
            </tr>
          </thead>

          <tbody>
            {products.map((product) => {
              // Values calculated separately for the current product row.
              const isExpanded = expandedProductId === product.id;
              const isSelected = selectedProductIds.includes(product.id);
              const stockStatus = getProductStockStatus(product);

              return (
                <Fragment key={product.id}>
                  <tr
                    className={
                      isSelected ? "orders-table__row--selected" : ""
                    }
                  >
                    <td>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelectedProduct(product.id)}
                        aria-label={`Select ${product.name}`}
                      />
                    </td>

                    <td>
                      <button
                        className="orders-table__expand-button"
                        type="button"
                        onClick={() => toggleExpandedProduct(product.id)}
                        aria-expanded={isExpanded}
                        aria-label={
                          isExpanded
                            ? `Collapse ${product.name}`
                            : `Expand ${product.name}`
                        }
                      >
                        {isExpanded ? (
                          <ChevronDown size={18} aria-hidden="true" />
                        ) : (
                          <ChevronRight size={18} aria-hidden="true" />
                        )}
                      </button>
                    </td>

                    <td>
                      <div className="inventory-table__product">
                        <ProductImage product={product} />
                        <div>
                          <strong>{product.name}</strong>
                          <span className="orders-table__secondary">
                            {product.productType}
                          </span>
                          {product.hasSizes && (
                            <span className="inventory-table__variant-count">
                              {product.sizes.length} sizes
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    <td>
                      <strong>
                        {product.hasSizes ? "Multiple SKUs" : product.sku}
                      </strong>
                      <span className="orders-table__secondary">
                        {product.hasSizes
                          ? "View size details"
                          : product.barcode}
                      </span>
                    </td>

                    <td>{product.category}</td>
                    <td className="orders-table__total">
                      {formatCurrency(product.sellingPrice)}
                    </td>
                    <td>{product.weightKg.toFixed(2)} kg</td>
                    <td>
                      <strong>{getProductStock(product)}</strong>
                    </td>
                    <td>
                      <span
                        className={`inventory-table__status inventory-table__status--${stockStatus}`}
                      >
                        {formatStatus(stockStatus)}
                      </span>
                    </td>
                    <td>
                      <ActionMenu label={`More actions for ${product.name}`} items={[
                        { label: "Edit product", icon: <Pencil size={16} />, onClick: () => onEditProduct?.(product) },
                        { label: "Adjust stock", icon: <PackagePlus size={16} />, onClick: () => onAdjustStock?.(product) },
                        { label: "View reviews", icon: <Star size={16} />, onClick: () => onViewReviews?.(product) },
                        { label: "Remove product", icon: <Trash2 size={16} />, danger: true, onClick: () => onRemoveProduct?.(product) },
                      ]} />
                    </td>
                  </tr>

                  {/* Show the correct expanded layout for sized or simple products. */}
                  {isExpanded && (
                    <tr className="inventory-table__details-row">
                      <td className="inventory-table__details-cell" colSpan={10}>
                        {product.hasSizes ? (
                          <SizeStockDetails
                            product={product}
                            onViewReviews={onViewReviews}
                            onAdjustStock={onAdjustStock}
                            onEditProduct={onEditProduct}
                            onRemoveProduct={onRemoveProduct}
                          />
                        ) : (
                          <SimpleProductDetails
                            product={product}
                            onViewReviews={onViewReviews}
                            onAdjustStock={onAdjustStock}
                            onEditProduct={onEditProduct}
                            onRemoveProduct={onRemoveProduct}
                          />
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Record count and temporary pagination controls. */}
      <footer className="orders-table__footer">
        <span>
          Showing {products.length === 0 ? 0 : 1} to {products.length} of{" "}
          {products.length} products
        </span>
        <div className="orders-table__pagination">
          <button type="button" disabled>
            Previous
          </button>
          <button className="orders-table__page--active" type="button">
            1
          </button>
          <button type="button">2</button>
          <button type="button">3</button>
          <button type="button">Next</button>
        </div>
      </footer>
    </section>
  );
}

export default InventoryTable;
````

### `frontend/src/data/sampleProducts.js`

````javascript
// Temporary product records used to build the inventory UI before Firestore.
const sampleProducts = [
  // Simple product without size variants.
  {
    id: "product-001",
    name: "Haylou Smart Watch LS02",
    productType: "Smart Watch",
    sku: "HW-LS02-BLK",
    barcode: "6971664930824",
    category: "Wearables",

    costPrice: 3300,
    sellingPrice: 4900,
    weightKg: 0.05,

    stock: 36,
    lowStockThreshold: 5,
    approvedReviews: 128,

    description:
      "Haylou LS02 is a sporty smart watch with 12 sport modes, heart rate monitoring, sleep tracking, and 30-day battery life. Water resistant up to 5ATM.Haylou LS02 is a sporty smart watch with 12 sport modes, heart rate monitoring, sleep tracking, and 30-day battery life. Water resistant up to 5ATM.Haylou LS02 is a sporty smart watch with 12 sport modes, heart rate monitoring, sleep tracking, and 30-day battery life. Water resistant up to 5ATM.",

    images: [
      "/products/haylou-ls02-front.png",
      "/products/haylou-ls02-side.png",
      "/products/haylou-ls02-box.png",
      "/products/haylou-ls02-back.png",
      "/products/haylou-ls02-strap.png",
    ],
  },

  // Another simple product record.
  {
    id: "product-002",
    name: "Redmi Buds 4 Lite",
    productType: "Earbuds",
    sku: "RB-4L-BLK",
    barcode: "6941812712569",
    category: "Audio",

    costPrice: 2700,
    sellingPrice: 3950,
    weightKg: 0.04,

    stock: 18,
    lowStockThreshold: 20,
    approvedReviews: 84,

    description:
      "Lightweight wireless earbuds supplied with a compact charging case.",

    images: [
      "/products/redmi-buds-front.png",
      "/products/redmi-buds-case.png",
    ],
  },

  // Product with no remaining stock.
  {
    id: "product-003",
    name: "Zara Mini Tote Bag - Beige",
    productType: "Handbag",
    sku: "ZARA-MINI-BGE",
    barcode: "2000003145123",
    category: "Bags",

    costPrice: 2400,
    sellingPrice: 3700,
    weightKg: 0.35,

    stock: 0,
    lowStockThreshold: 5,
    approvedReviews: 45,

    description:
      "A compact beige tote bag suitable for everyday use.",

    images: [
      "/products/zara-mini-bag-front.png",
      "/products/zara-mini-bag-side.png",
    ],
  },

  // Simple footwear product with one SKU.
  {
    id: "product-004",
    name: "Running Shoes - Black",
    productType: "Men's Shoes",
    sku: "RS-BLK-42",
    barcode: "8901234567890",
    category: "Footwear",

    costPrice: 6000,
    sellingPrice: 8250,
    weightKg: 0.8,

    stock: 42,
    lowStockThreshold: 10,
    approvedReviews: 62,

    description:
      "Black running shoes designed for everyday exercise and casual wear.",

    images: [
      "/products/running-shoes-left.png",
      "/products/running-shoes-right.png",
    ],
  },

  // Simple appliance product with one SKU.
  {
    id: "product-005",
    name: "Portable Blender 380ml",
    productType: "Home Appliance",
    sku: "PB-380-PNK",
    barcode: "8906123456781",
    category: "Appliances",

    costPrice: 3900,
    sellingPrice: 5680,
    weightKg: 0.6,

    stock: 27,
    lowStockThreshold: 10,
    approvedReviews: 31,

    description:
      "A compact 380ml portable blender suitable for preparing drinks while travelling.",

    images: [
      "/products/portable-blender-front.png",
      "/products/portable-blender-open.png",
    ],
  },

  // Pink shoe product; each size has its own SKU, barcode, and stock.
  {
    id: "product-006-pink",
    name: "Daisy Running Shoes - Pink",
    colour: "Pink",
    colourHex: "#ec7f9f",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 5,
    hasSizes: true,
    sizes: [
      { id: "pink-36", size: "36", sku: "DFS-PNK-36", barcode: "890123456001", stock: 5 },
      { id: "pink-37", size: "37", sku: "DFS-PNK-37", barcode: "890123456002", stock: 1 },
      { id: "pink-38", size: "38", sku: "DFS-PNK-38", barcode: "890123456003", stock: 2 },
      { id: "pink-39", size: "39", sku: "DFS-PNK-39", barcode: "890123456004", stock: 3 },
      { id: "pink-40", size: "40", sku: "DFS-PNK-40", barcode: "890123456005", stock: 4 },
    ],
    approvedReviews: 42,
    description:
      "Lightweight pink running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/pink.png"],
  },

  // Purple is stored as a separate product with size variants.
  {
    id: "product-007-purple",
    name: "Daisy Running Shoes - Purple",
    colour: "Purple",
    colourHex: "#8a62c2",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 6,
    hasSizes: true,
    sizes: [
      { id: "purple-36", size: "36", sku: "DFS-PUR-36", barcode: "890123456101", stock: 2 },
      { id: "purple-37", size: "37", sku: "DFS-PUR-37", barcode: "890123456102", stock: 1 },
      { id: "purple-38", size: "38", sku: "DFS-PUR-38", barcode: "890123456103", stock: 1 },
      { id: "purple-39", size: "39", sku: "DFS-PUR-39", barcode: "890123456104", stock: 1 },
      { id: "purple-40", size: "40", sku: "DFS-PUR-40", barcode: "890123456105", stock: 1 },
    ],
    approvedReviews: 18,
    description:
      "Lightweight purple running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/purple.png"],
  },

  // Burgundy is stored as a separate product with size variants.
  {
    id: "product-008-burgundy",
    name: "Daisy Running Shoes - Burgundy",
    colour: "Burgundy",
    colourHex: "#8b1e3f",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 5,
    hasSizes: true,
    sizes: [
      { id: "burgundy-36", size: "36", sku: "DFS-BUR-36", barcode: "890123456201", stock: 1 },
      { id: "burgundy-37", size: "37", sku: "DFS-BUR-37", barcode: "890123456202", stock: 1 },
      { id: "burgundy-38", size: "38", sku: "DFS-BUR-38", barcode: "890123456203", stock: 2 },
      { id: "burgundy-39", size: "39", sku: "DFS-BUR-39", barcode: "890123456204", stock: 2 },
      { id: "burgundy-40", size: "40", sku: "DFS-BUR-40", barcode: "890123456205", stock: 1 },
    ],
    approvedReviews: 23,
    description:
      "Lightweight burgundy running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/burgundy.png"],
  },

  // Black is stored as a separate product with size variants.
  {
    id: "product-009-black",
    name: "Daisy Running Shoes - Black",
    colour: "Black",
    colourHex: "#161616",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 5,
    hasSizes: true,
    sizes: [
      { id: "black-36", size: "36", sku: "DFS-BLK-36", barcode: "890123456301", stock: 0 },
      { id: "black-37", size: "37", sku: "DFS-BLK-37", barcode: "890123456302", stock: 0 },
      { id: "black-38", size: "38", sku: "DFS-BLK-38", barcode: "890123456303", stock: 0 },
      { id: "black-39", size: "39", sku: "DFS-BLK-39", barcode: "890123456304", stock: 0 },
      { id: "black-40", size: "40", sku: "DFS-BLK-40", barcode: "890123456305", stock: 0 },
    ],
    approvedReviews: 11,
    description:
      "Lightweight black running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/black.png"],
  },
];

// Export the records so inventory components can display and calculate them.
export default sampleProducts;
````

### `frontend/src/pages/InventoryPage.css`

````css
/* Page title and inventory action buttons share one horizontal row. */
.inventory-page__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 4px;
}

.inventory-page__heading h2 {
  margin-top: 10px;
  color: var(--color-text-strong);
  font-weight: 700;
}

.inventory-page__description {
  margin-bottom: 14px !important;
}

/* Scan, export, and add-product button group. */
.inventory-page__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.inventory-page__actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: 7px;
  color: var(--color-text-strong);
  background: var(--color-control);
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}

.inventory-page__actions button:hover {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

/* Primary action receives the filled Vendly blue style. */
.inventory-page__actions .inventory-page__add-button {
  color: white;
  border-color: var(--color-accent);
  background: var(--color-accent);
}

.inventory-page__actions .inventory-page__add-button:hover {
  color: white;
  border-color: #0879dd;
  background: #0879dd;
}

/* Stack the heading and action buttons on narrower screens. */
@media (max-width: 820px) {
  .inventory-page__heading {
    flex-direction: column;
  }

  .inventory-page__actions {
    justify-content: flex-start;
  }
}


/* Products and Categories tab navigation. */
.inventory-tabs {
  display: flex;
  align-items: center;
  gap: 26px;

  margin-top: 18px;
  margin-bottom: 16px;

  border-bottom: 1px solid var(--color-border);
}

.inventory-tabs__button {
  position: relative;

  display: inline-flex;
  align-items: center;
  gap: 7px;

  padding: 11px 4px;

  border: 0;
  color: var(--color-muted);
  background: transparent;

  font: inherit;
  font-size: 13px;
  font-weight: 600;

  cursor: pointer;
}

.inventory-tabs__button:hover {
  color: var(--color-accent);
}

.inventory-tabs__button--active {
  color: var(--color-accent);
}

/* Blue underline marks the currently selected inventory tab. */
.inventory-tabs__button--active::after {
  content: "";

  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;

  height: 2px;
  border-radius: 2px;
  background: var(--color-accent);
}

/* Temporary container for category content before its table is built. */
.inventory-categories {
  padding: 20px;

  border: 1px solid var(--color-border);
  border-radius: 10px;

  background: var(--color-surface);
}

.inventory-categories h3 {
  margin: 0 0 8px;
}

.inventory-categories p {
  margin: 0;
  color: var(--color-muted);
}
.inventory-page__notice {
  margin: 14px 0;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: var(--color-text-muted);
  background: var(--color-surface);
}

.inventory-page__notice--error {
  border-color: rgba(220, 38, 38, 0.35);
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.55);
}

[data-theme="dark"] .inventory-page__notice--error {
  color: #fca5a5;
  background: rgba(127, 29, 29, 0.2);
}
````

### `frontend/src/pages/InventoryPage.jsx`

````jsx
// React state remembers whether Products or Categories is selected.
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

// Icons used by statistics, tabs, and page action buttons.
import {
  Package,
  CircleCheck,
  TriangleAlert,
  CircleX,
  Download,
  Plus,
  ScanBarcode,
  Tags,
} from "lucide-react";

// Reusable inventory components, temporary data, and stock calculations.
import StatCard from "../components/StatCard";
import InventoryFilters from "../components/InventoryFilters";
import InventoryTable from "../components/InventoryTable";
import CategoryTable from "../components/CategoryTable";
import AddCategoryModal from "../components/AddCategoryModal";
import AddProductModal from "../components/AddProductModal";
import ConfirmDialog from "../components/ConfirmDialog";
import ReviewsModal from "../components/ReviewsModal";
import AdjustStockModal from "../components/AdjustStockModal";
import { useAuth } from "../context/authContextValue";
import { getCategories, removeCategory } from "../services/categoryService";
import { downloadInventoryCsv, getProducts, removeProduct, updateProduct, updateProductStatus } from "../services/productService";
import { getProductStockStatus } from "../utils/inventory";

import "./InventoryPage.css";

function InventoryPage() {
  const [searchParameters, setSearchParameters] = useSearchParams();
  const routeSearch = (searchParameters.get("search") ?? "").trim().toLowerCase();
  const { business, accountError } = useAuth();

  // Products is the default tab when the Inventory page opens.
  const [activeTab, setActiveTab] = useState("products");
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isInventoryLoading, setIsInventoryLoading] = useState(true);
  const [inventoryError, setInventoryError] = useState(null);
  const [isAddCategoryOpen, setIsAddCategoryOpen] = useState(false);
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [reviewProduct, setReviewProduct] = useState(null);
  const [stockAdjustment, setStockAdjustment] = useState(null);
  const [editingProduct, setEditingProduct] = useState(null);
  const [editingCategory, setEditingCategory] = useState(null);
  const [removalTarget, setRemovalTarget] = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [inventoryFilters, setInventoryFilters] = useState({});
  const [inventoryRefreshKey, setInventoryRefreshKey] = useState(0);

  // Reset local and URL filters, then reload the source data for a clean table.
  function resetInventoryFilters() {
    setInventoryFilters({});
    setSearchParameters({}, { replace: true });
    setInventoryRefreshKey((currentKey) => currentKey + 1);
  }

  useEffect(() => {
    let requestIsCurrent = true;

    async function loadInventory() {
      if (!business?.id) {
        setProducts([]);
        setCategories([]);
        setIsInventoryLoading(false);
        return;
      }

      setIsInventoryLoading(true);
      setInventoryError(null);

      try {
        const [productRecords, categoryResponse] = await Promise.all([
          getProducts(business.id),
          getCategories(business.id),
        ]);

        if (requestIsCurrent) {
          setProducts(productRecords);
          setCategories(categoryResponse.categories.filter((category) => category.status === "active"));
        }
      } catch (error) {
        console.error("Inventory could not be loaded:", error);

        if (requestIsCurrent) {
          setInventoryError(error);
          setProducts([]);
          setCategories([]);
        }
      } finally {
        if (requestIsCurrent) {
          setIsInventoryLoading(false);
        }
      }
    }

    loadInventory();

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id, inventoryRefreshKey]);

  const inventoryStats = useMemo(
    () => [
      {
        label: "All Items",
        value: products.length,
        icon: Package,
        tone: "blue",
      },
      {
        label: "In Stock",
        value: products.filter(
          (product) => getProductStockStatus(product) === "in-stock",
        ).length,
        icon: CircleCheck,
        tone: "green",
      },
      {
        label: "Low Stock",
        value: products.filter(
          (product) => getProductStockStatus(product) === "low-stock",
        ).length,
        icon: TriangleAlert,
        tone: "orange",
      },
      {
        label: "Out of Stock",
        value: products.filter(
          (product) => getProductStockStatus(product) === "out-of-stock",
        ).length,
        icon: CircleX,
        tone: "red",
      },
    ],
    [products],
  );

  const categoryStats = useMemo(() => {
    const categoryStock = categories.map((category) => ({
      ...category,
      stock: products
        .filter((product) => product.categoryId === category.id)
        .reduce((total, product) => total + product.stock, 0),
    }));
    const topCategory = categoryStock.reduce(
      (currentTop, category) =>
        category.stock > currentTop.stock ? category : currentTop,
      { name: "None", stock: -1 },
    );

    return [
      {
        label: "Total categories",
        value: categories.length,
        icon: Tags,
        tone: "blue",
      },
      {
        label: "Active categories",
        value: categories.filter((category) => category.status === "active")
          .length,
        icon: CircleCheck,
        tone: "green",
      },
      {
        label: "Uncategorized Products",
        value: products.filter((product) => !product.categoryId).length,
        icon: TriangleAlert,
        tone: "orange",
      },
      {
        label: "Top Category",
        value: topCategory.name,
        icon: Tags,
        tone: "blue",
      },
    ];
  }, [categories, products]);

  const visibleProducts = useMemo(() => {
    const searchText = (
      routeSearch || inventoryFilters.searchProduct || ""
    ).trim().toLowerCase();

    return products.filter((product) => {
      const matchesSearch =
        !searchText ||
        [
          product.name,
          product.sku,
          product.barcode,
          ...(product.sizes ?? []).flatMap((size) => [size.sku, size.barcode]),
        ].some((value) => String(value ?? "").toLowerCase().includes(searchText));
      const matchesCategory =
        !inventoryFilters.category ||
        product.categoryId === inventoryFilters.category;
      const matchesStock =
        !inventoryFilters.stockStatus ||
        getProductStockStatus(product) === inventoryFilters.stockStatus;

      return matchesSearch && matchesCategory && matchesStock;
    });
  }, [inventoryFilters, products, routeSearch]);

  async function confirmRemoval() {
    if (!removalTarget || !business?.id) return;
    setIsRemoving(true);
    try {
      if (removalTarget.type === "product") {
        await removeProduct(business.id, removalTarget.record.id);
        setProducts((current) => current.filter((product) => product.id !== removalTarget.record.id));
      } else {
        await removeCategory(business.id, removalTarget.record.id);
        setCategories((current) => current.filter((category) => category.id !== removalTarget.record.id));
      }
      setRemovalTarget(null);
    } catch (error) {
      setInventoryError(error);
    } finally {
      setIsRemoving(false);
    }
  }

  function handleExportInventory() {
    if (isExporting) return;
    setIsExporting(true);
    try {
      downloadInventoryCsv(visibleProducts);
    } finally {
      setIsExporting(false);
    }
  }

  function handleExportSelected(selectedIds) {
    const selectedProducts = visibleProducts.filter((product) => selectedIds.includes(product.id));
    downloadInventoryCsv(selectedProducts);
  }

  async function handleBulkStatusChange(selectedIds, status) {
    if (!business?.id) return;
    try {
      const selectedProducts = visibleProducts.filter((product) => selectedIds.includes(product.id));
      const updatedProducts = await Promise.all(
        selectedProducts.map((product) => updateProductStatus(business.id, product.id, status)),
      );
      setProducts((currentProducts) =>
        currentProducts.map((product) =>
          updatedProducts.find((updated) => updated.id === product.id) ?? product,
        ),
      );
    } catch (error) {
      setInventoryError(error);
    }
  }

  async function handleBulkCategoryChange(selectedIds, categoryId) {
    if (!business?.id || !categoryId) return;
    try {
      const selectedProducts = visibleProducts.filter((product) => selectedIds.includes(product.id));
      const updatedProducts = await Promise.all(
        selectedProducts.map((product) => updateProduct(business.id, product.id, { categoryId })),
      );
      setProducts((currentProducts) => currentProducts.map((product) => updatedProducts.find((updated) => updated.id === product.id) ?? product));
    } catch (error) {
      setInventoryError(error);
    }
  }

  return (
    <main className="dashboard">
      <div className="inventory-page__heading">
        <h2>Product Inventory</h2>

{/* inventory page buttons starts here*/}

{activeTab === "products" && (
        <>
        <div className="inventory-page__actions">
          <button type="button">
            <ScanBarcode size={18} aria-hidden="true" />
            Scan Barcode
          </button>
          <button type="button" onClick={handleExportInventory} disabled={isExporting}>
            <Download size={18} aria-hidden="true" />
            {isExporting ? "Exporting..." : "Export Inventory"}
          </button>
          <button
            className="inventory-page__add-button"
            type="button"
            onClick={() => setIsAddProductOpen(true)}
            disabled={!business?.id}
          >
            <Plus size={18} aria-hidden="true" />
            Add Product
          </button>
        </div>
        </>
)}

{activeTab === "categories" && (
        <>
        <div className="inventory-page__actions">
          <button
            className="inventory-page__add-button"
            type="button"
            onClick={() => setIsAddCategoryOpen(true)}
            disabled={!business?.id}
          >
            <Plus size={18} aria-hidden="true" />
            Add Category
          </button>
        </div>
        </>
)}

{/* inventory page buttons ends here*/}

      </div>

      <p className="inventory-page__description">
        Manage products, sizes, stock levels, SKUs and barcodes.
      </p>

      {(accountError || inventoryError) && (
        <p className="inventory-page__notice inventory-page__notice--error" role="alert">
          Inventory data could not be loaded from the Vendly API. Start the
          Flask server and check its Firebase Admin configuration.
        </p>
      )}

      {isInventoryLoading && (
        <p className="inventory-page__notice" role="status">
          Loading inventory...
        </p>
      )}

{/* Inventory dashboard starts here */}

{activeTab === "products" && (
      <>
      <section aria-label="Inventory dashboard">
        <div className="stats-grid">
          {inventoryStats.map((stat) => (
            <StatCard
              key={stat.label}
              label={stat.label}
              value={stat.value}
              icon={stat.icon}
              tone={stat.tone}
            />
          ))}
        </div>
      </section>
      </>
)}

{activeTab === "categories" && (
      <>
      <section aria-label="Inventory dashboard">
        <div className="stats-grid">
          {categoryStats.map((stat) => (
            <StatCard
              key={stat.label}
              label={stat.label}
              value={stat.value}
              icon={stat.icon}
              tone={stat.tone}
            />
          ))}
        </div>
      </section>
      </>
)}

{/* Inventory dashboard ends here */}

{/* Tabs allow the same Inventory page to switch between two sections. */}

<nav
  className="inventory-tabs"
  role="tablist"
  aria-label="Inventory sections"
>
  <button
    type="button"
    role="tab"
    aria-selected={activeTab === "products"}
    className={`inventory-tabs__button ${
      activeTab === "products"
        ? "inventory-tabs__button--active"
        : ""
    }`}
    onClick={() => setActiveTab("products")}
  >
    <Package size={17} aria-hidden="true" />
    Products
  </button>

  <button
    type="button"
    role="tab"
    aria-selected={activeTab === "categories"}
    className={`inventory-tabs__button ${
      activeTab === "categories"
        ? "inventory-tabs__button--active"
        : ""
    }`}
    onClick={() => setActiveTab("categories")}
  >
    <Tags size={17} aria-hidden="true" />
    Categories
  </button>
</nav>


{/* Product filters and table are rendered only while Products is active. */}
{activeTab === "products" && (
  <>
    <InventoryFilters
      categories={categories}
      onApply={setInventoryFilters}
      onReset={resetInventoryFilters}
    />
    <InventoryTable
      products={visibleProducts}
      onViewReviews={setReviewProduct}
      onEditProduct={setEditingProduct}
      onRemoveProduct={(product) => setRemovalTarget({ type: "product", record: product })}
      onChangeStatus={handleBulkStatusChange}
      categories={categories}
      onChangeCategory={handleBulkCategoryChange}
      onExportSelected={handleExportSelected}
      onAdjustStock={(product, variantId) =>
        setStockAdjustment({ product, variantId })
      }
    />
  </>
)}

{/* Temporary category content shown while Categories is active. */}
{activeTab === "categories" && (
  <CategoryTable categories={categories} products={products} onEditCategory={setEditingCategory} onRemoveCategory={(category) => setRemovalTarget({ type: "category", record: category })} />
)}

      <AddCategoryModal
        isOpen={isAddCategoryOpen}
        businessId={business?.id}
        onClose={() => setIsAddCategoryOpen(false)}
        onCreated={(category) =>
          setCategories((currentCategories) =>
            [...currentCategories, category].sort(
              (first, second) => first.sortOrder - second.sortOrder,
            ),
          )
        }
      />

      <AddCategoryModal
        isOpen={Boolean(editingCategory)}
        businessId={business?.id}
        category={editingCategory}
        onClose={() => setEditingCategory(null)}
        onUpdated={(updated) => {
          setCategories((current) => current.map((category) => category.id === updated.id ? updated : category));
          setEditingCategory(null);
        }}
      />

      <AddProductModal
        isOpen={isAddProductOpen}
        businessId={business?.id}
        categories={categories}
        onClose={() => setIsAddProductOpen(false)}
        onCreated={(product) =>
          setProducts((currentProducts) => [product, ...currentProducts])
        }
      />

      <AddProductModal
        isOpen={Boolean(editingProduct)}
        businessId={business?.id}
        product={editingProduct}
        categories={categories}
        onClose={() => setEditingProduct(null)}
        onUpdated={(updated) => {
          setProducts((current) => current.map((product) => product.id === updated.id ? updated : product));
          setEditingProduct(null);
        }}
      />

      <ConfirmDialog
        isOpen={Boolean(removalTarget)}
        title={removalTarget?.type === "product" ? "Remove product?" : "Remove category?"}
        message={`This will archive ${removalTarget?.record?.name ?? "this item"} and hide it from active lists.`}
        isWorking={isRemoving}
        onCancel={() => setRemovalTarget(null)}
        onConfirm={confirmRemoval}
      />

      <ReviewsModal
        businessId={business?.id}
        product={reviewProduct}
        onClose={() => setReviewProduct(null)}
        onApproved={(productId) =>
          setProducts((current) =>
            current.map((product) =>
              product.id === productId
                ? {
                    ...product,
                    approvedReviews: (product.approvedReviews ?? 0) + 1,
                    approvedReviewCount: (product.approvedReviewCount ?? 0) + 1,
                  }
                : product,
            ),
          )
        }
      />

      <AdjustStockModal
        businessId={business?.id}
        product={stockAdjustment?.product ?? null}
        initialVariantId={stockAdjustment?.variantId}
        onClose={() => setStockAdjustment(null)}
        onUpdated={(updatedProduct) =>
          setProducts((currentProducts) =>
            currentProducts.map((product) =>
              product.id === updatedProduct.id ? updatedProduct : product,
            ),
          )
        }
      />
    </main>
  );
}

export default InventoryPage;
````

### `frontend/src/utils/inventory.js`

````javascript
// Return direct stock for simple products or add all size stocks together.
export function getProductStock(product) {
  if (!product.hasSizes) {
    return product.stock;
  }

  return product.sizes.reduce(
    (totalStock, sizeOption) => totalStock + sizeOption.stock,
    0,
  );
}

// Convert a stock number into one of the three status names used by the UI.
export function getStockStatus(stock, lowStockThreshold = 5) {
  if (stock === 0) {
    return "out-of-stock";
  }

  if (stock <= lowStockThreshold) {
    return "low-stock";
  }

  return "in-stock";
}

// Calculate a complete product's status using its own low-stock threshold.
export function getProductStockStatus(product) {
  return getStockStatus(
    getProductStock(product),
    product.lowStockThreshold,
  );
}
````

## Feature 11 source — Customers and fraud risk

Files in this feature: 4

### `backend/app/api/customers.py`

````python
from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.customer_service import (
    create_customer,
    get_customer,
    list_customers,
    update_customer,
)


customers_blueprint = Blueprint("customers", __name__, url_prefix="/api/v1")


@customers_blueprint.get("/businesses/<business_id>/customers")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_customers(business_id):
    customers = list_customers(
        get_firestore_client(),
        business_id,
        phone=request.args.get("phone"),
        search=request.args.get("search"),
    )
    return jsonify({"customers": customers})


@customers_blueprint.post("/businesses/<business_id>/customers")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", "support", permission="customers:manage")
def add_customer(business_id):
    customer = create_customer(
        get_firestore_client(),
        business_id,
        get_json_object(),
    )
    return jsonify({"customer": customer}), 201


@customers_blueprint.get("/businesses/<business_id>/customers/<customer_id>")
@require_firebase_user
@require_business_member(permission="customers:read")
def get_customer_by_id(business_id, customer_id):
    customer = get_customer(get_firestore_client(), business_id, customer_id)
    return jsonify({"customer": customer})


@customers_blueprint.patch("/businesses/<business_id>/customers/<customer_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", "support", permission="customers:manage")
def edit_customer(business_id, customer_id):
    customer = update_customer(
        get_firestore_client(),
        business_id,
        customer_id,
        get_json_object(),
    )
    return jsonify({"customer": customer})
````

### `backend/app/services/customer_service.py`

````python
import re

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.text import optional_text, required_text


def normalize_sri_lankan_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))

    if digits.startswith("0094"):
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        digits = f"94{digits[1:]}"
    elif len(digits) == 9 and digits.startswith("7"):
        digits = f"94{digits}"

    if not re.fullmatch(r"947\d{8}", digits):
        raise ValueError(
            "Phone number must be a valid Sri Lankan mobile number.",
        )

    return digits


def validate_address(value):
    if not isinstance(value, dict):
        raise ValueError("Delivery address must be an object.")

    return {
        "line1": required_text(value.get("line1"), "Address line", 200),
        "line2": optional_text(value.get("line2"), 200),
        "city": required_text(value.get("city"), "City", 100),
        "district": required_text(value.get("district"), "District", 100),
        "postalCode": optional_text(value.get("postalCode"), 20),
        "country": "Sri Lanka",
    }


def validate_customer(payload):
    try:
        name = required_text(payload.get("name"), "Customer name", 160)
        normalized_phone = normalize_sri_lankan_phone(payload.get("phoneNumber"))
        secondary_phone_value = optional_text(payload.get("secondaryPhoneNumber"), 30)
        normalized_secondary_phone = (
            normalize_sri_lankan_phone(secondary_phone_value)
            if secondary_phone_value
            else ""
        )
        email = optional_text(payload.get("email"), 254).lower()
        address = validate_address(payload.get("address"))
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    return {
        "name": name,
        "normalizedPhone": normalized_phone,
        "normalizedSecondaryPhone": normalized_secondary_phone,
        "email": email,
        "address": address,
    }


def list_customers(database, business_id, phone=None, search=None):
    collection = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
    )

    if phone:
        try:
            normalized_phone = normalize_sri_lankan_phone(phone)
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

        query = collection.where(
            filter=FieldFilter("normalizedPhone", "==", normalized_phone),
        ).limit(1)
        return [serialize_snapshot(snapshot) for snapshot in query.stream()]

    customers = [
        serialize_snapshot(snapshot)
        for snapshot in collection.order_by("name").limit(200).stream()
    ]

    if search:
        search_text = search.strip().casefold()
        customers = [
            customer
            for customer in customers
            if search_text in customer.get("name", "").casefold()
            or search_text in customer.get("normalizedPhone", "")
        ]

    return customers


def get_customer(database, business_id, customer_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
        .document(customer_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("customer_not_found", "Customer not found.", 404)

    return serialize_snapshot(snapshot)


def create_customer(database, business_id, payload):
    customer = validate_customer(payload)
    business_reference = database.collection("businesses").document(business_id)
    customer_reference = business_reference.collection("customers").document()
    phone_reference = business_reference.collection("phoneRegistry").document(
        customer["normalizedPhone"],
    )
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        phone_snapshot = phone_reference.get(transaction=current_transaction)

        if phone_snapshot.exists:
            raise ApiError(
                "customer_phone_already_exists",
                "A customer with this phone number already exists.",
                409,
                {"customerId": phone_snapshot.to_dict().get("customerId")},
            )

        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.set(
            customer_reference,
            {
                "name": customer["name"],
                "normalizedPhone": customer["normalizedPhone"],
                "normalizedSecondaryPhone": customer["normalizedSecondaryPhone"],
                "email": customer["email"],
                "addresses": [customer["address"]],
                "defaultAddress": customer["address"],
                "tags": ["new-customer"],
                "privateNotes": "",
                "completedOrderCount": 0,
                "returnedOrderCount": 0,
                "totalSpentMinor": 0,
                "riskLevel": "low",
                "status": "active",
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            phone_reference,
            {
                "customerId": customer_reference.id,
                "normalizedPhone": customer["normalizedPhone"],
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return get_customer(database, business_id, customer_reference.id)


def update_customer(database, business_id, customer_id, payload):
    customer_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("customers")
        .document(customer_id)
    )
    snapshot = customer_reference.get()

    if not snapshot.exists:
        raise ApiError("customer_not_found", "Customer not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP}

    try:
        if "name" in payload:
            changes["name"] = required_text(payload.get("name"), "Customer name", 160)
        if "email" in payload:
            changes["email"] = optional_text(payload.get("email"), 254).lower()
        if "address" in payload:
            address = validate_address(payload.get("address"))
            changes["defaultAddress"] = address
            changes["addresses"] = firestore.ArrayUnion([address])
        if "privateNotes" in payload:
            changes["privateNotes"] = optional_text(
                payload.get("privateNotes"),
                2000,
            )
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if "status" in payload:
        if payload.get("status") not in {"active", "blocked", "archived"}:
            raise ApiError(
                "validation_error",
                "Customer status must be active, blocked or archived.",
                422,
            )
        changes["status"] = payload["status"]

    customer_reference.update(changes)
    return get_customer(database, business_id, customer_id)
````

### `frontend/src/pages/CustomersPage.jsx`

````jsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import { getCustomers } from "../services/customerService";

import "./ManagementPage.css";

function CustomersPage() {
  const [searchParameters] = useSearchParams();
  const routeSearch = (searchParameters.get("search") ?? "").trim().toLowerCase();
  const { business } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const visibleCustomers = routeSearch
    ? customers.filter((customer) =>
        [customer.name, customer.normalizedPhone, customer.email].some((value) =>
          String(value ?? "").toLowerCase().includes(routeSearch),
        ),
      )
    : customers;

  useEffect(() => {
    if (!business?.id) {
      setIsLoading(false);
      return;
    }

    getCustomers(business.id)
      .then(setCustomers)
      .catch((error) => setErrorMessage(error.message))
      .finally(() => setIsLoading(false));
  }, [business?.id]);

  return (
    <main className="dashboard">
      <div className="dashboard__intro">
        <h2>Customer Management</h2>
        <p>Review customer loyalty, order history and return risk.</p>
      </div>

      {isLoading && <p className="management-page__notice">Loading customers...</p>}
      {errorMessage && <p className="management-page__notice" role="alert">{errorMessage}</p>}

      <table className="management-table">
        <thead><tr><th>Customer</th><th>Phone</th><th>Completed</th><th>Returned</th><th>Total spent</th><th>Risk</th><th>Status</th></tr></thead>
        <tbody>
          {visibleCustomers.map((customer) => (
            <tr key={customer.id}>
              <td><strong>{customer.name}</strong><br /><small>{customer.email || "No email"}</small></td>
              <td>+{customer.normalizedPhone}</td>
              <td>{customer.completedOrderCount}</td>
              <td>{customer.returnedOrderCount}</td>
              <td>LKR {((customer.totalSpentMinor ?? 0) / 100).toLocaleString("en-LK")}</td>
              <td><span className={`management-table__badge management-table__badge--${customer.riskLevel}`}>{customer.riskLevel}</span></td>
              <td>{customer.status}</td>
            </tr>
          ))}
          {!isLoading && visibleCustomers.length === 0 && <tr><td colSpan={7}>No matching customers found.</td></tr>}
        </tbody>
      </table>
    </main>
  );
}

export default CustomersPage;
````

### `frontend/src/services/customerService.js`

````javascript
import { apiRequest } from "./apiClient";

export async function getCustomers(businessId, search = "") {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const response = await apiRequest(`/businesses/${businessId}/customers${query}`);
  return response.customers;
}

export async function createCustomer(businessId, customerData) {
  const response = await apiRequest(`/businesses/${businessId}/customers`, {
    method: "POST",
    body: customerData,
  });
  return response.customer;
}

export async function updateCustomer(businessId, customerId, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/customers/${customerId}`,
    {
      method: "PATCH",
      body: changes,
    },
  );
  return response.customer;
}
````

## Feature 12 source — Couriers and delivery

Files in this feature: 5

### `backend/app/api/couriers.py`

````python
from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.courier_service import (
    create_courier,
    list_couriers,
    recommend_couriers,
    update_courier,
)
from app.services.numbers import non_negative_integer


couriers_blueprint = Blueprint("couriers", __name__, url_prefix="/api/v1")


@couriers_blueprint.get("/businesses/<business_id>/couriers")
@require_firebase_user
@require_business_member(permission="couriers:read")
def get_couriers(business_id):
    couriers = list_couriers(get_firestore_client(), business_id)
    return jsonify({"couriers": couriers})


@couriers_blueprint.post("/businesses/<business_id>/couriers")
@require_firebase_user
@require_business_member("owner", "admin", permission="couriers:manage")
def add_courier(business_id):
    courier = create_courier(
        get_firestore_client(),
        business_id,
        get_json_object(),
    )
    return jsonify({"courier": courier}), 201


@couriers_blueprint.patch("/businesses/<business_id>/couriers/<courier_id>")
@require_firebase_user
@require_business_member("owner", "admin", permission="couriers:manage")
def edit_courier(business_id, courier_id):
    courier = update_courier(
        get_firestore_client(),
        business_id,
        courier_id,
        get_json_object(),
    )
    return jsonify({"courier": courier})


@couriers_blueprint.post("/businesses/<business_id>/couriers/recommend")
@require_firebase_user
@require_business_member(permission="couriers:read")
def recommend_for_order(business_id):
    payload = get_json_object()

    try:
        weight_grams = non_negative_integer(
            payload.get("totalWeightGrams"),
            "Total weight",
        )
        if weight_grams == 0:
            raise ValueError("Total weight must be greater than zero.")
    except ValueError as error:
        return jsonify(
            {
                "error": {
                    "code": "validation_error",
                    "message": str(error),
                },
            },
        ), 422

    recommendations = recommend_couriers(
        get_firestore_client(),
        business_id,
        weight_grams,
        payload.get("district"),
    )
    return jsonify({"recommendations": recommendations})
````

### `backend/app/services/courier_service.py`

````python
from decimal import Decimal, ROUND_CEILING

from firebase_admin import firestore

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.numbers import money_to_minor_units, non_negative_integer
from app.services.text import optional_text, required_text, slugify


def normalize_district(value):
    district = required_text(value, "District", 100)
    return slugify(district)


def calculate_delivery_fee(courier, total_weight_grams, district):
    if total_weight_grams <= 0:
        raise ValueError("Order weight must be greater than zero.")

    first_kg_price = courier.get("firstKgPriceMinor", 0)
    extra_kg_price = courier.get("extraKgPriceMinor", 0)
    extra_grams = max(total_weight_grams - 1000, 0)
    extra_kilograms = int(
        (Decimal(extra_grams) / Decimal(1000)).to_integral_value(
            rounding=ROUND_CEILING,
        ),
    )
    district_key = normalize_district(district)
    district_surcharge = courier.get("districtSurchargesMinor", {}).get(
        district_key,
        0,
    )

    return first_kg_price + (extra_kilograms * extra_kg_price) + district_surcharge


def courier_recommendation_score(courier, delivery_fee_minor, district):
    """Score active couriers using price and recorded delivery quality."""
    success_rate = float(courier.get("successRate", 0.8))
    return_rate = float(courier.get("returnRate", 0))
    district_key = normalize_district(district)
    district_issue_count = courier.get("districtIssueCounts", {}).get(district_key, 0)
    price_penalty = delivery_fee_minor / 100000

    return (success_rate * 100) - (return_rate * 60) - (district_issue_count * 4) - price_penalty


def validate_courier(payload):
    try:
        name = required_text(payload.get("name"), "Courier name", 160)
        code = required_text(payload.get("code"), "Courier code", 40).upper()
        first_kg_price_minor = money_to_minor_units(
            payload.get("firstKgPrice"),
            "First-kilogram price",
            allow_zero=False,
        )
        extra_kg_price_minor = money_to_minor_units(
            payload.get("extraKgPrice"),
            "Extra-kilogram price",
        )
        average_delivery_days = non_negative_integer(
            payload.get("averageDeliveryDays", 3),
            "Average delivery days",
        )
        tracking_url_template = optional_text(
            payload.get("trackingUrlTemplate"),
            1000,
        )
        waybill_prefix = optional_text(payload.get("waybillPrefix", "VWB"), 40) or "VWB"
        waybill_start = non_negative_integer(payload.get("waybillStart", 1), "Waybill range start")
        waybill_end = non_negative_integer(payload.get("waybillEnd", 999999), "Waybill range end")
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    raw_surcharges = payload.get("districtSurcharges", {})

    if waybill_end < waybill_start:
        raise ApiError("validation_error", "Waybill range end must be greater than or equal to its start.", 422)

    if not isinstance(raw_surcharges, dict):
        raise ApiError(
            "validation_error",
            "District surcharges must be an object.",
            422,
        )

    district_surcharges_minor = {}

    for district, amount in raw_surcharges.items():
        try:
            district_key = normalize_district(district)
            district_surcharges_minor[district_key] = money_to_minor_units(
                amount,
                f"Surcharge for {district}",
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

    return {
        "name": name,
        "code": code,
        "firstKgPriceMinor": first_kg_price_minor,
        "extraKgPriceMinor": extra_kg_price_minor,
        "averageDeliveryDays": average_delivery_days,
        "trackingUrlTemplate": tracking_url_template,
        "districtSurchargesMinor": district_surcharges_minor,
        "waybillPrefix": waybill_prefix,
        "waybillStart": waybill_start,
        "waybillEnd": waybill_end,
    }


def list_couriers(database, business_id, active_only=False):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .order_by("name")
        .stream()
    )
    couriers = [serialize_snapshot(snapshot) for snapshot in snapshots]

    if active_only:
        couriers = [courier for courier in couriers if courier.get("status") == "active"]

    return couriers


def get_courier(database, business_id, courier_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .document(courier_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("courier_not_found", "Courier not found.", 404)

    return serialize_snapshot(snapshot)


def create_courier(database, business_id, payload):
    courier = validate_courier(payload)
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .document()
    )
    timestamp = firestore.SERVER_TIMESTAMP
    reference.set(
        {
            **courier,
            "successRate": 0.8,
            "returnRate": 0,
            "deliveredOrderCount": 0,
            "returnedOrderCount": 0,
            "districtIssueCounts": {},
            "status": "active",
            "nextWaybillSequence": courier.get("waybillStart", 1),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        },
    )
    return get_courier(database, business_id, reference.id)


def update_courier(database, business_id, courier_id, payload):
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("couriers")
        .document(courier_id)
    )

    snapshot = reference.get()

    if not snapshot.exists:
        raise ApiError("courier_not_found", "Courier not found.", 404)

    current = snapshot.to_dict()
    merged_payload = {
        "name": current.get("name"),
        "code": current.get("code"),
        "firstKgPrice": current.get("firstKgPriceMinor", 0) / 100,
        "extraKgPrice": current.get("extraKgPriceMinor", 0) / 100,
        "averageDeliveryDays": current.get("averageDeliveryDays", 3),
        "trackingUrlTemplate": current.get("trackingUrlTemplate", ""),
        "waybillPrefix": current.get("waybillPrefix", "VWB"),
        "waybillStart": current.get("waybillStart", 1),
        "waybillEnd": current.get("waybillEnd", 999999),
        "districtSurcharges": {
            district: amount / 100
            for district, amount in current.get("districtSurchargesMinor", {}).items()
        },
        **payload,
    }
    changes = validate_courier(merged_payload)

    if "status" in payload:
        if payload.get("status") not in {"active", "inactive"}:
            raise ApiError(
                "validation_error",
                "Courier status must be active or inactive.",
                422,
            )
        changes["status"] = payload["status"]

    changes["updatedAt"] = firestore.SERVER_TIMESTAMP
    reference.update(changes)
    return get_courier(database, business_id, courier_id)


def recommend_couriers(database, business_id, total_weight_grams, district):
    recommendations = []

    for courier in list_couriers(database, business_id, active_only=True):
        delivery_fee = calculate_delivery_fee(courier, total_weight_grams, district)
        recommendations.append(
            {
                "courier": courier,
                "deliveryFeeMinor": delivery_fee,
                "score": round(
                    courier_recommendation_score(courier, delivery_fee, district),
                    3,
                ),
            },
        )

    return sorted(recommendations, key=lambda item: item["score"], reverse=True)
````

### `frontend/src/components/AddCourierModal.jsx`

````jsx
import { useEffect, useState } from "react";

import { createCourier } from "../services/courierService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";

function AddCourierModal({ isOpen, businessId, onClose, onCreated }) {
  const [formData, setFormData] = useState({
    name: "",
    code: "",
    firstKgPrice: "450",
    extraKgPrice: "100",
    averageDeliveryDays: "3",
    trackingUrlTemplate: "",
    surchargeDistrict: "",
    surchargeAmount: "0",
    waybillPrefix: "VWB",
    waybillStart: "1",
    waybillEnd: "999999",
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) setErrorMessage("");
  }, [isOpen]);

  function updateField(event) {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage("");

    try {
      const districtSurcharges = formData.surchargeDistrict.trim()
        ? { [formData.surchargeDistrict.trim()]: formData.surchargeAmount }
        : {};
      const courier = await createCourier(businessId, {
        name: formData.name,
        code: formData.code,
        firstKgPrice: formData.firstKgPrice,
        extraKgPrice: formData.extraKgPrice,
        averageDeliveryDays: formData.averageDeliveryDays,
        trackingUrlTemplate: formData.trackingUrlTemplate,
        districtSurcharges,
        waybillPrefix: formData.waybillPrefix,
        waybillStart: formData.waybillStart,
        waybillEnd: formData.waybillEnd,
      });
      onCreated(courier);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell
      isOpen={isOpen}
      title="Add Courier"
      description="Configure weight-based delivery pricing for one courier."
      onClose={onClose}
    >
      <form className="inventory-form" onSubmit={handleSubmit}>
        <div className="inventory-form__two-columns">
          <label>Courier name<input name="name" value={formData.name} onChange={updateField} required /></label>
          <label>Courier code<input name="code" value={formData.code} onChange={updateField} placeholder="KMB" required /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>First 1 kg price (LKR)<input name="firstKgPrice" type="number" min="0.01" step="0.01" value={formData.firstKgPrice} onChange={updateField} required /></label>
          <label>Each extra 1 kg (LKR)<input name="extraKgPrice" type="number" min="0" step="0.01" value={formData.extraKgPrice} onChange={updateField} required /></label>
        </div>
        <label>Average delivery days<input name="averageDeliveryDays" type="number" min="0" step="1" value={formData.averageDeliveryDays} onChange={updateField} required /></label>
        <label>Tracking URL template (optional)<input name="trackingUrlTemplate" value={formData.trackingUrlTemplate} onChange={updateField} placeholder="https://courier.lk/track/{waybill}" /></label>
        <div className="inventory-form__two-columns">
          <label>Waybill prefix<input name="waybillPrefix" value={formData.waybillPrefix} onChange={updateField} placeholder="VWB" /></label>
          <label>Waybill range<input name="waybillStart" type="number" min="1" value={formData.waybillStart} onChange={updateField} placeholder="Start" /></label>
        </div>
        <label>Waybill range end<input name="waybillEnd" type="number" min="1" value={formData.waybillEnd} onChange={updateField} /></label>
        <div className="inventory-form__two-columns">
          <label>District surcharge (optional)<input name="surchargeDistrict" value={formData.surchargeDistrict} onChange={updateField} placeholder="Jaffna" /></label>
          <label>Surcharge amount (LKR)<input name="surchargeAmount" type="number" min="0" step="0.01" value={formData.surchargeAmount} onChange={updateField} /></label>
        </div>
        {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}
        <footer className="inventory-form__footer">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="inventory-form__primary" type="submit" disabled={isSaving}>{isSaving ? "Saving..." : "Add Courier"}</button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default AddCourierModal;
````

### `frontend/src/pages/CouriersPage.jsx`

````jsx
import { useEffect, useState } from "react";
import { Plus, Truck } from "lucide-react";

import AddCourierModal from "../components/AddCourierModal";
import { useAuth } from "../context/authContextValue";
import { getCouriers } from "../services/courierService";

import "./ManagementPage.css";

function money(minor = 0) {
  return `LKR ${(minor / 100).toLocaleString("en-LK")}`;
}

function CouriersPage() {
  const { business } = useAuth();
  const [couriers, setCouriers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [isAddCourierOpen, setIsAddCourierOpen] = useState(false);

  useEffect(() => {
    if (!business?.id) {
      setIsLoading(false);
      return;
    }

    getCouriers(business.id)
      .then(setCouriers)
      .catch((error) => setErrorMessage(error.message))
      .finally(() => setIsLoading(false));
  }, [business?.id]);

  return (
    <main className="dashboard">
      <div className="management-page__heading">
        <div className="dashboard__intro">
          <h2>Couriers & Delivery</h2>
          <p>Manage courier services, weight pricing and delivery quality.</p>
        </div>
        <button className="management-page__primary-button" type="button" onClick={() => setIsAddCourierOpen(true)} disabled={!business?.id}>
          <Plus size={18} /> Add Courier
        </button>
      </div>

      {isLoading && <p className="management-page__notice">Loading couriers...</p>}
      {errorMessage && <p className="management-page__notice" role="alert">{errorMessage}</p>}

      <table className="management-table">
        <thead><tr><th>Courier</th><th>First 1 kg</th><th>Extra 1 kg</th><th>Success</th><th>Returns</th><th>Delivery</th><th>Status</th></tr></thead>
        <tbody>
          {couriers.map((courier) => (
            <tr key={courier.id}>
              <td><Truck size={17} aria-hidden="true" /> <strong>{courier.name}</strong> ({courier.code})</td>
              <td>{money(courier.firstKgPriceMinor)}</td>
              <td>{money(courier.extraKgPriceMinor)}</td>
              <td>{Math.round((courier.successRate ?? 0) * 100)}%</td>
              <td>{Math.round((courier.returnRate ?? 0) * 100)}%</td>
              <td>{courier.averageDeliveryDays} days</td>
              <td><span className="management-table__badge">{courier.status}</span></td>
            </tr>
          ))}
          {!isLoading && couriers.length === 0 && <tr><td colSpan={7}>No couriers configured yet.</td></tr>}
        </tbody>
      </table>

      <AddCourierModal
        isOpen={isAddCourierOpen}
        businessId={business?.id}
        onClose={() => setIsAddCourierOpen(false)}
        onCreated={(courier) => setCouriers((current) => [...current, courier])}
      />
    </main>
  );
}

export default CouriersPage;
````

### `frontend/src/services/courierService.js`

````javascript
import { apiRequest } from "./apiClient";

export async function getCouriers(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/couriers`);
  return response.couriers;
}

export async function createCourier(businessId, courierData) {
  const response = await apiRequest(`/businesses/${businessId}/couriers`, {
    method: "POST",
    body: courierData,
  });
  return response.courier;
}

export async function recommendCouriers(businessId, totalWeightGrams, district) {
  const response = await apiRequest(
    `/businesses/${businessId}/couriers/recommend`,
    {
      method: "POST",
      body: { totalWeightGrams, district },
    },
  );
  return response.recommendations;
}
````

## Feature 13 source — Order creation

Files in this feature: 5

### `backend/app/api/orders.py`

````python
from flask import Blueprint, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.order_service import (
    create_order,
    get_order,
    list_orders,
    update_order_status,
    update_order,
)


orders_blueprint = Blueprint("orders", __name__, url_prefix="/api/v1")


@orders_blueprint.get("/businesses/<business_id>/orders")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_orders(business_id):
    orders = list_orders(
        get_firestore_client(),
        business_id,
        status=request.args.get("status"),
        search=request.args.get("search"),
        date_from=request.args.get("dateFrom"),
        date_to=request.args.get("dateTo"),
        courier_id=request.args.get("courierId"),
    )
    return jsonify({"orders": orders})


@orders_blueprint.post("/businesses/<business_id>/orders")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def add_order(business_id):
    order = create_order(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"order": order}), 201


@orders_blueprint.get("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member(permission="orders:read")
def get_order_by_id(business_id, order_id):
    order = get_order(get_firestore_client(), business_id, order_id)
    return jsonify({"order": order})


@orders_blueprint.patch(
    "/businesses/<business_id>/orders/<order_id>/status",
)
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def change_order_status(business_id, order_id):
    order = update_order_status(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"order": order})


@orders_blueprint.patch("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def edit_order(business_id, order_id):
    order = update_order(
        get_firestore_client(), business_id, order_id,
        g.current_user["uid"], get_json_object(),
    )
    return jsonify({"order": order})


@orders_blueprint.delete("/businesses/<business_id>/orders/<order_id>")
@require_firebase_user
@require_business_member("owner", "admin", "order_manager", permission="orders:manage")
def remove_order(business_id, order_id):
    order = update_order_status(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        {"status": "cancelled", "note": "Removed by seller"},
    )
    return jsonify({"order": order})
````

### `backend/app/services/order_service.py`

````python
from collections import defaultdict
from datetime import datetime, timezone

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.courier_service import (
    calculate_delivery_fee,
    get_courier,
    recommend_couriers,
)
from app.services.customer_service import get_customer, validate_address
from app.services.numbers import money_to_minor_units, non_negative_integer
from app.services.product_service import stock_status
from app.services.text import optional_text, required_text


ALLOWED_PAYMENT_METHODS = {"cod", "paid", "deposit"}
ALLOWED_ORDER_SOURCES = {
    "dashboard",
    "chatbot",
    "whatsapp",
    "facebook",
    "phone",
    "mini-store",
}

STATUS_TRANSITIONS = {
    "needs-confirmation": {"confirmed", "cancelled"},
    "confirmed": {"packed", "cancelled"},
    "packed": {"shipped", "cancelled"},
    "shipped": {"delivered", "returned"},
    "delivered": set(),
    "returned": set(),
    "cancelled": set(),
}


def returned_customer_risk(returned_order_count):
    """Choose the customer risk level and tag after a returned order."""
    if returned_order_count >= 3:
        return "high", "high-return-rate"

    return "medium", "returned-order"


def validate_order_request(payload):
    try:
        customer_id = required_text(payload.get("customerId"), "Customer", 120)
        private_note = optional_text(payload.get("privateNote"), 2000)
        source = optional_text(payload.get("source"), 40) or "dashboard"
        payment_method = optional_text(payload.get("paymentMethod"), 40) or "cod"
        discount_minor = money_to_minor_units(
            payload.get("discountAmount", 0),
            "Discount",
        )
        deposit_minor = money_to_minor_units(
            payload.get("depositAmount", 0),
            "Deposit amount",
        )
        secondary_phone = optional_text(payload.get("secondaryPhoneNumber"), 30)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if source not in ALLOWED_ORDER_SOURCES:
        raise ApiError("validation_error", "Choose a valid order source.", 422)
    if payment_method not in ALLOWED_PAYMENT_METHODS:
        raise ApiError("validation_error", "Choose a valid payment method.", 422)

    raw_items = payload.get("items")

    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError("validation_error", "Add at least one order item.", 422)
    if len(raw_items) > 50:
        raise ApiError(
            "too_many_order_items",
            "An order can contain no more than 50 item rows.",
            422,
        )

    quantities_by_variant = defaultdict(int)

    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            raise ApiError(
                "validation_error",
                f"Order item {index} must be an object.",
                422,
            )

        try:
            variant_id = required_text(
                item.get("variantId"),
                f"Variant in item {index}",
                120,
            )
            quantity = non_negative_integer(
                item.get("quantity"),
                f"Quantity in item {index}",
            )
        except ValueError as error:
            raise ApiError("validation_error", str(error), 422) from error

        if quantity == 0:
            raise ApiError(
                "validation_error",
                f"Quantity in item {index} must be greater than zero.",
                422,
            )

        quantities_by_variant[variant_id] += quantity

    return {
        "customerId": customer_id,
        "items": [
            {"variantId": variant_id, "quantity": quantity}
            for variant_id, quantity in quantities_by_variant.items()
        ],
        "courierId": optional_text(payload.get("courierId"), 120),
        "deliveryAddress": payload.get("deliveryAddress"),
        "discountMinor": discount_minor,
        "depositMinor": deposit_minor,
        "secondaryPhoneNumber": secondary_phone,
        "paymentMethod": payment_method,
        "source": source,
        "privateNote": private_note,
        "assignedStaffUid": optional_text(payload.get("assignedStaffUid"), 120),
        "customerUid": optional_text(payload.get("customerUid"), 128),
    }


def filter_orders(
    orders,
    status=None,
    search=None,
    date_from=None,
    date_to=None,
    courier_id=None,
):
    if status:
        orders = [order for order in orders if order.get("fulfilmentStatus") == status]
    if courier_id:
        orders = [order for order in orders if order.get("courierId") == courier_id]
    if date_from:
        orders = [
            order
            for order in orders
            if str(order.get("createdAt", ""))[:10] >= date_from
        ]
    if date_to:
        orders = [
            order
            for order in orders
            if str(order.get("createdAt", ""))[:10] <= date_to
        ]
    if search:
        search_text = search.strip().casefold()
        orders = [
            order
            for order in orders
            if search_text in order.get("orderNumber", "").casefold()
            or search_text
            in order.get("customerSnapshot", {}).get("name", "").casefold()
            or search_text
            in order.get("customerSnapshot", {}).get("normalizedPhone", "")
            or search_text in order.get("waybillNumber", "").casefold()
            or any(
                search_text in item.get("name", "").casefold()
                or search_text in item.get("sku", "").casefold()
                or search_text in item.get("barcode", "").casefold()
                for item in order.get("items", [])
            )
        ]

    return orders


def list_orders(
    database,
    business_id,
    status=None,
    search=None,
    date_from=None,
    date_to=None,
    courier_id=None,
):
    collection = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
    )
    orders = [
        serialize_snapshot(snapshot)
        for snapshot in collection.order_by("createdAt", direction="DESCENDING")
        .limit(200)
        .stream()
    ]

    return filter_orders(
        orders,
        status=status,
        search=search,
        date_from=date_from,
        date_to=date_to,
        courier_id=courier_id,
    )


def get_order(database, business_id, order_id):
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .document(order_id)
        .get()
    )

    if not snapshot.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    return serialize_snapshot(snapshot)


def choose_courier(database, business_id, courier_id, weight_grams, district):
    if courier_id:
        courier = get_courier(database, business_id, courier_id)

        if courier.get("status") != "active":
            raise ApiError("invalid_courier", "Choose an active courier.", 422)

        return courier

    recommendations = recommend_couriers(
        database,
        business_id,
        weight_grams,
        district,
    )

    if not recommendations:
        raise ApiError(
            "courier_required",
            "Add an active courier before creating an order.",
            422,
        )

    return recommendations[0]["courier"]


def create_order(database, business_id, uid, payload):
    request_data = validate_order_request(payload)
    business_reference = database.collection("businesses").document(business_id)
    customer_reference = business_reference.collection("customers").document(
        request_data["customerId"],
    )
    customer = get_customer(database, business_id, request_data["customerId"])

    try:
        delivery_address = validate_address(
            request_data["deliveryAddress"] or customer.get("defaultAddress"),
        )
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    variant_collection = business_reference.collection("productVariants")
    preliminary_variants = []
    preliminary_weight = 0

    for item in request_data["items"]:
        snapshot = variant_collection.document(item["variantId"]).get()

        if not snapshot.exists:
            raise ApiError("variant_not_found", "A selected product is unavailable.", 404)

        variant = snapshot.to_dict()
        preliminary_variants.append(variant)
        preliminary_weight += variant.get("weightGrams", 0) * item["quantity"]

    courier = choose_courier(
        database,
        business_id,
        request_data["courierId"],
        preliminary_weight,
        delivery_address["district"],
    )
    courier_reference = business_reference.collection("couriers").document(courier["id"])
    order_reference = business_reference.collection("orders").document()
    waybill_reference = business_reference.collection("waybills").document(order_reference.id)
    notification_reference = business_reference.collection("notifications").document()
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        business_snapshot = business_reference.get(transaction=current_transaction)
        customer_snapshot = customer_reference.get(transaction=current_transaction)
        courier_snapshot = courier_reference.get(transaction=current_transaction)

        if not business_snapshot.exists:
            raise ApiError("business_not_found", "Business not found.", 404)
        if not customer_snapshot.exists:
            raise ApiError("customer_not_found", "Customer not found.", 404)
        if customer_snapshot.to_dict().get("status") != "active":
            raise ApiError("customer_blocked", "This customer is not active.", 409)
        if not courier_snapshot.exists or courier_snapshot.to_dict().get("status") != "active":
            raise ApiError("invalid_courier", "Choose an active courier.", 422)

        variant_snapshots = {}
        product_snapshots = {}

        for item in request_data["items"]:
            variant_reference = variant_collection.document(item["variantId"])
            variant_snapshot = variant_reference.get(transaction=current_transaction)

            if not variant_snapshot.exists:
                raise ApiError(
                    "variant_not_found",
                    "A selected product is unavailable.",
                    404,
                )

            variant = variant_snapshot.to_dict()

            if variant.get("status") != "active":
                raise ApiError("inactive_variant", "A selected product is inactive.", 409)
            if variant.get("stockAvailable", 0) < item["quantity"]:
                raise ApiError(
                    "insufficient_stock",
                    f"Only {variant.get('stockAvailable', 0)} unit(s) are available for SKU {variant.get('sku')}.",
                    409,
                )

            variant_snapshots[item["variantId"]] = variant_snapshot
            product_id = variant.get("productId")

            if product_id not in product_snapshots:
                product_snapshot = business_reference.collection("products").document(
                    product_id,
                ).get(transaction=current_transaction)

                if not product_snapshot.exists or product_snapshot.to_dict().get("status") != "active":
                    raise ApiError(
                        "inactive_product",
                        "A selected product is unavailable.",
                        409,
                    )

                product_snapshots[product_id] = product_snapshot

        business = business_snapshot.to_dict()
        customer_data = customer_snapshot.to_dict()
        courier_data = courier_snapshot.to_dict()
        sequence = business.get("nextOrderSequence", 1)
        order_prefix = business.get("orderPrefix", "VD")
        order_number = f"{order_prefix}-{sequence:06d}"
        waybill_sequence = courier_data.get(
            "nextWaybillSequence",
            courier_data.get("waybillStart", 1),
        )
        waybill_end = courier_data.get("waybillEnd", 999999)
        if waybill_sequence > waybill_end:
            raise ApiError(
                "waybill_range_exhausted",
                "This courier's waybill range is exhausted. Add a new range before creating the order.",
                409,
            )
        waybill_number = (
            f"{courier_data.get('waybillPrefix', 'VWB')}-{waybill_sequence:08d}"
        )
        items = []
        subtotal_minor = 0
        total_weight_grams = 0
        quantities_by_product = defaultdict(int)

        for requested_item in request_data["items"]:
            variant_snapshot = variant_snapshots[requested_item["variantId"]]
            variant = variant_snapshot.to_dict()
            product = product_snapshots[variant["productId"]].to_dict()
            quantity = requested_item["quantity"]
            unit_price_minor = variant.get("sellingPriceMinor", 0)
            line_total_minor = unit_price_minor * quantity
            line_weight_grams = variant.get("weightGrams", 0) * quantity
            media = product.get("media", [])
            items.append(
                {
                    "productId": variant["productId"],
                    "variantId": variant_snapshot.id,
                    "name": product.get("name", "Product"),
                    "size": variant.get("size", ""),
                    "sku": variant.get("sku", ""),
                    "barcode": variant.get("barcode", ""),
                    "quantity": quantity,
                    "unitPriceMinor": unit_price_minor,
                    "unitCostMinor": variant.get("costPriceMinor", 0),
                    "unitWeightGrams": variant.get("weightGrams", 0),
                    "lineTotalMinor": line_total_minor,
                    "mediaUrl": media[0].get("url", "") if media else "",
                },
            )
            subtotal_minor += line_total_minor
            total_weight_grams += line_weight_grams
            quantities_by_product[variant["productId"]] += quantity

        if request_data["discountMinor"] > subtotal_minor:
            raise ApiError(
                "invalid_discount",
                "Discount cannot be greater than the item subtotal.",
                422,
            )

        delivery_fee_minor = calculate_delivery_fee(
            courier_data,
            total_weight_grams,
            delivery_address["district"],
        )
        tax_minor = 0
        total_minor = (
            subtotal_minor
            - request_data["discountMinor"]
            + delivery_fee_minor
            + tax_minor
        )
        timestamp = firestore.SERVER_TIMESTAMP

        for requested_item in request_data["items"]:
            variant_snapshot = variant_snapshots[requested_item["variantId"]]
            variant = variant_snapshot.to_dict()
            quantity = requested_item["quantity"]
            available_before = variant.get("stockAvailable", 0)
            available_after = available_before - quantity
            reserved_after = variant.get("stockReserved", 0) + quantity
            product = product_snapshots[variant["productId"]].to_dict()
            threshold = product.get("lowStockThreshold", 0)
            current_transaction.update(
                variant_snapshot.reference,
                {
                    "stockReserved": reserved_after,
                    "stockAvailable": available_after,
                    "stockStatus": stock_status(available_after, threshold),
                    "updatedAt": timestamp,
                },
            )
            current_transaction.set(
                business_reference.collection("inventoryTransactions").document(),
                {
                    "productId": variant["productId"],
                    "variantId": variant_snapshot.id,
                    "type": "reserve",
                    "quantity": quantity,
                    "stockBefore": available_before,
                    "stockAfter": available_after,
                    "orderId": order_reference.id,
                    "reference": order_number,
                    "reason": "Order created",
                    "performedBy": uid,
                    "createdAt": timestamp,
                },
            )

        for product_id, reserved_quantity in quantities_by_product.items():
            product_snapshot = product_snapshots[product_id]
            product = product_snapshot.to_dict()
            variant_updates = {
                item["variantId"]: item["quantity"]
                for item in request_data["items"]
                if variant_snapshots[item["variantId"]].to_dict().get("productId")
                == product_id
            }
            summaries = []

            for summary in product.get("variantSummaries", []):
                quantity = variant_updates.get(summary.get("id"), 0)

                if quantity:
                    available = summary.get("stockAvailable", 0) - quantity
                    summaries.append(
                        {
                            **summary,
                            "stockReserved": summary.get("stockReserved", 0) + quantity,
                            "stockAvailable": available,
                            "stockStatus": stock_status(
                                available,
                                product.get("lowStockThreshold", 0),
                            ),
                        },
                    )
                else:
                    summaries.append(summary)

            available_product_stock = product.get("availableStock", 0) - reserved_quantity
            current_transaction.update(
                product_snapshot.reference,
                {
                    "reservedStock": product.get("reservedStock", 0) + reserved_quantity,
                    "availableStock": available_product_stock,
                    "stockStatus": stock_status(
                        available_product_stock,
                        product.get("lowStockThreshold", 0),
                    ),
                    "variantSummaries": summaries,
                    "updatedAt": timestamp,
                },
            )

        if request_data["depositMinor"] > total_minor:
            raise ApiError("invalid_deposit", "Deposit cannot exceed the order total.", 422)

        paid_amount_minor = (
            total_minor
            if request_data["paymentMethod"] == "paid"
            else request_data["depositMinor"]
            if request_data["paymentMethod"] == "deposit"
            else 0
        )
        payment_status = (
            "paid" if paid_amount_minor == total_minor
            else "partially-paid" if paid_amount_minor > 0
            else "unpaid"
        )
        current_transaction.set(
            order_reference,
            {
                "orderNumber": order_number,
                "customerId": customer_snapshot.id,
                "customerSnapshot": {
                    "name": customer_data.get("name", ""),
                    "normalizedPhone": customer_data.get("normalizedPhone", ""),
                    "email": customer_data.get("email", ""),
                    "secondaryPhoneNumber": request_data["secondaryPhoneNumber"] or customer_data.get("normalizedSecondaryPhone", ""),
                    "riskLevel": customer_data.get("riskLevel", "low"),
                },
                "items": items,
                "itemCount": sum(item["quantity"] for item in items),
                "subtotalMinor": subtotal_minor,
                "discountTotalMinor": request_data["discountMinor"],
                "deliveryFeeMinor": delivery_fee_minor,
                "taxTotalMinor": tax_minor,
                "totalAmountMinor": total_minor,
                "paidAmountMinor": paid_amount_minor,
                "depositAmountMinor": request_data["depositMinor"],
                "balanceAmountMinor": total_minor - paid_amount_minor,
                "paymentMethod": request_data["paymentMethod"],
                "paymentStatus": payment_status,
                "fulfilmentStatus": "needs-confirmation",
                "deliveryAddress": delivery_address,
                "district": delivery_address["district"],
                "courierId": courier_snapshot.id,
                "courierSnapshot": {
                    "name": courier_data.get("name", ""),
                    "code": courier_data.get("code", ""),
                    "averageDeliveryDays": courier_data.get(
                        "averageDeliveryDays",
                        0,
                    ),
                },
                "totalWeightGrams": total_weight_grams,
                "source": request_data["source"],
                "privateNote": request_data["privateNote"],
                "assignedStaffUid": request_data["assignedStaffUid"] or uid,
                "waybillNumber": waybill_number,
                "stockReservationStatus": "reserved",
                "createdBy": uid,
                "customerUid": request_data["customerUid"],
                "createdAt": timestamp,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            business_reference,
            {
                "nextOrderSequence": sequence + 1,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            courier_reference,
            {
                "nextWaybillSequence": waybill_sequence + 1,
                "updatedAt": timestamp,
            },
        )
        current_transaction.set(
            waybill_reference,
            {
                "waybillNumber": waybill_number,
                "orderId": order_reference.id,
                "orderNumber": order_number,
                "courierId": courier_snapshot.id,
                "courierSnapshot": {
                    "name": courier_data.get("name", ""),
                    "code": courier_data.get("code", ""),
                },
                "customerSnapshot": {
                    "name": customer_data.get("name", ""),
                    "normalizedPhone": customer_data.get("normalizedPhone", ""),
                },
                "deliveryAddress": delivery_address,
                "totalWeightGrams": total_weight_grams,
                "generatedBy": uid,
                "createdAt": timestamp,
            },
        )
        current_transaction.set(
            notification_reference,
            {
                "type": "new-order",
                "title": f"New order {order_number}",
                "message": f"{customer_data.get('name', 'Customer')} placed an order.",
                "orderId": order_reference.id,
                "orderNumber": order_number,
                "isRead": False,
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return get_order(database, business_id, order_reference.id)


def update_order_status(database, business_id, order_id, uid, payload):
    try:
        new_status = required_text(payload.get("status"), "Order status", 40)
        note = optional_text(payload.get("note"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    order_reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .document(order_id)
    )
    business_reference = database.collection("businesses").document(business_id)
    transaction = database.transaction()

    @google_firestore.transactional
    def update_in_transaction(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()
        current_status = order.get("fulfilmentStatus")
        allowed_next_statuses = STATUS_TRANSITIONS.get(current_status, set())

        if new_status not in allowed_next_statuses:
            raise ApiError(
                "invalid_status_transition",
                f"Order cannot move from {current_status} to {new_status}.",
                409,
                {"allowedStatuses": sorted(allowed_next_statuses)},
            )

        stock_action = None

        if new_status in {"cancelled", "returned"}:
            stock_action = "release"
        elif new_status == "delivered":
            stock_action = "sell"

        variant_snapshots = {}
        product_snapshots = {}
        customer_snapshot = None
        courier_snapshot = None

        if stock_action:
            customer_reference = business_reference.collection("customers").document(
                order["customerId"],
            )
            courier_reference = business_reference.collection("couriers").document(
                order["courierId"],
            )
            customer_snapshot = customer_reference.get(transaction=current_transaction)
            courier_snapshot = courier_reference.get(transaction=current_transaction)

            for item in order.get("items", []):
                variant_reference = business_reference.collection(
                    "productVariants",
                ).document(item["variantId"])
                variant_snapshot = variant_reference.get(transaction=current_transaction)

                if not variant_snapshot.exists:
                    raise ApiError(
                        "variant_not_found",
                        "A reserved product size/SKU no longer exists.",
                        409,
                    )

                variant_snapshots[item["variantId"]] = variant_snapshot
                product_id = item["productId"]

                if product_id not in product_snapshots:
                    product_snapshot = business_reference.collection("products").document(
                        product_id,
                    ).get(transaction=current_transaction)

                    if not product_snapshot.exists:
                        raise ApiError(
                            "product_not_found",
                            "A product in this order no longer exists.",
                            409,
                        )

                    product_snapshots[product_id] = product_snapshot

        timestamp = firestore.SERVER_TIMESTAMP

        if stock_action:
            quantities_by_product = defaultdict(int)

            for item in order.get("items", []):
                quantity = item["quantity"]
                variant_snapshot = variant_snapshots[item["variantId"]]
                variant = variant_snapshot.to_dict()
                product = product_snapshots[item["productId"]].to_dict()
                reserved_before = variant.get("stockReserved", 0)

                if reserved_before < quantity:
                    raise ApiError(
                        "invalid_stock_reservation",
                        "The order stock reservation is incomplete.",
                        409,
                    )

                reserved_after = reserved_before - quantity
                available_before = variant.get("stockAvailable", 0)
                on_hand_before = variant.get("stockOnHand", 0)

                if stock_action == "release":
                    available_after = available_before + quantity
                    on_hand_after = on_hand_before
                else:
                    available_after = available_before
                    on_hand_after = on_hand_before - quantity

                current_transaction.update(
                    variant_snapshot.reference,
                    {
                        "stockOnHand": on_hand_after,
                        "stockReserved": reserved_after,
                        "stockAvailable": available_after,
                        "stockStatus": stock_status(
                            available_after,
                            product.get("lowStockThreshold", 0),
                        ),
                        "updatedAt": timestamp,
                    },
                )
                current_transaction.set(
                    business_reference.collection("inventoryTransactions").document(),
                    {
                        "productId": item["productId"],
                        "variantId": item["variantId"],
                        "type": stock_action,
                        "quantity": quantity,
                        "stockBefore": (
                            available_before
                            if stock_action == "release"
                            else on_hand_before
                        ),
                        "stockAfter": (
                            available_after
                            if stock_action == "release"
                            else on_hand_after
                        ),
                        "orderId": order_id,
                        "reference": order.get("orderNumber", ""),
                        "reason": f"Order marked {new_status}",
                        "performedBy": uid,
                        "createdAt": timestamp,
                    },
                )
                quantities_by_product[item["productId"]] += quantity

            for product_id, quantity in quantities_by_product.items():
                product_snapshot = product_snapshots[product_id]
                product = product_snapshot.to_dict()
                item_quantities = {
                    item["variantId"]: item["quantity"]
                    for item in order.get("items", [])
                    if item["productId"] == product_id
                }
                summaries = []

                for summary in product.get("variantSummaries", []):
                    item_quantity = item_quantities.get(summary.get("id"), 0)

                    if not item_quantity:
                        summaries.append(summary)
                        continue

                    available = summary.get("stockAvailable", 0)
                    on_hand = summary.get("stockOnHand", 0)

                    if stock_action == "release":
                        available += item_quantity
                    else:
                        on_hand -= item_quantity

                    summaries.append(
                        {
                            **summary,
                            "stockOnHand": on_hand,
                            "stockReserved": summary.get("stockReserved", 0)
                            - item_quantity,
                            "stockAvailable": available,
                            "stockStatus": stock_status(
                                available,
                                product.get("lowStockThreshold", 0),
                            ),
                        },
                    )

                available_product_stock = product.get("availableStock", 0)
                total_product_stock = product.get("totalStock", 0)

                if stock_action == "release":
                    available_product_stock += quantity
                else:
                    total_product_stock -= quantity

                current_transaction.update(
                    product_snapshot.reference,
                    {
                        "totalStock": total_product_stock,
                        "reservedStock": product.get("reservedStock", 0) - quantity,
                        "availableStock": available_product_stock,
                        "stockStatus": stock_status(
                            available_product_stock,
                            product.get("lowStockThreshold", 0),
                        ),
                        "variantSummaries": summaries,
                        "updatedAt": timestamp,
                    },
                )

        order_changes = {
            "fulfilmentStatus": new_status,
            "updatedAt": timestamp,
            "statusHistory": firestore.ArrayUnion(
                [
                    {
                        "from": current_status,
                        "to": new_status,
                        "note": note,
                        "changedBy": uid,
                        "changedAt": datetime.now(timezone.utc),
                    },
                ],
            ),
        }

        if stock_action == "release":
            order_changes["stockReservationStatus"] = "released"
        elif stock_action == "sell":
            order_changes["stockReservationStatus"] = "sold"

        current_transaction.update(order_reference, order_changes)

        if new_status == "delivered" and customer_snapshot and customer_snapshot.exists:
            customer = customer_snapshot.to_dict()
            current_transaction.update(
                customer_snapshot.reference,
                {
                    "completedOrderCount": customer.get("completedOrderCount", 0) + 1,
                    "totalSpentMinor": customer.get("totalSpentMinor", 0)
                    + order.get("totalAmountMinor", 0),
                    "tags": firestore.ArrayUnion(["repeat-customer"]),
                    "updatedAt": timestamp,
                },
            )

        if new_status == "returned" and customer_snapshot and customer_snapshot.exists:
            customer = customer_snapshot.to_dict()
            returned_count = customer.get("returnedOrderCount", 0) + 1
            risk_level, return_tag = returned_customer_risk(returned_count)
            current_transaction.update(
                customer_snapshot.reference,
                {
                    "returnedOrderCount": returned_count,
                    "riskLevel": risk_level,
                    "tags": firestore.ArrayUnion([return_tag]),
                    "updatedAt": timestamp,
                },
            )

        if courier_snapshot and courier_snapshot.exists and new_status in {"delivered", "returned"}:
            courier = courier_snapshot.to_dict()
            delivered_count = courier.get("deliveredOrderCount", 0)
            returned_count = courier.get("returnedOrderCount", 0)

            if new_status == "delivered":
                delivered_count += 1
            else:
                returned_count += 1

            completed_count = delivered_count + returned_count
            current_transaction.update(
                courier_snapshot.reference,
                {
                    "deliveredOrderCount": delivered_count,
                    "returnedOrderCount": returned_count,
                    "successRate": delivered_count / completed_count,
                    "returnRate": returned_count / completed_count,
                    "updatedAt": timestamp,
                },
            )

    update_in_transaction(transaction)
    return get_order(database, business_id, order_id)


def update_order(database, business_id, order_id, uid, payload):
    """Update seller-editable order fields without changing reserved items."""
    order_reference = (
        database.collection("businesses").document(business_id)
        .collection("orders").document(order_id)
    )
    snapshot = order_reference.get()
    if not snapshot.exists:
        raise ApiError("order_not_found", "Order not found.", 404)

    changes = {"updatedAt": firestore.SERVER_TIMESTAMP, "updatedBy": uid}
    current_order = snapshot.to_dict()
    customer_snapshot = dict(current_order.get("customerSnapshot") or {})
    if "customerName" in payload:
        customer_snapshot["name"] = required_text(payload.get("customerName"), "Customer name", 160)
    if "phoneNumber" in payload:
        phone = required_text(payload.get("phoneNumber"), "Phone number", 40)
        customer_snapshot["normalizedPhone"] = phone
        customer_snapshot["phoneNumber"] = phone
    if "email" in payload:
        customer_snapshot["email"] = optional_text(payload.get("email"), 160)
    if any(field in payload for field in ("customerName", "phoneNumber", "email")):
        changes["customerSnapshot"] = customer_snapshot
    if "deliveryAddress" in payload:
        address = payload.get("deliveryAddress")
        if not isinstance(address, dict):
            raise ApiError("validation_error", "Delivery address must be an object.", 422)
        changes["deliveryAddress"] = address
    if "privateNote" in payload:
        changes["privateNote"] = optional_text(payload.get("privateNote"), 2000)
    if "assignedStaffUid" in payload:
        changes["assignedStaffUid"] = optional_text(payload.get("assignedStaffUid"), 120)
    if "paymentMethod" in payload:
        payment_method = optional_text(payload.get("paymentMethod"), 40)
        if payment_method not in ALLOWED_PAYMENT_METHODS:
            raise ApiError("validation_error", "Choose a valid payment method.", 422)
        changes["paymentMethod"] = payment_method

    if "waybillNumber" in payload:
        waybill_number = optional_text(payload.get("waybillNumber"), 120).upper()

        if waybill_number:
            duplicate_orders = (
                order_reference.parent
                .where(filter=FieldFilter("waybillNumber", "==", waybill_number))
                .limit(2)
                .stream()
            )
            if any(order.id != order_id for order in duplicate_orders):
                raise ApiError(
                    "duplicate_waybill_number",
                    "This waybill number is already assigned to another order.",
                    409,
                )

        changes["waybillNumber"] = waybill_number

    if "courierId" in payload:
        courier_id = optional_text(payload.get("courierId"), 120)
        if courier_id:
            courier_snapshot = (
                database.collection("businesses").document(business_id)
                .collection("couriers").document(courier_id).get()
            )
            if not courier_snapshot.exists:
                raise ApiError("courier_not_found", "Choose an active courier.", 422)
            changes["courierId"] = courier_id
            changes["courierSnapshot"] = {"id": courier_snapshot.id, **courier_snapshot.to_dict()}
        else:
            changes["courierId"] = ""
            changes["courierSnapshot"] = {}

    order_reference.update(changes)

    if "waybillNumber" in changes and changes["waybillNumber"]:
        waybill_reference = (
            database.collection("businesses").document(business_id)
            .collection("waybills").document(order_id)
        )
        waybill_reference.set(
            {
                "waybillNumber": changes["waybillNumber"],
                "orderId": order_id,
                "orderNumber": current_order.get("orderNumber", ""),
                "courierId": current_order.get("courierId", ""),
                "courierSnapshot": current_order.get("courierSnapshot", {}),
                "customerSnapshot": current_order.get("customerSnapshot", {}),
                "deliveryAddress": current_order.get("deliveryAddress", {}),
                "totalWeightGrams": current_order.get("totalWeightGrams", 0),
                "updatedBy": uid,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    return get_order(database, business_id, order_id)
````

### `frontend/src/components/AddOrderModal.css`

````css
.add-order {
  gap: 12px;
}

.add-order__loading {
  display: grid;
  place-items: center;
  min-height: 280px;
  color: var(--color-text-muted);
}

.add-order__steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 28px;
  width: min(100%, 620px);
  margin: -4px auto 4px;
  padding: 0;
  list-style: none;
}

.add-order__steps li {
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 650;
}

.add-order__steps li:not(:last-child)::after {
  position: absolute;
  top: 50%;
  left: calc(100% - 8px);
  width: 36px;
  height: 1px;
  background: var(--color-border);
  content: "";
}

.add-order__steps li span {
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border: 1px solid var(--color-border);
  border-radius: 50%;
  background: var(--color-surface);
}

.add-order__steps .add-order__step--active {
  color: #087cf0;
}

.add-order__steps .add-order__step--active span {
  border-color: #087cf0;
  color: #fff;
  background: #087cf0;
}

.add-order__layout {
  display: grid;
  grid-template-columns: minmax(620px, 1.75fr) minmax(320px, 0.85fr);
  align-items: start;
  gap: 12px;
}

.add-order__main,
.add-order__side {
  display: grid;
  align-content: start;
  gap: 12px;
}

.add-order__side {
  position: sticky;
  top: 0;
}

.add-order__section-heading,
.add-order__items-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.add-order__search-select,
.add-order__search-input {
  position: relative;
  display: flex !important;
  align-items: center;
}

.add-order__search-select svg,
.add-order__search-input svg {
  position: absolute;
  left: 12px;
  z-index: 1;
  color: var(--color-text-muted);
}

.add-order__search-select select,
.add-order__search-input input {
  padding-left: 39px;
}

.add-order__customer-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 12px;
  padding: 11px 13px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface-muted);
}

.add-order__customer-avatar {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  color: #3f46b9;
  background: #e9e8ff;
  font-weight: 700;
}

.add-order__customer-card > div {
  display: grid;
  gap: 3px;
}

.add-order__customer-card > div span {
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.add-order__customer-tag,
.add-order__risk-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 7px;
  border: 1px solid rgba(22, 134, 247, 0.25);
  border-radius: 6px;
  color: #0870d8;
  background: rgba(22, 134, 247, 0.08);
  font-size: 0.72rem;
  white-space: nowrap;
}

.add-order__risk-tag {
  border-color: rgba(28, 163, 105, 0.28);
  color: #148451;
  background: rgba(28, 163, 105, 0.09);
}

.add-order__new-customer {
  display: grid;
  gap: 10px;
  padding: 13px;
  border: 1px dashed #7faee0;
  border-radius: 10px;
  background: var(--color-surface-muted);
}

.add-order__new-customer > button {
  justify-self: end;
}

.add-order__product-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px;
  gap: 10px;
}

.add-order__product-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 9px;
}

.add-order__product-card {
  position: relative;
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  grid-template-rows: auto auto auto auto;
  column-gap: 10px;
  min-height: 118px;
  padding: 11px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: var(--color-text);
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.add-order__product-card:hover:not(:disabled) {
  border-color: #7fb8ee;
  box-shadow: 0 7px 18px rgba(19, 82, 142, 0.1);
  transform: translateY(-1px);
}

.add-order__product-card--selected {
  border-color: #1686f7;
  box-shadow: inset 0 0 0 1px #1686f7;
}

.add-order__product-card:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.add-order__product-image {
  grid-row: 1 / -1;
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  overflow: hidden;
  border-radius: 9px;
  color: #1686f7;
  background: var(--color-surface-muted);
}

.add-order__product-image img,
.add-order__item-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.add-order__product-card strong {
  overflow: hidden;
  font-size: 0.82rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.add-order__product-card small {
  color: var(--color-text-muted);
  font-size: 0.7rem;
}

.add-order__product-card b {
  color: var(--color-text-strong, var(--color-text));
  font-size: 0.83rem;
}

.add-order__stock-label {
  color: #168451;
  font-size: 0.7rem;
}

.add-order__selected-check {
  position: absolute;
  top: 7px;
  right: 7px;
  color: #087cf0;
  fill: var(--color-surface);
}

.add-order__variant-picker {
  display: grid;
  grid-template-columns: minmax(210px, 1fr) auto auto auto;
  align-items: end;
  gap: 10px;
  padding: 11px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-surface-muted);
}

.add-order__availability {
  align-self: center;
  color: #168451;
  font-size: 0.78rem;
  white-space: nowrap;
}

.add-order__quantity {
  display: grid;
  grid-template-columns: 36px 48px 36px;
  align-items: center;
  gap: 5px;
}

.add-order__quantity button,
.add-order__quantity input {
  display: grid;
  place-items: center;
  min-height: 38px;
  padding: 0;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  background: var(--color-surface);
  text-align: center;
}

.add-order__quantity button {
  cursor: pointer;
}

.add-order__add-item {
  min-height: 40px;
  padding: 0 18px;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
  white-space: nowrap;
}

.add-order__items-heading {
  margin-top: 4px;
}

.add-order__items-table {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 10px;
}

.add-order__items-head,
.add-order__item {
  display: grid;
  grid-template-columns: minmax(190px, 1.5fr) 0.48fr 0.75fr 0.38fr 0.7fr 0.75fr 34px;
  align-items: center;
  gap: 8px;
  min-width: 760px;
  padding: 9px 10px;
}

.add-order__items-head {
  color: var(--color-text-muted);
  background: var(--color-surface-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.add-order__item {
  border-top: 1px solid var(--color-border);
  font-size: 0.77rem;
}

.add-order__item > div {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.add-order__item > div strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.add-order__item-image {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 38px;
  height: 38px;
  overflow: hidden;
  border-radius: 7px;
  color: #1686f7;
  background: var(--color-surface-muted);
}

.add-order__item > button {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 7px;
  color: #ef4444;
  background: transparent;
  cursor: pointer;
}

.add-order__empty {
  grid-column: 1 / -1;
  margin: 0;
  padding: 18px;
  color: var(--color-text-muted);
  text-align: center;
}

.add-order__summary-card > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.add-order__summary-card > div strong,
.add-order__summary-card > div small {
  color: var(--color-text);
}

.add-order__summary-total {
  margin-top: 2px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  font-size: 0.95rem !important;
}

.add-order__delivery-note {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #168451;
  font-size: 0.78rem;
}

.add-order__payment-methods {
  display: grid;
  grid-template-columns: 1.35fr 0.7fr 0.8fr;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.add-order__payment-methods button {
  min-height: 38px;
  padding: 0 8px;
  border: 0;
  border-right: 1px solid var(--color-border);
  color: var(--color-text-muted);
  background: var(--color-surface);
  cursor: pointer;
  font-size: 0.72rem;
}

.add-order__payment-methods button:last-child {
  border-right: 0;
}

.add-order__payment-methods .add-order__payment--active {
  color: #fff;
  background: #087cf0;
}

.add-order__footer {
  position: sticky;
  bottom: -22px;
  z-index: 3;
  align-items: center;
  justify-content: space-between;
  margin: 0 -22px -22px;
  padding: 14px 22px;
  background: var(--color-surface);
}

.add-order__footer > div {
  display: flex;
  align-items: center;
  gap: 10px;
}

.add-order__footer-status {
  color: #168451;
  font-size: 0.8rem;
}

@media (max-width: 1050px) {
  .add-order__layout {
    grid-template-columns: 1fr;
  }

  .add-order__side {
    position: static;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .add-order__product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .add-order__steps {
    gap: 8px;
  }

  .add-order__steps li {
    font-size: 0.7rem;
  }

  .add-order__steps li::after {
    display: none;
  }

  .add-order__customer-card,
  .add-order__product-filters,
  .add-order__variant-picker,
  .add-order__side {
    grid-template-columns: 1fr;
  }

  .add-order__customer-avatar {
    display: none;
  }

  .add-order__product-grid {
    grid-template-columns: 1fr;
  }

  .add-order__footer {
    align-items: stretch;
    flex-direction: column;
  }

  .add-order__footer > div:last-child button {
    flex: 1;
  }
}

[data-theme="dark"] .add-order__customer-avatar {
  color: #b9c6ff;
  background: rgba(84, 91, 220, 0.25);
}

/* Two-stage Add Order dialog based on the approved reference. */
.modal-shell:has(.order-dialog) { width: min(1150px, calc(100vw - 32px)); max-height: calc(100vh - 28px); border-radius: 10px; }
.modal-shell:has(.order-dialog) .modal-shell__header { padding: 17px 24px; background: #fafbfc; }
.modal-shell:has(.order-dialog) .modal-shell__header h2 { font-size: 1.1rem; }
.modal-shell:has(.order-dialog) .modal-shell__header p { display: none; }
.modal-shell:has(.order-dialog) .modal-shell__content { padding: 0; }
.order-dialog { display: grid; grid-template-columns: 1fr 1fr; color: #344054; font-size: 12px; }
.order-dialog > section { min-width: 0; padding: 24px; }
.order-dialog__customer { border-right: 1px solid #d9e0e8; }
.order-dialog__customer > header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; }
.order-dialog__customer > header > strong,
.order-dialog__items > strong { letter-spacing: .06em; }
.order-dialog__customer > header button { display: inline-flex; align-items: center; gap: 4px; padding: 7px 11px; border: 1px solid #9bd5fa; border-radius: 5px; color: #087abc; background: #eef8ff; cursor: pointer; }
.order-dialog label { display: grid; gap: 5px; font-weight: 500; }
.order-dialog em { color: #ef4444; font-style: normal; }
.order-dialog input,
.order-dialog select,
.order-dialog textarea { width: 100%; min-width: 0; min-height: 38px; padding: 8px 11px; border: 1px solid #cbd6e4; border-radius: 6px; color: #344054; background: #fff; font: inherit; outline: none; }
.order-dialog input:focus,
.order-dialog select:focus,
.order-dialog textarea:focus { border-color: #21a9e8; box-shadow: 0 0 0 2px rgba(33,169,232,.1); }
.order-dialog__search { position: relative; display: flex !important; align-items: center; }
.order-dialog__search svg { position: absolute; left: 11px; z-index: 1; color: #8da0b8; }
.order-dialog__search input,
.order-dialog__search select { padding-left: 39px; }
.order-dialog__customer-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 24px; padding: 24px 0 26px; border-top: 1px solid #e7ebf0; border-bottom: 1px solid #e7ebf0; }
.order-dialog__wide { grid-column: 1 / -1; }
.order-dialog__wide textarea { min-height: 78px; resize: vertical; }
.order-dialog__details { display: grid; grid-template-columns: 1fr; gap: 14px; padding-top: 28px; }
.order-dialog__details label { grid-template-columns: 70px 1fr; align-items: center; }
.order-dialog__filters { display: grid; grid-template-columns: 1fr 145px; gap: 12px; margin: 14px 0; }
.order-dialog__results { display: flex; gap: 8px; min-height: 160px; padding: 12px; overflow-x: auto; border: 1px dashed #cbd6e4; border-radius: 7px; background: #fbfcfe; }
.order-dialog__results > p { margin: auto; color: #8da0b8; line-height: 1.45; text-align: center; }
.order-dialog__results > button { display: grid; grid-template-columns: 42px 115px; align-items: center; gap: 8px; flex: 0 0 auto; height: 66px; padding: 8px; border: 1px solid #dbe2ea; border-radius: 6px; color: #344054; background: #fff; text-align: left; cursor: pointer; }
.order-dialog__results > button.is-selected { border-color: #21a9e8; box-shadow: 0 0 0 1px #21a9e8; }
.order-dialog__results img { width: 42px; height: 42px; border-radius: 5px; object-fit: cover; }
.order-dialog__results button span { display: grid; gap: 4px; min-width: 0; }
.order-dialog__results button strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
.order-dialog__results button small { color: #168451; }
.order-dialog__picker { display: grid; grid-template-columns: 1fr 100px 60px; gap: 12px; margin-top: 15px; padding: 12px; border: 1px solid #dbe2ea; border-radius: 7px; box-shadow: 0 2px 5px rgba(23,43,77,.05); }
.order-dialog__picker > button { border: 0; border-radius: 5px; color: #fff; background: #1d2939; cursor: pointer; }
.order-dialog__quantity { display: grid; grid-template-columns: 28px 1fr 28px; align-items: center; min-height: 36px; border: 1px solid #d5dee9; border-radius: 6px; background: #fff; }
.order-dialog__quantity button { display: grid; place-items: center; padding: 0; border: 0; color: #8da0b8; background: transparent; cursor: pointer; }
.order-dialog__quantity b { text-align: center; }
.order-dialog__items hr { margin: 25px 0; border: 0; border-top: 1px solid #e1e6ec; }
.order-dialog__table { margin-top: 14px; overflow: hidden; border: 1px solid #dbe2ea; border-radius: 7px; }
.order-dialog__table-head,
.order-dialog__table-row { display: grid; grid-template-columns: minmax(0,1fr) 100px 110px 28px; align-items: center; gap: 10px; padding: 10px 14px; }
.order-dialog__table-head { color: #65758b; background: #f6f8fa; font-size: 10px; letter-spacing: .06em; }
.order-dialog__table-row { border-top: 1px solid #e3e8ef; }
.order-dialog__table-row > div { display: flex; align-items: center; gap: 10px; min-width: 0; }
.order-dialog__table-row img { width: 38px; height: 38px; border-radius: 5px; object-fit: cover; }
.order-dialog__table-row div span { display: grid; gap: 3px; min-width: 0; }
.order-dialog__table-row div strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.order-dialog__table-row small { color: #718096; }
.order-dialog__table-row > button { border: 0; color: #ef4444; background: transparent; cursor: pointer; }
.order-dialog__subtotal { display: flex; justify-content: space-between; margin-top: 18px; }
.order-dialog__error { grid-column: 1 / -1; margin: 0 24px 10px; padding: 9px 12px; border: 1px solid #fecaca; border-radius: 6px; color: #b91c1c; background: #fff1f2; }
.order-dialog__footer { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 10px; padding: 13px 24px; border-top: 1px solid #dbe2ea; background: #fafbfc; }
.order-dialog__footer button,
.order-summary footer button { min-height: 38px; padding: 0 18px; border: 1px solid #d1dae5; border-radius: 6px; background: #fff; cursor: pointer; }
.order-dialog__footer .order-dialog__checkout,
.order-summary footer button:last-child { border-color: #0ea5e9; color: #fff; background: #0ea5e9; }
.order-dialog__loading { display: flex; align-items: center; justify-content: center; gap: 10px; min-height: 420px; color: #718096; }

.order-summary__backdrop { position: fixed; inset: 0; z-index: 1200; display: grid; place-items: center; padding: 20px; background: rgba(25,35,49,.48); backdrop-filter: blur(1px); }
.order-summary { width: min(448px, 100%); overflow: hidden; border-radius: 11px; color: #1d2939; background: #fff; box-shadow: 0 28px 70px rgba(16,24,40,.3); animation: modal-panel-in 190ms cubic-bezier(.22,1,.36,1); }
.order-summary > header { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px; border-bottom: 1px solid #dbe2ea; }
.order-summary h2 { margin: 0; font-size: 1.12rem; }
.order-summary header button { border: 0; color: #94a3b8; background: transparent; cursor: pointer; }
.order-summary__body { display: grid; gap: 19px; padding: 25px 24px; }
.order-summary__body > div,
.order-summary__body > label:not(.order-summary__courier) { display: flex; align-items: center; justify-content: space-between; }
.order-summary__discount { display: grid; grid-template-columns: 20px 90px; align-items: center; }
.order-summary__discount input { width: 90px; height: 38px; border: 1px solid #d5dee9; border-radius: 6px; text-align: right; }
.order-summary__total { padding-top: 18px; border-top: 1px solid #dbe2ea; font-size: 1rem; }
.order-summary__total strong:last-child { color: #0ea5e9; font-size: 1.13rem; }
.order-summary fieldset { display: grid; align-content: start; gap: 15px; min-height: 250px; padding: 34px 16px 16px; border: 1px solid #d5dee9; border-radius: 7px; background: #fbfcfe; }
.order-summary legend { padding: 0 8px; font-weight: 700; }
.order-summary fieldset > label { display: flex; align-items: center; gap: 10px; min-height: 46px; padding: 0 12px; border: 1px solid #dbe2ea; border-radius: 6px; background: #fff; }
.order-summary fieldset input[type="radio"] { width: 17px; height: 17px; accent-color: #0ea5e9; }
.order-summary fieldset .order-summary__deposit { display: grid; grid-template-columns: 1fr 120px; }
.order-summary__deposit input,
.order-summary__courier select { min-height: 36px; border: 1px solid #d5dee9; border-radius: 6px; padding: 7px 9px; }
.order-summary__courier { display: grid; gap: 6px; }
.order-summary footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 24px; border-top: 1px solid #dbe2ea; background: #fafbfc; }

@media (max-width: 800px) {
  .order-dialog { grid-template-columns: 1fr; }
  .order-dialog__customer { border-right: 0; border-bottom: 1px solid #d9e0e8; }
  .order-dialog__customer-fields { grid-template-columns: 1fr; }
  .order-dialog__wide { grid-column: auto; }
  .order-dialog__picker { grid-template-columns: 1fr 100px 60px; }
}
````

### `frontend/src/components/AddOrderModal.jsx`

````jsx
import { useEffect, useMemo, useState } from "react";
import { Minus, Package, Plus, Search, Trash2, X } from "lucide-react";

import { createCustomer, getCustomers } from "../services/customerService";
import { getCouriers } from "../services/courierService";
import { createOrder } from "../services/orderService";
import { getProducts } from "../services/productService";
import ModalShell from "./ModalShell";
import OrderReceipt from "./OrderReceipt";
import "./AddOrderModal.css";

const emptyAddress = { line1: "", line2: "", city: "", district: "", postalCode: "" };
const emptyCustomer = { name: "", phoneNumber: "", secondaryPhoneNumber: "", email: "", address: { ...emptyAddress } };

function money(amount) {
  return `LKR ${Number(amount || 0).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AddOrderModal({ isOpen, businessId, business, onClose, onCreated }) {
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [couriers, setCouriers] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [customer, setCustomer] = useState(emptyCustomer);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [source, setSource] = useState("dashboard");
  const [privateNote, setPrivateNote] = useState("");
  const [courierId, setCourierId] = useState("");
  const [discountAmount, setDiscountAmount] = useState("0");
  const [paymentMethod, setPaymentMethod] = useState("cod");
  const [depositAmount, setDepositAmount] = useState("0");
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [receiptOrder, setReceiptOrder] = useState(null);

  useEffect(() => {
    if (!isOpen || !businessId) return undefined;
    let current = true;
    setIsLoading(true);
    setCustomerId(""); setCustomer(emptyCustomer); setItems([]); setSearch("");
    setCategoryId(""); setSelectedProductId(""); setSelectedVariantId("");
    setSource("dashboard"); setPrivateNote(""); setCourierId("");
    setDiscountAmount("0"); setPaymentMethod("cod"); setDepositAmount("0");
    setIsCheckoutOpen(false); setReceiptOrder(null); setErrorMessage("");

    Promise.all([getCustomers(businessId), getProducts(businessId), getCouriers(businessId)])
      .then(([customerRows, productRows, courierRows]) => {
        if (!current) return;
        setCustomers(customerRows);
        setProducts(productRows);
        const activeCouriers = courierRows.filter((courier) => courier.status === "active");
        setCouriers(activeCouriers);
        setCourierId(activeCouriers[0]?.id || "");
      })
      .catch((error) => current && setErrorMessage(error.message))
      .finally(() => current && setIsLoading(false));
    return () => { current = false; };
  }, [businessId, isOpen]);

  const variants = useMemo(() => products.flatMap((product) =>
    (product.sizes || []).map((variant) => ({
      ...variant,
      productId: product.id,
      productName: product.name,
      colour: product.colourName || product.colour || "",
      sellingPrice: variant.sellingPrice ?? product.sellingPrice,
      weightKg: product.weightKg,
      image: product.images?.[0] || "",
    }))), [products]);

  const categories = useMemo(() => Array.from(new Map(products.filter((product) => product.categoryId)
    .map((product) => [product.categoryId, product.categoryName || product.category]))), [products]);
  const matchingProducts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return products.filter((product) => !categoryId || product.categoryId === categoryId)
      .filter((product) => !query || [product.name, product.sku, product.barcode, ...(product.sizes || []).flatMap((variant) => [variant.sku, variant.barcode])]
        .some((value) => String(value || "").toLowerCase().includes(query))).slice(0, 5);
  }, [products, search, categoryId]);

  const selectedProduct = products.find((product) => product.id === selectedProductId);
  const selectedVariant = variants.find((variant) => variant.id === selectedVariantId);
  const subtotal = items.reduce((sum, item) => sum + item.sellingPrice * item.quantity, 0);
  const discount = Math.max(0, Number(discountAmount) || 0);
  const totalWeightKg = items.reduce((sum, item) => sum + item.weightKg * item.quantity, 0);
  const selectedCourier = couriers.find((courier) => courier.id === courierId) || couriers[0];
  const extraKg = Math.max(0, Math.ceil(totalWeightKg) - 1);
  const districtKey = customer.address.district.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const deliveryFee = selectedCourier
    ? (selectedCourier.firstKgPriceMinor || 0) / 100 + extraKg * (selectedCourier.extraKgPriceMinor || 0) / 100
      + ((selectedCourier.districtSurchargesMinor || {})[districtKey] || 0) / 100
    : 0;
  const estimatedTotal = Math.max(0, subtotal - discount + deliveryFee);

  function chooseCustomer(event) {
    const id = event.target.value;
    setCustomerId(id);
    const selected = customers.find((row) => row.id === id);
    if (!selected) return;
    setCustomer({
      name: selected.name || "",
      phoneNumber: selected.phoneNumber || selected.normalizedPhone || "",
      secondaryPhoneNumber: selected.secondaryPhoneNumber || selected.normalizedSecondaryPhone || "",
      email: selected.email || "",
      address: { ...emptyAddress, ...(selected.defaultAddress || {}) },
    });
  }

  function startNewCustomer() {
    setCustomerId("");
    setCustomer(emptyCustomer);
  }

  function updateCustomer(event) {
    const { name, value } = event.target;
    if (name.startsWith("address.")) {
      const field = name.slice(8);
      setCustomer((current) => ({ ...current, address: { ...current.address, [field]: value } }));
    } else setCustomer((current) => ({ ...current, [name]: value }));
  }

  function chooseProduct(product) {
    const first = variants.find((variant) => variant.productId === product.id && variant.stock > 0);
    setSelectedProductId(product.id);
    setSelectedVariantId(first?.id || "");
    setQuantity(1);
  }

  function addItem() {
    if (!selectedVariant) return setErrorMessage("Choose an available product variant.");
    const amount = Math.max(1, Number(quantity) || 1);
    const existing = items.find((item) => item.variantId === selectedVariant.id);
    if ((existing?.quantity || 0) + amount > selectedVariant.stock) return setErrorMessage(`Only ${selectedVariant.stock} unit(s) are available.`);
    setItems((current) => existing
      ? current.map((item) => item.variantId === selectedVariant.id ? { ...item, quantity: item.quantity + amount } : item)
      : [...current, { ...selectedVariant, variantId: selectedVariant.id, quantity: amount }]);
    setErrorMessage("");
  }

  function changeItemQuantity(variantId, amount) {
    setItems((current) => current.map((item) => item.variantId === variantId
      ? { ...item, quantity: Math.max(1, Math.min(item.stock, item.quantity + amount)) }
      : item));
  }

  function openCheckout(event) {
    event.preventDefault();
    if (!customer.name || !customer.phoneNumber || !customer.address.line1 || !customer.address.city || !customer.address.district) return setErrorMessage("Complete the required customer and delivery fields.");
    if (!items.length) return setErrorMessage("Add at least one item to the order.");
    if (!couriers.length) return setErrorMessage("Add an active courier before creating an order.");
    setErrorMessage("");
    setIsCheckoutOpen(true);
  }

  async function createConfirmedOrder() {
    setIsSaving(true);
    setErrorMessage("");
    try {
      let finalCustomerId = customerId;
      if (!finalCustomerId) {
        const created = await createCustomer(businessId, customer);
        finalCustomerId = created.id;
      }
      const order = await createOrder(businessId, {
        customerId: finalCustomerId,
        secondaryPhoneNumber: customer.secondaryPhoneNumber,
        items: items.map((item) => ({ variantId: item.variantId, quantity: item.quantity })),
        deliveryAddress: customer.address,
        courierId,
        paymentMethod,
        depositAmount: paymentMethod === "deposit" ? depositAmount : 0,
        source,
        discountAmount,
        privateNote,
      });
      onCreated(order);
      setReceiptOrder(order);
      setIsCheckoutOpen(false);
    } catch (error) {
      setErrorMessage(error.message);
      setIsCheckoutOpen(false);
    } finally { setIsSaving(false); }
  }

  return <>
    <ModalShell isOpen={isOpen && !isCheckoutOpen && !receiptOrder} title="Add Order" onClose={onClose} size="wide">
      {isLoading ? <div className="order-dialog__loading"><Package /><span>Loading order data...</span></div> :
        <form className="order-dialog" onSubmit={openCheckout}>
          <section className="order-dialog__customer">
            <header><strong>CUSTOMER DETAILS</strong><button type="button" onClick={startNewCustomer}><Plus size={14} /> New Customer</button></header>
            <label className="order-dialog__search"><Search size={15} /><select value={customerId} onChange={chooseCustomer}><option value="">Search or choose customer...</option>{customers.map((row) => <option key={row.id} value={row.id}>{row.name} â€” {row.normalizedPhone}</option>)}</select></label>
            <div className="order-dialog__customer-fields">
              <label>Name <em>*</em><input name="name" value={customer.name} onChange={updateCustomer} required /></label>
              <label>1st Phone No. <em>*</em><input name="phoneNumber" value={customer.phoneNumber} onChange={updateCustomer} required /></label>
              <label>Email Address<input name="email" type="email" value={customer.email} onChange={updateCustomer} /></label>
              <label>2nd Phone No.<input name="secondaryPhoneNumber" value={customer.secondaryPhoneNumber} onChange={updateCustomer} /></label>
              <label className="order-dialog__wide">Address <em>*</em><textarea name="address.line1" value={customer.address.line1} onChange={updateCustomer} required /></label>
              <label>City <em>*</em><input name="address.city" value={customer.address.city} onChange={updateCustomer} required /></label>
              <label>District <em>*</em><input name="address.district" value={customer.address.district} onChange={updateCustomer} required /></label>
            </div>
            <div className="order-dialog__details">
              <label>Source<select value={source} onChange={(event) => setSource(event.target.value)}><option value="dashboard">Select Source</option><option value="phone">Phone</option><option value="whatsapp">WhatsApp</option><option value="facebook">Facebook</option><option value="chatbot">Chatbot</option></select></label>
              <label>Note<input value={privateNote} onChange={(event) => setPrivateNote(event.target.value)} placeholder="Add internal notes..." /></label>
            </div>
          </section>

          <section className="order-dialog__items">
            <strong>ADD ITEM</strong>
            <div className="order-dialog__filters"><label className="order-dialog__search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product..." /></label><select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Category</option>{categories.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></div>
            <div className="order-dialog__results">
              {!search && !categoryId ? <p>Search for a product above.<br />Matching items will show here.</p> : matchingProducts.map((product) => <button className={selectedProductId === product.id ? "is-selected" : ""} type="button" key={product.id} onClick={() => chooseProduct(product)}>{product.images?.[0] ? <img src={product.images[0]} alt="" /> : <Package size={20} />}<span><strong>{product.name}</strong><small>{product.stock} in stock</small></span></button>)}
            </div>
            <div className="order-dialog__picker"><select value={selectedVariantId} onChange={(event) => setSelectedVariantId(event.target.value)}><option value="">Variants (e.g., Size L, Red)</option>{(selectedProduct?.sizes || []).map((variant) => <option key={variant.id} value={variant.id} disabled={!variant.stock}>{variant.size || variant.sku} â€” {variant.stock} available</option>)}</select><Quantity value={quantity} onMinus={() => setQuantity(Math.max(1, quantity - 1))} onPlus={() => setQuantity(quantity + 1)} /><button type="button" onClick={addItem}>Add</button></div>
            <hr />
            <strong>ORDER ITEMS</strong>
            <div className="order-dialog__table"><div className="order-dialog__table-head"><span>ITEM</span><span>QTY</span><span>PRICE</span><span /></div>{items.map((item) => <div className="order-dialog__table-row" key={item.variantId}><div>{item.image && <img src={item.image} alt="" />}<span><strong>{item.productName}</strong><small>{item.size ? `Variant: ${item.size}` : item.sku}</small></span></div><Quantity value={item.quantity} onMinus={() => changeItemQuantity(item.variantId, -1)} onPlus={() => changeItemQuantity(item.variantId, 1)} /><strong>{money(item.sellingPrice * item.quantity)}</strong><button type="button" onClick={() => setItems((current) => current.filter((row) => row.variantId !== item.variantId))}><Trash2 size={14} /></button></div>)}</div>
            <div className="order-dialog__subtotal"><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
          </section>
          {errorMessage && <p className="order-dialog__error">{errorMessage}</p>}
          <footer className="order-dialog__footer"><button type="button" onClick={onClose}>Cancel</button><button className="order-dialog__checkout" type="submit">Checkout</button></footer>
        </form>}
    </ModalShell>

    {isOpen && isCheckoutOpen && <div className="order-summary__backdrop" role="presentation">
      <section className="order-summary" role="dialog" aria-modal="true" aria-labelledby="order-summary-title">
        <header><h2 id="order-summary-title">Order Summary</h2><button type="button" onClick={() => setIsCheckoutOpen(false)}><X size={20} /></button></header>
        <div className="order-summary__body">
          <div><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
          <label><span>Discount</span><span className="order-summary__discount">âˆ’ <input type="number" min="0" max={subtotal} value={discountAmount} onChange={(event) => setDiscountAmount(event.target.value)} /></span></label>
          <div><span>Delivery fee</span><strong>{money(deliveryFee)}</strong></div>
          <div className="order-summary__total"><strong>Estimated Total</strong><strong>{money(estimatedTotal)}</strong></div>
          <fieldset><legend>Payment</legend><label><input type="radio" name="payment" checked={paymentMethod === "cod"} onChange={() => setPaymentMethod("cod")} /> COD</label><label><input type="radio" name="payment" checked={paymentMethod === "deposit"} onChange={() => setPaymentMethod("deposit")} /> Deposit</label>{paymentMethod === "deposit" && <label className="order-summary__deposit">Deposit amount<input type="number" min="0" max={estimatedTotal} value={depositAmount} onChange={(event) => setDepositAmount(event.target.value)} /></label>}</fieldset>
          <label className="order-summary__courier">Courier<select value={courierId} onChange={(event) => setCourierId(event.target.value)}>{couriers.map((courier) => <option key={courier.id} value={courier.id}>{courier.name}</option>)}</select></label>
        </div>
        <footer><button type="button" onClick={() => setIsCheckoutOpen(false)}>Cancel</button><button type="button" onClick={createConfirmedOrder} disabled={isSaving}>{isSaving ? "Creating..." : "Create order"}</button></footer>
      </section>
    </div>}
    {isOpen && receiptOrder && <OrderReceipt business={business} order={receiptOrder} closeLabel="Return to Orders" onClose={onClose} />}
  </>;
}

function Quantity({ value, onMinus, onPlus }) {
  return <span className="order-dialog__quantity"><button type="button" onClick={onMinus}><Minus size={14} /></button><b>{value}</b><button type="button" onClick={onPlus}><Plus size={14} /></button></span>;
}

export default AddOrderModal;
````

### `frontend/src/services/orderService.js`

````javascript
import { apiRequest } from "./apiClient";

function formatCurrency(minorUnits = 0) {
  return `LKR ${(minorUnits / 100).toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function displayStatus(status) {
  return status === "needs-confirmation" ? "pending" : status;
}

export function mapOrderForTable(order) {
  const createdAt = order.createdAt ? new Date(order.createdAt) : null;

  return {
    ...order,
    customerName: order.customerSnapshot?.name ?? "Customer",
    phoneNumber: order.customerSnapshot?.normalizedPhone ?? "",
    email: order.customerSnapshot?.email ?? "",
    courier: order.courierSnapshot?.name ?? "Not assigned",
    status: displayStatus(order.fulfilmentStatus),
    fulfilmentStatus: order.fulfilmentStatus,
    paymentMethod: order.paymentMethod ?? "cod",
    privateNote: order.privateNote ?? "",
    total: formatCurrency(order.totalAmountMinor),
    subtotal: formatCurrency(order.subtotalMinor),
    deliveryFee: formatCurrency(order.deliveryFeeMinor),
    deliveryAddress: [
      order.deliveryAddress?.line1,
      order.deliveryAddress?.line2,
      order.deliveryAddress?.city,
      order.deliveryAddress?.district,
      order.deliveryAddress?.postalCode,
      order.deliveryAddress?.country,
    ]
      .filter(Boolean)
      .join(", "),
    deliveryAddressObject: order.deliveryAddress ?? {},
    date: createdAt
      ? createdAt.toLocaleDateString("en-LK", {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : "",
    time: createdAt
      ? createdAt.toLocaleTimeString("en-LK", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "",
    items: (order.items ?? []).map((item) => ({
      ...item,
      id: item.variantId,
      unitPrice: formatCurrency(item.unitPriceMinor),
      price: formatCurrency(item.lineTotalMinor),
      imageUrl: item.mediaUrl ?? item.imageUrl ?? "",
    })),
  };
}

export async function getOrders(businessId, filters = {}) {
  const parameters = new URLSearchParams();

  if (filters.status) parameters.set("status", filters.status);
  if (filters.search) parameters.set("search", filters.search);
  if (filters.dateFrom) parameters.set("dateFrom", filters.dateFrom);
  if (filters.dateTo) parameters.set("dateTo", filters.dateTo);
  if (filters.courierId) parameters.set("courierId", filters.courierId);
  const query = parameters.toString();
  const response = await apiRequest(
    `/businesses/${businessId}/orders${query ? `?${query}` : ""}`,
  );
  return response.orders.map(mapOrderForTable);
}

export async function createOrder(businessId, orderData) {
  const response = await apiRequest(`/businesses/${businessId}/orders`, {
    method: "POST",
    body: orderData,
  });
  return mapOrderForTable(response.order);
}

export async function updateOrderStatus(businessId, orderId, status, note = "") {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/status`,
    {
      method: "PATCH",
      body: { status, note },
    },
  );
  return mapOrderForTable(response.order);
}

export async function removeOrder(businessId, orderId) {
  const response = await apiRequest(`/businesses/${businessId}/orders/${orderId}`, {
    method: "DELETE",
  });
  return mapOrderForTable(response.order);
}

export async function updateOrder(businessId, orderId, changes) {
  const response = await apiRequest(`/businesses/${businessId}/orders/${orderId}`, { method: "PATCH", body: changes });
  return mapOrderForTable(response.order);
}
````

## Feature 14 source — Order management UI and status

Files in this feature: 9

### `frontend/src/components/EditOrderModal.jsx`

````jsx
import { useEffect, useState } from "react";
import ModalShell from "./ModalShell";
import { getCouriers } from "../services/courierService";
import { updateOrder, updateOrderStatus } from "../services/orderService";
import "./InventoryForm.css";

const emptyAddress = { line1: "", line2: "", city: "", district: "", postalCode: "" };
const nextStatuses = {
  "needs-confirmation": ["confirmed", "cancelled"],
  confirmed: ["packed", "cancelled"],
  packed: ["shipped", "cancelled"],
  shipped: ["delivered", "returned"],
  delivered: ["returned"],
};

function EditOrderModal({ isOpen, businessId, order, onClose, onUpdated }) {
  const [couriers, setCouriers] = useState([]);
  const [form, setForm] = useState({ customerName: "", phoneNumber: "", email: "", deliveryAddress: emptyAddress, courierId: "", paymentMethod: "cod", privateNote: "", status: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen || !businessId || !order) return;
    setForm({
      customerName: order.customerName ?? "",
      phoneNumber: order.phoneNumber ?? "",
      email: order.email ?? "",
      deliveryAddress: { ...emptyAddress, ...(order.deliveryAddressObject ?? {}) },
      courierId: order.courierId ?? "",
      paymentMethod: order.paymentMethod ?? "cod",
      privateNote: order.privateNote ?? "",
      status: "",
    });
    setError("");
    getCouriers(businessId).then(setCouriers).catch(() => setCouriers([]));
  }, [businessId, isOpen, order]);

  function change(event) {
    const { name, value } = event.target;
    if (name.startsWith("address.")) {
      const field = name.slice("address.".length);
      setForm((current) => ({ ...current, deliveryAddress: { ...current.deliveryAddress, [field]: value } }));
      return;
    }
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!order) return;
    setSaving(true);
    setError("");
    try {
      let updated = await updateOrder(businessId, order.id, {
        customerName: form.customerName,
        phoneNumber: form.phoneNumber,
        email: form.email,
        deliveryAddress: form.deliveryAddress,
        courierId: form.courierId,
        paymentMethod: form.paymentMethod,
        privateNote: form.privateNote,
      });
      if (form.status && form.status !== order.fulfilmentStatus) {
        updated = await updateOrderStatus(businessId, order.id, form.status);
      }
      onUpdated?.(updated);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  const statusOptions = nextStatuses[order?.fulfilmentStatus] ?? [];

  return (
    <ModalShell isOpen={isOpen} title={`Edit Order ${order?.orderNumber ?? ""}`} description="Update customer, delivery, payment, courier, status, and internal notes." onClose={onClose} size="wide">
      <form className="inventory-form" onSubmit={submit}>
        <section className="inventory-form__panel"><h3>Customer details</h3>
          <div className="inventory-form__two-columns"><label>Customer name<input name="customerName" value={form.customerName} onChange={change} required /></label><label>Phone number<input name="phoneNumber" value={form.phoneNumber} onChange={change} required /></label></div>
          <label>Email<input name="email" type="email" value={form.email} onChange={change} /></label>
        </section>
        <section className="inventory-form__panel"><h3>Delivery address</h3>
          <label>Address line 1<input name="address.line1" value={form.deliveryAddress.line1} onChange={change} required /></label>
          <div className="inventory-form__two-columns"><label>Address line 2<input name="address.line2" value={form.deliveryAddress.line2} onChange={change} /></label><label>City<input name="address.city" value={form.deliveryAddress.city} onChange={change} required /></label></div>
          <div className="inventory-form__two-columns"><label>District<input name="address.district" value={form.deliveryAddress.district} onChange={change} required /></label><label>Postal code<input name="address.postalCode" value={form.deliveryAddress.postalCode} onChange={change} /></label></div>
        </section>
        <section className="inventory-form__panel"><h3>Order settings</h3>
          <div className="inventory-form__two-columns"><label>Courier<select name="courierId" value={form.courierId} onChange={change}><option value="">Choose courier</option>{couriers.map((courier) => <option key={courier.id} value={courier.id}>{courier.name}</option>)}</select></label><label>Payment<select name="paymentMethod" value={form.paymentMethod} onChange={change}><option value="cod">Cash on delivery</option><option value="paid">Paid</option><option value="deposit">Deposit</option></select></label></div>
          <label>Next status<select name="status" value={form.status} onChange={change}><option value="">Keep {order?.status ?? "current status"}</option>{statusOptions.map((status) => <option key={status} value={status}>{status.replaceAll("-", " ")}</option>)}</select></label>
          <label>Private order note<textarea name="privateNote" value={form.privateNote} onChange={change} rows={4} placeholder="Visible only to your team" /></label>
        </section>
        {error && <p className="inventory-form__error" role="alert">{error}</p>}
        <footer className="inventory-form__footer"><button type="button" onClick={onClose}>Cancel</button><button className="inventory-form__primary" type="submit" disabled={saving}>{saving ? "Saving..." : "Save order"}</button></footer>
      </form>
    </ModalShell>
  );
}

export default EditOrderModal;
````

### `frontend/src/components/OrderDetails.css`

````css
/* Expanded order panel divided into products, address, summary, and actions. */
.order-details {
  display: grid;
  grid-template-columns:
    minmax(280px, 1.5fr)
    minmax(210px, 1fr)
    minmax(210px, 1fr)
    minmax(180px, 0.8fr);

  gap: 18px;
  padding: 16px;

  border: 1px solid var(--color-border);
  border-radius: 10px;

  color: var(--color-text);
  background: var(--color-surface);

  animation: order-details-open 500ms ease-out;

  margin-top: 5px;
}

/* Shared section borders and headings. */
.order-details__section {
  min-width: 0;
  padding-right: 18px;
  border-right: 1px solid var(--color-border);
}

.order-details__section:last-child {
  padding-right: 0;
  border-right: 0;
}

.order-details__section h3 {
  margin: 0 0 12px;
  font-size: 12px;
}

/* Product list and individual order-item rows. */
.order-details__items {
  display: grid;
  gap: 8px;
}

.order-details__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;

  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}

.order-details__item:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.order-details__item span {
  display: block;
  margin-top: 3px;
  color: var(--color-muted);
  font-size: 10px;
}

/* Customer and delivery-address information. */
.order-details__information {
  display: grid;
  gap: 12px;
}

.order-details__information > div {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  line-height: 1.5;
}

.order-details__information svg {
  flex-shrink: 0;
  color: var(--color-accent);
}

/* Payment summary and highlighted final total. */
.order-details__summary {
  display: grid;
  align-content: start;
  gap: 12px;
}

.order-details__summary > div {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.order-details__total {
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  font-size: 14px;
}

.order-details__waybill {
  color: var(--color-accent);
}

.order-details__summary > .order-details__waybill-row {
  display: grid;
  gap: 7px;
}

.order-details__waybill-row label {
  font-weight: 600;
}

.order-details__waybill-editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px;
}

.order-details__waybill-editor input {
  min-width: 0;
  height: 34px;
  padding: 0 9px;
  border: 1px solid var(--color-border);
  border-radius: 7px;
  color: var(--color-text);
  background: var(--color-surface);
  font: inherit;
  font-size: 11px;
}

.order-details__waybill-editor input:focus {
  border-color: var(--color-accent);
  outline: 2px solid color-mix(in srgb, var(--color-accent) 18%, transparent);
}

.order-details__waybill-editor button {
  min-width: 52px;
  border: 1px solid var(--color-accent);
  border-radius: 7px;
  color: #fff;
  background: var(--color-accent);
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.order-details__waybill-editor button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* Order action buttons and their individual colour meanings. */
.order-details__actions {
  display: grid;
  align-content: start;
  gap: 9px;
}

.order-details__actions button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;

  min-height: 36px;
  padding: 8px 12px;

  border-radius: 7px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.order-details__status-button {
  color: white;
  border: 1px solid var(--color-accent);
  background: var(--color-accent);
}

.order-details__print-button {
  color: var(--color-accent);
  border: 1px solid var(--color-accent);
  background: transparent;
}

.order-details__fraud-button {
  color: #ef4444;
  border: 1px solid #ef4444;
  background: transparent;
}

.order-details__item-image {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--color-border);
}

.order-details__actions button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.order-details__action-error {
  margin: 2px 0 0;
  color: #dc2626;
  font-size: 11px;
  line-height: 1.4;
}

/* Table cell that contains the expanded details component. */
.orders-table__details-cell {
  padding: 0 10px 12px !important;
  background: var(--color-surface-soft);
}

.orders-table tbody .orders-table__details-row:hover {
  background: transparent;
}

/* Opening animation for the expanded panel. */
@keyframes order-details-open {
  from {
    opacity: 0;
    transform: translateY(-7px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Dark-theme expanded order panel. */
html[data-theme="dark"] .order-details {
  border-color: #2b4055;
  background: linear-gradient(
    145deg,
    rgba(18, 34, 51, 0.98),
    rgba(10, 22, 35, 0.98)
  );
}

html[data-theme="dark"] .orders-table__details-cell {
  background: rgba(7, 17, 28, 0.72);
}

/* Two-column layout when the screen cannot fit all four sections. */
@media (max-width: 1100px) {
  .order-details {
    grid-template-columns: repeat(2, minmax(250px, 1fr));
  }

  .order-details__section:nth-child(2) {
    border-right: 0;
  }
}
.order-details__status-control {
  display: grid;
  gap: 6px;
  font-size: 0.8rem;
  font-weight: 650;
}

.order-details__status-control > div {
  position: relative;
}

.order-details__status-control select {
  width: 100%;
  min-height: 38px;
  padding: 0 34px 0 11px;
  border: 1px solid #087cf0;
  border-radius: 8px;
  appearance: none;
  color: #fff;
  background: #087cf0;
  cursor: pointer;
  font: inherit;
}

.order-details__status-control svg {
  position: absolute;
  top: 50%;
  right: 10px;
  pointer-events: none;
  transform: translateY(-50%);
}
````

### `frontend/src/components/OrderDetails.jsx`

````jsx
// Icons used in the customer information and order action areas.
import {
  ChevronDown,
  CircleAlert,
  Flag,
  MapPin,
  Phone,
  Printer,
  User,
} from "lucide-react";
import { useEffect, useState } from "react";
import { printWaybill } from "../services/operationService";

import "./OrderDetails.css";

const nextStatuses = {
  "needs-confirmation": ["confirmed", "cancelled"],
  confirmed: ["packed", "cancelled"],
  packed: ["shipped", "cancelled"],
  shipped: ["delivered", "returned"],
};

function readableStatus(status) {
  return status
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function OrderDetails({
  order,
  onStatusChange,
  onGenerateWaybill,
  onFraudReport,
  onCourierIssue,
  onWaybillSave,
}) {
  const [actionError, setActionError] = useState("");
  const [isWorking, setIsWorking] = useState(false);
  const [waybillNumber, setWaybillNumber] = useState(order.waybillNumber ?? "");

  useEffect(() => {
    setWaybillNumber(order.waybillNumber ?? "");
  }, [order.id, order.waybillNumber]);
  // Use real order items when available, otherwise show a safe placeholder row.
  const items = order.items ?? [
    {
      id: `${order.id}-item`,
      name: "Order items",
      quantity: order.itemCount,
      price: order.total,
    },
  ];

  async function handlePrintWaybill() {
    const printWindow = window.open("", "_blank", "width=900,height=700");
    setActionError("");
    setIsWorking(true);

    try {
      const printableOrder = order.waybillNumber
        ? order
        : await onGenerateWaybill?.(order.id);
      printWaybill(printableOrder, printWindow);
    } catch (error) {
      printWindow?.close();
      setActionError(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleFraudReport() {
    const note = window.prompt(
      "Add a private note explaining why this appears to be a fake order:",
      "Customer details could not be verified.",
    );

    if (note === null) return;
    setActionError("");
    setIsWorking(true);

    try {
      await onFraudReport?.(order.id, note);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleCourierIssue() {
    const note = window.prompt(
      "Describe the courier branch problem:",
      "Delivery was affected by a courier branch problem.",
    );

    if (note === null) return;
    setActionError("");
    setIsWorking(true);

    try {
      await onCourierIssue?.(order.id, note);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleWaybillSave() {
    const trimmedWaybill = waybillNumber.trim();
    if (!trimmedWaybill) {
      setActionError("Enter a waybill number before saving.");
      return;
    }

    setActionError("");
    setIsWorking(true);
    try {
      await onWaybillSave?.(order.id, trimmedWaybill);
    } catch (error) {
      setActionError(error.message);
      window.alert(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div className="order-details">
      {/* Products included in this order. */}
      <section className="order-details__section">
        <h3>Items in this order</h3>

        <div className="order-details__items">
          {items.map((item) => (
            <div className="order-details__item" key={item.id}>
              {item.imageUrl ? <img className="order-details__item-image" src={item.imageUrl} alt="" /> : null}
              <div>
                <strong>{item.name}</strong>

                <span>
                  Qty: {item.quantity} Ã— {item.unitPrice ?? item.price}
                </span>
              </div>

              <strong>{item.price}</strong>
            </div>
          ))}
        </div>
      </section>

      {/* Customer contact information and delivery address. */}
      <section className="order-details__section">
        <h3>Delivery Address</h3>

        <div className="order-details__information">
          <div>
            <User size={17} />
            <span>{order.customerName}</span>
          </div>

          <div>
            <Phone size={17} />
            <span>{order.phoneNumber}</span>
          </div>

          <div>
            <MapPin size={17} />
            <span>{order.deliveryAddress ?? "Address not available"}</span>
          </div>
        </div>
      </section>

      {/* Product subtotal, delivery fee, final total, and waybill number. */}
      <section className="order-details__section order-details__summary">
        <div>
          <span>Subtotal</span>
          <strong>{order.subtotal ?? order.total}</strong>
        </div>

        <div>
          <span>Delivery Fee</span>
          <strong>{order.deliveryFee ?? "Not calculated"}</strong>
        </div>

        <div className="order-details__total">
          <span>Total</span>
          <strong>{order.total}</strong>
        </div>

        <div className="order-details__waybill-row">
          <label htmlFor={`waybill-${order.id}`}>Waybill No</label>
          <div className="order-details__waybill-editor">
            <input
              id={`waybill-${order.id}`}
              type="text"
              value={waybillNumber}
              onChange={(event) => setWaybillNumber(event.target.value)}
              placeholder="Enter waybill number"
              disabled={isWorking}
            />
            <button type="button" onClick={handleWaybillSave} disabled={isWorking}>
              Save
            </button>
          </div>
        </div>
      </section>

      {/* Seller actions for status, waybill printing, and fraud reporting. */}
      <section className="order-details__section order-details__actions">
        <h3>Order Actions</h3>

        <label className="order-details__status-control">
          <span>Update Status</span>
          <div>
            <select
              defaultValue=""
              onChange={(event) => {
                if (event.target.value) {
                  onStatusChange?.(order.id, event.target.value);
                  event.target.value = "";
                }
              }}
              disabled={(nextStatuses[order.fulfilmentStatus] ?? []).length === 0}
            >
              <option value="">Choose next status</option>
              {(nextStatuses[order.fulfilmentStatus] ?? []).map((status) => (
                <option key={status} value={status}>{readableStatus(status)}</option>
              ))}
            </select>
            <ChevronDown size={17} aria-hidden="true" />
          </div>
        </label>

        <button
          className="order-details__print-button"
          type="button"
          onClick={handlePrintWaybill}
          disabled={isWorking}
        >
          <Printer size={17} />
          Print Waybill
        </button>

        <button
          className="order-details__print-button"
          type="button"
          onClick={handleCourierIssue}
          disabled={isWorking}
        >
          <CircleAlert size={17} />
          Report Courier Issue
        </button>

        <button
          className="order-details__fraud-button"
          type="button"
          onClick={handleFraudReport}
          disabled={isWorking || Boolean(order.fraudReport)}
        >
          <Flag size={17} />
          {order.fraudReport ? "Fraud Reported" : "Report Fake Order"}
        </button>

        {actionError && (
          <p className="order-details__action-error" role="alert">{actionError}</p>
        )}
      </section>
    </div>
  );
}

export default OrderDetails;
````

### `frontend/src/components/OrderFilters.css`

````css
/* Outer card containing all order filter controls. */
.order-filters {
  margin-top: 10px;
  padding: 10px;
  padding-left: 5px;
  padding-right: 5px;

  border: 1px solid var(--color-border);
  border-radius: 12px;

  background: var(--color-surface);

  box-shadow: 0 4px 14px rgba(15, 59, 110, 0.06);

  transition:
    background 250ms ease,
    border-color 250ms ease,
    box-shadow 250ms ease;
}

/* Grid that arranges the date, search fields, courier, and buttons. */
.order-filters__form {
  display: grid;

  grid-template-columns:
    minmax(220px, 1.5fr)
    repeat(4, minmax(105px, 1fr))
    auto
    auto;

  align-items: end;
  gap: 4px;
}

/* Shared label and input layout for each filter field. */
.order-filters__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.order-filters__field label {
  color: var(--color-text-strong);
  font-size: 12px;
  font-weight: 650;
}

.order-filters__field > input,
/* Select and text-input styles. */
.order-filters__field > select {
  width: 100%;
  min-width: 0;
  height: 40px;
  padding: 0 11px;

  border: 1px solid var(--color-border);
  border-radius: 7px;
  outline: none;

  color: var(--color-text);
  background-color: var(--color-control);

  font-size: 13px;
  font-weight: 450;

  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease,
    color 180ms ease;
}

.order-filters__field > input::placeholder {
  color: var(--color-subtle);
}

.order-filters__field > input:focus,
.order-filters__field > select:focus {
  border-color: var(--color-accent);
  background-color: var(--color-control);
  box-shadow: 0 0 0 3px rgba(41, 151, 255, 0.14);
}

/* Combined start-date and end-date control. */
.order-filters__date-control {
  display: flex;
  align-items: center;
  gap: 7px;

  height: 40px;
  padding: 0 10px;

  border: 1px solid var(--color-border);
  border-radius: 7px;
  background-color: var(--color-control);

  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease;
}

.order-filters__date-control:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(22, 140, 245, 0.12);
}

.order-filters__date-control svg {
  flex-shrink: 0;
  color: var(--color-accent);
}

.order-filters__date-control input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  color: var(--color-text);
  background-color: transparent;
  font-size: 12px;
}

.order-filters__date-control span {
  color: var(--color-muted);
  font-size: 12px;
}

.order-filters__apply,
/* Reset and primary Filter buttons. */
.order-filters__reset {
  display: inline-flex;
  align-items: center;
  justify-content: center;

  height: 40px;
  border-radius: 7px;

  font-weight: 700;

  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    color 180ms ease,
    transform 180ms ease,
    box-shadow 180ms ease;
}

.order-filters__apply {
  gap: 8px;
  min-width: 104px;
  padding: 0 16px;

  border: 1px solid var(--color-accent);
  color: white;
  background-color: var(--color-accent);

  font-size: 13px;
  box-shadow: 0 4px 10px rgba(22, 140, 245, 0.2);
}

.order-filters__apply:hover {
  border-color: #0879dd;
  background-color: #0879dd;
  box-shadow: 0 6px 14px rgba(22, 140, 245, 0.28);
  transform: translateY(-1px);
}

.order-filters__reset {
  width: 42px;
  padding: 0;

  border: 1px solid var(--color-border);
  color: var(--color-accent);
  background-color: var(--color-control);
}

.order-filters__reset:hover {
  border-color: var(--color-accent);
  color: white;
  background-color: var(--color-accent);
}

.order-filters__resetbt{
  transform: rotate(45deg);
}

.order-filters__apply:active,
.order-filters__reset:active {
  transform: translateY(0);
}

/* Tablet filter layout. */
@media (max-width: 1050px) {
  .order-filters__form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .order-filters__date-field {
    grid-column: span 2;
  }

  .order-filters__apply {
    width: 100%;
  }
}

/* Mobile filter layout. */
@media (max-width: 620px) {
  .order-filters {
    padding: 12px;
  }

  .order-filters__form {
    grid-template-columns: 1fr;
  }

  .order-filters__date-field {
    grid-column: auto;
  }

  .order-filters__reset {
    width: 100%;
  }
}

/* Dark-theme filter card and form controls. */
html[data-theme="dark"] .order-filters {
  border-color: rgba(78, 111, 145, 0.45);

  background:
    radial-gradient(
      circle at 10% 0%,
      rgba(41, 151, 255, 0.09),
      transparent 35%
    ),
    linear-gradient(
      145deg,
      rgba(17, 31, 46, 0.96),
      rgba(10, 21, 34, 0.96)
    );

  box-shadow:
    0 12px 28px rgba(0, 0, 0, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.025);
}

html[data-theme="dark"] .order-filters__field label {
  color: #bed0e3;
}

html[data-theme="dark"] .order-filters__field > input,
html[data-theme="dark"] .order-filters__field > select,
html[data-theme="dark"] .order-filters__date-control {
  border-color: #2b4055;
  color: var(--color-text);
  background-color: rgba(7, 18, 30, 0.72);

  box-shadow:
    inset 0 1px 2px rgba(0, 0, 0, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.015);
}

html[data-theme="dark"]
  .order-filters__field
  > input::placeholder {
  color: #74879b;
}

html[data-theme="dark"] .order-filters__field select option {
  color: var(--color-text);
  background-color: #111e2d;
}

html[data-theme="dark"] .order-filters__field > input:focus,
html[data-theme="dark"] .order-filters__field > select:focus,
html[data-theme="dark"]
  .order-filters__date-control:focus-within {
  border-color: #2997ff;
  background-color: rgba(10, 25, 41, 0.95);

  box-shadow:
    0 0 0 3px rgba(41, 151, 255, 0.14),
    0 5px 14px rgba(0, 0, 0, 0.15);
}

html[data-theme="dark"] .order-filters__date-control input {
  color: var(--color-text);
}

html[data-theme="dark"] .order-filters__date-control span {
  color: #8496a9;
}

html[data-theme="dark"] .order-filters__reset {
  border-color: #31506d;
  color: #54aaff;
  background-color: rgba(13, 31, 48, 0.9);
}

html[data-theme="dark"] .order-filters__reset:hover {
  border-color: #2997ff;
  color: white;
  background-color: #176bb7;
}
.order-filters__field { position: relative; }
.order-filters__clear { position: absolute; right: 8px; bottom: 8px; display: grid; place-items: center; width: 24px; height: 24px; border: 0; border-radius: 50%; background: var(--color-surface-muted); color: var(--color-text-muted); cursor: pointer; }
.order-filters__clear:hover { color: var(--color-text); }
````

### `frontend/src/components/OrderFilters.jsx`

````jsx
// React state stores the filter form; icons improve the form controls visually.
import { useState } from "react";
import {
  CalendarDays,
  Funnel,
  RotateCcw,
  X,
} from "lucide-react";

import "./OrderFilters.css";

// Initial values are also reused when the user resets the form.
const initialFilters = {
  dateFrom: "",
  dateTo: "",
  orderNumber: "",
  itemName: "",
  customer: "",
  courier: "",
  waybillNumber: "",
};

function OrderFilters({ couriers = [], onApply, onReset }) {
  // One state object keeps all order-filter values together.
  const [filters, setFilters] = useState(initialFilters);

  // Use the input name to update only the field that changed.
  function handleInputChange(event) {
    const fieldName = event.target.name;
    const fieldValue = event.target.value;

    const nextFilters = {
      ...filters,
      [fieldName]: fieldValue,
    };
    setFilters((currentFilters) => ({
      ...currentFilters,
      [fieldName]: fieldValue,
    }));
    if (!fieldValue && ["orderNumber", "itemName", "customer"].includes(fieldName)) onApply?.(nextFilters);
  }

  // Stop the browser refresh and prepare filters for future API/database use.
  function handleSubmit(event) {
    event.preventDefault();

    onApply?.(filters);
  }

  // Clear all filters at once.
  function handleReset() {
    setFilters(initialFilters);
    onReset?.();
  }

  return (
    <section className="order-filters" aria-label="Order filters">
      {/* All fields below are controlled by the filters state object. */}
      <form className="order-filters__form" onSubmit={handleSubmit}>
        {/* Start and end date range. */}
        <div className="order-filters__field order-filters__date-field">
          <label htmlFor="date-from">Order date</label>

          <div className="order-filters__date-control">
            <CalendarDays size={17} aria-hidden="true" />

            <input
              id="date-from"
              name="dateFrom"
              type="date"
              value={filters.dateFrom}
              onChange={handleInputChange}
            />

            <span>to</span>

            <input
              id="date-to"
              name="dateTo"
              type="date"
              value={filters.dateTo}
              onChange={handleInputChange}
            />
          </div>
        </div>

        <div className="order-filters__field">
          <label htmlFor="waybill-number">Waybill number</label>
          <input id="waybill-number" name="waybillNumber" type="search" placeholder="Scan or enter waybill" value={filters.waybillNumber} onChange={handleInputChange} />
          {filters.waybillNumber && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "waybillNumber", value: "" } })} aria-label="Clear waybill number"><X size={15} /></button>}
        </div>

        {/* Search by order number. */}
        <div className="order-filters__field">
          <label htmlFor="order-number">Order number</label>

            <input
              id="order-number"
              name="orderNumber"
              type="search"
            placeholder="e.g. VD-100001"
            value={filters.orderNumber}
              onChange={handleInputChange}
            />
            {filters.orderNumber && <button type="button" className="order-filters__clear" onClick={() => { const event = { target: { name: "orderNumber", value: "" } }; handleInputChange(event); }} aria-label="Clear order number"><X size={15} /></button>}
        </div>

        {/* Search by product/item name. */}
        <div className="order-filters__field">
          <label htmlFor="item-name">Item name</label>

          <input
            id="item-name"
            name="itemName"
            type="search"
            placeholder="Search item"
            value={filters.itemName}
            onChange={handleInputChange}
          />
          {filters.itemName && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "itemName", value: "" } })} aria-label="Clear item name"><X size={15} /></button>}
        </div>

        {/* Search by customer name or phone number. */}
        <div className="order-filters__field">
          <label htmlFor="customer">Customer / Phone</label>

          <input
            id="customer"
            name="customer"
            type="search"
            placeholder="Name or phone"
            value={filters.customer}
            onChange={handleInputChange}
          />
          {filters.customer && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "customer", value: "" } })} aria-label="Clear customer search"><X size={15} /></button>}
        </div>

        {/* Restrict results to a selected courier. */}
        <div className="order-filters__field">
          <label htmlFor="courier">Courier</label>

          <select
            id="courier"
            name="courier"
            value={filters.courier}
            onChange={handleInputChange}
          >
            <option value="">All couriers</option>
            {couriers.map((courier) => (
              <option key={courier.id} value={courier.id}>{courier.name}</option>
            ))}
          </select>
        </div>

        {/* Apply or reset the completed filter form. */}
        <button className="order-filters__apply" type="submit">
          <Funnel size={18} aria-hidden="true" />
          <span>Filter</span>
        </button>

        <button
          className="order-filters__reset"
          type="button"
          onClick={handleReset}
          aria-label="Reset order filters"
          title="Reset filters"
        >
          <RotateCcw className="order-filters__resetbt" size={21} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}

export default OrderFilters;
````

### `frontend/src/components/OrderTable.css`

````css
/* Card that contains the scrollable order or inventory table. */
.orders-table-section {
  margin-top: 14px;
  overflow: hidden;

  border: 1px solid var(--color-border);
  border-radius: 12px;

  background: var(--color-surface);
  box-shadow: 0 5px 18px rgba(15, 59, 110, 0.06);
}

/* Horizontal scrolling prevents wide tables from breaking the page. */
.orders-table__scroll {
  overflow-x: auto;
}

/* Shared table sizing, borders, headers, and row interactions. */
.orders-table {
  width: 100%;
  min-width: 1040px;
  border-collapse: collapse;
  color: var(--color-text);
  font-size: 13px;
  font-weight: 450;
  line-height: 1.4;
}

.orders-table th,
.orders-table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: middle;
}

.orders-table th {
  color: var(--color-text-strong);
  background-color: var(--color-surface-soft);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.orders-table tbody tr {
  transition:
    background-color 180ms ease,
    box-shadow 180ms ease;
}

.orders-table tbody tr:hover {
  background-color: rgba(22, 140, 245, 0.045);
}

.orders-table tbody tr:last-child td {
  border-bottom: 0;
}

/* Selected-row highlight and checkbox/expand column sizing. */
.orders-table__row--selected {
  background-color: rgba(22, 140, 245, 0.075);
}

.orders-table__checkbox-column {
  width: 42px;
}

.orders-table__expand-column {
  width: 36px;
}

.orders-table input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--color-accent);
}

.orders-table__expand-button,
/* Expand and three-dot action buttons. */
.orders-table__more-button {
  display: grid;
  place-items: center;

  border: 0;
  color: var(--color-muted);
  background-color: transparent;
}

.orders-table__expand-button {
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 6px;
}

.orders-table__expand-button:hover {
  color: var(--color-accent);
  background-color: var(--color-surface-soft);
}

.orders-table__order-number,
.orders-table td > strong {
  display: block;
  color: var(--color-text-strong);
  font-size: 13px;
  font-weight: 650;
}

/* Secondary text, item previews, and total formatting. */
.orders-table__item-count {
  display: inline-block;
  margin-top: 4px;
  padding: 2px 7px;

  border-radius: 10px;

  color: #086fcb;
  background-color: rgba(22, 140, 245, 0.11);

  font-size: 10.5px;
  font-weight: 650;
}

.orders-table__secondary {
  display: block;
  margin-top: 3px;
  color: var(--color-subtle);
  font-size: 11.5px;
  font-weight: 450;
}

.orders-table__items {
  display: flex;
  align-items: center;
  gap: 5px;
}

.orders-table__product-preview {
  display: grid;
  place-items: center;

  width: 36px;
  height: 36px;

  border: 1px solid var(--color-border);
  border-radius: 7px;

  color: var(--color-accent);
  background-color: var(--color-surface-soft);
}

.orders-table__total {
  color: var(--color-text-strong);
  font-weight: 650;
  white-space: nowrap;
}

/* Shared status badge followed by status-specific colours. */
.orders-table__status {
  display: inline-flex;
  align-items: center;

  padding: 5px 9px;
  border: 1px solid;
  border-radius: 7px;

  font-size: 10.5px;
  font-weight: 650;
}

.orders-table__status--pending {
  color: #c77700;
  border-color: #f7b84b;
  background-color: rgba(245, 158, 11, 0.1);
}

.orders-table__status--confirmed,
.orders-table__status--delivered {
  color: #14835a;
  border-color: #54c99b;
  background-color: rgba(34, 164, 116, 0.1);
}

.orders-table__status--packed {
  color: #126ed1;
  border-color: #74aef2;
  background-color: rgba(29, 117, 232, 0.1);
}

.orders-table__status--shipped {
  color: #7540d4;
  border-color: #aa83ef;
  background-color: rgba(130, 71, 229, 0.1);
}

.orders-table__more-button {
  width: 34px;
  height: 34px;
  margin-left: auto;

  border: 1px solid var(--color-border);
  border-radius: 7px;
}

.orders-table__more-button:hover {
  color: var(--color-accent);
  border-color: var(--color-accent);
  background-color: var(--color-surface-soft);
}

.orders-table__actions-heading {
  text-align: right;
}

/* Footer record count and pagination controls. */
.orders-table__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;

  padding: 12px 14px;
  border-top: 1px solid var(--color-border);

  color: var(--color-muted);
  font-size: 12px;
  font-weight: 500;
}

.orders-table__pagination {
  display: flex;
  align-items: center;
  gap: 6px;
}

.orders-table__pagination button {
  min-width: 34px;
  height: 34px;
  padding: 0 10px;

  border: 1px solid var(--color-border);
  border-radius: 7px;

  color: var(--color-text);
  background-color: var(--color-control);
}

.orders-table__pagination button:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.orders-table__pagination button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.orders-table__pagination .orders-table__page--active {
  color: white;
  border-color: var(--color-accent);
  background-color: var(--color-accent);
}

/* Dark-theme table surfaces, rows, and status colours. */
html[data-theme="dark"] .orders-table-section {
  border-color: #263b50;

  background:
    linear-gradient(
      145deg,
      rgba(17, 31, 46, 0.97),
      rgba(9, 20, 32, 0.97)
    );

  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
}

html[data-theme="dark"] .orders-table th {
  color: #d5e3f3;
  background-color: rgba(29, 47, 66, 0.72);
}

.orders-table__product-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
}

.orders-table__product-more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 30px;
  border-radius: 7px;
  color: var(--color-text-muted);
  background: var(--color-surface-soft);
  font-size: 12px;
  font-weight: 650;
}

.orders-table-section .inventory-table__bulk-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 52px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-soft);
}

.orders-table-section .inventory-table__bulk-actions button,
.orders-table-section .inventory-table__bulk-status {
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--color-primary, #1683f5);
  border-radius: 8px;
  color: var(--color-primary-dark, #064e9b);
  background: var(--color-surface, #fff);
  font: inherit;
  cursor: pointer;
}

.orders-table-section .inventory-table__bulk-actions button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

html[data-theme="dark"] .orders-table tbody tr:hover {
  background-color: rgba(41, 151, 255, 0.07);
}

html[data-theme="dark"] .orders-table__row--selected {
  background-color: rgba(41, 151, 255, 0.1);
}

html[data-theme="dark"] .orders-table__item-count {
  color: #6db8ff;
}

html[data-theme="dark"] .orders-table__status--pending {
  color: #ffbd4a;
}

html[data-theme="dark"] .orders-table__status--confirmed,
html[data-theme="dark"] .orders-table__status--delivered {
  color: #5cdaa8;
}

html[data-theme="dark"] .orders-table__status--packed {
  color: #6eb3ff;
}

html[data-theme="dark"] .orders-table__status--shipped {
  color: #b18bff;
}

/* Mobile footer and pagination arrangement. */
@media (max-width: 700px) {
  .orders-table__footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
````

### `frontend/src/components/OrderTable.jsx`

````jsx
// React state controls selected and expanded order rows.
import { Fragment, useState } from "react";
import OrderDetails from "./OrderDetails";

import {
  ChevronDown,
  ChevronRight,
  Package,
  Download,
  Pencil,
  Trash2,
} from "lucide-react";
import ActionMenu from "./ActionMenu";

import "./OrderTable.css";

// Capitalize an order status for display inside its coloured status badge.
function formatStatus(status) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function OrderTable({
  orders = [],
  onStatusChange,
  onGenerateWaybill,
  onFraudReport,
  onCourierIssue,
  onEditOrder,
  onRemoveOrder,
  onBulkStatusChange,
  onExportSelected,
  onWaybillSave,
}) {
  // Remember which row is expanded and which rows are checkbox-selected.
  const [expandedOrderId, setExpandedOrderId] = useState(null);
  const [selectedOrderIds, setSelectedOrderIds] = useState([]);

  // Expand one order at a time, or close the row when clicked again.
  function toggleExpandedOrder(orderId) {
    if (expandedOrderId === orderId) {
      setExpandedOrderId(null);
      return;
    }

    setExpandedOrderId(orderId);
  }

  // Add or remove a single order ID from the selected-order list.
  function toggleSelectedOrder(orderId) {
    setSelectedOrderIds((currentIds) => {
      const isAlreadySelected = currentIds.includes(orderId);

      if (isAlreadySelected) {
        return currentIds.filter((id) => id !== orderId);
      }

      return [...currentIds, orderId];
    });
  }

  // Select every order or clear the full selection.
  function toggleAllOrders() {
    const allOrdersAreSelected =
      orders.length > 0 && selectedOrderIds.length === orders.length;

    if (allOrdersAreSelected) {
      setSelectedOrderIds([]);
      return;
    }

    setSelectedOrderIds(orders.map((order) => order.id));
  }

  return (
    <section className="orders-table-section" aria-label="Orders list">
      {selectedOrderIds.length > 0 && (
        <div className="inventory-table__bulk-actions">
          <strong>{selectedOrderIds.length} orders selected</strong>
          <select
            className="inventory-table__bulk-status"
            defaultValue=""
            aria-label="Change status for selected orders"
            onChange={(event) => {
              if (event.target.value) {
                onBulkStatusChange?.(selectedOrderIds, event.target.value);
                event.target.value = "";
              }
            }}
          >
            <option value="" disabled>Change status</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="packed">Packed</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="returned">Returned</option>
          </select>
          <button type="button" onClick={() => onExportSelected?.(selectedOrderIds)}>
            <Download size={16} aria-hidden="true" />
            Export selected
          </button>
        </div>
      )}
      {/* Horizontal scrolling protects the table layout on narrow screens. */}
      <div className="orders-table__scroll">
        <table className="orders-table">
          <thead>
            <tr>
              <th className="orders-table__checkbox-column">
                <input
                  type="checkbox"
                  checked={
                    orders.length > 0 && selectedOrderIds.length === orders.length
                  }
                  onChange={toggleAllOrders}
                  aria-label="Select all orders"
                />
              </th>

              <th className="orders-table__expand-column"></th>
              <th>Order</th>
              <th>Customer</th>
              <th>Items</th>
              <th>Total</th>
              <th>Courier</th>
              <th>Status</th>
              <th>Date</th>
              <th className="orders-table__actions-heading">Actions</th>
            </tr>
          </thead>

          <tbody>
            {orders.map((order) => {
              // Row-specific display values for the current order.
              const isExpanded = expandedOrderId === order.id;
              const isSelected = selectedOrderIds.includes(order.id);

              return (
              <Fragment key={order.id}>
              <tr
               className={isSelected ? "orders-table__row--selected" : ""}
              >
                  <td>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelectedOrder(order.id)}
                      aria-label={`Select order ${order.orderNumber}`}
                    />
                  </td>

                  <td>
                    <button
                      className="orders-table__expand-button"
                      type="button"
                      onClick={() => toggleExpandedOrder(order.id)}
                      aria-expanded={isExpanded}
                      aria-label={
                        isExpanded
                          ? `Collapse order ${order.orderNumber}`
                          : `Expand order ${order.orderNumber}`
                      }
                    >
                      {isExpanded ? (
                        <ChevronDown size={18} />
                      ) : (
                        <ChevronRight size={18} />
                      )}
                    </button>
                  </td>

                  <td>
                    <strong className="orders-table__order-number">
                      #{order.orderNumber}
                    </strong>

                    <span className="orders-table__item-count">
                      {order.itemCount}{" "}
                      {order.itemCount === 1 ? "item" : "items"}
                    </span>
                  </td>

                  <td>
                    <strong>{order.customerName}</strong>
                    <span className="orders-table__secondary">
                      {order.phoneNumber}
                    </span>
                  </td>

                  <td>
                    <div className="orders-table__items">
                      {(order.items ?? []).slice(0, 3).map((item, index) => (
                        <span
                          className="orders-table__product-preview"
                          key={item.id ?? index}
                        >
                          {item.imageUrl ? (
                            <img src={item.imageUrl} alt="" />
                          ) : (
                            <Package size={18} aria-hidden="true" />
                          )}
                        </span>
                      ))}
                      {order.itemCount > 3 && <span className="orders-table__product-more">+{order.itemCount - 3}</span>}
                    </div>
                  </td>

                  <td className="orders-table__total">{order.total}</td>

                  <td>{order.courier}</td>

                  <td>
                    <span
                      className={`orders-table__status orders-table__status--${order.status}`}
                    >
                      {formatStatus(order.status)}
                    </span>
                  </td>

                  <td>
                    <span>{order.date}</span>
                    <span className="orders-table__secondary">
                      {order.time}
                    </span>
                  </td>

                  <td>
                      <ActionMenu label={`More actions for ${order.orderNumber}`} items={[
                        { label: "Edit order", icon: <Pencil size={16} />, onClick: () => onEditOrder?.(order) },
                        { label: "Remove order", icon: <Trash2 size={16} />, danger: true, onClick: () => onRemoveOrder?.(order) },
                      ]} />
                  </td>
                </tr>
                {/* Insert the detailed order information directly below its row. */}
                {isExpanded && (
  <tr className="orders-table__details-row">
    <td className="orders-table__details-cell" colSpan={10}>
                  <OrderDetails
                    order={order}
                    onStatusChange={onStatusChange}
                    onGenerateWaybill={onGenerateWaybill}
                    onFraudReport={onFraudReport}
                    onCourierIssue={onCourierIssue}
                    onWaybillSave={onWaybillSave}
                  />
    </td>
  </tr>
)}
  </Fragment>

              );
            })}
          </tbody>
        </table>
      </div>

      {/* Temporary record count and pagination controls. */}
      <footer className="orders-table__footer">
        <span>
          Showing {orders.length === 0 ? 0 : 1} to {orders.length} of{" "}
          {orders.length} orders
        </span>

        <div className="orders-table__pagination">
          <button type="button" disabled>
            Previous
          </button>

          <button className="orders-table__page--active" type="button">
            1
          </button>

          <button type="button">2</button>
          <button type="button">3</button>
          <button type="button">Next</button>
        </div>
      </footer>
    </section>
  );
}

export default OrderTable;
````

### `frontend/src/pages/OrdersPage.css`

````css
/* Sales Orders title and export action alignment. */
.orders-page__heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.orders-page__heading h2 {
  margin: 0;
}

/* Export Orders button appearance and interaction states. */
.orders-page__export-button,
.orders-page__share-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;

  min-width: 140px;
  height: 37px;
  padding: 0 16px;

  border: 1px solid #9bb9dc;
  border-radius: 8px;

  color: var(--color-text-strong);
  background: var(--color-surface);

  font-size: 13px;
  font-weight: 650;
  white-space: nowrap;

  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    transform 180ms ease;
}

.orders-page__export-button:hover,
.orders-page__share-button:hover {
  border-color: #168cf5;
  background-color: #eef6ff;
  transform: translateY(-1px);
}

.orders-page__export-button:active,
.orders-page__share-button:active {
  transform: translateY(0);
}

.orders-page__export-button:disabled,
.orders-page__share-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

/* Orders-page spacing that does not affect the Overview page. */
.orders-page {
  padding-top: 15px;
}

.orders-page__export-button svg,
.orders-page__share-button svg {
  flex-shrink: 0;
  color: #14558f;
}

/* Dark-theme export-button colours. */
html[data-theme="dark"] .orders-page__export-button,
html[data-theme="dark"] .orders-page__share-button {
  border-color: #31506d;
  color: #c5dcf4;

  background:
    linear-gradient(
      145deg,
      rgba(20, 39, 58, 0.95),
      rgba(11, 27, 43, 0.95)
    );

  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.04),
    0 5px 14px rgba(0, 0, 0, 0.16);
}

html[data-theme="dark"] .orders-page__export-button svg,
html[data-theme="dark"] .orders-page__share-button svg {
  color: #54aaff;
}

html[data-theme="dark"] .orders-page__export-button:hover,
html[data-theme="dark"] .orders-page__share-button:hover {
  border-color: #2997ff;
  color: white;
  background-color: rgba(41, 151, 255, 0.14);

  box-shadow:
    0 6px 16px rgba(0, 0, 0, 0.2),
    0 0 14px rgba(41, 151, 255, 0.1);

  transform: translateY(-1px);
}

html[data-theme="dark"] .orders-page__export-button:hover svg,
html[data-theme="dark"] .orders-page__share-button:hover svg {
  color: white;
}

.orders-page__notice {
  margin: 12px 0;
  padding: 11px 13px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  color: var(--color-text-muted);
  background: var(--color-surface);
}

.orders-page__notice--error {
  border-color: rgba(220, 38, 38, 0.35);
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.55);
}

[data-theme="dark"] .orders-page__notice--error {
  color: #fca5a5;
  background: rgba(127, 29, 29, 0.2);
}
.orders-page__heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.orders-page__add-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid #087cf0;
  border-radius: 8px;
  color: #fff;
  background: linear-gradient(135deg, #178ff8, #066ce1);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}

.orders-page__add-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.orders-page__export-button,
.orders-page__share-button,
.orders-page__add-button {
  box-shadow: 0 4px 12px rgba(8, 54, 96, 0.08);
}

.orders-page__add-button {
  transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
}

.orders-page__add-button:hover:not(:disabled) {
  filter: brightness(1.05);
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(8, 124, 240, 0.22);
}

@media (max-width: 760px) {
  .orders-page__heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .orders-page__heading-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
````

### `frontend/src/pages/OrdersPage.jsx`

````jsx
// Icons used by the order statistics and export button.
import {
  CircleCheck,
  Clock3,
  Package,
  Truck,
  Undo2,
  SquareCheckBig,
  Package2,
  Download,
  Plus,
  Link2,
  Check,
  ScanLine,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

// Reusable components that build the Orders page.
import StatCard2 from "../components/StatCard2";
import OrderFilters from "../components/OrderFilters";
import OrderTable from "../components/OrderTable";
import { useAuth } from "../context/authContextValue";
import {
  getOrders,
  removeOrder,
  updateOrder,
  updateOrderStatus,
} from "../services/orderService";
import AddOrderModal from "../components/AddOrderModal";
import EditOrderModal from "../components/EditOrderModal";
import ConfirmDialog from "../components/ConfirmDialog";
import { getCouriers } from "../services/courierService";
import {
  downloadOrderExport,
  generateOrderWaybill,
  reportCourierIssue,
  reportFraudOrder,
} from "../services/operationService";

import "./OrdersPage.css";

function OrdersPage() {
  const [searchParameters, setSearchParameters] = useSearchParams();
  const routeSearch = searchParameters.get("search") ?? "";
  const { business, accountError } = useAuth();
  const [orders, setOrders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [ordersError, setOrdersError] = useState(null);
  const [filters, setFilters] = useState({});
  const [isAddOrderOpen, setIsAddOrderOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [couriers, setCouriers] = useState([]);
  const [linkWasCopied, setLinkWasCopied] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [editingOrder, setEditingOrder] = useState(null);
  const [removalTarget, setRemovalTarget] = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);

  // Reset field, status-card, and URL filters so the complete table is shown again.
  function resetOrderFilters() {
    setFilters({});
    setStatusFilter("");
    setSearchParameters({}, { replace: true });
  }

  useEffect(() => {
    let requestIsCurrent = true;

    async function loadOrders() {
      if (!business?.id) {
        setOrders([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setOrdersError(null);

      try {
        const orderRecords = await getOrders(business.id, {
          search: filters.orderNumber || filters.waybillNumber || filters.itemName || filters.customer,
          dateFrom: filters.dateFrom,
          dateTo: filters.dateTo,
          courierId: filters.courier,
          ...(routeSearch ? { search: routeSearch } : {}),
        });

        if (requestIsCurrent) {
          setOrders(orderRecords);
        }
      } catch (error) {
        console.error("Orders could not be loaded:", error);

        if (requestIsCurrent) {
          setOrdersError(error);
          setOrders([]);
        }
      } finally {
        if (requestIsCurrent) setIsLoading(false);
      }
    }

    loadOrders();
    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id, filters, routeSearch]);

  const visibleOrders = useMemo(() => {
    if (!statusFilter) return orders;
    return orders.filter((order) => order.status === statusFilter);
  }, [orders, statusFilter]);

  useEffect(() => {
    if (!business?.id) return;

    getCouriers(business.id)
      .then(setCouriers)
      .catch((error) => console.error("Courier filters could not be loaded:", error));
  }, [business?.id]);

  const orderStats2 = useMemo(
    () => [
      { label: "All", value: orders.length, icon: Package, tone: "blue" },
      {
        label: "Pending",
        value: orders.filter((order) => order.status === "pending").length,
        icon: Clock3,
        tone: "orange",
      },
      {
        label: "Confirmed",
        value: orders.filter((order) => order.status === "confirmed").length,
        icon: SquareCheckBig,
        tone: "green",
      },
      {
        label: "Packed",
        value: orders.filter((order) => order.status === "packed").length,
        icon: Package2,
        tone: "blue",
      },
      {
        label: "Shipped",
        value: orders.filter((order) => order.status === "shipped").length,
        icon: Truck,
        tone: "purple",
      },
      {
        label: "Delivered",
        value: orders.filter((order) => order.status === "delivered").length,
        icon: CircleCheck,
        tone: "green",
      },
      {
        label: "Returned",
        value: orders.filter((order) => order.status === "returned").length,
        icon: Undo2,
        tone: "red",
      },
    ],
    [orders],
  );

  async function handleStatusChange(orderId, status) {
    if (!business?.id) return;

    try {
      const updatedOrder = await updateOrderStatus(
        business.id,
        orderId,
        status,
      );
      setOrders((current) =>
        current.map((order) => (order.id === orderId ? updatedOrder : order)),
      );
    } catch (error) {
      setOrdersError(error);
    }
  }

  async function handleBulkStatusChange(selectedIds, status) {
    if (!business?.id) return;
    try {
      const updatedOrders = await Promise.all(
        selectedIds.map((orderId) => updateOrderStatus(business.id, orderId, status)),
      );
      setOrders((currentOrders) =>
        currentOrders.map((order) =>
          updatedOrders.find((updated) => updated.id === order.id) ?? order,
        ),
      );
    } catch (error) {
      setOrdersError(error);
    }
  }

  function handleExportSelected(selectedIds) {
    const selectedOrders = visibleOrders.filter((order) => selectedIds.includes(order.id));
    const columns = ["Order number", "Customer", "Phone", "Items", "Subtotal", "Delivery fee", "Total", "Courier", "Status", "Date"];
    const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const rows = selectedOrders.map((order) => [
      order.orderNumber,
      order.customerName,
      order.phoneNumber,
      order.itemCount,
      order.subtotal,
      order.deliveryFee,
      order.total,
      order.courier,
      order.status,
      `${order.date} ${order.time}`,
    ]);
    const csv = [columns, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `vendly-selected-orders-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function confirmOrderRemoval() {
    if (!removalTarget || !business?.id) return;
    setIsRemoving(true);
    try {
      const removed = await removeOrder(business.id, removalTarget.id);
      setOrders((current) => current.filter((order) => order.id !== removed.id));
      setRemovalTarget(null);
    } catch (error) { setOrdersError(error); }
    finally { setIsRemoving(false); }
  }

  async function handleGenerateWaybill(orderId) {
    const updatedOrder = await generateOrderWaybill(business.id, orderId);
    setOrders((current) =>
      current.map((order) => (order.id === orderId ? updatedOrder : order)),
    );
    return updatedOrder;
  }

  async function handleWaybillSave(orderId, waybillNumber) {
    const updatedOrder = await updateOrder(business.id, orderId, { waybillNumber });
    setOrders((current) =>
      current.map((order) => (order.id === orderId ? updatedOrder : order)),
    );
    return updatedOrder;
  }

  async function handleFraudReport(orderId, note) {
    await reportFraudOrder(business.id, orderId, "fake-details", note);
    setOrders((current) =>
      current.map((order) =>
        order.id === orderId
          ? { ...order, fraudReport: { status: "active", reason: "fake-details" } }
          : order,
      ),
    );
  }

  async function handleCourierIssue(orderId, note) {
    await reportCourierIssue(business.id, orderId, "branch-problem", note);
  }

  async function handleExport() {
    if (!business?.id || isExporting) return;

    setIsExporting(true);
    setOrdersError(null);

    try {
      await downloadOrderExport(business.id);
    } catch (error) {
      setOrdersError(error);
    } finally {
      setIsExporting(false);
    }
  }

  async function handleCopyChatbotLink() {
    if (!business?.shortCode) return;

    const chatbotLink = `${window.location.origin}/s/${business.shortCode}`;

    try {
      await navigator.clipboard.writeText(chatbotLink);
      setLinkWasCopied(true);
      window.setTimeout(() => setLinkWasCopied(false), 2200);
    } catch {
      window.prompt("Copy your Vendly chatbot link:", chatbotLink);
    }
  }

  function handleScanWaybill() {
    const waybill = window.prompt("Scan or enter the waybill number:", "");
    if (!waybill?.trim()) return;
    setFilters((current) => ({
      ...current,
      waybillNumber: waybill.trim(),
      orderNumber: "",
      itemName: "",
      customer: "",
    }));
  }

  return (
    <main className="dashboard orders-page">
      {/* Page title, description, and order export action. */}
      <div className="dashboard__intro">
 <div className="orders-page__heading">
  <h2>Sales Orders</h2>

 <div className="orders-page__heading-actions">
   <button className="orders-page__export-button" type="button" onClick={handleScanWaybill}>
     <ScanLine size={19} aria-hidden="true" />
     <span>Scan Waybill</span>
   </button>
   <button
     className="orders-page__share-button"
     type="button"
     onClick={handleCopyChatbotLink}
     disabled={!business?.shortCode}
     title="Copy the seller-specific catalogue and chatbot link"
   >
     {linkWasCopied ? (
       <Check size={19} aria-hidden="true" />
     ) : (
       <Link2 size={19} aria-hidden="true" />
     )}
     <span>{linkWasCopied ? "Link Copied" : "Chatbot Link"}</span>
   </button>

   <button
     className="orders-page__export-button"
     type="button"
     onClick={handleExport}
     disabled={isExporting || !business?.id}
   >
    <Download size={19} strokeWidth={1.8} />
    <span>{isExporting ? "Exporting..." : "Export Orders"}</span>
   </button>

   <button
     className="orders-page__add-button"
     type="button"
     onClick={() => setIsAddOrderOpen(true)}
     disabled={!business?.id}
   >
     <Plus size={19} aria-hidden="true" />
     Add Order
   </button>
 </div>
</div>
         <p>View and manage all customer orders.</p>
      </div>
      {(accountError || ordersError) && (
        <p className="orders-page__notice orders-page__notice--error" role="alert">
          Orders could not be loaded from the Vendly API.
        </p>
      )}
      {isLoading && (
        <p className="orders-page__notice" role="status">Loading orders...</p>
      )}
      {/* Order status summary cards. */}
      <section aria-labelledby="order-dashboard-title">

        <div className="order-stats-grid">
          {orderStats2.map((stat) => (
            <StatCard2
              key={stat.label}
              label={stat.label}
              value={stat.value}
              icon={stat.icon}
              tone={stat.tone}
              isActive={(statusFilter === "" && stat.label === "All") || statusFilter === stat.label.toLowerCase()}
              onClick={() => setStatusFilter(stat.label === "All" ? "" : stat.label.toLowerCase())}
            />
          ))}
        </div>
      </section>
      {/* Filters narrow the orders shown in the table below. */}
      <OrderFilters
        couriers={couriers}
        onApply={setFilters}
        onReset={resetOrderFilters}
      />

      {/* Main expandable orders table. */}
      <OrderTable
        orders={visibleOrders}
        onStatusChange={handleStatusChange}
        onGenerateWaybill={handleGenerateWaybill}
        onFraudReport={handleFraudReport}
        onCourierIssue={handleCourierIssue}
        onEditOrder={setEditingOrder}
        onRemoveOrder={setRemovalTarget}
        onBulkStatusChange={handleBulkStatusChange}
        onExportSelected={handleExportSelected}
        onWaybillSave={handleWaybillSave}
      />

      <AddOrderModal
        isOpen={isAddOrderOpen}
        businessId={business?.id}
        business={business}
        onClose={() => setIsAddOrderOpen(false)}
        onCreated={(order) => setOrders((current) => [order, ...current])}
      />

      <EditOrderModal isOpen={Boolean(editingOrder)} businessId={business?.id} order={editingOrder} onClose={() => setEditingOrder(null)} onUpdated={(updated) => { setOrders((current) => current.map((order) => order.id === updated.id ? updated : order)); setEditingOrder(null); }} />
      <ConfirmDialog isOpen={Boolean(removalTarget)} title="Remove order?" message={`This cancels ${removalTarget?.orderNumber ?? "this order"} and releases its reserved stock.`} isWorking={isRemoving} onCancel={() => setRemovalTarget(null)} onConfirm={confirmOrderRemoval} />
    </main>
  );
}

export default OrdersPage;
````

## Feature 15 source — Operations, notifications, exports and receipts

Files in this feature: 9

### `backend/app/api/operations.py`

````python
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request, send_file

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.requests import get_json_object
from app.services.operations_service import (
    create_fraud_report,
    export_orders,
    generate_waybill,
    list_notifications,
    mark_notification_read,
    record_courier_issue,
)


operations_blueprint = Blueprint("operations", __name__, url_prefix="/api/v1")


@operations_blueprint.post(
    "/businesses/<business_id>/orders/<order_id>/fraud-report",
)
@require_firebase_user
@require_business_member(permission="orders:manage")
def add_fraud_report(business_id, order_id):
    report = create_fraud_report(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"fraudReport": report}), 201


@operations_blueprint.post(
    "/businesses/<business_id>/orders/<order_id>/courier-issues",
)
@require_firebase_user
@require_business_member(permission="orders:manage")
def add_courier_issue(business_id, order_id):
    issue = record_courier_issue(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"courierIssue": issue}), 201


@operations_blueprint.post(
    "/businesses/<business_id>/orders/<order_id>/waybill",
)
@require_firebase_user
@require_business_member(permission="orders:manage")
def create_waybill(business_id, order_id):
    order = generate_waybill(
        get_firestore_client(),
        business_id,
        order_id,
        g.current_user["uid"],
    )
    return jsonify({"order": order})


@operations_blueprint.get("/businesses/<business_id>/orders-export.xlsx")
@require_firebase_user
@require_business_member(permission="orders:read")
def download_orders(business_id):
    workbook = export_orders(
        get_firestore_client(),
        business_id,
        status=request.args.get("status"),
        search=request.args.get("search"),
    )
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return send_file(
        workbook,
        as_attachment=True,
        download_name=f"vendly-orders-{date_stamp}.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )


@operations_blueprint.get("/businesses/<business_id>/notifications")
@require_firebase_user
@require_business_member()
def get_notifications(business_id):
    notifications = list_notifications(
        get_firestore_client(),
        business_id,
        unread_only=request.args.get("unread") == "true",
    )
    return jsonify({"notifications": notifications})


@operations_blueprint.patch(
    "/businesses/<business_id>/notifications/<notification_id>/read",
)
@require_firebase_user
@require_business_member()
def read_notification(business_id, notification_id):
    notification = mark_notification_read(
        get_firestore_client(),
        business_id,
        notification_id,
    )
    return jsonify({"notification": notification})
````

### `backend/app/services/operations_service.py`

````python
from io import BytesIO

from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.order_service import get_order, list_orders
from app.services.text import optional_text, required_text


FRAUD_REASONS = {
    "fake-details",
    "invalid-address",
    "no-contact",
    "refused-order",
    "repeat-return",
    "other",
}
COURIER_ISSUE_TYPES = {
    "branch-problem",
    "delayed",
    "damaged",
    "lost",
    "other",
}
WAYBILL_ALLOWED_STATUSES = {"confirmed", "packed", "shipped", "delivered"}


def validate_report_payload(payload, allowed_values, field_label):
    try:
        report_type = required_text(payload.get("type"), field_label, 60).lower()
        note = optional_text(payload.get("note"), 1000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if report_type not in allowed_values:
        raise ApiError(
            "validation_error",
            f"Choose a valid {field_label.lower()}.",
            422,
            {"allowedValues": sorted(allowed_values)},
        )

    return report_type, note


def create_fraud_report(database, business_id, order_id, uid, payload):
    reason, note = validate_report_payload(payload, FRAUD_REASONS, "Fraud reason")
    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)
    report_reference = business_reference.collection("fraudReports").document(order_id)
    notification_reference = business_reference.collection("notifications").document()
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)
        report_snapshot = report_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)
        if report_snapshot.exists:
            raise ApiError(
                "fraud_report_exists",
                "This order has already been reported.",
                409,
            )

        order = order_snapshot.to_dict()
        customer_reference = business_reference.collection("customers").document(
            order.get("customerId", ""),
        )
        customer_snapshot = customer_reference.get(transaction=current_transaction)
        timestamp = firestore.SERVER_TIMESTAMP
        report = {
            "orderId": order_id,
            "orderNumber": order.get("orderNumber", ""),
            "customerId": order.get("customerId", ""),
            "customerSnapshot": order.get("customerSnapshot", {}),
            "reason": reason,
            "note": note,
            "status": "active",
            "reportedBy": uid,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        current_transaction.set(report_reference, report)
        current_transaction.update(
            order_reference,
            {
                "fraudReport": {
                    "reason": reason,
                    "status": "active",
                    "reportedBy": uid,
                },
                "updatedAt": timestamp,
            },
        )

        if customer_snapshot.exists:
            customer = customer_snapshot.to_dict()
            current_transaction.update(
                customer_reference,
                {
                    "fraudReportCount": customer.get("fraudReportCount", 0) + 1,
                    "riskLevel": "high",
                    "tags": firestore.ArrayUnion(["fraud-reported"]),
                    "updatedAt": timestamp,
                },
            )

        current_transaction.set(
            notification_reference,
            {
                "type": "fraud-report",
                "title": f"Fraud report for {order.get('orderNumber', 'order')}",
                "message": f"Reason: {reason.replace('-', ' ')}.",
                "orderId": order_id,
                "orderNumber": order.get("orderNumber", ""),
                "isRead": False,
                "createdAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return serialize_snapshot(report_reference.get())


def record_courier_issue(database, business_id, order_id, uid, payload):
    issue_type, note = validate_report_payload(
        payload,
        COURIER_ISSUE_TYPES,
        "Courier issue type",
    )
    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)
    issue_reference = business_reference.collection("courierIssues").document()
    transaction = database.transaction()

    @google_firestore.transactional
    def create_in_transaction(current_transaction):
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()
        courier_id = order.get("courierId")

        if not courier_id:
            raise ApiError(
                "courier_not_assigned",
                "Assign a courier before reporting a courier issue.",
                409,
            )

        courier_reference = business_reference.collection("couriers").document(
            courier_id,
        )
        courier_snapshot = courier_reference.get(transaction=current_transaction)

        if not courier_snapshot.exists:
            raise ApiError("courier_not_found", "Courier not found.", 404)

        courier = courier_snapshot.to_dict()
        district = order.get("district", "unknown")
        district_counts = dict(courier.get("districtIssueCounts", {}))
        district_counts[district] = district_counts.get(district, 0) + 1
        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.set(
            issue_reference,
            {
                "orderId": order_id,
                "orderNumber": order.get("orderNumber", ""),
                "courierId": courier_id,
                "courierName": courier.get("name", ""),
                "district": district,
                "type": issue_type,
                "note": note,
                "reportedBy": uid,
                "createdAt": timestamp,
            },
        )
        current_transaction.update(
            courier_reference,
            {
                "districtIssueCounts": district_counts,
                "issueCount": courier.get("issueCount", 0) + 1,
                "updatedAt": timestamp,
            },
        )
        current_transaction.update(
            order_reference,
            {
                "courierIssueCount": order.get("courierIssueCount", 0) + 1,
                "updatedAt": timestamp,
            },
        )

    create_in_transaction(transaction)
    return serialize_snapshot(issue_reference.get())


def generate_waybill(database, business_id, order_id, uid):
    business_reference = database.collection("businesses").document(business_id)
    order_reference = business_reference.collection("orders").document(order_id)
    waybill_reference = business_reference.collection("waybills").document(order_id)
    transaction = database.transaction()

    @google_firestore.transactional
    def generate_in_transaction(current_transaction):
        business_snapshot = business_reference.get(transaction=current_transaction)
        order_snapshot = order_reference.get(transaction=current_transaction)

        if not order_snapshot.exists:
            raise ApiError("order_not_found", "Order not found.", 404)

        order = order_snapshot.to_dict()

        if order.get("waybillNumber"):
            return
        if order.get("fulfilmentStatus") not in WAYBILL_ALLOWED_STATUSES:
            raise ApiError(
                "order_not_ready_for_waybill",
                "Confirm the order before generating a waybill.",
                409,
            )

        business = business_snapshot.to_dict() if business_snapshot.exists else {}
        courier_reference = business_reference.collection("couriers").document(order.get("courierId", ""))
        courier_snapshot = courier_reference.get(transaction=current_transaction) if order.get("courierId") else None
        courier = courier_snapshot.to_dict() if courier_snapshot and courier_snapshot.exists else {}
        sequence = courier.get("nextWaybillSequence", courier.get("waybillStart", business.get("nextWaybillSequence", 1)))
        waybill_end = courier.get("waybillEnd", 999999)
        if sequence > waybill_end:
            raise ApiError("waybill_range_exhausted", "This courier's waybill range is exhausted.", 409)
        waybill_number = f"{courier.get('waybillPrefix', 'VWB')}-{sequence:08d}"
        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.set(
            waybill_reference,
            {
                "waybillNumber": waybill_number,
                "orderId": order_id,
                "orderNumber": order.get("orderNumber", ""),
                "courierId": order.get("courierId", ""),
                "courierSnapshot": order.get("courierSnapshot", {}),
                "customerSnapshot": order.get("customerSnapshot", {}),
                "deliveryAddress": order.get("deliveryAddress", {}),
                "totalWeightGrams": order.get("totalWeightGrams", 0),
                "generatedBy": uid,
                "createdAt": timestamp,
            },
        )
        current_transaction.update(
            order_reference,
            {"waybillNumber": waybill_number, "updatedAt": timestamp},
        )
        current_transaction.update(
            business_reference,
            {"nextWaybillSequence": sequence + 1, "updatedAt": timestamp},
        )
        if courier_snapshot and courier_snapshot.exists:
            current_transaction.update(
                courier_reference,
                {"nextWaybillSequence": sequence + 1, "updatedAt": timestamp},
            )

    generate_in_transaction(transaction)
    return get_order(database, business_id, order_id)


def format_address(address):
    return ", ".join(
        str(address.get(field, "")).strip()
        for field in ("line1", "line2", "city", "district", "postalCode", "country")
        if str(address.get(field, "")).strip()
    )


def build_orders_workbook(orders):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Orders"
    headers = [
        "Order No",
        "Created At",
        "Customer",
        "Phone",
        "Delivery Address",
        "Items",
        "Quantity",
        "Subtotal (LKR)",
        "Discount (LKR)",
        "Delivery Fee (LKR)",
        "Total (LKR)",
        "Courier",
        "Waybill No",
        "Payment",
        "Status",
    ]
    sheet.append(headers)
    header_fill = PatternFill("solid", fgColor="0B3B6E")

    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill

    for order in orders:
        items = order.get("items", [])
        sheet.append(
            [
                order.get("orderNumber", ""),
                str(order.get("createdAt", "")),
                order.get("customerSnapshot", {}).get("name", ""),
                order.get("customerSnapshot", {}).get("normalizedPhone", ""),
                format_address(order.get("deliveryAddress", {})),
                "; ".join(
                    f"{item.get('name', '')} {item.get('size', '')}".strip()
                    for item in items
                ),
                order.get("itemCount", 0),
                order.get("subtotalMinor", 0) / 100,
                order.get("discountTotalMinor", 0) / 100,
                order.get("deliveryFeeMinor", 0) / 100,
                order.get("totalAmountMinor", 0) / 100,
                order.get("courierSnapshot", {}).get("name", ""),
                order.get("waybillNumber", ""),
                order.get("paymentStatus", ""),
                order.get("fulfilmentStatus", ""),
            ],
        )

    for column in sheet.columns:
        maximum_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(
            maximum_length + 2,
            45,
        )

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def export_orders(database, business_id, status=None, search=None):
    return build_orders_workbook(
        list_orders(database, business_id, status=status, search=search),
    )


def list_notifications(database, business_id, unread_only=False):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("notifications")
        .order_by("createdAt", direction="DESCENDING")
        .limit(50)
        .stream()
    )
    notifications = [serialize_snapshot(snapshot) for snapshot in snapshots]

    if unread_only:
        notifications = [item for item in notifications if not item.get("isRead")]

    return notifications


def mark_notification_read(database, business_id, notification_id):
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("notifications")
        .document(notification_id)
    )

    if not reference.get().exists:
        raise ApiError("notification_not_found", "Notification not found.", 404)

    reference.update({"isRead": True, "readAt": firestore.SERVER_TIMESTAMP})
    return serialize_snapshot(reference.get())
````

### `frontend/src/components/ConfirmDialog.css`

````css
.confirm-dialog p { margin: 0; color: var(--color-text-muted); line-height: 1.6; }
.confirm-dialog__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
.confirm-dialog__actions button { min-height: 40px; padding: 0 16px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-surface); color: var(--color-text); cursor: pointer; font-weight: 600; }
.confirm-dialog__actions .confirm-dialog__danger { border-color: #ef4444; background: #ef4444; color: white; }
````

### `frontend/src/components/ConfirmDialog.jsx`

````jsx
import ModalShell from "./ModalShell";

import "./ConfirmDialog.css";

function ConfirmDialog({ isOpen, title, message, confirmLabel = "Remove", isWorking = false, onCancel, onConfirm }) {
  return (
    <ModalShell isOpen={isOpen} title={title} description="Please confirm this action." onClose={onCancel}>
      <div className="confirm-dialog">
        <p>{message}</p>
        <footer className="confirm-dialog__actions">
          <button type="button" onClick={onCancel} disabled={isWorking}>Cancel</button>
          <button className="confirm-dialog__danger" type="button" onClick={onConfirm} disabled={isWorking}>
            {isWorking ? "Removing..." : confirmLabel}
          </button>
        </footer>
      </div>
    </ModalShell>
  );
}

export default ConfirmDialog;
````

### `frontend/src/components/OrderReceipt.css`

````css
.receipt-layer { position: fixed; inset: 0; z-index: 1400; overflow-y: auto; padding: 30px 18px; color: #20262e; background: rgba(246,248,251,.98); }
.receipt-page { width: min(770px, 100%); margin: 0 auto; text-align: center; }
.receipt-success-mark { display: grid; place-items: center; width: 64px; height: 64px; margin: 0 auto 12px; border-radius: 50%; color: #003b52; background: #08b4ec; }
.receipt-page > h1 { margin: 0; font-size: 1.7rem; }
.receipt-page > p { margin: 8px 0 24px; color: #536173; }
.receipt-card { overflow: hidden; border: 1px solid #aebdca; border-radius: 11px; background: #fff; box-shadow: 0 18px 50px rgba(18,38,63,.12); text-align: left; }
.receipt-card > header { display: flex; justify-content: space-between; padding: 16px 25px; background: #f2f5f8; }
.receipt-card > header div { display: grid; gap: 3px; }
.receipt-card > header div:last-child { text-align: right; }
.receipt-card small { color: #536173; }
.receipt-card > header strong { font-size: 1.25rem; }
.receipt-status,
.receipt-items,
.receipt-details,
.receipt-totals { padding: 24px 25px; border-top: 1px solid #cfd8e1; }
.receipt-card h2 { margin: 0 0 18px; font-size: 1.12rem; }
.receipt-status__track { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); margin-bottom: 20px; }
.receipt-status__track::before { position: absolute; top: 12px; left: 8px; right: 8px; height: 4px; border-radius: 3px; background: linear-gradient(90deg,#087397 0 58%,#dfe5ea 58%); content: ""; }
.receipt-status__track span { position: relative; z-index: 1; display: grid; justify-items: start; gap: 6px; font-weight: 650; }
.receipt-status__track span:nth-child(2) { justify-items: center; }
.receipt-status__track span:last-child { justify-items: end; }
.receipt-status__track svg { box-sizing: content-box; padding: 5px; border-radius: 50%; color: #fff; background: #087397; }
.receipt-status__track .is-muted svg { color: #526273; background: #dfe5ea; }
.receipt-info { display: flex; gap: 10px; padding: 15px; border-radius: 7px; background: #dce7fa; }
.receipt-info span { display: grid; gap: 4px; }
.receipt-info strong { color: #526273; font-size: .72rem; letter-spacing: .05em; }
.receipt-items > div { display: grid; grid-template-columns: 80px 1fr auto; align-items: center; gap: 16px; margin-top: 14px; }
.receipt-item__image { display: grid; place-items: center; width: 80px; height: 80px; overflow: hidden; border: 1px solid #c7d2dc; border-radius: 8px; background: #f2f5f8; }
.receipt-item__image img { width: 100%; height: 100%; object-fit: cover; }
.receipt-items > div > span:nth-child(2) { display: grid; gap: 5px; }
.receipt-details { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
.receipt-details > div { display: grid; align-content: start; gap: 7px; }
.receipt-details small { font-weight: 700; letter-spacing: .05em; }
.receipt-details span { color: #536173; line-height: 1.5; }
.receipt-totals { background: #f2f5f8; }
.receipt-totals > div { display: flex; justify-content: space-between; margin-bottom: 10px; color: #445161; }
.receipt-totals .receipt-total { margin: 15px 0 0; padding-top: 14px; border-top: 1px solid #cbd5df; color: #20262e; font-size: 1.15rem; }
.receipt-total strong:last-child { color: #087397; font-size: 1.4rem; }
.receipt-actions { display: flex; justify-content: center; gap: 14px; margin-top: 24px; }
.receipt-actions button { display: inline-flex; align-items: center; gap: 8px; min-height: 48px; padding: 0 22px; border: 1px solid #8d9bab; border-radius: 7px; color: #20262e; background: #fff; cursor: pointer; font-weight: 700; }
.receipt-actions button:first-child { border-color: #087397; color: #fff; background: #087397; }
@media (max-width: 600px) { .receipt-layer { padding: 18px 10px; } .receipt-details { grid-template-columns: 1fr; } .receipt-items > div { grid-template-columns: 58px 1fr auto; } .receipt-item__image { width: 58px; height: 58px; } .receipt-actions { flex-direction: column; } .receipt-actions button { justify-content: center; } }
````

### `frontend/src/components/OrderReceipt.jsx`

````jsx
import { Check, CircleHelp, Download, Home, Info, Package, Truck } from "lucide-react";
import { downloadReceiptPdf } from "../services/receiptService";
import "./OrderReceipt.css";

function money(minorUnits = 0) {
  return `LKR ${(Number(minorUnits) / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value) {
  const date = value ? new Date(value) : new Date();
  return Number.isNaN(date.getTime()) ? new Date().toLocaleDateString("en-LK") : date.toLocaleDateString("en-LK", { year: "numeric", month: "long", day: "numeric" });
}

export default function OrderReceipt({ business, order, onClose, closeLabel = "Return" }) {
  const address = order.deliveryAddress || order.deliveryAddressObject || {};
  const customer = order.customerSnapshot || {};
  const payment = order.paymentMethod === "deposit" ? "Deposit / balance due" : order.paymentMethod === "paid" ? "Paid" : "Cash on delivery";

  return <div className="receipt-layer">
    <section className="receipt-page">
      <div className="receipt-success-mark"><Check size={25} strokeWidth={3} /></div>
      <h1>Order Confirmed</h1>
      <p>Thank you for your purchase. Your order is being processed.</p>

      <article className="receipt-card">
        <header><div><small>ORDER NUMBER</small><strong>#{order.orderNumber}</strong></div><div><small>ORDER DATE</small><span>{dateLabel(order.createdAt)}</span></div></header>
        <section className="receipt-status">
          <h2>Order Status</h2>
          <div className="receipt-status__track"><span><Package size={15} />Confirmed</span><span><Truck size={15} />Processing</span><span className="is-muted"><Home size={15} />Delivered</span></div>
          <div className="receipt-info"><Info size={18} /><span><strong>TRACKING INFO</strong>Your items are being prepared for shipping. We will provide tracking information when the order is dispatched.</span></div>
        </section>

        <section className="receipt-items"><h2>Items in your order</h2>{(order.items || []).map((item) => <div key={item.variantId || item.id}><span className="receipt-item__image">{item.mediaUrl || item.imageUrl ? <img src={item.mediaUrl || item.imageUrl} alt="" /> : <Package size={25} />}</span><span><strong>{item.name || item.productName}</strong><small>{item.size ? `Variant: ${item.size} | ` : ""}Qty: {item.quantity}</small></span><strong>{money(item.lineTotalMinor ?? Number(item.sellingPrice || 0) * item.quantity * 100)}</strong></div>)}</section>

        <section className="receipt-details"><div><small>SHIPPING ADDRESS</small><strong>{customer.name || order.customerName || "Customer"}</strong><span>{[address.line1, address.line2, address.city, address.district, address.postalCode, address.country].filter(Boolean).join(", ")}</span></div><div><small>PAYMENT METHOD</small><strong>{payment}</strong><span>{order.paymentStatus === "partially-paid" ? `${money(order.balanceAmountMinor)} balance remaining` : "Payment details saved with this order."}</span></div></section>

        <section className="receipt-totals"><div><span>Subtotal</span><strong>{money(order.subtotalMinor)}</strong></div>{order.discountTotalMinor > 0 && <div><span>Discount</span><strong>- {money(order.discountTotalMinor)}</strong></div>}<div><span>Delivery</span><strong>{money(order.deliveryFeeMinor)}</strong></div><div><span>Tax</span><strong>{money(order.taxTotalMinor)}</strong></div><div className="receipt-total"><strong>Total</strong><strong>{money(order.totalAmountMinor)}</strong></div></section>
      </article>

      <div className="receipt-actions"><button type="button" onClick={() => downloadReceiptPdf(business, order)}><Download size={17} /> Download Receipt PDF</button><button type="button" onClick={onClose}><CircleHelp size={17} /> {closeLabel}</button></div>
    </section>
  </div>;
}
````

### `frontend/src/services/notificationService.js`

````javascript
import { apiRequest } from "./apiClient";


export async function getNotifications(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/notifications`);
  return response.notifications;
}


export async function markNotificationRead(businessId, notificationId) {
  const response = await apiRequest(
    `/businesses/${businessId}/notifications/${notificationId}/read`,
    { method: "PATCH" },
  );
  return response.notification;
}
````

### `frontend/src/services/operationService.js`

````javascript
import { apiFileRequest, apiRequest } from "./apiClient";
import { mapOrderForTable } from "./orderService";


export async function generateOrderWaybill(businessId, orderId) {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/waybill`,
    { method: "POST" },
  );
  return mapOrderForTable(response.order);
}


export async function reportFraudOrder(businessId, orderId, reason, note = "") {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/fraud-report`,
    { method: "POST", body: { type: reason, note } },
  );
  return response.fraudReport;
}


export async function reportCourierIssue(
  businessId,
  orderId,
  issueType,
  note = "",
) {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/courier-issues`,
    { method: "POST", body: { type: issueType, note } },
  );
  return response.courierIssue;
}


export async function downloadOrderExport(businessId) {
  const { blob, filename } = await apiFileRequest(
    `/businesses/${businessId}/orders-export.xlsx`,
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = decodeURIComponent(filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


export function printWaybill(order, printWindow = window.open("", "_blank")) {
  if (!printWindow) {
    throw new Error("Allow pop-ups to print the waybill.");
  }

  const itemRows = (order.items ?? [])
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.name)}</td>
          <td>${escapeHtml(item.size || "-")}</td>
          <td>${escapeHtml(item.quantity)}</td>
        </tr>`,
    )
    .join("");

  printWindow.document.write(`<!doctype html>
    <html><head><title>${escapeHtml(order.waybillNumber)}</title>
    <style>
      body{font:14px Arial,sans-serif;color:#0b2440;margin:32px}
      header{display:flex;justify-content:space-between;border-bottom:2px solid #0b3b6e;padding-bottom:16px}
      h1{margin:0;color:#0b3b6e} section{margin-top:22px}
      table{width:100%;border-collapse:collapse} th,td{padding:9px;border:1px solid #cbd5e1;text-align:left}
      .total{font-size:20px;font-weight:700}.muted{color:#64748b}
      @media print{button{display:none}}
    </style></head><body>
      <header><div><h1>Vendly.lk Waybill</h1><div class="muted">${escapeHtml(order.orderNumber)}</div></div>
      <strong>${escapeHtml(order.waybillNumber)}</strong></header>
      <section><h2>Delivery</h2><strong>${escapeHtml(order.customerName)}</strong><br>
      ${escapeHtml(order.phoneNumber)}<br>${escapeHtml(order.deliveryAddress)}</section>
      <section><h2>Courier</h2>${escapeHtml(order.courier)}</section>
      <section><table><thead><tr><th>Item</th><th>Size</th><th>Qty</th></tr></thead>
      <tbody>${itemRows}</tbody></table></section>
      <section class="total">Collect: ${escapeHtml(order.total)}</section>
      <script>window.onload=()=>window.print()</script>
    </body></html>`);
  printWindow.document.close();
}
````

### `frontend/src/services/receiptService.js`

````javascript
import { jsPDF } from "jspdf";

function amount(value = 0) {
  return `LKR ${(Number(value) / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function safeText(value) {
  return String(value || "").replace(/[^\x20-\x7E]/g, "-");
}

export function downloadReceiptPdf(business, order) {
  const pdf = new jsPDF({ unit: "mm", format: "a4" });
  const left = 18;
  const right = 192;
  let y = 18;

  pdf.setFillColor(8, 115, 151);
  pdf.circle(105, y + 3, 7, "F");
  pdf.setDrawColor(255, 255, 255);
  pdf.setLineWidth(1.2);
  pdf.line(101.5, y + 3, 104, y + 5.5);
  pdf.line(104, y + 5.5, 108.5, y);
  y += 18;
  pdf.setTextColor(29, 41, 57);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(19);
  pdf.text("Order Confirmed", 105, y, { align: "center" });
  y += 7;
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(91, 103, 120);
  pdf.text(`Thank you for your purchase from ${safeText(business?.name || "Vendly.lk")}.`, 105, y, { align: "center" });
  y += 12;

  pdf.setFillColor(243, 246, 249);
  pdf.roundedRect(left, y, right - left, 18, 2, 2, "F");
  pdf.setTextColor(71, 84, 103);
  pdf.setFontSize(7);
  pdf.text("ORDER NUMBER", left + 6, y + 6);
  pdf.text("ORDER DATE", right - 6, y + 6, { align: "right" });
  pdf.setTextColor(29, 41, 57);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(12);
  pdf.text(`#${safeText(order.orderNumber)}`, left + 6, y + 13);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  const date = order.createdAt ? new Date(order.createdAt) : new Date();
  pdf.text(date.toLocaleDateString("en-LK"), right - 6, y + 13, { align: "right" });
  y += 27;

  pdf.setFont("helvetica", "bold"); pdf.setFontSize(12); pdf.text("Order Status", left + 6, y);
  y += 9;
  pdf.setDrawColor(8, 115, 151); pdf.setLineWidth(1); pdf.line(left + 8, y, 105, y);
  pdf.setDrawColor(220, 226, 232); pdf.line(105, y, right - 8, y);
  pdf.setFontSize(8); pdf.setTextColor(29, 41, 57);
  pdf.text("Confirmed", left + 8, y + 7); pdf.text("Processing", 105, y + 7, { align: "center" }); pdf.text("Delivered", right - 8, y + 7, { align: "right" });
  y += 14;
  pdf.setFillColor(226, 235, 250); pdf.roundedRect(left + 6, y, right - left - 12, 18, 2, 2, "F");
  pdf.setFont("helvetica", "bold"); pdf.setFontSize(7); pdf.setTextColor(71, 84, 103); pdf.text("TRACKING INFO", left + 12, y + 6);
  pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.text("Your items are being prepared for shipping. Tracking will be available after dispatch.", left + 12, y + 12);
  y += 28;

  pdf.setFont("helvetica", "bold"); pdf.setFontSize(12); pdf.setTextColor(29, 41, 57); pdf.text("Items in your order", left + 6, y);
  y += 8;
  (order.items || []).forEach((item) => {
    if (y > 244) { pdf.addPage(); y = 18; }
    pdf.setFillColor(247, 249, 251); pdf.roundedRect(left + 6, y, 16, 16, 2, 2, "F");
    pdf.setFont("helvetica", "bold"); pdf.setFontSize(9); pdf.text(safeText(item.name || item.productName || "Product"), left + 27, y + 6);
    pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(91, 103, 120); pdf.text(`${item.size ? `Variant: ${safeText(item.size)} | ` : ""}Qty: ${item.quantity}`, left + 27, y + 12);
    pdf.setFont("helvetica", "bold"); pdf.setFontSize(9); pdf.setTextColor(29, 41, 57); pdf.text(amount(item.lineTotalMinor ?? Number(item.sellingPrice || 0) * item.quantity * 100), right - 6, y + 9, { align: "right" });
    y += 20;
  });
  y += 3;

  const address = order.deliveryAddress || order.deliveryAddressObject || {};
  const addressText = [address.line1, address.line2, address.city, address.district, address.postalCode, address.country].filter(Boolean).join(", ");
  pdf.setDrawColor(220, 226, 232); pdf.line(left + 6, y, right - 6, y); y += 8;
  pdf.setFont("helvetica", "bold"); pdf.setFontSize(7); pdf.setTextColor(71, 84, 103); pdf.text("SHIPPING ADDRESS", left + 6, y); pdf.text("PAYMENT METHOD", 112, y);
  pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.setTextColor(29, 41, 57);
  const addressLines = pdf.splitTextToSize(safeText(addressText), 75); pdf.text(addressLines, left + 6, y + 6);
  pdf.text(order.paymentMethod === "deposit" ? "Deposit / balance due" : order.paymentMethod === "paid" ? "Paid" : "Cash on delivery", 112, y + 6);
  y += Math.max(22, addressLines.length * 4 + 10);

  pdf.setFillColor(243, 246, 249); pdf.roundedRect(left, y, right - left, 42, 2, 2, "F");
  const rows = [["Subtotal", order.subtotalMinor], ["Discount", -Number(order.discountTotalMinor || 0)], ["Delivery", order.deliveryFeeMinor], ["Tax", order.taxTotalMinor]];
  pdf.setFontSize(8); rows.forEach(([label, value], index) => { pdf.setFont("helvetica", "normal"); pdf.setTextColor(71, 84, 103); pdf.text(label, left + 7, y + 7 + index * 6); pdf.setTextColor(29, 41, 57); pdf.text(amount(value), right - 7, y + 7 + index * 6, { align: "right" }); });
  pdf.setDrawColor(210, 218, 227); pdf.line(left + 7, y + 31, right - 7, y + 31);
  pdf.setFont("helvetica", "bold"); pdf.setFontSize(12); pdf.text("Total", left + 7, y + 39); pdf.setTextColor(8, 115, 151); pdf.text(amount(order.totalAmountMinor), right - 7, y + 39, { align: "right" });
  pdf.save(`${safeText(order.orderNumber || "vendly-order")}-receipt.pdf`);
}
````

## Feature 16 source — Public short links and catalogue service

Files in this feature: 1

### `backend/app/services/public_catalog_service.py`

````python
from app.core.errors import ApiError
from app.services.product_service import get_product, list_products


def resolve_short_link(database, short_code, expected_type=None):
    snapshot = database.collection("shortLinks").document(short_code).get()

    if not snapshot.exists:
        raise ApiError("public_link_not_found", "This Vendly link is invalid.", 404)

    link = {"shortCode": snapshot.id, **snapshot.to_dict()}

    if link.get("status") != "active":
        raise ApiError("public_link_inactive", "This Vendly link is inactive.", 404)
    if expected_type and link.get("type") != expected_type:
        raise ApiError("public_link_not_found", "This Vendly link is invalid.", 404)

    return link


def public_variant(variant):
    return {
        "id": variant.get("id"),
        "size": variant.get("size", ""),
        "sku": variant.get("sku", ""),
        "availableStock": variant.get("stockAvailable", 0),
        "stockStatus": variant.get("stockStatus", "out-of-stock"),
    }


def public_product(product):
    return {
        "id": product["id"],
        "shortCode": product.get("shortCode", ""),
        "name": product.get("name", ""),
        "colourName": product.get("colourName", ""),
        "colourHex": product.get("colourHex", ""),
        "productType": product.get("productType", ""),
        "categoryId": product.get("categoryId", ""),
        "categoryName": product.get("categoryName", ""),
        "brand": product.get("brand", ""),
        "description": product.get("description", ""),
        "aiDescription": product.get("aiDescription", ""),
        "sellingPriceMinor": product.get("sellingPriceMinor", 0),
        "compareAtPriceMinor": product.get("compareAtPriceMinor", 0),
        "weightGrams": product.get("weightGrams", 0),
        "availableStock": product.get("availableStock", 0),
        "stockStatus": product.get("stockStatus", "out-of-stock"),
        "approvedReviewCount": product.get("approvedReviewCount", 0),
        "media": [
            {
                "type": item.get("type", "image"),
                "url": item.get("url", ""),
            }
            for item in product.get("media", [])
            if item.get("url")
        ],
        "hasSizes": product.get("hasSizes", False),
        "variants": [
            public_variant(variant)
            for variant in product.get("variantSummaries", [])
            if variant.get("stockAvailable", 0) > 0
        ],
    }


def public_business(snapshot):
    business = snapshot.to_dict()
    return {
        "id": snapshot.id,
        "name": business.get("name", ""),
        "shortCode": business.get("shortCode", ""),
        "logoUrl": business.get("logoUrl", ""),
        "phone": business.get("publicPhone", ""),
        "email": business.get("publicEmail", ""),
        "currency": business.get("currency", "LKR"),
        "status": business.get("status", "inactive"),
    }


def get_public_store(database, short_code):
    link = resolve_short_link(database, short_code, "store")
    business_snapshot = database.collection("businesses").document(
        link["businessId"],
    ).get()

    if not business_snapshot.exists or business_snapshot.to_dict().get("status") != "active":
        raise ApiError("store_not_found", "This Vendly store is unavailable.", 404)

    products = list_products(database, business_snapshot.id, status="active")
    return {
        "business": public_business(business_snapshot),
        "products": [public_product(product) for product in products],
    }


def get_public_product(database, short_code):
    link = resolve_short_link(database, short_code, "product")
    business_snapshot = database.collection("businesses").document(
        link["businessId"],
    ).get()

    if not business_snapshot.exists or business_snapshot.to_dict().get("status") != "active":
        raise ApiError("store_not_found", "This Vendly store is unavailable.", 404)

    product = get_product(database, link["businessId"], link["productId"])

    if product.get("status") != "active":
        raise ApiError("product_not_found", "This product is unavailable.", 404)

    return {
        "business": public_business(business_snapshot),
        "product": public_product(product),
    }
````

## Feature 17 source — Storefront catalogue and checkout

Files in this feature: 2

### `frontend/src/pages/StorefrontPage.css`

````css
.storefront {
  --sf-primary: #0872d9;
  --sf-primary-dark: #0058ac;
  --sf-navy: #003158;
  --sf-text: #142238;
  --sf-muted: #667386;
  --sf-bg: #f7f8fc;
  --sf-surface: #ffffff;
  --sf-soft: #f2f4f8;
  --sf-border: #dfe4ec;
  --sf-success: #0fac83;
  --sf-warning: #f19b16;
  --sf-danger: #e24848;
  --sf-shadow: 0 14px 42px rgba(19, 45, 78, 0.09);
  min-height: 100vh;
  color: var(--sf-text);
  background: var(--sf-bg);
}

.storefront--dark {
  --sf-primary: #43a0ff;
  --sf-primary-dark: #1683eb;
  --sf-navy: #021e37;
  --sf-text: #eef6ff;
  --sf-muted: #9aabc0;
  --sf-bg: #07111d;
  --sf-surface: #0d1927;
  --sf-soft: #122131;
  --sf-border: #23374d;
  --sf-shadow: 0 18px 46px rgba(0, 0, 0, 0.28);
}

.storefront *,
.storefront *::before,
.storefront *::after {
  box-sizing: border-box;
}

.storefront button,
.storefront input,
.storefront select,
.storefront textarea {
  font: inherit;
}

.storefront button {
  color: inherit;
}

.storefront h1,
.storefront h2,
.storefront h3,
.storefront p {
  margin: 0;
}

.storefront-loading {
  display: grid;
  min-height: 100vh;
  place-content: center;
  justify-items: center;
  gap: 14px;
  color: #19314e;
  background: #f7f9fc;
}

.storefront-loading__mark {
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  border-radius: 15px;
  color: #fff;
  font-size: 1.8rem;
  font-weight: 800;
  background: linear-gradient(145deg, #008df3, #003c75);
  box-shadow: 0 12px 26px rgba(0, 99, 190, 0.25);
}

.storefront-loading--error {
  color: #b22c2c;
}

/* Shared public-store navigation */
.storefront-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 50;
  display: flex;
  width: 180px;
  padding: 26px 18px 18px;
  flex-direction: column;
  color: #eaf5ff;
  background:
    radial-gradient(circle at 8% 75%, rgba(7, 119, 221, 0.18), transparent 30%),
    linear-gradient(165deg, #003158 0%, #002a4c 58%, #00233f 100%);
  box-shadow: 8px 0 34px rgba(2, 28, 52, 0.12);
}

.storefront-brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 4px 7px;
}

.storefront-brand > span,
.storefront-brand > img {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 8px;
  color: var(--sf-navy);
  object-fit: contain;
  font-size: 1.15rem;
  font-weight: 900;
  background: #fff;
}

.storefront-brand div {
  display: grid;
}

.storefront-brand strong {
  font-size: 1.42rem;
  letter-spacing: -0.04em;
}

.storefront-brand small {
  margin-top: 1px;
  color: #adc2d6;
  font-size: 0.72rem;
}

.storefront-nav {
  display: grid;
  gap: 7px;
  margin-top: 48px;
}

.storefront-nav button,
.storefront-sidebar__assistant {
  display: flex;
  width: 100%;
  min-height: 48px;
  padding: 0 15px;
  align-items: center;
  gap: 13px;
  border: 0;
  border-radius: 9px;
  color: #c4d5e6;
  text-align: left;
  font-size: 0.9rem;
  font-weight: 650;
  background: transparent;
  cursor: pointer;
  transition: color 160ms ease, background 160ms ease, transform 160ms ease;
}

.storefront-nav button:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
  transform: translateX(2px);
}

.storefront-nav button.is-active {
  color: #032c50;
  background: linear-gradient(135deg, #56a8ff, #3d91ec);
  box-shadow: 0 9px 20px rgba(0, 105, 208, 0.22);
}

.storefront-sidebar__assistant {
  min-height: 44px;
  margin-top: auto;
  justify-content: center;
  border: 1px solid rgba(64, 164, 255, 0.7);
  color: #e7f4ff;
  font-size: 0.78rem;
  background: rgba(0, 92, 174, 0.18);
}

.storefront-sidebar__assistant:hover {
  background: rgba(21, 131, 234, 0.27);
}

.storefront-sidebar__close {
  display: none;
}

.storefront-sidebar-backdrop {
  display: none;
}

.storefront-workspace {
  min-height: 100vh;
  margin-left: 180px;
  background: var(--sf-bg);
}

.storefront-topbar {
  position: sticky;
  top: 0;
  z-index: 35;
  display: flex;
  height: 64px;
  padding: 0 27px;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--sf-border);
  background: color-mix(in srgb, var(--sf-bg) 91%, transparent);
  backdrop-filter: blur(14px);
}

.storefront-topbar__title,
.storefront-topbar__actions,
.storefront-topbar__title > div:first-child {
  display: flex;
  align-items: center;
}

.storefront-customer-avatar {
  display: grid;
  width: 27px;
  height: 27px;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 800;
  background: var(--sf-primary);
}

.storefront-topbar__title {
  min-width: 0;
  gap: 10px;
}

.storefront-topbar__title > div:last-child {
  display: grid;
  min-width: 0;
}

.storefront-topbar__title strong {
  overflow: hidden;
  font-size: 1.15rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.storefront-topbar__title small {
  display: none;
  color: var(--sf-muted);
}

.storefront-topbar__actions {
  gap: 5px;
}

.storefront-icon-button,
.storefront-cart-button,
.storefront-sidebar__close {
  display: grid;
  width: 40px;
  height: 40px;
  padding: 0;
  place-items: center;
  border: 0;
  border-radius: 10px;
  color: var(--sf-muted);
  background: transparent;
  cursor: pointer;
}

.storefront-icon-button:hover,
.storefront-cart-button:hover {
  color: var(--sf-primary);
  background: var(--sf-soft);
}

.storefront-sidebar__close {
  display: none;
}

.storefront-topbar__menu {
  display: none;
}

.storefront-cart-button {
  position: relative;
}

.storefront-cart-button span {
  position: absolute;
  top: 1px;
  right: 0;
  display: grid;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  place-items: center;
  border: 2px solid var(--sf-bg);
  border-radius: 999px;
  color: #fff;
  font-size: 0.65rem;
  font-weight: 800;
  background: var(--sf-primary);
}

.storefront-error {
  position: fixed;
  z-index: 120;
  top: 78px;
  left: 50%;
  display: flex;
  width: min(560px, calc(100vw - 36px));
  padding: 12px 15px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #ef9d9d;
  border-radius: 10px;
  color: #a72525;
  background: #fff2f2;
  box-shadow: var(--sf-shadow);
  transform: translateX(-50%);
}

.storefront-error button {
  display: grid;
  padding: 3px;
  place-items: center;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.storefront-page {
  width: min(1180px, calc(100% - 46px));
  margin: 0 auto;
  padding: 30px 0 48px;
}

/* Catalog */
.storefront-catalog-hero {
  text-align: center;
}

.storefront-catalog-hero h1 {
  margin-top: 2px;
  color: var(--sf-text);
  font-size: clamp(1.8rem, 4vw, 2.35rem);
  line-height: 1.15;
  letter-spacing: -0.04em;
}

.storefront-catalog-hero h1 span {
  color: var(--sf-primary-dark);
}

.storefront-catalog-hero p {
  margin-top: 9px;
  color: var(--sf-muted);
}

.storefront-search {
  display: flex;
  width: min(570px, 100%);
  height: 50px;
  margin: 26px auto 18px;
  padding: 0 15px;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--sf-border);
  border-radius: 999px;
  color: var(--sf-muted);
  background: var(--sf-surface);
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

.storefront-search:focus-within {
  border-color: var(--sf-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--sf-primary) 15%, transparent);
}

.storefront-search input {
  width: 100%;
  border: 0;
  outline: 0;
  color: var(--sf-text);
  background: transparent;
}

.storefront-search input::placeholder {
  color: var(--sf-muted);
}

.storefront-categories {
  display: flex;
  margin-bottom: 28px;
  justify-content: center;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.storefront-categories::-webkit-scrollbar {
  display: none;
}

.storefront-categories button {
  min-width: 72px;
  padding: 8px 17px;
  border: 1px solid var(--sf-border);
  border-radius: 999px;
  color: var(--sf-muted);
  background: var(--sf-surface);
  cursor: pointer;
  white-space: nowrap;
}

.storefront-categories button:hover,
.storefront-categories button.is-active {
  border-color: var(--sf-primary);
  color: #fff;
  background: var(--sf-primary);
}

.storefront-product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 20px;
}

.storefront-product-card {
  overflow: hidden;
  border: 1px solid var(--sf-border);
  border-radius: 14px;
  background: var(--sf-surface);
  box-shadow: 0 5px 15px rgba(27, 49, 76, 0.04);
  transition: transform 220ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 220ms ease;
}

.storefront-product-card:hover {
  box-shadow: var(--sf-shadow);
  transform: translateY(-4px);
}

.storefront-product-card__media {
  position: relative;
  display: grid;
  height: 185px;
  place-items: center;
  overflow: hidden;
  color: var(--sf-primary);
  background: var(--sf-soft);
}

.storefront-product-card__media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 350ms ease;
}

.storefront-product-card:hover .storefront-product-card__media img {
  transform: scale(1.045);
}

.storefront-product-card__media strong,
.storefront-product-card__media small {
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  color: var(--sf-navy);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 4px 12px rgba(19, 40, 64, 0.1);
}

.storefront-product-card__media small {
  top: 48px;
  color: #7a8796;
  text-decoration: line-through;
}

.storefront-product-card__body {
  display: grid;
  gap: 8px;
  padding: 17px;
}

.storefront-product-card__body > span {
  color: var(--sf-primary);
  font-size: 0.72rem;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.storefront-product-card__body h2 {
  min-height: 48px;
  font-size: 1.15rem;
  line-height: 1.28;
}

.storefront-product-card__body > p {
  display: -webkit-box;
  min-height: 44px;
  overflow: hidden;
  color: var(--sf-muted);
  font-size: 0.83rem;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.storefront-product-card__stock {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--sf-success);
  font-size: 0.76rem;
}

.storefront-product-card__stock > span {
  display: inline-flex;
  margin-left: auto;
  align-items: center;
  gap: 4px;
  color: #f0a10c;
}

.storefront-product-card__variants {
  display: flex;
  gap: 5px;
  overflow-x: auto;
}

.storefront-product-card__variants button {
  padding: 5px 8px;
  border: 1px solid var(--sf-border);
  border-radius: 6px;
  color: var(--sf-muted);
  background: var(--sf-soft);
  cursor: pointer;
  white-space: nowrap;
}

.storefront-product-card__variants button:hover {
  border-color: var(--sf-primary);
  color: var(--sf-primary);
}

.storefront-product-card__actions {
  display: grid;
  grid-template-columns: 1fr 42px;
  gap: 7px;
  margin-top: 3px;
}

.storefront-product-card__actions button {
  display: flex;
  height: 40px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--sf-primary);
  border-radius: 8px;
  color: #fff;
  font-size: 0.82rem;
  font-weight: 750;
  background: var(--sf-primary);
  cursor: pointer;
}

.storefront-product-card__actions button:last-child {
  color: var(--sf-primary);
  background: transparent;
}

.storefront-product-card__actions button:disabled {
  border-color: var(--sf-border);
  color: var(--sf-muted);
  background: var(--sf-soft);
  cursor: not-allowed;
}

.storefront-empty-state {
  display: grid;
  min-height: 250px;
  grid-column: 1 / -1;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: var(--sf-muted);
  text-align: center;
}

.storefront-empty-state h2 {
  color: var(--sf-text);
}

/* Chat */
.storefront-chat-page {
  display: grid;
  width: min(1280px, calc(100% - 36px));
  height: calc(100vh - 64px);
  min-height: 0;
  padding: 0;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 18px;
}

.storefront-chat-panel,
.storefront-draft {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--sf-border) 82%, transparent);
  border-radius: 4px;
  background: var(--sf-surface);
  box-shadow:
    0 18px 45px rgba(7, 45, 78, 0.1),
    0 2px 8px rgba(7, 45, 78, 0.05);
}

.storefront-chat-panel {
  display: grid;
  min-width: 0;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--sf-primary) 3%, var(--sf-surface)), var(--sf-surface) 18%);
}

.storefront-chat-panel__header,
.storefront-draft > header {
  display: flex;
  height: 58px;
  padding: 0 19px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--sf-border);
  background: color-mix(in srgb, var(--sf-surface) 92%, var(--sf-primary) 8%);
}

.storefront-chat-panel__header > div,
.storefront-chat-panel__header > small,
.storefront-draft > header {
  display: flex;
  align-items: center;
  gap: 9px;
}

.storefront-chat-panel__header > div > span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sf-success);
}

.storefront-chat-panel__header small {
  padding: 6px 11px;
  border-radius: 999px;
  color: var(--sf-success);
  background: color-mix(in srgb, var(--sf-success) 11%, transparent);
}

.storefront-chat-messages {
  overflow-y: auto;
  padding: 26px 24px 38px;
  scrollbar-color: var(--sf-border) transparent;
}

.storefront-chat-message {
  display: flex;
  margin-bottom: 19px;
  align-items: flex-start;
  gap: 10px;
}

.storefront-chat-message--customer {
  flex-direction: row-reverse;
}

.storefront-chat-message__avatar {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 12px;
  color: #005699;
  background: #55a8ff;
  box-shadow: 0 6px 16px rgba(26, 123, 222, 0.22);
}

.storefront-chat-message--customer .storefront-chat-message__avatar {
  color: #fff;
  background: #0b518e;
}

.storefront-chat-message__content {
  display: grid;
  max-width: min(72%, 560px);
  gap: 8px;
}

.storefront-chat-message__content > p,
.storefront-typing {
  padding: 14px 17px;
  border: 1px solid color-mix(in srgb, var(--sf-border) 70%, transparent);
  border-radius: 6px 19px 19px 19px;
  color: var(--sf-text);
  line-height: 1.48;
  background: var(--sf-soft);
  font-size: 0.88rem;
  box-shadow: 0 3px 7px rgba(24, 44, 70, 0.05);
}

.storefront-chat-message--customer .storefront-chat-message__content > p {
  border-color: transparent;
  border-radius: 19px 6px 19px 19px;
  color: #fff;
  background: #086abd;
}

.storefront-chat-catalog {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.storefront-chat-catalog-card {
  display: grid;
  min-width: 0;
  padding: 10px;
  gap: 7px;
  border: 2px solid var(--sf-border);
  border-radius: 18px;
  color: var(--sf-text);
  text-align: left;
  background: var(--sf-surface);
  box-shadow: 0 7px 18px rgba(7, 55, 91, 0.06);
}

.storefront-chat-catalog-card:hover,
.storefront-chat-catalog-card.is-selected {
  border-color: var(--sf-primary);
}

.storefront-chat-catalog img,
.storefront-chat-catalog-card > svg {
  width: 100%;
  height: 150px;
  border-radius: 13px;
  object-fit: cover;
}

.storefront-chat-catalog strong,
.storefront-chat-catalog small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.storefront-chat-catalog strong {
  font-size: 0.92rem;
  line-height: 1.3;
}

.storefront-chat-catalog small {
  margin-top: 3px;
  color: var(--sf-muted);
  font-size: 0.78rem;
}

.storefront-chat-catalog-card > button,
.storefront-chat-catalog-card__select {
  width: 100%;
  min-height: 38px;
  padding: 8px 9px;
  border: 0;
  border-radius: 12px;
  color: var(--sf-text);
  background: var(--sf-surface-muted);
  cursor: pointer;
}

.storefront-chat-catalog-card__select {
  font-weight: 700;
}

.storefront-chat-catalog-card.is-selected .storefront-chat-catalog-card__select {
  color: #fff;
  background: var(--sf-primary);
}

.storefront-chat-catalog-card__quantity {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.storefront-chat-catalog-card__quantity button {
  width: 38px;
  height: 38px;
  padding: 0;
  border: 1px solid var(--sf-primary);
  border-radius: 11px;
  color: var(--sf-primary);
  background: transparent;
  font-size: 1.25rem;
  font-weight: 700;
}

.storefront-chat-catalog-card button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.storefront-chat-product {
  padding: 13px;
  border: 1px solid var(--sf-border);
  border-radius: 18px;
  background: var(--sf-surface);
}

.storefront-chat-product > div:first-child {
  display: flex;
  align-items: center;
  gap: 9px;
}

.storefront-chat-product img,
.storefront-chat-product > div:first-child > svg {
  width: 76px;
  height: 76px;
  border-radius: 13px;
  object-fit: cover;
}

.storefront-chat-product span {
  display: grid;
}

.storefront-chat-product__description {
  margin-top: 10px !important;
  color: var(--sf-muted);
  font-size: 0.76rem;
  line-height: 1.5;
}

.storefront-chat-product small {
  margin-top: 3px;
  color: var(--sf-primary);
}

.storefront-chat-product__variants {
  display: grid;
  margin-top: 9px;
  gap: 8px;
}

.storefront-chat-product__variant-row {
  display: flex;
  min-height: 46px;
  padding: 6px 8px 6px 10px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--sf-border);
  border-radius: 10px;
  background: var(--sf-soft);
}

.storefront-chat-product__variant-row.is-selected {
  border-color: var(--sf-primary);
  background: color-mix(in srgb, var(--sf-primary) 8%, var(--sf-surface));
}

.storefront-chat-product__variant-row > span {
  display: grid;
  gap: 2px;
}

.storefront-chat-product__variant-row > span small {
  margin: 0;
  color: var(--sf-muted);
  font-size: 0.67rem;
}

.storefront-chat-product__variant-row > button,
.storefront-chat-product__quantity button {
  display: inline-flex;
  min-width: 34px;
  height: 34px;
  padding: 0 10px;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1px solid var(--sf-primary);
  border-radius: 8px;
  color: var(--sf-primary);
  font-size: 0.72rem;
  background: transparent;
  cursor: pointer;
}

.storefront-chat-product__quantity {
  display: flex;
  align-items: center;
  gap: 5px;
}

.storefront-chat-product__quantity input {
  width: 48px;
  height: 34px;
  padding: 0 3px;
  border: 1px solid var(--sf-border);
  border-radius: 8px;
  color: var(--sf-text);
  text-align: center;
  background: var(--sf-surface);
}

.storefront-chat-product__quantity button:disabled,
.storefront-chat-product__variant-row > button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.storefront-chat-confirmation {
  display: grid;
  padding: 13px;
  gap: 11px;
  border: 1px solid color-mix(in srgb, var(--sf-primary) 45%, var(--sf-border));
  border-radius: 18px;
  background: var(--sf-surface);
  box-shadow: 0 8px 22px rgba(7, 70, 128, 0.08);
}

.storefront-chat-confirmation > strong {
  color: var(--sf-primary-dark);
  font-size: 0.84rem;
}

.storefront-chat-confirmation__items,
.storefront-chat-confirmation__customer {
  display: grid;
  gap: 6px;
}

.storefront-chat-confirmation__items > span {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--sf-muted);
  font-size: 0.74rem;
}

.storefront-chat-confirmation__items > span strong {
  color: var(--sf-text);
  white-space: nowrap;
}

.storefront-chat-confirmation__customer {
  padding-top: 9px;
  border-top: 1px solid var(--sf-border);
  color: var(--sf-muted);
  font-size: 0.72rem;
}

.storefront-chat-confirmation__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
}

.storefront-chat-confirmation__actions button {
  display: flex;
  min-height: 35px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--sf-border);
  border-radius: 11px;
  color: var(--sf-muted);
  font-size: 0.72rem;
  font-weight: 700;
  background: var(--sf-surface);
  cursor: pointer;
}

.storefront-chat-confirmation__actions button:last-child {
  border-color: var(--sf-primary);
  color: #fff;
  background: var(--sf-primary);
}

.storefront-chat-quick-actions {
  display: flex;
  padding: 8px 16px;
  gap: 7px;
  overflow-x: auto;
  border-top: 1px solid var(--sf-border);
  background: color-mix(in srgb, var(--sf-surface) 88%, var(--sf-primary) 12%);
}

.storefront-chat-quick-actions button {
  padding: 6px 10px;
  border: 1px solid var(--sf-border);
  border-radius: 999px;
  color: var(--sf-primary);
  font-size: 0.72rem;
  background: var(--sf-surface);
  cursor: pointer;
  white-space: nowrap;
}

.storefront-chat-input {
  display: grid;
  padding: 15px 16px 17px;
  grid-template-columns: 1fr 45px;
  gap: 10px;
  border-top: 1px solid var(--sf-border);
  background: color-mix(in srgb, var(--sf-surface) 90%, var(--sf-primary) 10%);
}

.storefront-chat-input input {
  min-width: 0;
  height: 45px;
  padding: 0 15px;
  border: 1px solid var(--sf-border);
  border-radius: 14px;
  outline: 0;
  color: var(--sf-text);
  background: var(--sf-surface);
}

.storefront-chat-input input:focus {
  border-color: var(--sf-primary);
}

.storefront-chat-input button {
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 14px;
  color: #fff;
  background: var(--sf-primary);
  cursor: pointer;
}

.storefront-chat-input button:disabled,
.storefront-draft__bottom > button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.storefront-typing {
  display: flex;
  width: 60px;
  gap: 4px;
}

.storefront-typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--sf-muted);
  animation: storefrontTyping 1s infinite ease-in-out;
}

.storefront-typing i:nth-child(2) { animation-delay: 0.15s; }
.storefront-typing i:nth-child(3) { animation-delay: 0.3s; }

@keyframes storefrontTyping {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.storefront-draft {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.storefront-draft > header {
  justify-content: flex-start;
  color: var(--sf-text);
}

.storefront-draft > header svg {
  color: var(--sf-primary);
}

.storefront-draft > header h2 {
  font-size: 0.9rem;
}

.storefront-draft > section,
.storefront-draft__bottom > section {
  padding: 22px 18px;
  border-bottom: 1px solid var(--sf-border);
}

.storefront-draft h3 {
  margin-bottom: 12px;
  color: var(--sf-muted);
  font-size: 0.69rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.storefront-draft__items {
  display: grid;
  gap: 8px;
}

.storefront-draft__items article {
  display: grid;
  padding: 11px;
  align-items: center;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 10px;
  border: 1px solid var(--sf-border);
  border-radius: 14px;
  background: var(--sf-soft);
}

.storefront-draft__item-details {
  display: grid;
  gap: 3px;
}

.storefront-draft__item-image {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  overflow: hidden;
  border-radius: 11px;
  color: var(--sf-primary);
  background: var(--sf-surface);
}

.storefront-draft__item-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.storefront-draft__items article strong {
  font-size: 0.82rem;
}

.storefront-draft__items article span,
.storefront-draft__items article small,
.storefront-draft__items > p {
  color: var(--sf-muted);
  font-size: 0.76rem;
}

.storefront-draft__items article small {
  color: var(--sf-primary);
}

.storefront-draft__items article button {
  display: grid;
  padding: 5px;
  place-items: center;
  border: 0;
  color: var(--sf-muted);
  background: transparent;
  cursor: pointer;
}

.storefront-draft__field {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.storefront-draft__field > span {
  color: var(--sf-muted);
  font-size: 0.72rem;
}

.storefront-draft__field > strong {
  min-height: 43px;
  padding: 11px;
  border: 1px solid var(--sf-border);
  border-radius: 12px;
  font-size: 0.83rem;
  font-weight: 500;
  background: var(--sf-soft);
}

.storefront-draft__field > strong.is-empty {
  color: #a1a8b2;
}

.storefront-draft__bottom {
  display: grid;
  margin-top: auto;
  gap: 10px;
}

.storefront-draft__bottom > section {
  padding-bottom: 8px;
  border: 0;
}

.storefront-draft__status {
  display: flex;
  padding: 10px 12px;
  align-items: center;
  gap: 8px;
  border: 1px solid #f3ca89;
  border-radius: 12px;
  color: var(--sf-warning);
  font-size: 0.76rem;
  background: color-mix(in srgb, var(--sf-warning) 9%, transparent);
}

.storefront-draft__status > span {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
}

.storefront-draft__status.is-active {
  border-color: color-mix(in srgb, var(--sf-success) 45%, var(--sf-border));
  color: var(--sf-success);
  background: color-mix(in srgb, var(--sf-success) 9%, transparent);
}

.storefront-draft__bottom > button {
  display: flex;
  height: 43px;
  margin: 0 18px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: 13px;
  color: #fff;
  font-weight: 700;
  background: var(--sf-primary);
  cursor: pointer;
}

.storefront-draft__bottom > small {
  padding: 0 18px 15px;
  color: var(--sf-muted);
  text-align: center;
}

/* Contact */
.storefront-contact-page {
  width: min(900px, calc(100% - 46px));
  padding-top: 62px;
}

.storefront-contact-hero {
  text-align: center;
}

.storefront-contact-hero h1 {
  font-size: clamp(1.8rem, 4vw, 2.4rem);
  letter-spacing: -0.04em;
}

.storefront-contact-hero h1 span {
  color: var(--sf-primary-dark);
}

.storefront-contact-hero p {
  margin-top: 14px;
  color: var(--sf-muted);
}

.storefront-contact-grid {
  display: grid;
  margin-top: 50px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 28px;
}

.storefront-contact-card {
  min-height: 310px;
  padding: 32px;
  border: 1px solid var(--sf-border);
  border-radius: 13px;
  background: var(--sf-surface);
  box-shadow: 0 8px 24px rgba(31, 58, 92, 0.04);
}

.storefront-contact-card__icon {
  display: grid;
  width: 58px;
  height: 58px;
  place-items: center;
  border-radius: 13px;
  color: var(--sf-primary-dark);
  background: color-mix(in srgb, var(--sf-primary) 13%, var(--sf-surface));
}

.storefront-contact-card h2 {
  margin-top: 28px;
  font-size: 1.28rem;
}

.storefront-contact-card p {
  min-height: 45px;
  margin-top: 9px;
  color: var(--sf-muted);
  font-size: 0.86rem;
  line-height: 1.5;
}

.storefront-contact-card > button {
  display: flex;
  width: 100%;
  min-height: 60px;
  margin-top: 25px;
  padding: 0 16px;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 0;
  border-radius: 9px;
  color: var(--sf-navy);
  text-align: left;
  background: var(--sf-soft);
  cursor: pointer;
}

.storefront--dark .storefront-contact-card > button {
  color: var(--sf-text);
}

.storefront-contact-card > button:disabled {
  color: var(--sf-muted);
  cursor: default;
}

.storefront-contact-note {
  display: flex;
  width: fit-content;
  margin: 26px auto 0;
  padding: 12px 16px;
  align-items: center;
  gap: 9px;
  color: var(--sf-muted);
}

.storefront-contact-note div {
  display: grid;
}

.storefront-contact-note strong {
  color: var(--sf-text);
}

.storefront-contact-note span {
  font-size: 0.73rem;
}

/* Cart */
.storefront-modal-backdrop,
.storefront-sidebar-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  border: 0;
  background: rgba(1, 18, 34, 0.46);
  backdrop-filter: blur(3px);
}

.storefront-cart {
  position: fixed;
  inset: 0 -390px 0 auto;
  z-index: 90;
  display: grid;
  width: min(390px, 100vw);
  grid-template-rows: auto minmax(0, 1fr) auto;
  border-left: 1px solid var(--sf-border);
  background: var(--sf-surface);
  box-shadow: -18px 0 50px rgba(0, 23, 45, 0.18);
  transition: right 260ms cubic-bezier(0.22, 1, 0.36, 1);
}

.storefront-cart--open {
  right: 0;
}

.storefront-cart > header {
  display: flex;
  min-height: 66px;
  padding: 0 19px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--sf-border);
}

.storefront-cart > header > div {
  display: flex;
  align-items: center;
  gap: 9px;
}

.storefront-cart h2 {
  font-size: 1.15rem;
}

.storefront-cart > header span {
  display: grid;
  min-width: 24px;
  height: 24px;
  padding: 0 6px;
  place-items: center;
  border-radius: 999px;
  color: #fff;
  font-size: 0.75rem;
  background: var(--sf-primary-dark);
}

.storefront-cart > header button,
.storefront-cart__items article > button {
  display: grid;
  padding: 6px;
  place-items: center;
  border: 0;
  color: var(--sf-muted);
  background: transparent;
  cursor: pointer;
}

.storefront-cart__items {
  padding: 16px;
  overflow-y: auto;
}

.storefront-cart__items article {
  display: grid;
  margin-bottom: 12px;
  padding: 11px;
  grid-template-columns: 70px minmax(0, 1fr) auto;
  gap: 11px;
  border: 1px solid var(--sf-border);
  border-radius: 10px;
  background: var(--sf-soft);
}

.storefront-cart__image {
  display: grid;
  width: 70px;
  height: 70px;
  place-items: center;
  overflow: hidden;
  border-radius: 8px;
  color: var(--sf-primary);
  background: var(--sf-surface);
}

.storefront-cart__image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.storefront-cart__details {
  display: grid;
  align-content: center;
  gap: 4px;
}

.storefront-cart__details > strong {
  font-size: 0.82rem;
}

.storefront-cart__details > span {
  color: var(--sf-primary);
  font-size: 0.74rem;
}

.storefront-cart__details > div {
  display: flex;
  width: fit-content;
  margin-top: 3px;
  align-items: center;
  gap: 6px;
  border-radius: 6px;
  background: var(--sf-surface);
}

.storefront-cart__details > div button {
  display: grid;
  width: 25px;
  height: 25px;
  padding: 0;
  place-items: center;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.storefront-cart__details > div strong {
  min-width: 18px;
  text-align: center;
  font-size: 0.75rem;
}

.storefront-cart__empty {
  display: grid;
  min-height: 100%;
  place-content: center;
  justify-items: center;
  gap: 8px;
  color: var(--sf-muted);
  text-align: center;
}

.storefront-cart__empty h3 {
  color: var(--sf-text);
}

.storefront-cart > footer {
  display: grid;
  padding: 19px;
  gap: 12px;
  border-top: 1px solid var(--sf-border);
}

.storefront-cart > footer > div {
  display: flex;
  justify-content: space-between;
}

.storefront-cart > footer > div:nth-child(2) {
  font-size: 1.2rem;
}

.storefront-cart > footer small {
  color: var(--sf-muted);
  font-size: 0.7rem;
}

.storefront-cart > footer > button {
  display: flex;
  height: 48px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  font-weight: 700;
  background: var(--sf-primary);
  cursor: pointer;
}

.storefront-cart > footer > button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* Checkout modal */
.storefront-modal-layer,
.storefront-success-layer {
  position: fixed;
  inset: 0;
  z-index: 150;
  display: grid;
  padding: 24px;
  place-items: center;
}

.storefront-modal-layer .storefront-modal-backdrop {
  z-index: -1;
}

.storefront-checkout-modal {
  width: min(620px, 100%);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  border: 1px solid var(--sf-border);
  border-radius: 16px;
  color: var(--sf-text);
  background: var(--sf-surface);
  box-shadow: 0 30px 80px rgba(1, 20, 38, 0.3);
  animation: storefrontModalIn 220ms cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes storefrontModalIn {
  from { opacity: 0; transform: translateY(16px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.storefront-checkout-modal > header {
  display: grid;
  padding: 20px 23px;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--sf-border);
}

.storefront-checkout-modal > header > span {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 50%;
  color: var(--sf-primary-dark);
  background: color-mix(in srgb, var(--sf-primary) 12%, var(--sf-surface));
}

.storefront-checkout-modal > header h2 {
  font-size: 1.28rem;
}

.storefront-checkout-modal > header p {
  margin-top: 2px;
  color: var(--sf-muted);
  font-size: 0.76rem;
}

.storefront-checkout-modal > header button {
  display: grid;
  padding: 6px;
  place-items: center;
  border: 0;
  color: var(--sf-muted);
  background: transparent;
  cursor: pointer;
}

.storefront-checkout-modal__body {
  display: grid;
  padding: 22px 23px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 17px 20px;
}

.storefront-checkout-modal label {
  display: grid;
  gap: 7px;
  font-size: 0.78rem;
  font-weight: 650;
}

.storefront-checkout-modal label.is-wide {
  grid-column: 1 / -1;
}

.storefront-checkout-modal label > div {
  display: flex;
  min-height: 46px;
  padding: 0 12px;
  align-items: center;
  gap: 9px;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--sf-muted);
  background: var(--sf-soft);
}

.storefront-checkout-modal label > div:focus-within {
  border-color: var(--sf-primary);
}

.storefront-checkout-modal input,
.storefront-checkout-modal textarea {
  width: 100%;
  border: 0;
  outline: 0;
  color: var(--sf-text);
  background: transparent;
  resize: vertical;
}

.storefront-checkout-modal textarea {
  padding: 12px 0;
}

.storefront-checkout-modal input::placeholder,
.storefront-checkout-modal textarea::placeholder {
  color: #959daa;
}

.storefront-checkout-summary {
  display: flex;
  margin: 0 23px 20px;
  padding: 13px 15px;
  align-items: center;
  gap: 18px;
  border: 1px solid var(--sf-border);
  border-radius: 9px;
  background: var(--sf-soft);
}

.storefront-checkout-summary span {
  white-space: nowrap;
}

.storefront-checkout-summary small {
  margin-left: auto;
  color: var(--sf-muted);
  text-align: right;
}

.storefront-checkout-modal > footer {
  display: flex;
  padding: 16px 23px;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  border-top: 1px solid var(--sf-border);
  background: color-mix(in srgb, var(--sf-soft) 65%, var(--sf-surface));
}

.storefront-checkout-modal > footer > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--sf-muted);
  font-size: 0.72rem;
}

.storefront-checkout-modal > footer > span svg {
  color: var(--sf-success);
}

.storefront-checkout-modal > footer > div {
  display: flex;
  gap: 9px;
}

.storefront-checkout-modal > footer button {
  display: inline-flex;
  min-height: 40px;
  padding: 0 18px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid var(--sf-border);
  border-radius: 8px;
  background: var(--sf-surface);
  cursor: pointer;
}

.storefront-checkout-modal > footer button[type="submit"] {
  border-color: var(--sf-primary-dark);
  color: #fff;
  background: var(--sf-primary-dark);
}

.storefront-checkout-modal > footer button:disabled {
  opacity: 0.55;
  cursor: wait;
}

/* Order confirmation */
.storefront-success-layer {
  z-index: 200;
  overflow-y: auto;
  background: var(--sf-bg);
}

.storefront-success {
  width: min(670px, 100%);
  padding: 48px;
  border: 1px solid var(--sf-border);
  border-radius: 16px;
  color: var(--sf-text);
  text-align: center;
  background: var(--sf-surface);
  box-shadow: var(--sf-shadow);
}

.storefront-success__icon {
  display: grid;
  width: 88px;
  height: 88px;
  margin: 0 auto 24px;
  place-items: center;
  border: 2px solid #8de0c9;
  border-radius: 50%;
  color: #fff;
  background: color-mix(in srgb, var(--sf-success) 10%, var(--sf-surface));
}

.storefront-success__icon svg {
  padding: 8px;
  border-radius: 50%;
  background: var(--sf-success);
}

.storefront-success > h1 {
  font-size: 1.8rem;
  letter-spacing: -0.04em;
}

.storefront-success > p {
  max-width: 510px;
  margin: 14px auto 0;
  color: var(--sf-muted);
  line-height: 1.55;
}

.storefront-success__items {
  margin-top: 36px;
  text-align: left;
}

.storefront-success__items h2 {
  display: flex;
  margin-bottom: 12px;
  align-items: center;
  gap: 8px;
  font-size: 1.08rem;
}

.storefront-success__items > div {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
  gap: 10px;
}

.storefront-success__items article {
  display: grid;
  padding: 9px;
  gap: 3px;
  border: 1px solid var(--sf-border);
  border-radius: 9px;
  background: var(--sf-soft);
}

.storefront-success__items article > div {
  display: grid;
  height: 92px;
  margin-bottom: 4px;
  place-items: center;
  overflow: hidden;
  border-radius: 7px;
  color: var(--sf-primary);
  background: var(--sf-surface);
}

.storefront-success__items article img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.storefront-success__items article strong {
  font-size: 0.75rem;
}

.storefront-success__items article span,
.storefront-success__items article small {
  color: var(--sf-muted);
  font-size: 0.69rem;
}

.storefront-success__summary {
  display: grid;
  margin-top: 28px;
  padding: 21px 30px;
  gap: 12px;
  border: 1px solid var(--sf-border);
  border-radius: 11px;
  background: var(--sf-soft);
}

.storefront-success__summary > div {
  display: flex;
  justify-content: space-between;
  color: var(--sf-muted);
}

.storefront-success__summary > div strong {
  color: var(--sf-text);
}

.storefront-success__summary > div.is-total {
  margin-top: 3px;
  padding-top: 15px;
  border-top: 1px solid var(--sf-border);
  color: var(--sf-text);
  font-size: 1.2rem;
}

.storefront-success__actions {
  display: flex;
  margin-top: 22px;
  align-items: center;
  justify-content: flex-end;
  gap: 13px;
}

.storefront-success__actions button {
  display: inline-flex;
  min-height: 43px;
  padding: 0 19px;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  font-weight: 700;
  background: var(--sf-navy);
  cursor: pointer;
}

.storefront-success__actions button:last-child {
  padding: 0;
  color: var(--sf-muted);
  text-decoration: underline;
  background: transparent;
}

/* Product link reviews */
.storefront-reviews {
  display: grid;
  margin-top: 35px;
  padding: 22px;
  grid-template-columns: 1.25fr 0.75fr;
  gap: 24px;
  border: 1px solid var(--sf-border);
  border-radius: 14px;
  background: var(--sf-surface);
}

.storefront-reviews h2,
.storefront-reviews h3 {
  margin-bottom: 14px;
}

.storefront-reviews__list {
  display: grid;
  gap: 9px;
}

.storefront-reviews__list article {
  padding: 12px;
  border: 1px solid var(--sf-border);
  border-radius: 8px;
  background: var(--sf-soft);
}

.storefront-reviews__list header {
  display: flex;
  justify-content: space-between;
}

.storefront-reviews__list header span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #f0a10c;
}

.storefront-reviews__list p {
  margin-top: 8px;
  color: var(--sf-muted);
  font-size: 0.83rem;
}

.storefront-reviews__list small {
  color: var(--sf-success);
}

.storefront-reviews form {
  display: grid;
  align-content: start;
  gap: 9px;
}

.storefront-reviews input,
.storefront-reviews select,
.storefront-reviews textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--sf-border);
  border-radius: 7px;
  outline: 0;
  color: var(--sf-text);
  background: var(--sf-soft);
}

.storefront-reviews form > button {
  min-height: 40px;
  border: 0;
  border-radius: 7px;
  color: #fff;
  background: var(--sf-primary);
  cursor: pointer;
}

.storefront-reviews__success {
  color: var(--sf-success);
  font-size: 0.78rem;
}

@media (max-width: 1000px) {
  .storefront-sidebar {
    width: 230px;
  }

  .storefront-workspace {
    margin-left: 230px;
  }

  .storefront-chat-page {
    width: calc(100% - 24px);
    grid-template-columns: minmax(0, 1fr) 285px;
    gap: 12px;
  }

  .storefront-contact-card {
    padding: 24px;
  }
}

@media (max-width: 820px) {
  .storefront-sidebar {
    z-index: 110;
    width: min(280px, 86vw);
    transform: translateX(-102%);
    transition: transform 240ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .storefront-sidebar--open {
    transform: translateX(0);
  }

  .storefront-sidebar__close {
    position: absolute;
    top: 13px;
    right: 10px;
    display: grid;
    color: #dcecff;
  }

  .storefront-sidebar-backdrop {
    z-index: 105;
    display: block;
  }

  .storefront-workspace {
    margin-left: 0;
  }

  .storefront-topbar {
    padding: 0 15px;
  }

  .storefront-topbar__menu {
    display: grid;
  }

  .storefront-chat-page {
    display: block;
    width: calc(100% - 20px);
    height: auto;
    margin: 10px auto 24px;
  }

  .storefront-chat-panel {
    height: calc(100vh - 84px);
    min-height: calc(100vh - 84px);
    border: 1px solid var(--sf-border);
    border-radius: 5px;
  }

  .storefront-draft {
    margin-top: 16px;
    min-height: auto;
    border: 1px solid var(--sf-border);
    border-radius: 5px;
  }

  .storefront-contact-page {
    padding-top: 42px;
  }
}

@media (max-width: 640px) {
  .storefront-page,
  .storefront-contact-page {
    width: calc(100% - 28px);
    padding-top: 22px;
  }

  .storefront-topbar__title strong {
    font-size: 0.98rem;
  }

  .storefront-topbar__title small {
    display: block;
    overflow: hidden;
    max-width: 160px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .storefront-topbar__actions .storefront-icon-button:first-child,
  .storefront-topbar__actions .storefront-icon-button:last-of-type {
    display: none;
  }

  .storefront-product-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 11px;
  }

  .storefront-product-card__media {
    height: 135px;
  }

  .storefront-product-card__body {
    padding: 12px;
  }

  .storefront-product-card__body h2 {
    min-height: 40px;
    font-size: 0.94rem;
  }

  .storefront-product-card__body > p {
    display: none;
  }

  .storefront-product-card__stock {
    font-size: 0.68rem;
  }

  .storefront-product-card__stock > span {
    display: none;
  }

  .storefront-product-card__media strong {
    top: 8px;
    right: 8px;
    padding: 5px 7px;
    font-size: 0.73rem;
  }

  .storefront-product-card__actions {
    grid-template-columns: 1fr;
  }

  .storefront-product-card__actions button:last-child {
    display: none;
  }

  .storefront-contact-grid,
  .storefront-reviews {
    grid-template-columns: 1fr;
  }

  .storefront-contact-grid {
    margin-top: 30px;
    gap: 14px;
  }

  .storefront-contact-card {
    min-height: auto;
    padding: 22px;
  }

  .storefront-contact-card h2 {
    margin-top: 18px;
  }

  .storefront-chat-messages {
    padding: 18px 12px 25px;
  }

  .storefront-chat-message__content {
    max-width: 82%;
  }

  .storefront-chat-catalog {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .storefront-chat-catalog-card {
    display: grid;
    padding: 8px;
  }

  .storefront-chat-catalog img,
  .storefront-chat-catalog-card > svg {
    width: 100%;
    height: 140px;
    margin-bottom: 0;
  }

  .storefront-chat-catalog strong {
    display: block;
    font-size: 0.82rem;
  }

  .storefront-chat-catalog small {
    font-size: 0.73rem;
  }

  .storefront-checkout-modal__body {
    grid-template-columns: 1fr;
  }

  .storefront-checkout-modal label.is-wide {
    grid-column: auto;
  }

  .storefront-checkout-summary,
  .storefront-checkout-modal > footer {
    align-items: stretch;
    flex-direction: column;
  }

  .storefront-checkout-modal > footer > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .storefront-success {
    padding: 30px 20px;
  }

  .storefront-success__actions {
    flex-direction: column;
  }
}

@media (max-width: 380px) {
  .storefront-product-grid {
    grid-template-columns: 1fr;
  }
}
````

### `frontend/src/pages/StorefrontPage.jsx`

````jsx
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  Bot,
  Building2,
  Check,
  CheckCircle2,
  CircleUserRound,
  ClipboardList,
  Copy,
  Mail,
  MapPin,
  Menu,
  MessageCircleQuestion,
  Minus,
  Moon,
  Package,
  Phone,
  Plus,
  Search,
  Send,
  ShieldCheck,
  ShoppingBag,
  ShoppingCart,
  Star,
  Store,
  Sun,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { useParams } from "react-router-dom";
import vendlyLogo from "../assets/vendly-logo.png";
import {
  createPublicChatOrder,
  createPublicChatSession,
  getPublicProduct,
  getPublicProductReviews,
  getPublicStore,
  sendPublicChatMessage,
  submitPublicReview,
} from "../services/publicService";
import OrderReceipt from "../components/OrderReceipt";
import CustomerAccountModal from "../components/CustomerAccountModal";
import { useAuth } from "../context/authContextValue";
import { claimPublicChatSession } from "../services/publicService";

import "./StorefrontPage.css";

const EMPTY_CUSTOMER = {
  name: "",
  phoneNumber: "",
  email: "",
  deliveryNote: "",
  address: {
    line1: "",
    line2: "",
    city: "",
    district: "",
    postalCode: "",
  },
};

function money(minor = 0) {
  return `Rs ${Number(minor / 100).toLocaleString("en-LK", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function getInitialView() {
  const view = window.location.hash.replace("#", "");
  return ["catalog", "chatbot", "contact"].includes(view) ? view : "catalog";
}

function getInitialTheme() {
  return localStorage.getItem("vendly-storefront-theme") === "dark"
    ? "dark"
    : "light";
}

function StorefrontPage({ linkType }) {
  const { user } = useAuth();
  const { storeCode, productCode } = useParams();
  const [business, setBusiness] = useState(null);
  const [products, setProducts] = useState([]);
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messageText, setMessageText] = useState("");
  const [cart, setCart] = useState([]);
  const [customer, setCustomer] = useState(EMPTY_CUSTOMER);
  const [activeView, setActiveView] = useState(getInitialView);
  const [theme, setTheme] = useState(getInitialTheme);
  const [searchText, setSearchText] = useState("");
  const [activeCategory, setActiveCategory] = useState("All");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [confirmedOrder, setConfirmedOrder] = useState(null);
  const [copiedField, setCopiedField] = useState("");
  const [reviews, setReviews] = useState([]);
  const [reviewForm, setReviewForm] = useState({
    orderNumber: "",
    phoneNumber: "",
    rating: "5",
    reviewText: "",
  });
  const [reviewMessage, setReviewMessage] = useState("");
  const [isAccountOpen, setIsAccountOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    let requestIsCurrent = true;

    async function loadStorefront() {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const catalogRequest =
          linkType === "product"
            ? getPublicProduct(productCode)
            : getPublicStore(storeCode);
        const sessionRequest = createPublicChatSession({
          storeCode: linkType === "store" ? storeCode : undefined,
          productCode: linkType === "product" ? productCode : undefined,
        });
        const reviewRequest =
          linkType === "product"
            ? getPublicProductReviews(productCode)
            : Promise.resolve({ reviews: [] });
        const [catalog, chatSession, reviewResponse] = await Promise.all([
          catalogRequest,
          sessionRequest,
          reviewRequest,
        ]);

        if (!requestIsCurrent) return;

        setBusiness(catalog.business);
        setProducts(
          linkType === "product" ? [catalog.product] : catalog.products,
        );
        setSession(chatSession);
        setMessages([
          {
            role: "assistant",
            text: chatSession.message,
            action: chatSession.action,
            product: chatSession.product,
            products: chatSession.products,
          },
        ]);
        setReviews(reviewResponse.reviews);
      } catch (error) {
        if (requestIsCurrent) setErrorMessage(error.message);
      } finally {
        if (requestIsCurrent) setIsLoading(false);
      }
    }

    loadStorefront();
    return () => {
      requestIsCurrent = false;
    };
  }, [linkType, productCode, storeCode]);

  useEffect(() => {
    if (!user || !session?.sessionId || !session?.sessionToken) return;
    claimPublicChatSession(session.sessionId, session.sessionToken).catch((error) => {
      setErrorMessage(error.message);
    });
  }, [session?.sessionId, session?.sessionToken, user]);

  useEffect(() => {
    localStorage.setItem("vendly-storefront-theme", theme);
  }, [theme]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [messages, isSending]);

  useEffect(() => {
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setIsCheckoutOpen(false);
        setIsCartOpen(false);
        setIsMobileMenuOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const categories = useMemo(
    () => [
      "All",
      ...new Set(
        products.map((product) => product.categoryName).filter(Boolean),
      ),
    ],
    [products],
  );

  const visibleProducts = useMemo(() => {
    const query = searchText.trim().toLowerCase();

    return products.filter((product) => {
      const matchesCategory =
        activeCategory === "All" || product.categoryName === activeCategory;
      const matchesSearch =
        !query ||
        [product.name, product.brand, product.categoryName, product.description]
          .join(" ")
          .toLowerCase()
          .includes(query);
      return matchesCategory && matchesSearch;
    });
  }, [activeCategory, products, searchText]);

  const cartQuantity = useMemo(
    () => cart.reduce((total, item) => total + item.quantity, 0),
    [cart],
  );

  const cartSubtotal = useMemo(
    () =>
      cart.reduce(
        (total, item) => total + item.sellingPriceMinor * item.quantity,
        0,
      ),
    [cart],
  );

  function changeView(view) {
    setActiveView(view);
    setIsMobileMenuOpen(false);
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}#${view}`,
    );
  }

  function addToCart(product, variant) {
    if (!variant || variant.availableStock < 1) return;

    setCart((current) => {
      const existing = current.find((item) => item.variantId === variant.id);

      if (existing) {
        if (existing.quantity >= variant.availableStock) return current;
        return current.map((item) =>
          item.variantId === variant.id
            ? { ...item, quantity: item.quantity + 1 }
            : item,
        );
      }

      return [
        ...current,
        {
          variantId: variant.id,
          productName: product.name,
          size: variant.size,
          sku: variant.sku,
          imageUrl: product.media?.[0]?.url || "",
          sellingPriceMinor: product.sellingPriceMinor,
          availableStock: variant.availableStock,
          quantity: 1,
        },
      ];
    });
  }

  function updateCartQuantity(variantId, amount) {
    setCart((current) =>
      current
        .map((item) => {
          if (item.variantId !== variantId) return item;
          const quantity = Math.min(
            item.availableStock,
            Math.max(0, item.quantity + amount),
          );
          return { ...item, quantity };
        })
        .filter((item) => item.quantity > 0),
    );
  }

  function setCartQuantity(variantId, requestedQuantity) {
    const parsedQuantity = Number.parseInt(requestedQuantity, 10);

    setCart((current) =>
      current
        .map((item) => {
          if (item.variantId !== variantId) return item;
          return {
            ...item,
            quantity: Math.min(
              item.availableStock,
              Math.max(0, Number.isNaN(parsedQuantity) ? 0 : parsedQuantity),
            ),
          };
        })
        .filter((item) => item.quantity > 0),
    );
  }

  async function requestChatMessage(cleanMessage) {
    if (!cleanMessage || !session || isSending) return;

    setMessages((current) => [
      ...current,
      { role: "customer", text: cleanMessage },
    ]);
    setMessageText("");
    setIsSending(true);
    setErrorMessage("");

    try {
      const response = await sendPublicChatMessage(
        session.sessionId,
        session.sessionToken,
        cleanMessage,
        {
          cart: cart.map((item) => ({
            variantId: item.variantId,
            quantity: item.quantity,
          })),
        },
      );

      if (response.customerDraft) {
        setCustomer((current) => ({
          ...current,
          ...response.customerDraft,
          address: {
            ...current.address,
            ...(response.customerDraft.address || {}),
          },
        }));
      }

      if (response.order) {
        setConfirmedOrder(response.order);
        setCart([]);
      }

      setSession((current) => ({
        ...current,
        state: response.state,
      }));
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          text: response.message,
          action: response.action,
          product: response.product,
          products: response.products,
          cartSummary: response.cartSummary,
          customerDraft: response.customerDraft,
        },
      ]);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    await requestChatMessage(messageText.trim());
  }

  function addFromChat(product, variant) {
    addToCart(product, variant);
    setMessages((current) => [
      ...current,
      {
        role: "assistant",
        text: `${product.name}${variant.size ? `, size ${variant.size}` : ""} was added to your order draft. You can add another item or continue to checkout.`,
        action: "cart-updated",
      },
    ]);
  }

  function updateCustomer(event) {
    const { name, value } = event.target;

    if (name.startsWith("address.")) {
      const addressField = name.replace("address.", "");
      setCustomer((current) => ({
        ...current,
        address: { ...current.address, [addressField]: value },
      }));
      return;
    }

    setCustomer((current) => ({ ...current, [name]: value }));
  }

  async function checkout(event) {
    event.preventDefault();
    if (!session || cart.length === 0) return;

    setIsSending(true);
    setErrorMessage("");

    try {
      const response = await createPublicChatOrder(
        session.sessionId,
        session.sessionToken,
        {
          customer: {
            name: customer.name,
            phoneNumber: customer.phoneNumber,
            email: customer.email,
            address: customer.address,
          },
          deliveryNote: customer.deliveryNote,
          items: cart.map((item) => ({
            variantId: item.variantId,
            quantity: item.quantity,
          })),
        },
      );
      setConfirmedOrder(response.order);
      setIsCheckoutOpen(false);
      setIsCartOpen(false);
      setCart([]);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function submitReview(event) {
    event.preventDefault();
    if (!business?.shortCode || products.length !== 1) return;

    setIsSending(true);
    setErrorMessage("");
    setReviewMessage("");

    try {
      await submitPublicReview(business.shortCode, {
        ...reviewForm,
        rating: Number(reviewForm.rating),
        productId: products[0].id,
      });
      setReviewMessage(
        "Thank you. Your verified review is waiting for approval.",
      );
      setReviewForm({
        orderNumber: "",
        phoneNumber: "",
        rating: "5",
        reviewText: "",
      });
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSending(false);
    }
  }

  async function copyContact(value, field) {
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedField(field);
    window.setTimeout(() => setCopiedField(""), 1600);
  }

  if (isLoading) {
    return (
      <main className="storefront-loading">
        <span className="storefront-loading__mark">V</span>
        <strong>Opening storefrontâ€¦</strong>
      </main>
    );
  }

  if (!business) {
    return (
      <main className="storefront-loading storefront-loading--error">
        <Package size={38} />
        <strong>{errorMessage || "This store is unavailable."}</strong>
      </main>
    );
  }

  const storefrontClass = `storefront storefront--${theme}`;

  return (
    <main className={storefrontClass}>
      <aside
        className={`storefront-sidebar ${isMobileMenuOpen ? "storefront-sidebar--open" : ""}`}
      >
        <button
          className="storefront-sidebar__close"
          type="button"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-label="Close menu"
        >
          <X size={21} />
        </button>

          <div>
            <img className="sidebar__logo-image" src={vendlyLogo} alt="Vendly.lk"/>
            <small align ="center">Customer Storefront</small>
          </div>

        <nav className="storefront-nav" aria-label="Storefront navigation">
          <button
            className={activeView === "catalog" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("catalog")}
          >
            <Store size={20} /> Catalog
          </button>
          <button
            className={activeView === "chatbot" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("chatbot")}
          >
            <Bot size={21} /> Chatbot
          </button>
          <button
            className={activeView === "contact" ? "is-active" : ""}
            type="button"
            onClick={() => changeView("contact")}
          >
            <MessageCircleQuestion size={20} /> Contact
          </button>
          <button
            type="button"
            onClick={() => {
              setIsMobileMenuOpen(false);
              setIsAccountOpen(true);
            }}
          >
            <UserRound size={20} /> {user ? "My orders" : "Login / Guest"}
          </button>
        </nav>
      </aside>

      {isMobileMenuOpen && (
        <button
          className="storefront-sidebar-backdrop"
          type="button"
          aria-label="Close menu"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      <section className="storefront-workspace">
        <header className="storefront-topbar">
          <div className="storefront-topbar__title">
            <button
              className="storefront-icon-button storefront-topbar__menu"
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              aria-label="Open menu"
            >
              <Menu size={21} />
            </button>
            <div>
              <strong>
                {activeView === "catalog" && "Catalog"}
                {activeView === "chatbot" &&
                  `${business.name} â€“ AI Ordering Assistant`}
                {activeView === "contact" && "Contact"}
              </strong>
              <small>{business.name}</small>
            </div>
          </div>

          <div className="storefront-topbar__actions">
            <button
              className="storefront-icon-button"
              type="button"
              aria-label="Notifications"
            >
              <Bell size={20} />
            </button>
            <button
              className="storefront-icon-button"
              type="button"
              onClick={() =>
                setTheme((current) => (current === "light" ? "dark" : "light"))
              }
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
            </button>
            <button
              className="storefront-icon-button"
              type="button"
              aria-label="Customer account"
              onClick={() => setIsAccountOpen(true)}
            >
              {user ? (
                <span className="storefront-customer-avatar">
                  {user.isAnonymous ? "G" : (user.displayName || user.email || "C").charAt(0).toUpperCase()}
                </span>
              ) : <CircleUserRound size={21} />}
            </button>
            <button
              className="storefront-cart-button"
              type="button"
              onClick={() => setIsCartOpen(true)}
              aria-label={`Open cart with ${cartQuantity} items`}
            >
              <ShoppingCart size={21} />
              {cartQuantity > 0 && <span>{cartQuantity}</span>}
            </button>
          </div>
        </header>

        {errorMessage && (
          <div className="storefront-error" role="alert">
            <span>{errorMessage}</span>
            <button
              type="button"
              onClick={() => setErrorMessage("")}
              aria-label="Dismiss error"
            >
              <X size={17} />
            </button>
          </div>
        )}

        {activeView === "catalog" && (
          <CatalogView
            business={business}
            products={visibleProducts}
            categories={categories}
            activeCategory={activeCategory}
            searchText={searchText}
            linkType={linkType}
            reviews={reviews}
            reviewForm={reviewForm}
            reviewMessage={reviewMessage}
            isSending={isSending}
            onSearchChange={setSearchText}
            onCategoryChange={setActiveCategory}
            onAddToCart={addToCart}
            onOpenChat={() => changeView("chatbot")}
            onReviewFormChange={setReviewForm}
            onSubmitReview={submitReview}
          />
        )}

        {activeView === "chatbot" && (
          <ChatbotView
            business={business}
            cart={cart}
            customer={customer}
            chatState={session?.state || "browsing"}
            messages={messages}
            messageText={messageText}
            isSending={isSending}
            messagesEndRef={messagesEndRef}
            onMessageTextChange={setMessageText}
            onSendMessage={sendMessage}
            onQuickMessage={requestChatMessage}
            onAddFromChat={addFromChat}
            onDecreaseItem={(variantId) => updateCartQuantity(variantId, -1)}
            onIncreaseItem={(variantId) => updateCartQuantity(variantId, 1)}
            onSetItemQuantity={setCartQuantity}
            onRemoveItem={(variantId) =>
              setCart((current) =>
                current.filter((item) => item.variantId !== variantId),
              )
            }
            onOpenCheckout={() => setIsCheckoutOpen(true)}
          />
        )}

        {activeView === "contact" && (
          <ContactView
            business={business}
            copiedField={copiedField}
            onCopyContact={copyContact}
          />
        )}
      </section>

      <CartDrawer
        isOpen={isCartOpen}
        cart={cart}
        subtotal={cartSubtotal}
        onClose={() => setIsCartOpen(false)}
        onUpdateQuantity={updateCartQuantity}
        onCheckout={() => {
          setIsCartOpen(false);
          setIsCheckoutOpen(true);
        }}
      />

      {isCheckoutOpen && (
        <CheckoutModal
          cart={cart}
          customer={customer}
          subtotal={cartSubtotal}
          isSending={isSending}
          onClose={() => setIsCheckoutOpen(false)}
          onCustomerChange={updateCustomer}
          onSubmit={checkout}
        />
      )}

      {confirmedOrder && (
        <OrderSuccess
          business={business}
          order={confirmedOrder}
          closeLabel="Return to Storefront"
          onClose={() => {
            setConfirmedOrder(null);
            setCustomer(EMPTY_CUSTOMER);
            window.location.reload();
          }}
        />
      )}

      <CustomerAccountModal
        isOpen={isAccountOpen}
        onClose={() => setIsAccountOpen(false)}
        user={user}
        storeCode={business.shortCode}
      />
    </main>
  );
}

function CatalogView({
  business,
  products,
  categories,
  activeCategory,
  searchText,
  linkType,
  reviews,
  reviewForm,
  reviewMessage,
  isSending,
  onSearchChange,
  onCategoryChange,
  onAddToCart,
  onOpenChat,
  onReviewFormChange,
  onSubmitReview,
}) {
  return (
    <div className="storefront-page storefront-catalog-page">
      <section className="storefront-catalog-hero">
        <h1>
          Welcome to <span>{business.name}</span>
        </h1>
        <p>Discover products, check live availability, and order securely.</p>
      </section>

      <div className="storefront-search">
        <Search size={21} />
        <input
          value={searchText}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search products, brands or categoriesâ€¦"
          aria-label="Search products"
        />
      </div>

      <div className="storefront-categories" aria-label="Product categories">
        {categories.map((category) => (
          <button
            className={activeCategory === category ? "is-active" : ""}
            type="button"
            key={category}
            onClick={() => onCategoryChange(category)}
          >
            {category}
          </button>
        ))}
      </div>

      <section className="storefront-product-grid">
        {products.map((product) => (
          <ProductCard
            product={product}
            key={product.id}
            onAddToCart={onAddToCart}
            onOpenChat={onOpenChat}
          />
        ))}
        {products.length === 0 && (
          <div className="storefront-empty-state">
            <Search size={34} />
            <h2>No matching products</h2>
            <p>Try a different search or category.</p>
          </div>
        )}
      </section>

      {linkType === "product" && (
        <ProductReviews
          reviews={reviews}
          reviewForm={reviewForm}
          reviewMessage={reviewMessage}
          isSending={isSending}
          onReviewFormChange={onReviewFormChange}
          onSubmitReview={onSubmitReview}
        />
      )}
    </div>
  );
}

function ProductCard({ product, onAddToCart, onOpenChat }) {
  const firstVariant = product.variants?.[0];
  const hasMultipleVariants = product.variants?.length > 1;

  return (
    <article className="storefront-product-card">
      <div className="storefront-product-card__media">
        {product.media?.[0]?.url ? (
          <img src={product.media[0].url} alt={product.name} />
        ) : (
          <Package size={52} />
        )}
        <strong>{money(product.sellingPriceMinor)}</strong>
        {product.compareAtPriceMinor > product.sellingPriceMinor && (
          <small>{money(product.compareAtPriceMinor)}</small>
        )}
      </div>

      <div className="storefront-product-card__body">
        <span>{product.categoryName || product.brand || "Product"}</span>
        <h2>{product.name}</h2>
        <p>
          {product.description ||
            product.aiDescription ||
            "Ask our chatbot for more information."}
        </p>
        <div className="storefront-product-card__stock">
          <CheckCircle2 size={15} /> {product.availableStock} available
          {product.approvedReviewCount > 0 && (
            <span>
              <Star size={14} fill="currentColor" />{" "}
              {product.approvedReviewCount} reviews
            </span>
          )}
        </div>

        {hasMultipleVariants && (
          <div className="storefront-product-card__variants">
            {product.variants.map((variant) => (
              <button
                type="button"
                key={variant.id}
                onClick={() => onAddToCart(product, variant)}
                title={`Add ${variant.size || variant.sku} to cart`}
              >
                {variant.size ? `Size ${variant.size}` : variant.sku}
              </button>
            ))}
          </div>
        )}

        <div className="storefront-product-card__actions">
          <button
            type="button"
            disabled={!firstVariant}
            onClick={() => onAddToCart(product, firstVariant)}
          >
            <ShoppingCart size={17} />
            {hasMultipleVariants ? "Add first size" : "Add to Cart"}
          </button>
          <button
            type="button"
            onClick={onOpenChat}
            aria-label={`Ask about ${product.name}`}
          >
            <Bot size={17} />
          </button>
        </div>
      </div>
    </article>
  );
}

function ChatCatalogCard({ product, productIndex, isOrderMode, cart, onQuickMessage, onAddFromChat, onDecreaseItem, onIncreaseItem }) {
  const variant = product.variants?.[0];
  const selectedItem = cart.find((item) => item.variantId === variant?.id);
  const quantity = selectedItem?.quantity ?? 0;
  const availableStock = variant?.availableStock ?? product.availableStock ?? 0;

  if (!isOrderMode) {
    return (
      <article className="storefront-chat-catalog-card">
        {product.media?.[0]?.url ? <img src={product.media[0].url} alt="" /> : <Package size={24} />}
        <strong>{productIndex + 1}. {product.name}</strong>
        <small>{money(product.sellingPriceMinor)} Â· {availableStock} available</small>
        <button type="button" onClick={() => onQuickMessage(String(productIndex + 1))}>View product details</button>
      </article>
    );
  }

  return (
    <article className={`storefront-chat-catalog-card ${quantity ? "is-selected" : ""}`}>
      {product.media?.[0]?.url ? <img src={product.media[0].url} alt="" /> : <Package size={24} />}
      <strong>{product.name}</strong>
      <small>{money(product.sellingPriceMinor)}</small>
      <small>{availableStock} available</small>
      <button className="storefront-chat-catalog-card__select" type="button" disabled={!variant || availableStock < 1} onClick={() => onAddFromChat(product, variant)}>
        {quantity ? "Selected" : "Select"}
      </button>
      <div className="storefront-chat-catalog-card__quantity" aria-label={`Quantity for ${product.name}`}>
        <button type="button" aria-label={`Remove one ${product.name}`} disabled={!quantity} onClick={() => onDecreaseItem(variant.id)}>-</button>
        <strong>{quantity}</strong>
        <button type="button" aria-label={`Add one ${product.name}`} disabled={!variant || quantity >= availableStock} onClick={() => quantity ? onIncreaseItem(variant.id) : onAddFromChat(product, variant)}>+</button>
      </div>
    </article>
  );
}

function ChatProductVariantControl({
  product,
  variant,
  cart,
  onAddFromChat,
  onDecreaseItem,
  onIncreaseItem,
  onSetItemQuantity,
}) {
  const selectedItem = cart.find((item) => item.variantId === variant.id);
  const quantity = selectedItem?.quantity ?? 0;
  const availableStock = variant.availableStock ?? 0;
  const variantLabel = variant.size ? `Size ${variant.size}` : variant.sku;

  return (
    <div className={`storefront-chat-product__variant-row ${quantity ? "is-selected" : ""}`}>
      <span>
        <strong>{variantLabel}</strong>
        <small>{availableStock} available</small>
      </span>

      {quantity === 0 ? (
        <button
          type="button"
          disabled={availableStock < 1}
          onClick={() => onAddFromChat(product, variant)}
        >
          <Plus size={14} /> Add
        </button>
      ) : (
        <div className="storefront-chat-product__quantity">
          <button
            type="button"
            onClick={() => onDecreaseItem(variant.id)}
            aria-label={`Remove one ${product.name}, ${variantLabel}`}
          >
            <Minus size={14} />
          </button>
          <input
            type="number"
            min="1"
            max={availableStock}
            value={quantity}
            aria-label={`Quantity for ${product.name}, ${variantLabel}`}
            onChange={(event) =>
              onSetItemQuantity(variant.id, event.target.value)
            }
          />
          <button
            type="button"
            disabled={quantity >= availableStock}
            onClick={() => onIncreaseItem(variant.id)}
            aria-label={`Add one ${product.name}, ${variantLabel}`}
          >
            <Plus size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function ChatbotView({
  business,
  cart,
  customer,
  chatState,
  messages,
  messageText,
  isSending,
  messagesEndRef,
  onMessageTextChange,
  onSendMessage,
  onQuickMessage,
  onAddFromChat,
  onDecreaseItem,
  onIncreaseItem,
  onSetItemQuantity,
  onRemoveItem,
  onOpenCheckout,
}) {
  return (
    <div className="storefront-page storefront-chat-page">
      <section className="storefront-chat-panel">
        <header className="storefront-chat-panel__header">
          <div>
            <span />
            <strong>Order Chat</strong>
          </div>
          <small>
            <CheckCircle2 size={14} /> Ready
          </small>
        </header>

        <div className="storefront-chat-messages">
          {messages.map((message, index) => (
            <div
              className={`storefront-chat-message storefront-chat-message--${message.role}`}
              key={`${message.role}-${index}`}
            >
              <span className="storefront-chat-message__avatar">
                {message.role === "assistant" ? (
                  <Bot size={18} />
                ) : (
                  <UserRound size={18} />
                )}
              </span>
              <div className="storefront-chat-message__content">
                <p>{message.text}</p>

                {message.role === "assistant" &&
                  [
                    "show-catalog",
                    "start-order",
                    "show-category",
                    "suggest-alternatives",
                  ].includes(message.action) &&
                  !message.product &&
                  message.products?.length > 0 && (
                    <div className="storefront-chat-catalog">
                      {message.products.map((product, productIndex) => (
                        <ChatCatalogCard
                          key={product.id}
                          product={product}
                          productIndex={productIndex}
                          isOrderMode={message.action === "start-order"}
                          cart={cart}
                          onQuickMessage={onQuickMessage}
                          onAddFromChat={onAddFromChat}
                          onDecreaseItem={onDecreaseItem}
                          onIncreaseItem={onIncreaseItem}
                        />
                      ))}
                    </div>
                  )}

                {message.role === "assistant" && message.product && (
                  <div className="storefront-chat-product">
                    <div>
                      {message.product.media?.[0]?.url ? (
                        <img src={message.product.media[0].url} alt="" />
                      ) : (
                        <Package size={28} />
                      )}
                      <span>
                        <strong>{message.product.name}</strong>
                        <small>
                          {money(message.product.sellingPriceMinor)}
                        </small>
                      </span>
                    </div>
                    <p className="storefront-chat-product__description">
                      {message.product.description ||
                        message.product.aiDescription ||
                        "The seller has not added a product description yet."}
                    </p>
                    <div className="storefront-chat-product__variants">
                      {message.product.variants?.map((variant) => (
                        <ChatProductVariantControl
                          key={variant.id}
                          product={message.product}
                          variant={variant}
                          cart={cart}
                          onAddFromChat={onAddFromChat}
                          onDecreaseItem={onDecreaseItem}
                          onIncreaseItem={onIncreaseItem}
                          onSetItemQuantity={onSetItemQuantity}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {message.role === "assistant" &&
                  message.action === "confirm-order" && (
                    <div className="storefront-chat-confirmation">
                      <strong>Confirm order before submission</strong>
                      <div className="storefront-chat-confirmation__items">
                        {message.cartSummary?.map((item) => (
                          <span key={item.variantId}>
                            {item.quantity} Ã— {item.productName}
                            {item.size ? ` Â· Size ${item.size}` : ""}
                            <strong>{money(item.lineTotalMinor)}</strong>
                          </span>
                        ))}
                      </div>
                      <div className="storefront-chat-confirmation__customer">
                        <span>{message.customerDraft?.name}</span>
                        <span>{message.customerDraft?.phoneNumber}</span>
                        <span>
                          {[
                            message.customerDraft?.address?.line1,
                            message.customerDraft?.address?.city,
                            message.customerDraft?.address?.district,
                          ]
                            .filter(Boolean)
                            .join(", ")}
                        </span>
                      </div>
                      <div className="storefront-chat-confirmation__actions">
                        <button
                          type="button"
                          onClick={() => onQuickMessage("change order")}
                          disabled={isSending}
                        >
                          Change details
                        </button>
                        <button
                          type="button"
                          onClick={() => onQuickMessage("confirm order")}
                          disabled={isSending}
                        >
                          <Check size={15} /> Confirm order
                        </button>
                      </div>
                    </div>
                  )}
              </div>
            </div>
          ))}

          {isSending && (
            <div className="storefront-chat-message storefront-chat-message--assistant">
              <span className="storefront-chat-message__avatar">
                <Bot size={18} />
              </span>
              <div
                className="storefront-typing"
                aria-label="Assistant is typing"
              >
                <i />
                <i />
                <i />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="storefront-chat-quick-actions">
          <button
            type="button"
            onClick={() => onQuickMessage("Show products")}
            disabled={isSending}
          >
            Show products
          </button>
          <button
            type="button"
            onClick={() => onQuickMessage("I want to order")}
            disabled={isSending}
          >
            I want to order
          </button>
          <button
            type="button"
            onClick={() => onQuickMessage("Show customer reviews")}
            disabled={isSending}
          >
            Reviews
          </button>
        </div>

        <form className="storefront-chat-input" onSubmit={onSendMessage}>
          <input
            value={messageText}
            onChange={(event) => onMessageTextChange(event.target.value)}
            placeholder="Type a messageâ€¦"
            aria-label="Chat message"
          />
          <button
            type="submit"
            disabled={isSending || !messageText.trim()}
            aria-label="Send message"
          >
            <Send size={20} />
          </button>
        </form>
      </section>

      <aside className="storefront-draft">

        <section>
          <h3>Products & quantity</h3>
          <div className="storefront-draft__items">
            {cart.map((item) => (
              <article key={item.variantId}>
                <div className="storefront-draft__item-image">
                  {item.imageUrl ? (
                    <img src={item.imageUrl} alt="" />
                  ) : (
                    <Package size={22} />
                  )}
                </div>
                <div className="storefront-draft__item-details">
                  <strong>{item.productName}</strong>
                  <span>
                    Qty: {item.quantity}
                    {item.size ? ` Â· Size ${item.size}` : ""}
                  </span>
                  <small>{money(item.sellingPriceMinor * item.quantity)}</small>
                </div>
                <button
                  type="button"
                  onClick={() => onRemoveItem(item.variantId)}
                  aria-label={`Remove ${item.productName}`}
                >
                  <Trash2 size={16} />
                </button>
              </article>
            ))}
            {cart.length === 0 && <p>No products selected yet.</p>}
          </div>
        </section>

        <section>
          <h3>Customer details</h3>
          <DraftField label="Customer Name" value={customer.name} />
          <DraftField label="Phone No" value={customer.phoneNumber} />
          {customer.secondaryPhoneNumber && (
            <DraftField label="Second phone" value={customer.secondaryPhoneNumber} />
          )}
          <DraftField
            label="Address"
            value={[
              customer.address.line1,
              customer.address.city,
              customer.address.district,
            ]
              .filter(Boolean)
              .join(", ")}
          />
        </section>

        <div className="storefront-draft__bottom">
          <section>
            <h3>Status</h3>
            <div
              className={`storefront-draft__status ${cart.length ? "is-active" : ""}`}
            >
              <span />{" "}
              {chatState === "awaiting-confirmation"
                ? "Awaiting order confirmation"
                : chatState.startsWith("collecting-")
                  ? "Collecting customer details"
                  : cart.length
                    ? "Items selected Â· Ready to order"
                    : "Waiting for product selection"}
            </div>
          </section>
          <button
            type="button"
            disabled={cart.length === 0}
            onClick={onOpenCheckout}
          >
            Continue to checkout <Check size={17} />
          </button>
          <small>Ordering from {business.name}</small>
        </div>
      </aside>
    </div>
  );
}

function DraftField({ label, value }) {
  return (
    <div className="storefront-draft__field">
      <span>{label}</span>
      <strong className={value ? "" : "is-empty"}>
        {value || "Awaiting inputâ€¦"}
      </strong>
    </div>
  );
}

function ContactView({ business, copiedField, onCopyContact }) {
  const phone = business.phone || "Not provided by this seller";
  const email = business.email || "Not provided by this seller";

  return (
    <div className="storefront-page storefront-contact-page">
      <section className="storefront-contact-hero">
        <h1>
          Welcome to <span>{business.name}</span>
        </h1>
        <p>We are here to help. Reach out through any of the channels below.</p>
      </section>

      <div className="storefront-contact-grid">
        <ContactCard
          icon={<Phone size={25} />}
          title="Contact No."
          description="Call us directly for assistance with your orders or enquiries."
          value={phone}
          canCopy={Boolean(business.phone)}
          copied={copiedField === "phone"}
          onCopy={() => onCopyContact(business.phone, "phone")}
        />
        <ContactCard
          icon={<Mail size={25} />}
          title="Email"
          description="Drop us an email anytime. The seller will reply as soon as possible."
          value={email}
          canCopy={Boolean(business.email)}
          copied={copiedField === "email"}
          onCopy={() => onCopyContact(business.email, "email")}
        />
      </div>

      <section className="storefront-contact-note">
        <Building2 size={22} />
        <div>
          <strong>{business.name}</strong>
          <span>Powered by Vendly.lk secure ordering</span>
        </div>
      </section>
    </div>
  );
}

function ContactCard({
  icon,
  title,
  description,
  value,
  canCopy,
  copied,
  onCopy,
}) {
  return (
    <article className="storefront-contact-card">
      <span className="storefront-contact-card__icon">{icon}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      <button type="button" disabled={!canCopy} onClick={onCopy}>
        <strong>{value}</strong>
        {canCopy && (copied ? <Check size={17} /> : <Copy size={16} />)}
      </button>
    </article>
  );
}

function CartDrawer({
  isOpen,
  cart,
  subtotal,
  onClose,
  onUpdateQuantity,
  onCheckout,
}) {
  return (
    <>
      {isOpen && (
        <button
          className="storefront-modal-backdrop"
          type="button"
          aria-label="Close cart"
          onClick={onClose}
        />
      )}
      <aside
        className={`storefront-cart ${isOpen ? "storefront-cart--open" : ""}`}
        aria-hidden={!isOpen}
      >
        <header>
          <div>
            <ShoppingCart size={22} />
            <h2>Your Cart</h2>
            <span>
              {cart.reduce((total, item) => total + item.quantity, 0)}
            </span>
          </div>
          <button type="button" onClick={onClose} aria-label="Close cart">
            <X size={20} />
          </button>
        </header>

        <div className="storefront-cart__items">
          {cart.map((item) => (
            <article key={item.variantId}>
              <div className="storefront-cart__image">
                {item.imageUrl ? (
                  <img src={item.imageUrl} alt="" />
                ) : (
                  <Package size={28} />
                )}
              </div>
              <div className="storefront-cart__details">
                <strong>{item.productName}</strong>
                <span>
                  {item.size ? `Size ${item.size} Â· ` : ""}
                  {money(item.sellingPriceMinor)}
                </span>
                <div>
                  <button
                    type="button"
                    onClick={() => onUpdateQuantity(item.variantId, -1)}
                  >
                    <Minus size={14} />
                  </button>
                  <strong>{item.quantity}</strong>
                  <button
                    type="button"
                    onClick={() => onUpdateQuantity(item.variantId, 1)}
                  >
                    <Plus size={14} />
                  </button>
                </div>
              </div>
              <button
                type="button"
                onClick={() => onUpdateQuantity(item.variantId, -item.quantity)}
                aria-label={`Remove ${item.productName}`}
              >
                <Trash2 size={16} />
              </button>
            </article>
          ))}
          {cart.length === 0 && (
            <div className="storefront-cart__empty">
              <ShoppingBag size={38} />
              <h3>Your cart is empty</h3>
              <p>Add a product from the catalog or chatbot.</p>
            </div>
          )}
        </div>

        <footer>
          <div>
            <span>Subtotal</span>
            <strong>{money(subtotal)}</strong>
          </div>
          <div>
            <span>Total</span>
            <strong>{money(subtotal)}</strong>
          </div>
          <small>
            Delivery will be calculated from your district and order weight.
          </small>
          <button
            type="button"
            disabled={cart.length === 0}
            onClick={onCheckout}
          >
            Checkout <Check size={18} />
          </button>
        </footer>
      </aside>
    </>
  );
}

function CheckoutModal({
  cart,
  customer,
  subtotal,
  isSending,
  onClose,
  onCustomerChange,
  onSubmit,
}) {
  return (
    <div className="storefront-modal-layer" role="presentation">
      <button
        className="storefront-modal-backdrop"
        type="button"
        aria-label="Close checkout"
        onClick={onClose}
      />
      <form className="storefront-checkout-modal" onSubmit={onSubmit}>
        <header>
          <span>
            <ShoppingBag size={22} />
          </span>
          <div>
            <h2>Contact & Delivery Details</h2>
            <p>Please provide accurate shipping information.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close checkout">
            <X size={21} />
          </button>
        </header>

        <div className="storefront-checkout-modal__body">
          <label>
            <span>Full Name *</span>
            <div>
              <UserRound size={17} />
              <input
                name="name"
                value={customer.name}
                onChange={onCustomerChange}
                placeholder="Your full name"
                required
              />
            </div>
          </label>
          <label>
            <span>Phone Number *</span>
            <div>
              <Phone size={17} />
              <input
                name="phoneNumber"
                value={customer.phoneNumber}
                onChange={onCustomerChange}
                placeholder="077 123 4567"
                required
              />
            </div>
          </label>
          <label className="is-wide">
            <span>Street Address *</span>
            <div>
              <MapPin size={17} />
              <input
                name="address.line1"
                value={customer.address.line1}
                onChange={onCustomerChange}
                placeholder="No. 123, Main Street"
                required
              />
            </div>
          </label>
          <label>
            <span>District *</span>
            <div>
              <MapPin size={17} />
              <input
                name="address.district"
                value={customer.address.district}
                onChange={onCustomerChange}
                placeholder="e.g. Colombo"
                required
              />
            </div>
          </label>
          <label>
            <span>Nearest City *</span>
            <div>
              <Building2 size={17} />
              <input
                name="address.city"
                value={customer.address.city}
                onChange={onCustomerChange}
                placeholder="e.g. Nugegoda"
                required
              />
            </div>
          </label>
          <label>
            <span>Email (Optional)</span>
            <div>
              <Mail size={17} />
              <input
                name="email"
                type="email"
                value={customer.email}
                onChange={onCustomerChange}
                placeholder="you@example.com"
              />
            </div>
          </label>
          <label>
            <span>Postal Code (Optional)</span>
            <div>
              <Building2 size={17} />
              <input
                name="address.postalCode"
                value={customer.address.postalCode}
                onChange={onCustomerChange}
                placeholder="10250"
              />
            </div>
          </label>
          <label className="is-wide">
            <span>Delivery Note (Optional)</span>
            <div>
              <ClipboardList size={17} />
              <textarea
                name="deliveryNote"
                value={customer.deliveryNote}
                onChange={onCustomerChange}
                placeholder="Call before dispatch or other courier instructions"
                rows="2"
              />
            </div>
          </label>
        </div>

        <div className="storefront-checkout-summary">
          <span>
            {cart.reduce((total, item) => total + item.quantity, 0)} items
          </span>
          <span>
            Subtotal: <strong>{money(subtotal)}</strong>
          </span>
          <small>
            Delivery fee is calculated securely when the order is placed.
          </small>
        </div>

        <footer>
          <span>
            <ShieldCheck size={16} /> Secure cash-on-delivery checkout
          </span>
          <div>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={isSending}>
              {isSending ? "Placing orderâ€¦" : "Place Order"} <Check size={17} />
            </button>
          </div>
        </footer>
      </form>
    </div>
  );
}

function OrderSuccess({ business, order, onClose, closeLabel }) {
  return <OrderReceipt business={business} order={order} onClose={onClose} closeLabel={closeLabel} />;
  /* Previous receipt design retained temporarily for easy visual comparison.
  return (
    <div className="storefront-success-layer">
      <section className="storefront-success">
        <span className="storefront-success__icon">
          <Check size={34} strokeWidth={3} />
        </span>
        <h1>Order placed successfully!</h1>
        <p>
          Your order <strong>{order.orderNumber}</strong> is confirmed and{" "}
          {business.name} will process it shortly.
        </p>

        <div className="storefront-success__items">
          <h2>
            <ClipboardList size={20} /> Ordered Items
          </h2>
          <div>
            {order.items.map((item) => (
              <article key={item.variantId}>
                <div>
                  {item.mediaUrl ? (
                    <img src={item.mediaUrl} alt="" />
                  ) : (
                    <Package size={30} />
                  )}
                </div>
                <strong>{item.name}</strong>
                <span>
                  Qty: {item.quantity}
                  {item.size ? ` Â· Size ${item.size}` : ""}
                </span>
                <small>{money(item.lineTotalMinor)}</small>
              </article>
            ))}
          </div>
        </div>

        <div className="storefront-success__summary">
          <div>
            <span>Items subtotal</span>
            <strong>{money(order.subtotalMinor)}</strong>
          </div>
          <div>
            <span>Delivery fee</span>
            <strong>{money(order.deliveryFeeMinor)}</strong>
          </div>
          {order.discountTotalMinor > 0 && (
            <div>
              <span>Discount</span>
              <strong>- {money(order.discountTotalMinor)}</strong>
            </div>
          )}
          <div className="is-total">
            <span>Total</span>
            <strong>{money(order.totalAmountMinor)}</strong>
          </div>
        </div>

        <div className="storefront-success__actions">
          <button type="button" onClick={onDownloadReceipt}>
            <Download size={17} /> Download Receipt
          </button>
          <button type="button" onClick={onReturn}>
            Return to Storefront
          </button>
        </div>
      </section>
    </div>
  );
  */
}

function ProductReviews({
  reviews,
  reviewForm,
  reviewMessage,
  isSending,
  onReviewFormChange,
  onSubmitReview,
}) {
  return (
    <section className="storefront-reviews">
      <div>
        <h2>Verified customer reviews</h2>
        <div className="storefront-reviews__list">
          {reviews.map((review) => (
            <article key={review.id}>
              <header>
                <strong>{review.customerName}</strong>
                <span>
                  <Star size={14} fill="currentColor" /> {review.rating}/5
                </span>
              </header>
              <p>{review.reviewText}</p>
              <small>Verified purchase</small>
            </article>
          ))}
          {reviews.length === 0 && <p>No approved reviews yet.</p>}
        </div>
      </div>
      <form onSubmit={onSubmitReview}>
        <h3>Review a delivered order</h3>
        <input
          value={reviewForm.orderNumber}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              orderNumber: event.target.value,
            }))
          }
          placeholder="Order number (VD-000001)"
          required
        />
        <input
          value={reviewForm.phoneNumber}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              phoneNumber: event.target.value,
            }))
          }
          placeholder="Order phone number"
          required
        />
        <select
          value={reviewForm.rating}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              rating: event.target.value,
            }))
          }
        >
          <option value="5">5 - Excellent</option>
          <option value="4">4 - Good</option>
          <option value="3">3 - Average</option>
          <option value="2">2 - Poor</option>
          <option value="1">1 - Very poor</option>
        </select>
        <textarea
          value={reviewForm.reviewText}
          onChange={(event) =>
            onReviewFormChange((current) => ({
              ...current,
              reviewText: event.target.value,
            }))
          }
          placeholder="Write your review"
          rows="4"
          required
        />
        <button type="submit" disabled={isSending}>
          Submit verified review
        </button>
        {reviewMessage && (
          <p className="storefront-reviews__success">{reviewMessage}</p>
        )}
      </form>
    </section>
  );
}

export default StorefrontPage;
````

## Feature 18 source — Chatbot

Files in this feature: 1

### `backend/app/services/public_chat_service.py`

````python
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from firebase_admin import firestore

from app.core.errors import ApiError
from app.services.customer_service import (
    create_customer,
    list_customers,
    normalize_sri_lankan_phone,
)
from app.services.ai_service import generate_product_answer
from app.services.order_service import create_order
from app.services.public_catalog_service import (
    get_public_product,
    get_public_store,
    public_product,
)
from app.services.text import optional_text, required_text
from app.services.review_service import list_public_product_reviews


PRODUCT_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "product",
    "item",
}

ORDER_INTENT_PHRASES = {
    "i want to order",
    "place order",
    "buy this",
    "order this",
    "ready to order",
    "checkout",
}

CONFIRMATION_PHRASES = {
    "yes",
    "yes confirm",
    "confirm",
    "confirm order",
    "submit order",
    "place it",
    "ok",
    "okay",
}


def message_tokens(value):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).casefold())
        if len(token) > 2 and token not in PRODUCT_STOP_WORDS
    }


def find_product_in_message(message, products):
    """Resolve a catalogue choice by number, name, short code or useful words."""
    clean_message = str(message).strip().casefold()
    numbered_choice = re.fullmatch(
        r"(?:product|item)?\s*#?\s*(\d+)",
        clean_message,
    )

    if numbered_choice:
        product_index = int(numbered_choice.group(1)) - 1
        if 0 <= product_index < len(products):
            return products[product_index]

    for product in products:
        product_name = product.get("name", "").strip().casefold()
        short_code = product.get("shortCode", "").strip().casefold()

        if short_code and short_code in clean_message:
            return product
        if product_name and product_name in clean_message:
            return product

    customer_tokens = message_tokens(clean_message)
    scored_products = []

    for product in products:
        product_words = message_tokens(product.get("name", ""))
        matching_words = customer_tokens & product_words

        if matching_words:
            scored_products.append((len(matching_words), product))

    if not scored_products:
        return None

    scored_products.sort(key=lambda item: item[0], reverse=True)
    highest_score = scored_products[0][0]
    best_matches = [
        product for score, product in scored_products if score == highest_score
    ]
    return best_matches[0] if len(best_matches) == 1 else None


def is_catalog_number_choice(message):
    """Return True when the customer only selects a numbered catalogue item."""
    return bool(
        re.fullmatch(
            r"(?:product|item)?\s*#?\s*\d+",
            str(message).strip().casefold(),
        ),
    )


def normalized_phrase(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def find_category_request(message, products):
    """Resolve an explicit request for a whole product category."""
    clean_message = str(message).strip().casefold()
    compact_message = normalized_phrase(clean_message)
    category_cues = {"show", "list", "all", "category", "categories", "have"}
    message_words = message_tokens(clean_message)
    categories = {
        product.get("categoryName", "").strip()
        for product in products
        if product.get("categoryName", "").strip()
    }

    for category in categories:
        compact_category = normalized_phrase(category)
        category_aliases = {compact_category}
        if compact_category.endswith("s"):
            category_aliases.add(compact_category[:-1])
        if compact_category.endswith("es"):
            category_aliases.add(compact_category[:-2])
        category_words = message_tokens(category)
        exact_category = compact_message in category_aliases
        category_is_named = (
            any(alias and alias in compact_message for alias in category_aliases)
            or category_words.issubset(message_words)
        )
        has_category_cue = bool(category_cues & message_words)

        if exact_category or (category_is_named and has_category_cue):
            return category

    return None


def category_products(products, category_name, excluded_product_id=None):
    return [
        product
        for product in products
        if product.get("categoryName") == category_name
        and product.get("id") != excluded_product_id
    ]


def normalize_chat_cart(value):
    """Keep only variant identifiers and safe positive quantities in chat state."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ApiError("validation_error", "The order draft must be a list.", 422)
    if len(value) > 50:
        raise ApiError(
            "too_many_order_items",
            "An order can contain no more than 50 item rows.",
            422,
        )

    quantities = {}

    for item in value:
        if not isinstance(item, dict):
            continue
        variant_id = str(item.get("variantId") or "").strip()

        try:
            quantity = int(item.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0

        if variant_id and 0 < quantity <= 999:
            quantities[variant_id] = min(
                999,
                quantities.get(variant_id, 0) + quantity,
            )

    return [
        {"variantId": variant_id, "quantity": quantity}
        for variant_id, quantity in quantities.items()
    ]


def summarize_chat_cart(cart, products):
    variants = {}

    for product in products:
        for variant in product.get("variants", []):
            variants[variant.get("id")] = (product, variant)

    summary = []

    for item in cart:
        match = variants.get(item.get("variantId"))

        if not match:
            continue

        product, variant = match
        quantity = item["quantity"]
        unit_price = product.get("sellingPriceMinor", 0)
        summary.append(
            {
                "variantId": variant.get("id"),
                "productId": product.get("id"),
                "productName": product.get("name", ""),
                "size": variant.get("size", ""),
                "sku": variant.get("sku", ""),
                "quantity": quantity,
                "unitPriceMinor": unit_price,
                "lineTotalMinor": unit_price * quantity,
                "imageUrl": (product.get("media") or [{}])[0].get("url", ""),
            },
        )

    return summary


def parse_customer_name(message):
    clean_name = re.sub(
        r"^(?:my name is|name is|i am|i'm)\s+",
        "",
        str(message).strip(),
        flags=re.IGNORECASE,
    ).strip()

    if len(clean_name) < 2 or not any(character.isalpha() for character in clean_name):
        raise ValueError("Please enter a valid full name.")

    return required_text(clean_name, "Customer name", 160)


def parse_delivery_address(message):
    clean_address = re.sub(
        r"^(?:my address is|deliver to|delivery address is)\s+",
        "",
        str(message).strip(),
        flags=re.IGNORECASE,
    ).strip()
    parts = [part.strip() for part in clean_address.split(",") if part.strip()]

    if len(parts) < 3:
        raise ValueError(
            "Please send the street address, nearest city and district separated "
            "by commas. Example: No. 45 Park Road, Dehiwala, Colombo.",
        )

    return {
        "line1": ", ".join(parts[:-2]),
        "line2": "",
        "city": parts[-2],
        "district": parts[-1],
        "postalCode": "",
    }


def is_optional_phone_skip(message):
    """Return True when the customer intentionally has no second number."""
    return str(message).strip().lower() in {
        "skip", "no", "none", "n/a", "na", "no second number",
        "i don't have one", "i do not have one", "continue",
    }


def parse_required_location(message, field_name):
    """Validate a single free-text location field collected by the chatbot."""
    value = str(message).strip()
    if len(value) < 2 or not any(character.isalpha() for character in value):
        raise ValueError(f"Please enter a valid {field_name}.")
    return required_text(value, field_name, 120)


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_public_chat_session(database, payload, customer_uid=None):
    store_code = payload.get("storeCode")
    product_code = payload.get("productCode")

    if product_code:
        catalog = get_public_product(database, product_code)
        business = catalog["business"]
        product = catalog["product"]
    elif store_code:
        catalog = get_public_store(database, store_code)
        business = catalog["business"]
        product = None
    else:
        raise ApiError(
            "public_link_required",
            "A store or product code is required.",
            422,
        )

    session_reference = database.collection("publicChatSessions").document()
    session_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session_reference.set(
        {
            "businessId": business["id"],
            "productId": product["id"] if product else None,
            "selectedProductId": product["id"] if product else None,
            "tokenHash": token_hash(session_token),
            "state": "browsing",
            "cart": [],
            "customerDraft": {},
            "customerUid": customer_uid,
            "status": "active",
            "createdAt": now,
            "updatedAt": now,
            "expiresAt": now + timedelta(hours=24),
        },
    )

    greeting = (
        f"Welcome to {business['name']}. What would you like to know about "
        f"{product['name']}?"
        if product
        else f"Welcome to {business['name']}. What product would you like to know about?"
    )

    return {
        "sessionId": session_reference.id,
        "sessionToken": session_token,
        "business": business,
        "product": product,
        "message": greeting,
        "action": "show-product" if product else "show-catalog",
        "products": [product] if product else catalog.get("products", []),
    }


def authorize_public_chat_session(
    database,
    session_id,
    provided_token,
    allow_closed=False,
):
    if not provided_token:
        raise ApiError(
            "chat_session_token_required",
            "A chat session token is required.",
            401,
        )

    snapshot = database.collection("publicChatSessions").document(session_id).get()

    if not snapshot.exists:
        raise ApiError("chat_session_not_found", "Chat session not found.", 404)

    session = snapshot.to_dict()

    if not hmac.compare_digest(
        session.get("tokenHash", ""),
        token_hash(provided_token),
    ):
        raise ApiError("invalid_chat_session", "Chat session is invalid.", 401)
    if not allow_closed and session.get("status") != "active":
        raise ApiError("chat_session_closed", "Chat session is closed.", 409)

    expires_at = session.get("expiresAt")

    if expires_at and expires_at < datetime.now(timezone.utc):
        raise ApiError("chat_session_expired", "Chat session has expired.", 401)

    return snapshot, session


def save_chat_message(session_reference, role, message, metadata=None):
    session_reference.collection("messages").document().set(
        {
            "role": role,
            "message": message,
            "metadata": metadata or {},
            "createdAt": firestore.SERVER_TIMESTAMP,
        },
    )


def claim_public_chat_session(database, session_id, provided_token, customer_uid):
    """Attach an active guest chat to the customer who has just signed in."""
    snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
        allow_closed=True,
    )
    existing_uid = session.get("customerUid")
    if existing_uid and existing_uid != customer_uid:
        raise ApiError(
            "chat_session_owner_mismatch",
            "This chat belongs to another customer account.",
            403,
        )
    snapshot.reference.update(
        {
            "customerUid": customer_uid,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    if session.get("orderId"):
        (
            database.collection("businesses")
            .document(session["businessId"])
            .collection("orders")
            .document(session["orderId"])
            .update({"customerUid": customer_uid})
        )
    return {"sessionId": snapshot.id, "claimed": True}


def public_order_confirmation(order):
    """Return only the order fields that the customer is allowed to see."""
    return {
        "id": order.get("id"),
        "orderNumber": order.get("orderNumber", ""),
        "items": [
            {
                "productId": item.get("productId"),
                "variantId": item.get("variantId"),
                "name": item.get("name", ""),
                "size": item.get("size", ""),
                "sku": item.get("sku", ""),
                "quantity": item.get("quantity", 0),
                "unitPriceMinor": item.get("unitPriceMinor", 0),
                "lineTotalMinor": item.get("lineTotalMinor", 0),
                "mediaUrl": item.get("mediaUrl", ""),
            }
            for item in order.get("items", [])
        ],
        "itemCount": order.get("itemCount", 0),
        "subtotalMinor": order.get("subtotalMinor", 0),
        "discountTotalMinor": order.get("discountTotalMinor", 0),
        "deliveryFeeMinor": order.get("deliveryFeeMinor", 0),
        "taxTotalMinor": order.get("taxTotalMinor", 0),
        "totalAmountMinor": order.get("totalAmountMinor", 0),
        "paymentMethod": order.get("paymentMethod", "cod"),
        "paymentStatus": order.get("paymentStatus", "unpaid"),
        "fulfilmentStatus": order.get("fulfilmentStatus", "needs-confirmation"),
        "deliveryAddress": order.get("deliveryAddress", {}),
        "courier": order.get("courierSnapshot", {}),
        "waybillNumber": order.get("waybillNumber", ""),
        "createdAt": order.get("createdAt"),
    }


def answer_public_message(database, session_id, provided_token, payload):
    session_snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
    )

    try:
        message = required_text(payload.get("message"), "Message", 2000)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    save_chat_message(session_snapshot.reference, "customer", message)
    business_snapshot = (
        database.collection("businesses").document(session["businessId"]).get()
    )
    store_code = business_snapshot.to_dict().get("shortCode")
    catalog = get_public_store(database, store_code)
    products = catalog["products"]
    supplied_cart = (
        normalize_chat_cart(payload.get("cart"))
        if "cart" in payload
        else None
    )
    cart = supplied_cart if supplied_cart is not None else session.get("cart", [])
    cart_summary = summarize_chat_cart(cart, products)
    valid_variant_ids = {item["variantId"] for item in cart_summary}
    cart = [item for item in cart if item["variantId"] in valid_variant_ids]
    customer_draft = dict(session.get("customerDraft") or {})
    current_state = session.get("state", "browsing")
    lowered_message = message.strip().casefold()

    def respond(
        response_message,
        action,
        *,
        next_state=None,
        product=None,
        response_products=None,
        selected_product_id="unchanged",
    ):
        state = next_state or current_state
        save_chat_message(
            session_snapshot.reference,
            "assistant",
            response_message,
            {
                "action": action,
                "productId": product.get("id") if product else None,
                "state": state,
            },
        )
        changes = {
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "state": state,
            "cart": cart,
            "customerDraft": customer_draft,
        }

        if selected_product_id != "unchanged":
            changes["selectedProductId"] = selected_product_id

        session_snapshot.reference.update(changes)
        return {
            "message": response_message,
            "action": action,
            "state": state,
            "product": product,
            "products": response_products or [],
            "cart": cart,
            "cartSummary": cart_summary,
            "cartSubtotalMinor": sum(
                item["lineTotalMinor"] for item in cart_summary
            ),
            "customerDraft": customer_draft,
        }

    # Contact collection is deterministic so invalid details never reach orders.
    if current_state == "collecting-name":
        try:
            customer_draft["name"] = parse_customer_name(message)
        except ValueError as error:
            return respond(str(error), "collect-name", next_state="collecting-name")

        return respond(
            f"Thanks, {customer_draft['name']}. What is your Sri Lankan mobile "
            "number? Example: 077 123 4567.",
            "collect-phone",
            next_state="collecting-phone",
        )

    if current_state == "collecting-phone":
        try:
            normalize_sri_lankan_phone(message)
        except ValueError as error:
            return respond(str(error), "collect-phone", next_state="collecting-phone")

        customer_draft["phoneNumber"] = message.strip()
        return respond(
            "Do you have a second phone number? Send it, or type 'skip' if you "
            "only have one number.",
            "collect-secondary-phone",
            next_state="collecting-secondary-phone",
        )

    if current_state == "collecting-secondary-phone":
        if is_optional_phone_skip(message):
            customer_draft["secondaryPhoneNumber"] = ""
        else:
            try:
                normalize_sri_lankan_phone(message)
            except ValueError as error:
                return respond(
                    f"{error} Send a valid second number, or type 'skip' to continue with one number.",
                    "collect-secondary-phone",
                    next_state="collecting-secondary-phone",
                )
            customer_draft["secondaryPhoneNumber"] = message.strip()
        return respond(
            "Please send your street address (for example: No. 45 Park Road).",
            "collect-address",
            next_state="collecting-address",
        )

    if current_state == "collecting-address":
        try:
            address_line = required_text(message.strip(), "Street address", 200)
        except ValueError as error:
            return respond(
                str(error),
                "collect-address",
                next_state="collecting-address",
            )

        customer_draft["address"] = {
            "line1": address_line, "line2": "", "city": "",
            "district": "", "postalCode": "",
        }
        return respond("Which district should we deliver to?", "collect-district", next_state="collecting-district")

    if current_state == "collecting-district":
        try:
            customer_draft["address"]["district"] = parse_required_location(message, "district")
        except ValueError as error:
            return respond(str(error), "collect-district", next_state="collecting-district")
        return respond("What is the nearest city?", "collect-nearest-city", next_state="collecting-nearest-city")

    if current_state == "collecting-nearest-city":
        try:
            customer_draft["address"]["city"] = parse_required_location(message, "nearest city")
        except ValueError as error:
            return respond(str(error), "collect-nearest-city", next_state="collecting-nearest-city")
        return respond(
            "Do you have any extra delivery note? Type it, or type 'skip' if there is no note.",
            "collect-delivery-note",
            next_state="collecting-delivery-note",
        )

    if current_state == "collecting-delivery-note":
        customer_draft["deliveryNote"] = "" if is_optional_phone_skip(message) else message.strip()

        item_text = ", ".join(
            f"{item['quantity']} Ã— {item['productName']}"
            + (f" (size {item['size']})" if item["size"] else "")
            for item in cart_summary
        )
        address = customer_draft["address"]
        response_message = (
            f"Please confirm your order: {item_text}. Customer: "
            f"{customer_draft['name']}, {customer_draft['phoneNumber']}"
            + (f" / {customer_draft['secondaryPhoneNumber']}" if customer_draft.get("secondaryPhoneNumber") else "")
            + ". Delivery: "
            f"{address['line1']}, {address['city']}, {address['district']}. "
            + (f"Note: {customer_draft['deliveryNote']}. " if customer_draft.get("deliveryNote") else "")
            + "The delivery fee will be calculated from the district and total weight. "
            + "Reply 'confirm order' to submit, or 'change order' to edit the details."
        )
        return respond(
            response_message,
            "confirm-order",
            next_state="awaiting-confirmation",
        )

    if current_state == "awaiting-confirmation":
        confirms_order = (
            lowered_message in CONFIRMATION_PHRASES
            or "confirm order" in lowered_message
        )
        changes_order = any(
            phrase in lowered_message
            for phrase in ("change", "edit", "no", "cancel")
        )

        if confirms_order:
            order = create_public_chat_order(
                database,
                session_id,
                provided_token,
                {
                    "customer": {
                        "name": customer_draft.get("name"),
                        "phoneNumber": customer_draft.get("phoneNumber"),
                        "secondaryPhoneNumber": customer_draft.get("secondaryPhoneNumber", ""),
                        "email": customer_draft.get("email", ""),
                        "address": customer_draft.get("address"),
                    },
                    "items": cart,
                    "deliveryNote": customer_draft.get("deliveryNote", ""),
                },
            )
            response_message = (
                f"Your order {order['orderNumber']} was placed successfully. "
                f"Items subtotal: LKR {order['subtotalMinor'] / 100:,.2f}, "
                f"delivery: LKR {order['deliveryFeeMinor'] / 100:,.2f}, total: "
                f"LKR {order['totalAmountMinor'] / 100:,.2f}."
            )
            save_chat_message(
                session_snapshot.reference,
                "assistant",
                response_message,
                {"action": "order-confirmed", "orderId": order["id"]},
            )
            return {
                "message": response_message,
                "action": "order-confirmed",
                "state": "completed",
                "product": None,
                "products": [],
                "cart": [],
                "cartSummary": [],
                "cartSubtotalMinor": 0,
                "customerDraft": customer_draft,
                "order": order,
            }

        if changes_order:
            customer_draft = {}
            return respond(
                "No problem. Your selected products are still in the draft. "
                "Please enter the customer full name again.",
                "collect-name",
                next_state="collecting-name",
            )

        return respond(
            "Please reply 'confirm order' to submit this order, or 'change order' "
            "to correct the customer or delivery details.",
            "confirm-order",
            next_state="awaiting-confirmation",
        )

    wants_catalog = any(
        phrase in lowered_message
        for phrase in (
            "show products",
            "show catalogue",
            "show catalog",
            "what do you have",
        )
    )
    wants_to_order = any(phrase in lowered_message for phrase in ORDER_INTENT_PHRASES)
    wants_alternatives = any(
        phrase in lowered_message
        for phrase in (
            "not satisfied",
            "not interested",
            "don't like",
            "do not like",
            "something else",
            "similar product",
            "other option",
            "other item",
            "another product",
        )
    )
    category_request = find_category_request(message, products)
    explicitly_selected_product = find_product_in_message(message, products)
    remembered_product_id = session.get("productId") or session.get(
        "selectedProductId",
    )
    remembered_product = next(
        (
            product
            for product in products
            if product["id"] == remembered_product_id
        ),
        None,
    )
    selected_product = explicitly_selected_product or remembered_product

    if wants_to_order:
        if not cart_summary:
            response_message = (
                "First select the product and size, then use Add to order. "
                "Your selected items will appear in the Live Order Draft on the right."
            )
            return respond(
                response_message,
                "start-order",
                next_state="browsing",
                product=selected_product,
                response_products=[selected_product] if selected_product else products,
                selected_product_id=(
                    selected_product["id"] if selected_product else "unchanged"
                ),
            )

        return respond(
            f"Great. Your draft contains {sum(item['quantity'] for item in cart_summary)} "
            "item(s). What is the customer's full name?",
            "collect-name",
            next_state="collecting-name",
        )

    if wants_alternatives and selected_product:
        alternatives = category_products(
            products,
            selected_product.get("categoryName"),
            selected_product["id"],
        )
        if not alternatives:
            alternatives = [
                product for product in products if product["id"] != selected_product["id"]
            ]

        return respond(
            (
                f"Here are other {selected_product.get('categoryName') or 'product'} "
                "options you may prefer. Select one to see its photos and details."
                if alternatives
                else "There are no other available products in this category right now."
            ),
            "suggest-alternatives",
            next_state="browsing",
            response_products=alternatives,
        )

    if category_request:
        matches = category_products(products, category_request)
        return respond(
            f"Here are all available products in {category_request}.",
            "show-category",
            next_state="browsing",
            response_products=matches,
            selected_product_id=None if not session.get("productId") else "unchanged",
        )

    if wants_catalog:
        return respond(
            "Here is the catalogue. Choose a product to see its image, description, "
            "price, available sizes and stock.",
            "show-catalog",
            next_state="browsing",
            response_products=products,
            selected_product_id=None if not session.get("productId") else "unchanged",
        )

    if selected_product:
        if "review" in lowered_message:
            reviews = list_public_product_reviews(
                database,
                session["businessId"],
                selected_product["id"],
            )
            selected_product = {
                **selected_product,
                "approvedReviewSnippets": [
                    {
                        "rating": review["rating"],
                        "reviewText": review["reviewText"],
                    }
                    for review in reviews[:5]
                ],
            }

        deterministic_description = (
            selected_product.get("aiDescription")
            or selected_product.get("description")
            or "The seller has not added a detailed description yet."
        )

        if "review" in lowered_message and selected_product.get("approvedReviewSnippets"):
            review_text = "; ".join(
                f"{review['rating']}/5 - {review['reviewText']}"
                for review in selected_product["approvedReviewSnippets"]
            )
            response_message = f"Verified customer reviews: {review_text}"
        elif "review" in lowered_message:
            response_message = "This product does not have approved customer reviews yet."
        elif is_catalog_number_choice(message) or explicitly_selected_product:
            available_sizes = [
                variant.get("size")
                for variant in selected_product.get("variants", [])
                if variant.get("size")
            ]
            size_text = (
                f" Available sizes: {', '.join(available_sizes)}."
                if available_sizes
                else ""
            )
            response_message = (
                f"{selected_product['name']}: {deterministic_description} "
                f"Price: LKR {selected_product['sellingPriceMinor'] / 100:,.2f}."
                f"{size_text} Ask me about a specific feature, add it to your order, "
                "or ask for other options in this category."
            )
        else:
            response_message = generate_product_answer(message, selected_product) or (
                f"Based on the seller's information: {deterministic_description} "
                "If that does not answer the specific feature you asked about, the "
                "seller has not provided that detail yet."
            )

        return respond(
            response_message,
            "show-product",
            next_state="browsing",
            product=selected_product,
            selected_product_id=selected_product["id"],
        )

    return respond(
        "Please choose a product or category. I can show product photos and "
        "descriptions, answer feature questions, suggest alternatives and take "
        "a complete order.",
        "show-catalog",
        next_state="browsing",
        response_products=products,
    )


def create_public_chat_order(database, session_id, provided_token, payload):
    session_snapshot, session = authorize_public_chat_session(
        database,
        session_id,
        provided_token,
    )
    customer_payload = payload.get("customer")

    if not isinstance(customer_payload, dict):
        raise ApiError("validation_error", "Customer details are required.", 422)

    existing_customers = list_customers(
        database,
        session["businessId"],
        phone=customer_payload.get("phoneNumber"),
    )
    customer = (
        existing_customers[0]
        if existing_customers
        else create_customer(database, session["businessId"], customer_payload)
    )
    try:
        delivery_note = optional_text(payload.get("deliveryNote"), 500)
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    private_note = "Created through the public Vendly chatbot."
    if delivery_note:
        private_note = f"{private_note} Customer delivery note: {delivery_note}"

    order_payload = {
        "customerId": customer["id"],
        "items": payload.get("items"),
        "deliveryAddress": customer_payload.get("address"),
        "courierId": payload.get("courierId", ""),
        "paymentMethod": "cod",
        "source": "chatbot",
        "discountAmount": 0,
        "privateNote": private_note,
        "customerUid": session.get("customerUid", ""),
    }

    if session.get("productId"):
        for item in order_payload.get("items") or []:
            variant_snapshot = (
                database.collection("businesses")
                .document(session["businessId"])
                .collection("productVariants")
                .document(item.get("variantId", ""))
                .get()
            )

            if (
                not variant_snapshot.exists
                or variant_snapshot.to_dict().get("productId") != session["productId"]
            ):
                raise ApiError(
                    "product_link_restriction",
                    "This product link can only order the linked product.",
                    403,
                )

    order = create_order(
        database,
        session["businessId"],
        f"public-chat:{session_id}",
        order_payload,
    )
    session_snapshot.reference.update(
        {
            "status": "completed",
            "orderId": order["id"],
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return public_order_confirmation(order)
````

## Feature 19 source — Customer accounts, guest history and tracking

Files in this feature: 3

### `backend/app/services/customer_portal_service.py`

````python
from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.public_catalog_service import resolve_short_link
from app.services.public_chat_service import public_order_confirmation


def resolve_store_business_id(database, store_code):
    return resolve_short_link(database, store_code, "store")["businessId"]


def list_customer_orders(database, store_code, customer_uid):
    business_id = resolve_store_business_id(database, store_code)
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .where("customerUid", "==", customer_uid)
        .stream()
    )
    orders = [public_order_confirmation(serialize_snapshot(item)) for item in snapshots]
    return sorted(orders, key=lambda item: str(item.get("createdAt", "")), reverse=True)


def get_customer_order(database, store_code, customer_uid, order_id):
    business_id = resolve_store_business_id(database, store_code)
    snapshot = (
        database.collection("businesses")
        .document(business_id)
        .collection("orders")
        .document(order_id)
        .get()
    )
    if not snapshot.exists or snapshot.to_dict().get("customerUid") != customer_uid:
        raise ApiError("customer_order_not_found", "Order not found.", 404)
    return public_order_confirmation(serialize_snapshot(snapshot))


def list_customer_chats(database, store_code, customer_uid):
    business_id = resolve_store_business_id(database, store_code)
    snapshots = (
        database.collection("publicChatSessions")
        .where("customerUid", "==", customer_uid)
        .stream()
    )
    chats = []
    for snapshot in snapshots:
        session = serialize_snapshot(snapshot)
        if session.get("businessId") != business_id:
            continue
        messages = [
            serialize_snapshot(message)
            for message in snapshot.reference.collection("messages").stream()
        ]
        messages.sort(key=lambda item: str(item.get("createdAt", "")))
        chats.append(
            {
                "id": snapshot.id,
                "status": session.get("status", "active"),
                "state": session.get("state", "browsing"),
                "orderId": session.get("orderId", ""),
                "createdAt": session.get("createdAt"),
                "updatedAt": session.get("updatedAt"),
                "messages": messages,
            }
        )
    return sorted(chats, key=lambda item: str(item.get("updatedAt", "")), reverse=True)
````

### `frontend/src/components/CustomerAccountModal.jsx`

````jsx
import { useEffect, useState } from "react";
import { Clock3, LogIn, LogOut, MessageSquareText, PackageSearch, UserRound, X } from "lucide-react";
import {
  loginAsGuest,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import { getCustomerChats, getCustomerOrders } from "../services/publicService";
import "./CustomerAccountModal.css";

function readableStatus(value = "") {
  return value.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function CustomerAccountModal({ isOpen, onClose, user, storeCode }) {
  const [mode, setMode] = useState("login");
  const [tab, setTab] = useState("orders");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [orders, setOrders] = useState([]);
  const [chats, setChats] = useState([]);
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    if (!isOpen || !user || !storeCode) return;
    let active = true;
    setIsBusy(true);
    Promise.all([getCustomerOrders(storeCode), getCustomerChats(storeCode)])
      .then(([orderResponse, chatResponse]) => {
        if (!active) return;
        setOrders(orderResponse.orders ?? []);
        setChats(chatResponse.chats ?? []);
        setError("");
      })
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setIsBusy(false));
    return () => { active = false; };
  }, [isOpen, storeCode, user]);

  if (!isOpen) return null;

  async function submit(event) {
    event.preventDefault();
    setIsBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await registerWithEmail(form.name, form.email, form.password);
        await logoutUser();
        setError("Check your email and verify your address, then log in.");
        setMode("login");
      } else {
        await loginWithEmail(form.email, form.password);
      }
    } catch (authError) {
      setError(authError.message);
    } finally {
      setIsBusy(false);
    }
  }

  async function authenticate(action) {
    setIsBusy(true);
    setError("");
    try { await action(); } catch (authError) { setError(authError.message); }
    finally { setIsBusy(false); }
  }

  return (
    <div className="customer-account-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="customer-account-modal" role="dialog" aria-modal="true" aria-label="Customer account">
        <header><div><UserRound size={20} /><div><strong>{user ? "My account" : "Customer login"}</strong><small>Save chats, orders and tracking details</small></div></div><button type="button" onClick={onClose} aria-label="Close"><X size={19} /></button></header>

        {!user ? (
          <div className="customer-account-auth">
            <div className="customer-account-switch"><button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => setMode("login")}>Log in</button><button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => setMode("register")}>Create account</button></div>
            <form onSubmit={submit}>
              {mode === "register" && <label>Name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>}
              <label>Email<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
              <label>Password<input type="password" minLength={6} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
              <button className="customer-account-primary" disabled={isBusy}><LogIn size={17} />{mode === "login" ? "Log in" : "Create account"}</button>
            </form>
            <div className="customer-account-divider"><span>or</span></div>
            <button type="button" onClick={() => authenticate(loginWithGoogle)} disabled={isBusy}>Continue with Google</button>
            <button type="button" onClick={() => authenticate(loginAsGuest)} disabled={isBusy}>Continue as guest</button>
            <small className="customer-account-hint">Guest history remains available on this browser. Create an account to use it across devices.</small>
          </div>
        ) : (
          <div className="customer-account-portal">
            <div className="customer-account-identity"><span>{user.isAnonymous ? "G" : (user.displayName || user.email || "C").charAt(0).toUpperCase()}</span><div><strong>{user.isAnonymous ? "Guest customer" : user.displayName || "Customer"}</strong><small>{user.isAnonymous ? "History saved on this device" : user.email}</small></div><button type="button" onClick={() => authenticate(logoutUser)}><LogOut size={16} /> Log out</button></div>
            <nav><button className={tab === "orders" ? "is-active" : ""} type="button" onClick={() => setTab("orders")}><PackageSearch size={16} /> Orders</button><button className={tab === "chats" ? "is-active" : ""} type="button" onClick={() => setTab("chats")}><MessageSquareText size={16} /> Chats</button></nav>
            {isBusy && <p className="customer-account-empty">Loading historyâ€¦</p>}
            {!isBusy && tab === "orders" && <div className="customer-account-list">{orders.length ? orders.map((order) => <article key={order.id}><div><strong>{order.orderNumber}</strong><span className={`customer-order-status customer-order-status--${order.fulfilmentStatus}`}>{readableStatus(order.fulfilmentStatus)}</span></div><p>{order.items.map((item) => `${item.name} Ã— ${item.quantity}`).join(", ")}</p><dl><div><dt>Total</dt><dd>Rs {(order.totalAmountMinor / 100).toLocaleString("en-LK")}</dd></div><div><dt>Courier</dt><dd>{order.courier?.name || "Being assigned"}</dd></div><div><dt>Waybill</dt><dd>{order.waybillNumber || "Pending"}</dd></div></dl><div className="customer-order-progress"><span className="is-complete">Confirmed</span><span className={["packed", "shipped", "delivered"].includes(order.fulfilmentStatus) ? "is-complete" : ""}>Packed</span><span className={["shipped", "delivered"].includes(order.fulfilmentStatus) ? "is-complete" : ""}>Shipped</span><span className={order.fulfilmentStatus === "delivered" ? "is-complete" : ""}>Delivered</span></div></article>) : <p className="customer-account-empty">No orders are linked to this account yet.</p>}</div>}
            {!isBusy && tab === "chats" && <div className="customer-account-list">{chats.length ? chats.map((chat) => <article key={chat.id}><div><strong>Chat conversation</strong><span><Clock3 size={13} /> {chat.status}</span></div>{chat.messages.slice(-4).map((message) => <p key={message.id}><b>{message.role === "assistant" ? "Vendly" : "You"}:</b> {message.message}</p>)}</article>) : <p className="customer-account-empty">No saved chats yet.</p>}</div>}
          </div>
        )}
        {error && <p className="customer-account-error" role="alert">{error}</p>}
      </section>
    </div>
  );
}

export default CustomerAccountModal;
````

### `frontend/src/components/CustomerAccountModal.css`

````css
.customer-account-backdrop {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: grid;
  padding: 20px;
  place-items: center;
  background: rgba(4, 18, 34, 0.58);
  backdrop-filter: blur(7px);
}

.customer-account-modal {
  width: min(680px, 100%);
  max-height: min(760px, calc(100vh - 40px));
  overflow: auto;
  border: 1px solid var(--sf-border, #dfe4ec);
  border-radius: 20px;
  color: var(--sf-text, #142238);
  background: var(--sf-surface, #fff);
  box-shadow: 0 28px 80px rgba(0, 22, 48, 0.28);
  animation: customer-modal-in 180ms ease-out;
}

@keyframes customer-modal-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: none; }
}

.customer-account-modal > header,
.customer-account-modal > header > div,
.customer-account-identity,
.customer-account-identity > div,
.customer-account-portal nav,
.customer-account-list article > div,
.customer-account-list article > div > span {
  display: flex;
  align-items: center;
}

.customer-account-modal > header {
  position: sticky;
  top: 0;
  z-index: 2;
  min-height: 72px;
  padding: 14px 20px;
  justify-content: space-between;
  border-bottom: 1px solid var(--sf-border, #dfe4ec);
  background: var(--sf-surface, #fff);
}

.customer-account-modal > header > div { gap: 11px; }
.customer-account-modal > header > div > div { display: grid; gap: 2px; }
.customer-account-modal > header small { color: var(--sf-muted, #667386); }
.customer-account-modal button { border: 1px solid var(--sf-border, #dfe4ec); border-radius: 10px; background: var(--sf-surface, #fff); cursor: pointer; }
.customer-account-modal > header > button { display: grid; width: 36px; height: 36px; padding: 0; place-items: center; }

.customer-account-auth { display: grid; width: min(400px, 100%); margin: auto; padding: 26px; gap: 12px; }
.customer-account-switch { display: grid; grid-template-columns: 1fr 1fr; padding: 4px; border-radius: 12px; background: var(--sf-soft, #f2f4f8); }
.customer-account-switch button { min-height: 38px; border: 0; background: transparent; }
.customer-account-switch button.is-active { color: #fff; background: var(--sf-primary, #0872d9); }
.customer-account-auth form { display: grid; gap: 12px; }
.customer-account-auth label { display: grid; gap: 6px; font-size: 0.82rem; font-weight: 700; }
.customer-account-auth input { height: 43px; padding: 0 12px; border: 1px solid var(--sf-border, #dfe4ec); border-radius: 9px; color: inherit; background: var(--sf-surface, #fff); }
.customer-account-auth > button,
.customer-account-primary { display: flex; min-height: 43px; align-items: center; justify-content: center; gap: 8px; font-weight: 750; }
.customer-account-primary { border-color: transparent !important; color: #fff !important; background: var(--sf-primary, #0872d9) !important; }
.customer-account-divider { position: relative; text-align: center; color: var(--sf-muted, #667386); }
.customer-account-divider::before { position: absolute; top: 50%; right: 0; left: 0; height: 1px; content: ""; background: var(--sf-border, #dfe4ec); }
.customer-account-divider span { position: relative; padding: 0 10px; background: var(--sf-surface, #fff); }
.customer-account-hint { color: var(--sf-muted, #667386); text-align: center; line-height: 1.5; }

.customer-account-portal { padding: 20px; }
.customer-account-identity { gap: 12px; padding: 14px; border-radius: 14px; background: var(--sf-soft, #f2f4f8); }
.customer-account-identity > span { display: grid; width: 43px; height: 43px; place-items: center; border-radius: 50%; color: #fff; font-weight: 800; background: var(--sf-primary, #0872d9); }
.customer-account-identity > div { display: grid; flex: 1; gap: 2px; }
.customer-account-identity small { color: var(--sf-muted, #667386); }
.customer-account-identity button { display: flex; padding: 9px 12px; align-items: center; gap: 6px; color: #d73737; }
.customer-account-portal nav { gap: 7px; margin: 18px 0 12px; border-bottom: 1px solid var(--sf-border, #dfe4ec); }
.customer-account-portal nav button { display: flex; padding: 10px 14px; align-items: center; gap: 7px; border: 0; border-radius: 9px 9px 0 0; background: transparent; }
.customer-account-portal nav button.is-active { color: var(--sf-primary, #0872d9); background: color-mix(in srgb, var(--sf-primary, #0872d9) 10%, transparent); }
.customer-account-list { display: grid; gap: 11px; }
.customer-account-list article { padding: 15px; border: 1px solid var(--sf-border, #dfe4ec); border-radius: 13px; background: var(--sf-surface, #fff); }
.customer-account-list article > div { justify-content: space-between; gap: 10px; }
.customer-account-list article > div > span { gap: 5px; color: var(--sf-muted, #667386); font-size: 0.76rem; }
.customer-account-list article > p { margin: 10px 0; color: var(--sf-muted, #667386); font-size: 0.83rem; line-height: 1.45; }
.customer-account-list dl { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0; }
.customer-account-list dl div { display: grid; gap: 3px; }
.customer-account-list dt { color: var(--sf-muted, #667386); font-size: 0.72rem; }
.customer-account-list dd { margin: 0; font-size: 0.82rem; font-weight: 700; }
.customer-order-status { padding: 5px 8px; border-radius: 999px; color: #087c58 !important; background: #e5f7f0; }
.customer-order-progress { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; }
.customer-order-progress span { padding-top: 8px; border-top: 3px solid var(--sf-border, #dfe4ec); color: var(--sf-muted, #667386); text-align: center; font-size: 0.67rem; }
.customer-order-progress span.is-complete { border-color: var(--sf-primary, #0872d9); color: var(--sf-primary, #0872d9); font-weight: 750; }
.customer-account-empty { padding: 32px; color: var(--sf-muted, #667386); text-align: center; }
.customer-account-error { margin: 0 20px 20px; padding: 10px 12px; border-radius: 9px; color: #a32929; background: #ffeded; }

@media (max-width: 600px) {
  .customer-account-backdrop { padding: 0; align-items: end; }
  .customer-account-modal { max-height: 92vh; border-radius: 20px 20px 0 0; }
  .customer-account-list dl { grid-template-columns: 1fr 1fr; }
  .customer-account-identity { align-items: flex-start; flex-wrap: wrap; }
}
````

## Feature 20 source — Reviews

Files in this feature: 5

### `backend/app/api/reviews.py`

````python
from flask import Blueprint, g, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.core.rate_limit import limiter
from app.core.requests import get_json_object
from app.services.public_catalog_service import get_public_product
from app.services.review_service import (
    create_verified_review,
    list_public_product_reviews,
    list_reviews,
    moderate_review,
)


reviews_blueprint = Blueprint("reviews", __name__, url_prefix="/api/v1")


@reviews_blueprint.get("/public/products/<short_code>/reviews")
@limiter.limit("120 per minute")
def public_product_reviews(short_code):
    catalog = get_public_product(get_firestore_client(), short_code)
    reviews = list_public_product_reviews(
        get_firestore_client(),
        catalog["business"]["id"],
        catalog["product"]["id"],
    )
    return jsonify({"reviews": reviews})


@reviews_blueprint.post("/public/stores/<store_code>/reviews")
@limiter.limit("5 per hour")
def submit_public_review(store_code):
    review = create_verified_review(
        get_firestore_client(),
        store_code,
        get_json_object(),
    )
    return jsonify({"review": review}), 201


@reviews_blueprint.get("/businesses/<business_id>/reviews")
@require_firebase_user
@require_business_member(permission="inventory:read")
def get_reviews(business_id):
    reviews = list_reviews(
        get_firestore_client(),
        business_id,
        status=request.args.get("status"),
        product_id=request.args.get("productId"),
    )
    return jsonify({"reviews": reviews})


@reviews_blueprint.patch("/businesses/<business_id>/reviews/<review_id>")
@require_firebase_user
@require_business_member(permission="reviews:manage")
def update_review(business_id, review_id):
    review = moderate_review(
        get_firestore_client(),
        business_id,
        review_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"review": review})
````

### `backend/app/services/review_service.py`

````python
from firebase_admin import firestore
from google.cloud import firestore as google_firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.core.errors import ApiError
from app.core.serialization import serialize_snapshot
from app.services.customer_service import normalize_sri_lankan_phone
from app.services.numbers import non_negative_integer
from app.services.public_catalog_service import resolve_short_link
from app.services.text import optional_text, required_text


REVIEW_STATUSES = {"pending", "approved", "rejected"}


def validate_review_payload(payload):
    try:
        order_number = required_text(payload.get("orderNumber"), "Order number", 40).upper()
        normalized_phone = normalize_sri_lankan_phone(payload.get("phoneNumber"))
        product_id = optional_text(payload.get("productId"), 120)
        review_text = required_text(payload.get("reviewText"), "Review", 2000)
        rating = non_negative_integer(payload.get("rating"), "Rating")
    except ValueError as error:
        raise ApiError("validation_error", str(error), 422) from error

    if rating < 1 or rating > 5:
        raise ApiError("validation_error", "Rating must be between 1 and 5.", 422)

    return {
        "orderNumber": order_number,
        "normalizedPhone": normalized_phone,
        "productId": product_id,
        "reviewText": review_text,
        "rating": rating,
    }


def create_verified_review(database, store_code, payload):
    review = validate_review_payload(payload)
    link = resolve_short_link(database, store_code, "store")
    business_id = link["businessId"]
    business_reference = database.collection("businesses").document(business_id)
    order_snapshots = list(
        business_reference.collection("orders")
        .where(filter=FieldFilter("orderNumber", "==", review["orderNumber"]))
        .limit(1)
        .stream(),
    )

    if not order_snapshots:
        raise ApiError(
            "review_order_not_found",
            "The order number and phone number could not be verified.",
            404,
        )

    order_snapshot = order_snapshots[0]
    order = order_snapshot.to_dict()

    if order.get("customerSnapshot", {}).get("normalizedPhone") != review["normalizedPhone"]:
        raise ApiError(
            "review_order_not_found",
            "The order number and phone number could not be verified.",
            404,
        )
    if order.get("fulfilmentStatus") != "delivered":
        raise ApiError(
            "review_order_not_delivered",
            "A review can be submitted after the order is delivered.",
            409,
        )

    product_id = review["productId"]

    if product_id and not any(
        item.get("productId") == product_id for item in order.get("items", [])
    ):
        raise ApiError(
            "review_product_not_in_order",
            "The selected product was not included in this order.",
            403,
        )

    review_type = "product" if product_id else "seller"
    review_id = f"{order_snapshot.id}_{product_id or 'seller'}"
    reference = business_reference.collection("reviews").document(review_id)

    if reference.get().exists:
        raise ApiError(
            "review_already_submitted",
            "A review for this order has already been submitted.",
            409,
        )

    reference.set(
        {
            "type": review_type,
            "orderId": order_snapshot.id,
            "orderNumber": order.get("orderNumber", ""),
            "productId": product_id,
            "customerId": order.get("customerId", ""),
            "customerName": order.get("customerSnapshot", {}).get("name", "Customer"),
            "rating": review["rating"],
            "reviewText": review["reviewText"],
            "media": [],
            "status": "pending",
            "verifiedPurchase": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )
    return serialize_snapshot(reference.get())


def list_reviews(database, business_id, status=None, product_id=None):
    snapshots = (
        database.collection("businesses")
        .document(business_id)
        .collection("reviews")
        .order_by("createdAt", direction="DESCENDING")
        .limit(200)
        .stream()
    )
    reviews = [serialize_snapshot(snapshot) for snapshot in snapshots]

    if status:
        reviews = [review for review in reviews if review.get("status") == status]
    if product_id:
        reviews = [review for review in reviews if review.get("productId") == product_id]

    return reviews


def list_public_product_reviews(database, business_id, product_id):
    return [
        {
            "id": review["id"],
            "customerName": review.get("customerName", "Customer"),
            "rating": review.get("rating", 0),
            "reviewText": review.get("reviewText", ""),
            "verifiedPurchase": review.get("verifiedPurchase", False),
            "createdAt": review.get("createdAt"),
        }
        for review in list_reviews(
            database,
            business_id,
            status="approved",
            product_id=product_id,
        )
    ]


def moderate_review(database, business_id, review_id, uid, payload):
    status = str(payload.get("status", "")).strip().lower()

    if status not in {"approved", "rejected"}:
        raise ApiError(
            "validation_error",
            "Review status must be approved or rejected.",
            422,
        )

    business_reference = database.collection("businesses").document(business_id)
    review_reference = business_reference.collection("reviews").document(review_id)
    transaction = database.transaction()

    @google_firestore.transactional
    def update_in_transaction(current_transaction):
        review_snapshot = review_reference.get(transaction=current_transaction)

        if not review_snapshot.exists:
            raise ApiError("review_not_found", "Review not found.", 404)

        review = review_snapshot.to_dict()

        if review.get("status") != "pending":
            raise ApiError(
                "review_already_moderated",
                "This review has already been moderated.",
                409,
            )

        target_reference = business_reference
        if review.get("type") == "product":
            target_reference = business_reference.collection("products").document(
                review.get("productId", ""),
            )

        target_snapshot = target_reference.get(transaction=current_transaction)
        timestamp = firestore.SERVER_TIMESTAMP
        current_transaction.update(
            review_reference,
            {
                "status": status,
                "moderatedBy": uid,
                "moderatedAt": timestamp,
                "updatedAt": timestamp,
            },
        )

        if status == "approved" and target_snapshot.exists:
            target = target_snapshot.to_dict()
            count = target.get("approvedReviewCount", 0) + 1
            rating_total = target.get("approvedReviewRatingTotal", 0) + review.get(
                "rating",
                0,
            )
            current_transaction.update(
                target_reference,
                {
                    "approvedReviewCount": count,
                    "approvedReviewRatingTotal": rating_total,
                    "averageRating": round(rating_total / count, 2),
                    "updatedAt": timestamp,
                },
            )

    update_in_transaction(transaction)
    return serialize_snapshot(review_reference.get())
````

### `frontend/src/components/ReviewsModal.css`

````css
.reviews-modal__list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.reviews-modal__review {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface-soft);
}

.reviews-modal__review header,
.reviews-modal__review footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.reviews-modal__review header > div {
  display: grid;
  gap: 3px;
}

.reviews-modal__review header span,
.reviews-modal__review small,
.reviews-modal__review p {
  color: var(--color-muted);
}

.reviews-modal__review p {
  margin: 0;
  line-height: 1.55;
}

.reviews-modal__stars {
  display: flex;
  color: #f59e0b;
}

.reviews-modal__status {
  padding: 4px 8px;
  border-radius: 999px;
  color: #9a5b00;
  background: rgba(245, 158, 11, 0.14);
  font-size: 11px;
  font-weight: 700;
  text-transform: capitalize;
}

.reviews-modal__status--approved {
  color: #067647;
  background: rgba(16, 185, 129, 0.14);
}

.reviews-modal__status--rejected {
  color: #b42318;
  background: rgba(239, 68, 68, 0.14);
}

.reviews-modal__review footer {
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
}

.reviews-modal__review footer button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-text);
  background: var(--color-surface);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}

.reviews-modal__review footer .reviews-modal__approve {
  border-color: #087cf0;
  color: white;
  background: #087cf0;
}

.reviews-modal__notice,
.reviews-modal__empty {
  padding: 18px;
  border-radius: 10px;
  color: var(--color-muted);
  background: var(--color-surface-soft);
  text-align: center;
}

.reviews-modal__notice--error {
  color: #b42318;
  background: rgba(239, 68, 68, 0.12);
}

@media (max-width: 760px) {
  .reviews-modal__list {
    grid-template-columns: 1fr;
  }
}
````

### `frontend/src/components/ReviewsModal.jsx`

````jsx
import { Check, Star, X } from "lucide-react";
import { useEffect, useState } from "react";

import { getProductReviews, moderateReview } from "../services/reviewService";
import ModalShell from "./ModalShell";
import "./ReviewsModal.css";


function ReviewsModal({ businessId, product, onClose, onApproved }) {
  const [reviews, setReviews] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [workingReviewId, setWorkingReviewId] = useState("");

  useEffect(() => {
    let requestIsCurrent = true;

    if (!businessId || !product?.id) return undefined;
    setIsLoading(true);
    setErrorMessage("");

    getProductReviews(businessId, product.id)
      .then((records) => {
        if (requestIsCurrent) setReviews(records);
      })
      .catch((error) => {
        if (requestIsCurrent) setErrorMessage(error.message);
      })
      .finally(() => {
        if (requestIsCurrent) setIsLoading(false);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [businessId, product?.id]);

  async function changeStatus(review, status) {
    setWorkingReviewId(review.id);
    setErrorMessage("");

    try {
      const updatedReview = await moderateReview(businessId, review.id, status);
      setReviews((current) =>
        current.map((item) => (item.id === review.id ? updatedReview : item)),
      );
      if (status === "approved") onApproved?.(product.id);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setWorkingReviewId("");
    }
  }

  return (
    <ModalShell
      isOpen={Boolean(product)}
      title={`${product?.name ?? "Product"} reviews`}
      description="Approve verified reviews before they appear in the public catalogue and chatbot."
      onClose={onClose}
      size="large"
    >
      {isLoading && <p className="reviews-modal__notice">Loading reviews...</p>}
      {errorMessage && <p className="reviews-modal__notice reviews-modal__notice--error" role="alert">{errorMessage}</p>}

      <div className="reviews-modal__list">
        {reviews.map((review) => (
          <article className="reviews-modal__review" key={review.id}>
            <header>
              <div>
                <strong>{review.customerName}</strong>
                <span>{review.verifiedPurchase ? "Verified purchase" : "Customer review"}</span>
              </div>
              <span className={`reviews-modal__status reviews-modal__status--${review.status}`}>
                {review.status}
              </span>
            </header>

            <div className="reviews-modal__stars" aria-label={`${review.rating} out of 5 stars`}>
              {Array.from({ length: 5 }, (_, index) => (
                <Star
                  key={index}
                  size={16}
                  fill={index < review.rating ? "currentColor" : "none"}
                />
              ))}
            </div>
            <p>{review.reviewText}</p>
            <small>Order {review.orderNumber}</small>

            {review.status === "pending" && (
              <footer>
                <button
                  type="button"
                  onClick={() => changeStatus(review, "rejected")}
                  disabled={workingReviewId === review.id}
                >
                  <X size={16} /> Reject
                </button>
                <button
                  className="reviews-modal__approve"
                  type="button"
                  onClick={() => changeStatus(review, "approved")}
                  disabled={workingReviewId === review.id}
                >
                  <Check size={16} /> Approve
                </button>
              </footer>
            )}
          </article>
        ))}

        {!isLoading && reviews.length === 0 && (
          <p className="reviews-modal__empty">No reviews have been submitted for this product yet.</p>
        )}
      </div>
    </ModalShell>
  );
}

export default ReviewsModal;
````

### `frontend/src/services/reviewService.js`

````javascript
import { apiRequest } from "./apiClient";


export async function getProductReviews(businessId, productId) {
  const response = await apiRequest(
    `/businesses/${businessId}/reviews?productId=${encodeURIComponent(productId)}`,
  );
  return response.reviews;
}


export async function moderateReview(businessId, reviewId, status) {
  const response = await apiRequest(
    `/businesses/${businessId}/reviews/${reviewId}`,
    { method: "PATCH", body: { status } },
  );
  return response.review;
}
````

## Feature 21 source — Analytics and search

Files in this feature: 13

### `backend/app/api/analytics.py`

````python
from flask import Blueprint, jsonify

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.services.analytics_service import get_business_analytics


analytics_blueprint = Blueprint("analytics", __name__, url_prefix="/api/v1")


@analytics_blueprint.get("/businesses/<business_id>/analytics/overview")
@require_firebase_user
@require_business_member(permission="analytics:read")
def analytics_overview(business_id):
    return jsonify(
        {"analytics": get_business_analytics(get_firestore_client(), business_id)},
    )
````

### `backend/app/api/search.py`

````python
from flask import Blueprint, jsonify, request

from app.core.auth import require_firebase_user
from app.core.authorization import require_business_member
from app.core.firebase import get_firestore_client
from app.services.search_service import global_search


search_blueprint = Blueprint("search", __name__, url_prefix="/api/v1")


@search_blueprint.get("/businesses/<business_id>/search")
@require_firebase_user
@require_business_member()
def search_business(business_id):
    return jsonify(
        {
            "results": global_search(
                get_firestore_client(),
                business_id,
                request.args.get("q", ""),
            ),
        },
    )
````

### `backend/app/services/analytics_service.py`

````python
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core.serialization import serialize_snapshot


ORDER_STATUSES = (
    "needs-confirmation",
    "confirmed",
    "packed",
    "shipped",
    "delivered",
    "returned",
    "cancelled",
)


def as_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def month_key(year, month):
    return f"{year:04d}-{month:02d}"


def recent_months(now, count=12):
    months = []
    year = now.year
    month = now.month

    for offset in range(count - 1, -1, -1):
        absolute_month = (year * 12 + month - 1) - offset
        selected_year, selected_month_index = divmod(absolute_month, 12)
        months.append(month_key(selected_year, selected_month_index + 1))

    return months


def delivered_financials(order):
    product_revenue = max(
        order.get("subtotalMinor", 0) - order.get("discountTotalMinor", 0),
        0,
    )
    cost_of_goods = sum(
        item.get("unitCostMinor", 0) * item.get("quantity", 0)
        for item in order.get("items", [])
    )
    return product_revenue, cost_of_goods, product_revenue - cost_of_goods


def calculate_analytics(
    orders,
    products,
    customers=None,
    unread_notification_count=0,
    now=None,
):
    now = now or datetime.now(timezone.utc)
    customers = customers or []
    status_counts = {status: 0 for status in ORDER_STATUSES}
    product_revenue_minor = 0
    cost_of_goods_minor = 0
    gross_profit_minor = 0
    top_products = defaultdict(
        lambda: {"name": "Product", "quantity": 0, "revenueMinor": 0},
    )
    day_keys = [
        (now.date() - timedelta(days=offset)).isoformat()
        for offset in range(6, -1, -1)
    ]
    daily_counts = {key: 0 for key in day_keys}
    selected_months = recent_months(now)
    monthly_revenue = {key: 0 for key in selected_months}

    for order in orders:
        status = order.get("fulfilmentStatus", "needs-confirmation")
        if status in status_counts:
            status_counts[status] += 1

        created_at = as_datetime(order.get("createdAt"))
        if created_at and created_at.date().isoformat() in daily_counts:
            daily_counts[created_at.date().isoformat()] += 1

        if status != "delivered":
            continue

        revenue, cost, profit = delivered_financials(order)
        product_revenue_minor += revenue
        cost_of_goods_minor += cost
        gross_profit_minor += profit

        if created_at:
            key = month_key(created_at.year, created_at.month)
            if key in monthly_revenue:
                monthly_revenue[key] += revenue

        for item in order.get("items", []):
            product_id = item.get("productId", "unknown")
            summary = top_products[product_id]
            summary["id"] = product_id
            summary["name"] = item.get("name", "Product")
            summary["quantity"] += item.get("quantity", 0)
            summary["revenueMinor"] += item.get("lineTotalMinor", 0)

    active_orders = [
        order
        for order in orders
        if order.get("fulfilmentStatus") != "cancelled"
    ]
    total_order_value = sum(
        order.get("totalAmountMinor", 0) for order in active_orders
    )
    low_stock_count = sum(
        product.get("stockStatus") == "low-stock" for product in products
    )
    out_of_stock_count = sum(
        product.get("stockStatus") == "out-of-stock" for product in products
    )

    return {
        "orderCounts": {"all": len(orders), **status_counts},
        "inventory": {
            "productCount": len(products),
            "totalUnits": sum(product.get("availableStock", 0) for product in products),
            "lowStockCount": low_stock_count,
            "outOfStockCount": out_of_stock_count,
        },
        "customers": {"total": len(customers)},
        "financials": {
            "productRevenueMinor": product_revenue_minor,
            "costOfGoodsMinor": cost_of_goods_minor,
            "grossProfitMinor": gross_profit_minor,
            "averageOrderValueMinor": (
                total_order_value // len(active_orders) if active_orders else 0
            ),
        },
        "dailyOrders": [
            {"date": key, "count": daily_counts[key]} for key in day_keys
        ],
        "monthlyRevenue": [
            {"month": key, "revenueMinor": monthly_revenue[key]}
            for key in selected_months
        ],
        "topProducts": sorted(
            top_products.values(),
            key=lambda item: (item["quantity"], item["revenueMinor"]),
            reverse=True,
        )[:5],
        "workCentre": {
            "needsConfirmation": status_counts["needs-confirmation"],
            "needsPacking": status_counts["confirmed"],
            "lowStockProducts": low_stock_count,
            "outOfStockProducts": out_of_stock_count,
            "unreadNotifications": unread_notification_count,
        },
    }


def get_business_analytics(database, business_id):
    business_reference = database.collection("businesses").document(business_id)
    orders = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("orders")
        .order_by("createdAt", direction="DESCENDING")
        .limit(1000)
        .stream()
    ]
    products = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("products").limit(1000).stream()
    ]
    customers = [
        serialize_snapshot(snapshot)
        for snapshot in business_reference.collection("customers").limit(1000).stream()
    ]
    notifications = [
        snapshot.to_dict()
        for snapshot in business_reference.collection("notifications").limit(100).stream()
    ]
    return calculate_analytics(
        orders,
        products,
        customers,
        unread_notification_count=sum(
            not notification.get("isRead") for notification in notifications
        ),
    )
````

### `backend/app/services/search_service.py`

````python
from app.services.customer_service import list_customers
from app.services.order_service import list_orders
from app.services.product_service import list_products


def contains_query(values, query):
    return any(query in str(value or "").casefold() for value in values)


def search_records(orders, products, customers, query, limit_per_type=8):
    query_text = str(query or "").strip().casefold()

    if len(query_text) < 2:
        return {"orders": [], "products": [], "customers": []}

    order_results = []
    for order in orders:
        item_values = [
            value
            for item in order.get("items", [])
            for value in (item.get("name"), item.get("sku"), item.get("barcode"))
        ]
        if contains_query(
            [
                order.get("orderNumber"),
                order.get("waybillNumber"),
                order.get("customerSnapshot", {}).get("name"),
                order.get("customerSnapshot", {}).get("normalizedPhone"),
                *item_values,
            ],
            query_text,
        ):
            order_results.append(
                {
                    "id": order.get("id"),
                    "orderNumber": order.get("orderNumber", ""),
                    "customerName": order.get("customerSnapshot", {}).get("name", ""),
                    "status": order.get("fulfilmentStatus", ""),
                    "waybillNumber": order.get("waybillNumber", ""),
                },
            )

    product_results = []
    for product in products:
        variant_values = [
            value
            for variant in product.get("variantSummaries", [])
            for value in (variant.get("sku"), variant.get("barcode"), variant.get("size"))
        ]
        if contains_query(
            [
                product.get("name"),
                product.get("skuPrefix"),
                product.get("brand"),
                product.get("categoryName"),
                *variant_values,
            ],
            query_text,
        ):
            product_results.append(
                {
                    "id": product.get("id"),
                    "name": product.get("name", ""),
                    "sku": product.get("skuPrefix", ""),
                    "availableStock": product.get("availableStock", 0),
                    "status": product.get("stockStatus", ""),
                },
            )

    customer_results = []
    for customer in customers:
        if contains_query(
            [
                customer.get("name"),
                customer.get("normalizedPhone"),
                customer.get("email"),
            ],
            query_text,
        ):
            customer_results.append(
                {
                    "id": customer.get("id"),
                    "name": customer.get("name", ""),
                    "phone": customer.get("normalizedPhone", ""),
                    "riskLevel": customer.get("riskLevel", "low"),
                },
            )

    return {
        "orders": order_results[:limit_per_type],
        "products": product_results[:limit_per_type],
        "customers": customer_results[:limit_per_type],
    }


def global_search(database, business_id, query):
    return search_records(
        list_orders(database, business_id),
        list_products(database, business_id),
        list_customers(database, business_id),
        query,
    )
````

### `frontend/src/components/StatCard.css`

````css
/* Large statistic card container. */
.stat-card {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 82px;
  padding: 14px;
}

/* Decorative hover glow placed behind the card content. */
.stat-card::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border: 1px solid var(--color-border);
  border-radius: 8px;
background: var(--card-background);
box-shadow: var(--card-shadow);

  transform: scale(1);
  transition:
    transform 500ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 500ms ease,
    border-color 500ms ease;
}

html[data-theme="dark"] .stat-card:hover::before {
  border-color: rgba(41, 151, 255, 0.65);

  box-shadow:
    0 16px 34px rgba(0, 0, 0, 0.38),
    0 0 22px rgba(41, 151, 255, 0.08);
}

/* Card lift and icon scale interactions. */
.stat-card:hover {
  z-index: 10;
}

.stat-card:hover::before {
  transform: scale(1.1);
  transition:
    transform 500ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 500ms ease,
    border-color 500ms ease;
  border-color: #9cc7f5;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
}

.stat-card__icon {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  flex-shrink: 0;
  border-radius: 12px;
  transform: scale(1);
  transition: transform 500ms cubic-bezier(0.22, 1, 0.36, 1);
}

.stat-card:hover .stat-card__icon {
  transform: scale(1.2);
}

/* Respect users who prefer reduced animation. */
@media (prefers-reduced-motion: reduce) {
  .stat-card,
  .stat-card__icon {
    transition: none;
  }

  .stat-card:hover {
    transform: none;
  }
}

/* Statistic label and value typography. */
.stat-card__content {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.stat-card__label {
  color: var(--color-text);
  font-size: 14px;
  font-weight: 550;
}

.stat-card__value {
  color: var(--color-text-strong);
  font-size: 26px;
  font-weight: 700;
}

/* Tone classes give icons meaning through consistent status colours. */
.stat-card--blue .stat-card__icon {
  color: #1d75e8e0;
  background-color: #e8f1ff;
}

.stat-card--orange .stat-card__icon {
  color: #f59e0b;
  background-color: #fff4df;
}

.stat-card--green .stat-card__icon {
  color: #22a474;
  background-color: #e6f8f1;
}

.stat-card--purple .stat-card__icon {
  color: #8247e5;
  background-color: #f0eaff;
}

.stat-card--red .stat-card__icon {
  color: #ef4444;
  background-color: #feecec;
}

html[data-theme="dark"] .stat-card--blue .stat-card__icon,
/* Brighter icon treatments used against the dark theme. */
html[data-theme="dark"] .stat-card2--blue .stat-card2__icon {
  color: #469cff;
  background-color: rgba(41, 132, 255, 0.16);
}

html[data-theme="dark"] .stat-card--orange .stat-card__icon,
html[data-theme="dark"] .stat-card2--orange .stat-card2__icon {
  color: #ffad24;
  background-color: rgba(245, 158, 11, 0.15);
}

html[data-theme="dark"] .stat-card--green .stat-card__icon,
html[data-theme="dark"] .stat-card2--green .stat-card2__icon {
  color: #4bd99d;
  background-color: rgba(34, 164, 116, 0.16);
}

html[data-theme="dark"] .stat-card--purple .stat-card__icon,
html[data-theme="dark"] .stat-card2--purple .stat-card2__icon {
  color: #a77bff;
  background-color: rgba(130, 71, 229, 0.17);
}

html[data-theme="dark"] .stat-card--red .stat-card__icon,
html[data-theme="dark"] .stat-card2--red .stat-card2__icon {
  color: #ff6262;
  background-color: rgba(239, 68, 68, 0.16);
}
````

### `frontend/src/components/StatCard.jsx`

````jsx
// Styles for the larger dashboard statistic cards.
import "./StatCard.css";

// A reusable card receives its text, number, icon, and colour tone as props.
function StatCard({ label, value, icon: Icon, tone = "blue" }) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      {/* Render the icon component supplied through the icon prop. */}
      <div className="stat-card__icon">
        <Icon size={40} aria-hidden="true" />
      </div>

      {/* Display the statistic label and value. */}
      <div className="stat-card__content">
        <span className="stat-card__label">{label}</span>
        <strong className="stat-card__value">{value}</strong>
      </div>
    </article>
  );
}

export default StatCard;
````

### `frontend/src/components/StatCard2.css`

````css
/* Single-row grid used by the compact order statistic cards. */
.order-stats-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(135px, 1fr));
  gap: 10px;
  overflow-x: auto;
  padding: 6px 3px;
}

/* Compact statistic card container. */
.stat-card2 {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  min-height: 30px;
  padding: 6px;
  outline: none;
  cursor: pointer;
}



/* Hover glow and lift animation. */
.stat-card2::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  border: 2px solid var(--color-border);
  border-radius: 15px;
background: var(--card-background);
box-shadow: var(--card-shadow);

  transform: scale(1);
  transition:
    transform 500ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 500ms ease,
    border-color 500ms ease;
}

.stat-card2:hover {
  z-index: 10;
}
.stat-card2--active::before {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--color-primary) 18%, transparent);
}

.stat-card2:focus-visible::before {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-primary) 25%, transparent);
}

html[data-theme="dark"] .stat-card2:hover::before {
  border-color: rgba(41, 151, 255, 0.65);

  box-shadow:
    0 10px 24px rgba(0, 0, 0, 0.36),
    0 0 18px rgba(41, 151, 255, 0.08);
}

.stat-card2:hover::before {
  transform: scale(1.04);
  transition:
    transform 500ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 500ms ease,
    border-color 500ms ease;
  border-color: #9cc7f5;
  box-shadow: 0 2px 3px rgba(15, 23, 42, 0.18);
}

/* Icon tile and its hover scale. */
.stat-card2__icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 12px;
  transform: scale(1);
  transition: transform 500ms cubic-bezier(0.22, 1, 0.36, 1);
}

.stat-card2:hover .stat-card2__icon {
  transform: scale(1.1);
}

/* Disable card motion when requested by the operating system. */
@media (prefers-reduced-motion: reduce) {
  .stat-card2,
  .stat-card2__icon {
    transition: none;
  }

  .stat-card2:hover {
    transform: none;
  }
}

/* Compact card label and value layout. */
.stat-card2__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.stat-card2__label {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 550;
  white-space: nowrap;
}

.stat-card2__value {
  color: var(--color-text-strong);
  font-size: 16px;
  font-weight: 700;
  margin-right: 2px;
}

/* Status tone classes. */
.stat-card2--blue {
  color: #1d75e8e0;
}

.stat-card2--orange {
  color: #f59e0b;
}

.stat-card2--green {
  color: #22a474;
}

.stat-card2--purple {
  color: #8247e5;
}

.stat-card2--red {
  color: #ef4444;
}

html[data-theme="dark"] .stat-card--blue .stat-card__icon,
/* Dark-theme icon colours and backgrounds. */
html[data-theme="dark"] .stat-card2--blue .stat-card2__icon {
  color: #469cff;
  background-color: rgba(41, 132, 255, 0.16);
}

html[data-theme="dark"] .stat-card--orange .stat-card__icon,
html[data-theme="dark"] .stat-card2--orange .stat-card2__icon {
  color: #ffad24;
  background-color: rgba(245, 158, 11, 0.15);
}

html[data-theme="dark"] .stat-card--green .stat-card__icon,
html[data-theme="dark"] .stat-card2--green .stat-card2__icon {
  color: #4bd99d;
  background-color: rgba(34, 164, 116, 0.16);
}

html[data-theme="dark"] .stat-card--purple .stat-card__icon,
html[data-theme="dark"] .stat-card2--purple .stat-card2__icon {
  color: #a77bff;
  background-color: rgba(130, 71, 229, 0.17);
}

html[data-theme="dark"] .stat-card--red .stat-card__icon,
html[data-theme="dark"] .stat-card2--red .stat-card2__icon {
  color: #ff6262;
  background-color: rgba(239, 68, 68, 0.16);
}
````

### `frontend/src/components/StatCard2.jsx`

````jsx
// Styles for the compact statistic cards used on the Orders page.
import "./StatCard2.css";

// This compact card uses props so the same layout can show many statistics.
function StatCard2({ label, value, icon: Icon, tone = "blue", onClick, isActive = false }) {
  return (
    <article className={`stat-card2 stat-card2--${tone} ${isActive ? "stat-card2--active" : ""}`} onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined} onKeyDown={(event) => { if (onClick && (event.key === "Enter" || event.key === " ")) onClick(); }}>
      {/* Icon supplied by the parent page. */}
      <div className="stat-card2__icon">
        <Icon size={28} aria-hidden="true" />
      </div>

{/* Statistic label and value. */}
<div className="stat-card2__content">
  <span className="stat-card2__label">{label}</span>
  <strong className="stat-card2__value">{value}</strong>
</div>
    </article>
  );
}

export default StatCard2;
````

### `frontend/src/pages/AnalyticsPage.css`

````css
.analytics-page {
  display: grid;
  gap: 20px;
}

.analytics-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.analytics-summary article {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 3px 12px;
  min-height: 92px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
  box-shadow: 0 8px 22px rgba(14, 49, 82, 0.06);
}

.analytics-summary svg {
  grid-row: span 2;
  width: 42px;
  height: 42px;
  padding: 9px;
  border-radius: 11px;
  color: var(--color-accent);
  background: rgba(22, 140, 245, 0.1);
}

.analytics-summary span,
.analytics-panel > p,
.analytics-page__footnote {
  color: var(--color-muted);
}

.analytics-summary strong {
  font-size: 22px;
}

.analytics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.analytics-panel {
  min-height: 310px;
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-surface);
}

.analytics-panel h3,
.analytics-panel > p {
  margin: 0;
}

.analytics-panel > p {
  margin-top: 4px;
  font-size: 12px;
}

.analytics-bars {
  display: flex;
  align-items: end;
  gap: 13px;
  height: 220px;
  padding-top: 35px;
}

.analytics-bars > div {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  flex-direction: column;
  justify-content: end;
  height: 100%;
}

.analytics-bars i {
  width: min(42px, 75%);
  min-height: 5px;
  border-radius: 7px 7px 2px 2px;
  background: linear-gradient(180deg, #2e9cff, #0874e7);
}

.analytics-bars--daily i {
  background: linear-gradient(180deg, #16b981, #078b68);
}

.analytics-bars small {
  margin-top: 8px;
  color: var(--color-muted);
  font-size: 10px;
}

.analytics-bars__value {
  margin-bottom: 5px;
  font-size: 9px;
  font-weight: 700;
}

.analytics-products,
.analytics-work {
  display: grid;
  gap: 8px;
  margin-top: 18px;
}

.analytics-products > div,
.analytics-work > div {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 9px;
  background: var(--color-surface-soft);
}

.analytics-products b {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: var(--color-accent);
  background: rgba(22, 140, 245, 0.12);
}

.analytics-products span {
  display: grid;
  flex: 1;
}

.analytics-products small {
  color: var(--color-muted);
}

.analytics-products em {
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.analytics-work > div {
  justify-content: space-between;
}

.analytics-work strong {
  color: var(--color-accent);
  font-size: 19px;
}

.analytics-page__footnote {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.overview-work {
  margin-top: 26px;
}

.overview-work__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.overview-work__grid span {
  padding: 13px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  color: var(--color-text);
  background: var(--color-surface);
  font-size: 12px;
}

@media (max-width: 1000px) {
  .analytics-summary,
  .overview-work__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .analytics-summary,
  .analytics-grid,
  .overview-work__grid {
    grid-template-columns: 1fr;
  }
}
````

### `frontend/src/pages/AnalyticsPage.jsx`

````jsx
import {
  Banknote,
  Boxes,
  PackageCheck,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../context/authContextValue";
import {
  formatAnalyticsMoney,
  getAnalyticsOverview,
} from "../services/analyticsService";
import "./AnalyticsPage.css";


function AnalyticsPage() {
  const { business } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!business?.id) return undefined;

    getAnalyticsOverview(business.id)
      .then((data) => {
        if (requestIsCurrent) setAnalytics(data);
      })
      .catch((requestError) => {
        if (requestIsCurrent) setError(requestError);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id]);

  const maximumDailyOrders = useMemo(
    () => Math.max(...(analytics?.dailyOrders ?? []).map((item) => item.count), 1),
    [analytics],
  );
  const visibleMonths = analytics?.monthlyRevenue?.slice(-6) ?? [];
  const maximumMonthlyRevenue = Math.max(
    ...visibleMonths.map((item) => item.revenueMinor),
    1,
  );

  if (error) {
    return (
      <main className="dashboard analytics-page">
        <div className="dashboard__intro">
          <h2>Business Analytics</h2>
          <p role="alert">Analytics could not be loaded from the Vendly API.</p>
        </div>
      </main>
    );
  }

  const financials = analytics?.financials ?? {};

  return (
    <main className="dashboard analytics-page">
      <div className="dashboard__intro">
        <h2>Business Analytics</h2>
        <p>Revenue, gross profit, orders and product performance from Firestore.</p>
      </div>

      <section className="analytics-summary" aria-label="Business totals">
        <article><Banknote /><span>Product revenue</span><strong>{formatAnalyticsMoney(financials.productRevenueMinor)}</strong></article>
        <article><PackageCheck /><span>Total orders</span><strong>{analytics?.orderCounts?.all ?? 0}</strong></article>
        <article><Boxes /><span>Stock units</span><strong>{analytics?.inventory?.totalUnits ?? 0}</strong></article>
        <article><TrendingUp /><span>Gross profit</span><strong>{formatAnalyticsMoney(financials.grossProfitMinor)}</strong></article>
      </section>

      <section className="analytics-grid">
        <article className="analytics-panel">
          <h3>Daily orders</h3>
          <p>Orders created during the last seven days</p>
          <div className="analytics-bars analytics-bars--daily">
            {(analytics?.dailyOrders ?? []).map((item) => (
              <div key={item.date}>
                <span className="analytics-bars__value">{item.count}</span>
                <i style={{ height: `${Math.max((item.count / maximumDailyOrders) * 100, 4)}%` }} />
                <small>{new Date(`${item.date}T00:00:00`).toLocaleDateString("en-LK", { weekday: "short" })}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="analytics-panel">
          <h3>Monthly product revenue</h3>
          <p>Delivered product sales, excluding delivery fees</p>
          <div className="analytics-bars">
            {visibleMonths.map((item) => (
              <div key={item.month}>
                <span className="analytics-bars__value">{formatAnalyticsMoney(item.revenueMinor).replace("LKR ", "")}</span>
                <i style={{ height: `${Math.max((item.revenueMinor / maximumMonthlyRevenue) * 100, 4)}%` }} />
                <small>{item.month}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="analytics-panel">
          <h3>Top-selling products</h3>
          <p>Ranked by delivered units</p>
          <div className="analytics-products">
            {(analytics?.topProducts ?? []).length === 0 ? (
              <span>No delivered product sales yet.</span>
            ) : (
              analytics.topProducts.map((product, index) => (
                <div key={product.id}>
                  <b>{index + 1}</b>
                  <span><strong>{product.name}</strong><small>{product.quantity} units</small></span>
                  <em>{formatAnalyticsMoney(product.revenueMinor)}</em>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="analytics-panel">
          <h3>Daily work centre</h3>
          <p>Actions that currently need attention</p>
          <div className="analytics-work">
            <div><span>Needs confirmation</span><strong>{analytics?.workCentre?.needsConfirmation ?? 0}</strong></div>
            <div><span>Ready to pack</span><strong>{analytics?.workCentre?.needsPacking ?? 0}</strong></div>
            <div><span>Low stock</span><strong>{analytics?.workCentre?.lowStockProducts ?? 0}</strong></div>
            <div><span>Out of stock</span><strong>{analytics?.workCentre?.outOfStockProducts ?? 0}</strong></div>
          </div>
        </article>
      </section>

      <p className="analytics-page__footnote">
        Gross profit is product revenue minus recorded product cost. It does not yet subtract salaries, rent, advertising, tax or other business expenses.
      </p>
    </main>
  );
}

export default AnalyticsPage;
````

### `frontend/src/pages/OverviewPage.jsx`

````jsx
// Icons used by the order summary cards.
import {
  CircleCheck,
  Clock3,
  Package,
  Truck,
  Undo2,
  SquareCheckBig,
  Package2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import "./OrdersPage.css";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/authContextValue";
import { getAnalyticsOverview } from "../services/analyticsService";


function OverviewPage() {
  const { sellerProfile, business } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";
  const [analytics, setAnalytics] = useState(null);
  const [analyticsError, setAnalyticsError] = useState(null);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!business?.id) return undefined;

    getAnalyticsOverview(business.id)
      .then((data) => {
        if (requestIsCurrent) setAnalytics(data);
      })
      .catch((error) => {
        if (requestIsCurrent) setAnalyticsError(error);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id]);

  const orderStats = useMemo(() => {
    const counts = analytics?.orderCounts ?? {};
    return [
      { label: "All", value: counts.all ?? 0, icon: Package, tone: "blue" },
      {
        label: "Pending",
        value: counts["needs-confirmation"] ?? 0,
        icon: Clock3,
        tone: "orange",
      },
      {
        label: "Confirmed",
        value: counts.confirmed ?? 0,
        icon: SquareCheckBig,
        tone: "green",
      },
      { label: "Packed", value: counts.packed ?? 0, icon: Package2, tone: "blue" },
      { label: "Shipped", value: counts.shipped ?? 0, icon: Truck, tone: "purple" },
      {
        label: "Delivered",
        value: counts.delivered ?? 0,
        icon: CircleCheck,
        tone: "green",
      },
      { label: "Returned", value: counts.returned ?? 0, icon: Undo2, tone: "red" },
    ];
  }, [analytics]);

  return (
    <main className="dashboard">
      {/* Store greeting and short page explanation. */}
      <div className="dashboard__intro">
        <h2>Hi! {businessName}</h2>
        <p>Here is your business summary.</p>
      </div>

      {analyticsError && (
        <p className="orders-page__notice orders-page__notice--error" role="alert">
          The current business summary could not be loaded.
        </p>
      )}

      {/* Overview cards created by mapping over orderStats. */}
      <section aria-labelledby="order-dashboard-title">
        <h2 id="order-dashboard-title">Order Dashboard</h2>

        <div className="stats-grid">
          {orderStats.map((stat) => (
            <StatCard
              key={stat.label}
              label={stat.label}
              value={stat.value}
              icon={stat.icon}
              tone={stat.tone}
            />
          ))}
        </div>
      </section>

      {analytics?.workCentre && (
        <section className="overview-work" aria-labelledby="work-centre-title">
          <h2 id="work-centre-title">Today&apos;s work centre</h2>
          <div className="overview-work__grid">
            <span>{analytics.workCentre.needsConfirmation} orders need confirmation</span>
            <span>{analytics.workCentre.needsPacking} orders are ready to pack</span>
            <span>{analytics.workCentre.lowStockProducts} products are low in stock</span>
            <span>{analytics.workCentre.unreadNotifications} unread notifications</span>
          </div>
        </section>
      )}
    </main>
  );
}

export default OverviewPage;
````

### `frontend/src/services/analyticsService.js`

````javascript
import { apiRequest } from "./apiClient";


export async function getAnalyticsOverview(businessId) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/overview`,
  );
  return response.analytics;
}


export function formatAnalyticsMoney(minorUnits = 0) {
  return `LKR ${(minorUnits / 100).toLocaleString("en-LK", {
    maximumFractionDigits: 0,
  })}`;
}
````

### `frontend/src/services/searchService.js`

````javascript
import { apiRequest } from "./apiClient";


export async function searchBusiness(businessId, query, signal) {
  const response = await apiRequest(
    `/businesses/${businessId}/search?q=${encodeURIComponent(query)}`,
    { signal },
  );
  return response.results;
}
````

## Feature 22 source — Automated tests

Files in this feature: 17

### `backend/tests/test_ai_prompt.py`

````python
from app.services.ai_service import product_prompt


def test_product_prompt_contains_guardrails_and_seller_facts():
    prompt = product_prompt(
        "Is it waterproof?",
        {
            "name": "Watch",
            "description": "IP67 water resistance",
            "sellingPriceMinor": 200000,
            "variants": [],
        },
    )

    assert "IP67 water resistance" in prompt
    assert "Never invent features" in prompt
    assert "Is it waterproof?" in prompt
````

### `backend/tests/test_analytics.py`

````python
from datetime import datetime, timezone

from app.services.analytics_service import calculate_analytics, recent_months


def test_analytics_uses_only_delivered_orders_for_revenue_and_profit():
    now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
    analytics = calculate_analytics(
        [
            {
                "fulfilmentStatus": "delivered",
                "createdAt": now,
                "subtotalMinor": 200000,
                "discountTotalMinor": 10000,
                "totalAmountMinor": 235000,
                "items": [
                    {
                        "productId": "p1",
                        "name": "Watch",
                        "quantity": 2,
                        "unitCostMinor": 50000,
                        "lineTotalMinor": 200000,
                    },
                ],
            },
            {
                "fulfilmentStatus": "returned",
                "createdAt": now,
                "subtotalMinor": 500000,
                "totalAmountMinor": 545000,
                "items": [],
            },
        ],
        [],
        now=now,
    )

    assert analytics["financials"]["productRevenueMinor"] == 190000
    assert analytics["financials"]["costOfGoodsMinor"] == 100000
    assert analytics["financials"]["grossProfitMinor"] == 90000
    assert analytics["orderCounts"]["returned"] == 1
    assert analytics["topProducts"][0]["quantity"] == 2


def test_recent_months_crosses_year_boundary():
    months = recent_months(datetime(2026, 2, 1, tzinfo=timezone.utc), count=4)
    assert months == ["2025-11", "2025-12", "2026-01", "2026-02"]
````

### `backend/tests/test_auth.py`

````python
from unittest.mock import patch

from app import create_app


def test_me_requires_a_bearer_token():
    app = create_app({"TESTING": True})
    response = app.test_client().get("/api/v1/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "authentication_required"


@patch("app.core.auth.firebase_auth.verify_id_token")
def test_password_account_must_verify_email(verify_id_token):
    verify_id_token.return_value = {
        "uid": "seller-1",
        "email_verified": False,
        "firebase": {"sign_in_provider": "password"},
    }
    app = create_app({"TESTING": True})
    response = app.test_client().get(
        "/api/v1/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "email_not_verified"
````

### `backend/tests/test_customer_validation.py`

````python
import pytest

from app.services.customer_service import (
    normalize_sri_lankan_phone,
    validate_address,
)


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        ("077 123 4567", "94771234567"),
        ("+94 77 123 4567", "94771234567"),
        ("771234567", "94771234567"),
    ],
)
def test_phone_numbers_are_normalized(provided, expected):
    assert normalize_sri_lankan_phone(provided) == expected


def test_invalid_phone_is_rejected():
    with pytest.raises(ValueError, match="valid Sri Lankan"):
        normalize_sri_lankan_phone("12345")


def test_address_requires_district_and_city():
    with pytest.raises(ValueError, match="City is required"):
        validate_address({"line1": "45 Park Road", "district": "Colombo"})
````

### `backend/tests/test_delivery.py`

````python
from app.services.courier_service import (
    calculate_delivery_fee,
    courier_recommendation_score,
)


def sample_courier():
    return {
        "firstKgPriceMinor": 45000,
        "extraKgPriceMinor": 10000,
        "districtSurchargesMinor": {"jaffna": 5000},
        "successRate": 0.9,
        "returnRate": 0.05,
        "districtIssueCounts": {},
    }


def test_first_kilogram_uses_base_price():
    assert calculate_delivery_fee(sample_courier(), 800, "Colombo") == 45000


def test_partial_extra_kilogram_rounds_up():
    assert calculate_delivery_fee(sample_courier(), 1100, "Colombo") == 55000


def test_district_surcharge_is_added():
    assert calculate_delivery_fee(sample_courier(), 1000, "Jaffna") == 50000


def test_more_branch_issues_reduce_recommendation_score():
    courier = sample_courier()
    normal_score = courier_recommendation_score(courier, 45000, "Kandy")
    courier["districtIssueCounts"] = {"kandy": 3}
    issue_score = courier_recommendation_score(courier, 45000, "Kandy")

    assert issue_score < normal_score
````

### `backend/tests/test_health.py`

````python
from app import create_app


def test_health_endpoint():
    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "service": "vendly-api",
    }
````

### `backend/tests/test_media.py`

````python
from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.core.errors import ApiError
from app.services.media_service import firebase_download_url, validate_media


def test_image_media_is_accepted():
    upload = FileStorage(
        stream=BytesIO(b"small-image"),
        filename="shoe.webp",
        content_type="image/webp",
    )

    media_type, size = validate_media(upload)

    assert media_type == "image"
    assert size == 11


def test_unsupported_media_is_rejected():
    upload = FileStorage(
        stream=BytesIO(b"document"),
        filename="product.pdf",
        content_type="application/pdf",
    )

    with pytest.raises(ApiError) as error:
        validate_media(upload)

    assert error.value.code == "unsupported_media_type"


def test_download_url_encodes_storage_path():
    url = firebase_download_url("bucket", "businesses/one/image 1.png", "token")

    assert "businesses%2Fone%2Fimage%201.png" in url
````

### `backend/tests/test_members.py`

````python
import pytest

from app.core.errors import ApiError
from app.services.member_service import ROLE_PERMISSIONS, validate_member_payload
from app.core.authorization import membership_has_permission


def test_staff_role_maps_to_explicit_permissions():
    member = validate_member_payload(
        {"email": "staff@example.com", "role": "inventory_manager"},
    )
    assert member["permissions"] == ROLE_PERMISSIONS["inventory_manager"]
    assert "inventory:*" in member["permissions"]


def test_owner_cannot_be_assigned_through_staff_endpoint():
    with pytest.raises(ApiError):
        validate_member_payload(
            {"email": "staff@example.com", "role": "owner"},
        )


def test_role_wildcard_grants_resource_permission():
    membership = {"role": "order_manager", "permissions": ["orders:*"]}
    assert membership_has_permission(membership, "orders:read")
    assert membership_has_permission(membership, "orders:manage")
    assert not membership_has_permission(membership, "inventory:manage")


def test_owner_always_has_permission():
    assert membership_has_permission({"role": "owner", "permissions": ["*"]}, "staff:manage")
````

### `backend/tests/test_numbers.py`

````python
import pytest

from app.services.numbers import (
    kilograms_to_grams,
    integer_value,
    money_to_minor_units,
    non_negative_integer,
)


def test_money_is_stored_as_integer_minor_units():
    assert money_to_minor_units("1899.50", "Price") == 189950


def test_weight_is_stored_as_integer_grams():
    assert kilograms_to_grams("0.45") == 450


def test_stock_rejects_fractional_values():
    with pytest.raises(ValueError, match="whole number"):
        non_negative_integer("2.5", "Stock")


def test_stock_adjustment_allows_negative_whole_numbers():
    assert integer_value("-3", "Quantity change") == -3
````

### `backend/tests/test_operations.py`

````python
import pytest
from openpyxl import load_workbook

from app.core.errors import ApiError
from app.services.operations_service import (
    build_orders_workbook,
    validate_report_payload,
)


def test_report_payload_rejects_unknown_type():
    with pytest.raises(ApiError) as error:
        validate_report_payload(
            {"type": "unknown"},
            {"delayed", "lost"},
            "Courier issue type",
        )

    assert error.value.status_code == 422


def test_order_export_creates_real_excel_workbook():
    stream = build_orders_workbook(
        [
            {
                "orderNumber": "VD-000001",
                "customerSnapshot": {
                    "name": "Kamal",
                    "normalizedPhone": "94771234567",
                },
                "deliveryAddress": {"line1": "10 Main Road", "district": "Colombo"},
                "items": [{"name": "Watch", "size": "", "quantity": 1}],
                "itemCount": 1,
                "subtotalMinor": 200000,
                "deliveryFeeMinor": 45000,
                "totalAmountMinor": 245000,
                "courierSnapshot": {"name": "Courier One"},
                "fulfilmentStatus": "confirmed",
            },
        ],
    )
    workbook = load_workbook(stream)
    sheet = workbook["Orders"]

    assert sheet["A2"].value == "VD-000001"
    assert sheet["C2"].value == "Kamal"
    assert sheet["K2"].value == 2450
````

### `backend/tests/test_order_status.py`

````python
from app.services.order_service import STATUS_TRANSITIONS, returned_customer_risk


def test_order_status_follows_fulfilment_sequence():
    assert "confirmed" in STATUS_TRANSITIONS["needs-confirmation"]
    assert "packed" in STATUS_TRANSITIONS["confirmed"]
    assert "shipped" in STATUS_TRANSITIONS["packed"]
    assert "delivered" in STATUS_TRANSITIONS["shipped"]


def test_completed_order_cannot_move_backwards():
    assert STATUS_TRANSITIONS["delivered"] == set()


def test_returned_customer_risk_increases_after_three_returns():
    assert returned_customer_risk(1) == ("medium", "returned-order")
    assert returned_customer_risk(2) == ("medium", "returned-order")
    assert returned_customer_risk(3) == ("high", "high-return-rate")
````

### `backend/tests/test_order_validation.py`

````python
import pytest

from app.core.errors import ApiError
from app.services.order_service import filter_orders, validate_order_request


def valid_order_payload():
    return {
        "customerId": "customer-1",
        "items": [
            {"variantId": "variant-1", "quantity": 1},
            {"variantId": "variant-1", "quantity": 2},
        ],
        "paymentMethod": "cod",
        "source": "dashboard",
    }


def test_duplicate_item_rows_are_combined():
    order = validate_order_request(valid_order_payload())
    assert order["items"] == [{"variantId": "variant-1", "quantity": 3}]


def test_order_quantity_must_be_positive():
    payload = valid_order_payload()
    payload["items"][0]["quantity"] = 0

    with pytest.raises(ApiError, match="greater than zero"):
        validate_order_request(payload)


def test_invalid_order_source_is_rejected():
    payload = valid_order_payload()
    payload["source"] = "unknown"

    with pytest.raises(ApiError, match="valid order source"):
        validate_order_request(payload)


def test_order_filters_apply_date_courier_and_waybill_search():
    orders = [
        {
            "id": "one",
            "createdAt": "2026-08-17T10:00:00+00:00",
            "courierId": "courier-one",
            "waybillNumber": "VWB-123",
            "fulfilmentStatus": "confirmed",
            "customerSnapshot": {},
            "items": [],
        },
        {
            "id": "two",
            "createdAt": "2026-08-10T10:00:00+00:00",
            "courierId": "courier-two",
            "fulfilmentStatus": "confirmed",
            "customerSnapshot": {},
            "items": [],
        },
    ]

    assert filter_orders(
        orders,
        date_from="2026-08-15",
        courier_id="courier-one",
        search="vwb-123",
    ) == [orders[0]]
````

### `backend/tests/test_product_validation.py`

````python
import pytest

from app.core.errors import ApiError
from app.services.product_service import validate_product


def valid_product_payload():
    return {
        "name": "Daisy Running Shoes - Pink",
        "colourName": "Pink",
        "categoryId": "footwear",
        "costPrice": 1200,
        "sellingPrice": 1899,
        "weightKg": 0.45,
        "lowStockThreshold": 2,
        "hasSizes": True,
        "variants": [
            {
                "size": "36",
                "sku": "DFS-PNK-36",
                "barcode": "890123456001",
                "stock": 5,
            },
            {
                "size": "37",
                "sku": "DFS-PNK-37",
                "barcode": "890123456002",
                "stock": 1,
            },
        ],
    }


def test_product_validation_normalizes_prices_and_skus():
    product = validate_product(valid_product_payload())

    assert product["sellingPriceMinor"] == 189900
    assert product["weightGrams"] == 450
    assert product["variants"][0]["sku"] == "DFS-PNK-36"


def test_product_validation_rejects_duplicate_sizes():
    payload = valid_product_payload()
    payload["variants"][1]["size"] = "36"

    with pytest.raises(ApiError) as error:
        validate_product(payload)

    assert error.value.code == "duplicate_size"


def test_product_without_sizes_requires_one_stock_row():
    payload = valid_product_payload()
    payload["hasSizes"] = False

    with pytest.raises(ApiError) as error:
        validate_product(payload)

    assert error.value.code == "validation_error"
````

### `backend/tests/test_public_catalog.py`

````python
from app.services.public_catalog_service import public_product
from app.services.public_chat_service import (
    find_category_request,
    find_product_in_message,
    is_catalog_number_choice,
    normalize_chat_cart,
    parse_delivery_address,
    public_order_confirmation,
    summarize_chat_cart,
    token_hash,
)


def test_public_product_hides_cost_and_supplier_fields():
    product = public_product(
        {
            "id": "product-1",
            "name": "Watch",
            "costPriceMinor": 10000,
            "sellingPriceMinor": 20000,
            "supplierId": "private-supplier",
            "variantSummaries": [],
        },
    )

    assert product["sellingPriceMinor"] == 20000
    assert "costPriceMinor" not in product
    assert "supplierId" not in product


def test_chat_session_token_is_stored_as_a_hash():
    assert token_hash("secret-token") != "secret-token"
    assert token_hash("secret-token") == token_hash("secret-token")


def test_public_order_confirmation_hides_internal_costs_and_notes():
    confirmation = public_order_confirmation(
        {
            "id": "order-1",
            "orderNumber": "VD-000001",
            "items": [
                {
                    "productId": "product-1",
                    "variantId": "variant-1",
                    "name": "Watch",
                    "quantity": 1,
                    "unitPriceMinor": 20000,
                    "unitCostMinor": 10000,
                    "lineTotalMinor": 20000,
                },
            ],
            "subtotalMinor": 20000,
            "deliveryFeeMinor": 45000,
            "totalAmountMinor": 65000,
            "privateNote": "Seller-only information",
            "createdBy": "private-user-id",
        },
    )

    assert confirmation["orderNumber"] == "VD-000001"
    assert confirmation["totalAmountMinor"] == 65000
    assert "unitCostMinor" not in confirmation["items"][0]
    assert "privateNote" not in confirmation
    assert "createdBy" not in confirmation


def test_chat_product_selection_accepts_catalogue_number_and_partial_name():
    products = [
        {"id": "watch", "name": "T800 Ultra Smart Watch", "shortCode": "P8x43K"},
        {"id": "earbuds", "name": "Wireless Earbuds", "shortCode": "A2b9Lm"},
    ]

    assert find_product_in_message("2", products)["id"] == "earbuds"
    assert find_product_in_message("Tell me about the smart watch", products)["id"] == "watch"
    assert find_product_in_message("P8x43K", products)["id"] == "watch"


def test_chat_product_selection_does_not_guess_when_names_are_ambiguous():
    products = [
        {"id": "pink", "name": "Daisy Running Shoes Pink"},
        {"id": "black", "name": "Daisy Running Shoes Black"},
    ]

    assert find_product_in_message("Tell me about Daisy shoes", products) is None


def test_catalog_number_choice_only_matches_a_direct_selection():
    assert is_catalog_number_choice("2") is True
    assert is_catalog_number_choice("Product #2") is True
    assert is_catalog_number_choice("Does product 2 have Bluetooth?") is False


def test_chat_category_request_finds_all_matching_products():
    products = [
        {"id": "watch-1", "name": "Alpha Watch", "categoryName": "Smartwatches"},
        {"id": "watch-2", "name": "Beta Watch", "categoryName": "Smartwatches"},
        {"id": "buds", "name": "Earbuds", "categoryName": "Audio"},
    ]

    assert find_category_request("show all smartwatches", products) == "Smartwatches"
    assert find_category_request("smartwatch", products) == "Smartwatches"


def test_chat_cart_is_normalized_and_summarized_for_confirmation():
    cart = normalize_chat_cart(
        [
            {"variantId": "black-42", "quantity": 1},
            {"variantId": "black-42", "quantity": 2},
        ],
    )
    products = [
        {
            "id": "shoe",
            "name": "Running Shoe",
            "sellingPriceMinor": 189900,
            "media": [{"url": "https://example.test/shoe.jpg"}],
            "variants": [
                {"id": "black-42", "size": "42", "sku": "SHOE-BLK-42"},
            ],
        },
    ]

    assert cart == [{"variantId": "black-42", "quantity": 3}]
    assert summarize_chat_cart(cart, products)[0]["lineTotalMinor"] == 569700


def test_chat_delivery_address_requires_street_city_and_district():
    address = parse_delivery_address("No. 45 Park Road, Dehiwala, Colombo")

    assert address["line1"] == "No. 45 Park Road"
    assert address["city"] == "Dehiwala"
    assert address["district"] == "Colombo"
````

### `backend/tests/test_reviews.py`

````python
import pytest

from app.core.errors import ApiError
from app.services.review_service import validate_review_payload


def test_review_requires_rating_between_one_and_five():
    with pytest.raises(ApiError):
        validate_review_payload(
            {
                "orderNumber": "VD-000001",
                "phoneNumber": "0771234567",
                "rating": 6,
                "reviewText": "Good",
            },
        )


def test_review_normalizes_phone_and_order_number():
    review = validate_review_payload(
        {
            "orderNumber": "vd-000001",
            "phoneNumber": "077 123 4567",
            "rating": 5,
            "reviewText": "Excellent product.",
        },
    )

    assert review["orderNumber"] == "VD-000001"
    assert review["normalizedPhone"] == "94771234567"
````

### `backend/tests/test_search.py`

````python
from app.services.search_service import search_records


def test_global_search_finds_sku_barcode_waybill_and_phone():
    results = search_records(
        [
            {
                "id": "o1",
                "orderNumber": "VD-000001",
                "waybillNumber": "VWB-1234",
                "customerSnapshot": {"name": "Kamal", "normalizedPhone": "94771234567"},
                "items": [],
            },
        ],
        [
            {
                "id": "p1",
                "name": "Smart Watch",
                "variantSummaries": [{"sku": "WATCH-BLK", "barcode": "890123"}],
            },
        ],
        [{"id": "c1", "name": "Kamal", "normalizedPhone": "94771234567"}],
        "890123",
    )
    assert results["products"][0]["id"] == "p1"

    results = search_records([], [], [{"id": "c1", "name": "Kamal"}], "kam")
    assert results["customers"][0]["name"] == "Kamal"


def test_global_search_waits_for_two_characters():
    assert search_records([], [], [], "a") == {
        "orders": [],
        "products": [],
        "customers": [],
    }
````

### `backend/tests/test_text.py`

````python
import pytest

from app.services.text import optional_text, required_text, slugify


def test_required_text_trims_value():
    assert required_text("  Smart Watches  ", "Name") == "Smart Watches"


def test_required_text_rejects_blank_value():
    with pytest.raises(ValueError, match="Name is required"):
        required_text("   ", "Name")


def test_optional_text_allows_blank_value():
    assert optional_text(None) == ""


def test_slugify_creates_url_safe_slug():
    assert slugify("Smart Watches & Wearables") == "smart-watches-wearables"
````

# Latest update: automatic customer authentication

Storefront routes now render `CustomerAuthGate`. It automatically opens a customer login page on first load, supports email registration/login, Google login, and Firebase anonymous guest login, then renders the catalogue only after authentication. The gate does not create a chat session while Firebase is still checking the user. Once authenticated, `StorefrontPage` loads the signed-in customer's previous chat messages through the protected customer-chat endpoint. Enable the Anonymous provider in Firebase Console for the guest button.

## Current project implementation map

The setup references are split into three smaller documents:

- `FIREBASE_DATABASE_GUIDE.md` — Firebase project, Auth, Firestore structure, rules and indexes.
- `BACKEND_API_FROM_SCRATCH.md` — Flask setup, token verification, endpoints, checkout and testing.
- `PROGRAMMING_LEARNING_PATH.md` — JavaScript, React, Python, Flask and Firestore concepts in learning order.

For every feature: define its Firestore document, add a protected Flask endpoint, test validation and permissions, connect one React component, then add loading and error states. Trusted totals, stock deductions and role checks must never exist only in the browser.

## Chatbot contact collection (latest)

When a customer checks out through the chatbot, collect these values in order:

1. Full name.
2. Primary Sri Lankan phone number.
3. Optional second phone number. Accept `skip`, `no`, or `none` when the customer has only one number.
4. Street address.
5. District.
6. Nearest city.
7. Optional delivery note. Accept `skip` when there is no note.
8. Show the complete order summary and wait for `confirm order`.

The chatbot state machine uses `collecting-secondary-phone`, `collecting-address`, `collecting-district`, `collecting-nearest-city`, and `collecting-delivery-note`. Invalid phone numbers and empty location fields keep the customer in the same state and display a correction message. The final customer object contains `phoneNumber`, `secondaryPhoneNumber`, and an address with `line1`, `city`, and `district`; `deliveryNote` is saved with the order.
