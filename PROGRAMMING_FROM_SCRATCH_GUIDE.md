# Vendly.lk — Programming From Scratch

This handbook explains how to rebuild the current Vendly system from an empty
folder. It is written for a beginner, but it follows the same production-shaped
architecture used by the current project.

> Important: never put a Firebase Admin service-account key, Cloudinary secret,
> or AI API key in React, in a `VITE_*` variable, or in GitHub.

## 1. What we are building

Vendly is a multi-seller commerce-management system for Sri Lankan businesses.
It contains:

- a seller registration and login system;
- a seller dashboard;
- categories and product inventory;
- optional product size variants;
- SKU, barcode, stock and media management;
- customers and fraud-risk information;
- multi-product orders;
- courier prices, recommendations and waybill ranges;
- automatic totals, delivery fees, order numbers and waybill numbers;
- a public seller storefront and seller-specific chatbot;
- customer email, Google and anonymous guest storefront login;
- customer-owned chat history, order history and delivery tracking;
- reviews, notifications, Excel exports and analytics.

## 2. Architecture

Vendly uses three tiers:

```text
React browser application
        |
        | HTTPS + JSON + Firebase ID token
        v
Flask REST API
        |
        +------ Firebase Admin ------> Cloud Firestore
        |
        +------ Cloudinary ----------> Product images/videos
        |
        +------ Optional AI API -----> Product text/chat answers
```

### Why React does not write orders directly to Firestore

The browser cannot be trusted to calculate prices, change stock, assign order
numbers, or set staff permissions. A customer could alter browser JavaScript.
Therefore React sends a request to Flask. Flask verifies the user, loads the
real database values, performs calculations and writes the final result.

### Responsibilities

| Layer | Responsibility |
|---|---|
| React | Screens, forms, state, navigation, API calls |
| Firebase Authentication | Email/password and Google identity |
| Flask | Validation, authorization and business rules |
| Firestore | Persistent documents and transactions |
| Cloudinary | Product image/video files |
| AI provider | Optional natural-language generation |

## 3. Required software

Install:

1. Git
2. Node.js 20 or newer
3. Python 3.11 or newer
4. VS Code
5. A Firebase account
6. A free Cloudinary account

Check the tools:

```powershell
git --version
node --version
npm --version
python --version
```

## 4. Create the folders

```powershell
cd D:\Documents\orderflow
mkdir vendly-lk-web
cd vendly-lk-web
mkdir backend
mkdir docs
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install firebase react-router-dom lucide-react jspdf @fontsource-variable/inter
cd ..
```

The finished high-level layout is:

```text
vendly-lk-web/
├── backend/
│   ├── app/
│   │   ├── api/          # URL/HTTP layer
│   │   ├── core/         # configuration, auth and errors
│   │   └── services/     # business logic and Firestore operations
│   ├── tests/
│   ├── .env
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── firebase/
│   │   ├── pages/
│   │   ├── services/
│   │   └── utils/
│   ├── .env.local
│   └── package.json
├── firestore.rules
├── firestore.indexes.json
└── README.md
```

## 5. Create the Firebase project

1. Open Firebase Console and create a project.
2. Go to **Authentication → Sign-in method**.
3. Enable **Email/Password** and **Google**.
4. Keep **one account per email address** enabled.
5. Go to **Firestore Database → Create database**.
6. Choose the region nearest the main audience (for example Singapore).
7. Add a **Web app** and copy its configuration values.
8. In **Project settings → Service accounts**, generate a private key for the
   backend. Save it outside the repository, for example:

```text
D:\secure\vendly-firebase-admin.json
```

The web configuration is public and may be used in React. The Admin JSON is a
secret and may only be read by Flask.

## 6. Frontend environment

Create `frontend/.env.local`:

```dotenv
VITE_FIREBASE_API_KEY=your-web-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id
VITE_API_BASE_URL=http://127.0.0.1:5000/api/v1
```

Add to `frontend/.gitignore`:

```gitignore
.env
.env.*
!.env.example
dist/
node_modules/
```

Create `frontend/src/firebase/firebase.js`:

```javascript
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const firebaseApp = initializeApp(firebaseConfig);
export const auth = getAuth(firebaseApp);
```

## 7. Authentication in React

Use Firebase client functions only for authentication. Useful functions are:

```javascript
import {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from "firebase/auth";
import { auth } from "../firebase/firebase";

export async function registerWithEmail(email, password) {
  const credential = await createUserWithEmailAndPassword(auth, email, password);
  await sendEmailVerification(credential.user);
  return credential.user;
}

export function loginWithEmail(email, password) {
  return signInWithEmailAndPassword(auth, email, password);
}

export function loginWithGoogle() {
  return signInWithPopup(auth, new GoogleAuthProvider());
}

export function logout() {
  return signOut(auth);
}
```

`AuthContext` listens for login changes and exposes the current user:

```jsx
import { onAuthStateChanged } from "firebase/auth";
import { createContext, useEffect, useState } from "react";
import { auth } from "../firebase/firebase";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    return onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  );
}
```

Do not ask for the business name on every login. After login call `GET /me`.
If it returns an existing business, go to the dashboard. Only show business
setup when no business exists.

## 8. React routing and page shell

The application needs protected seller routes and public store routes:

```jsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route path="/setup-business" element={<BusinessSetupPage />} />
  <Route path="/s/:storeCode" element={<StorefrontPage />} />
  <Route path="/p/:productCode" element={<StorefrontPage />} />

  <Route element={<ProtectedRoute />}>
    <Route element={<ManagementPage />}>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/orders" element={<OrdersPage />} />
      <Route path="/inventory" element={<InventoryPage />} />
      <Route path="/couriers" element={<CouriersPage />} />
      <Route path="/customers" element={<CustomersPage />} />
      <Route path="/analytics" element={<AnalyticsPage />} />
    </Route>
  </Route>
</Routes>
```

`ManagementPage` owns the shared sidebar and header. Each child page is shown
inside React Router's `<Outlet />`.

## 9. The frontend API client

Every authenticated request must include the current Firebase ID token.
Create `frontend/src/services/apiClient.js`:

```javascript
import { auth } from "../firebase/firebase";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000/api/v1";

export async function apiRequest(path, options = {}) {
  const token = await auth.currentUser?.getIdToken();
  const headers = new Headers(options.headers);

  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    body:
      options.body instanceof FormData
        ? options.body
        : options.body
          ? JSON.stringify(options.body)
          : undefined,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error?.message ?? "Request failed.");
  }

  return response.status === 204 ? null : response.json();
}
```

Example product service:

```javascript
export async function getProducts(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/products`);
  return response.products;
}

export async function createProduct(businessId, product) {
  const response = await apiRequest(`/businesses/${businessId}/products`, {
    method: "POST",
    body: product,
  });
  return response.product;
}
```

## 10. Create the Flask backend

From the backend folder:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install Flask flask-cors Flask-Limiter firebase-admin google-genai httpx openpyxl python-dotenv gunicorn pytest
```

Create `requirements.txt`:

```text
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
```

Create `backend/.env`:

```dotenv
FLASK_DEBUG=true
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=D:\secure\vendly-firebase-admin.json
FRONTEND_ORIGINS=http://localhost:5173
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-cloudinary-key
CLOUDINARY_API_SECRET=your-cloudinary-secret
AI_PROVIDER=none
AI_API_KEY=
AI_MODEL=
AI_API_BASE_URL=
AI_TIMEOUT_SECONDS=15
RATE_LIMIT_STORAGE_URI=memory://
```

Add `.env`, `.venv/`, `__pycache__/` and service-account JSON files to the
backend `.gitignore`.

Create `run.py`:

```python
import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=app.config["DEBUG"],
    )
```

## 11. Flask application factory

An application factory creates a configured Flask instance. Its job is to:

1. read environment variables;
2. configure CORS and upload limits;
3. initialize Firebase Admin;
4. enable rate limiting;
5. register API blueprints;
6. return consistent JSON errors.

Simplified `app/__init__.py`:

```python
from flask import Flask, jsonify
from flask_cors import CORS
from app.core.firebase import initialize_firebase

def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173"]}})
    initialize_firebase()

    from app.api.health import health_blueprint
    from app.api.products import products_blueprint
    app.register_blueprint(health_blueprint)
    app.register_blueprint(products_blueprint)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": {"code": "not_found", "message": "Route not found."}}), 404

    return app
```

The real project registers all blueprints in `backend/app/__init__.py`.

## 12. Initialize Firebase Admin

```python
import firebase_admin
from firebase_admin import credentials, firestore

def initialize_firebase(settings):
    if firebase_admin._apps:
        return

    credential = credentials.Certificate(settings.firebase_service_account_path)
    firebase_admin.initialize_app(credential, {
        "projectId": settings.firebase_project_id,
    })

def get_firestore_client():
    return firestore.client()
```

The backend service account bypasses Firestore browser rules. This is why every
Flask route must perform authentication and authorization correctly.

## 13. Firebase token verification

React sends:

```http
Authorization: Bearer FIREBASE_ID_TOKEN
```

Flask verifies it:

```python
from functools import wraps
from firebase_admin import auth
from flask import g, request

def require_firebase_user(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise ApiError("authentication_required", "Please sign in.", 401)

        token = header.removeprefix("Bearer ").strip()
        try:
            g.current_user = auth.verify_id_token(token)
        except Exception as error:
            raise ApiError("invalid_token", "Your session is invalid.", 401) from error

        return view(*args, **kwargs)
    return wrapped
```

## 14. Business membership and permissions

Authentication answers “who is this?”. Authorization answers “may this user
manage this business?”. Each business has `members/{uid}` with a role.

```python
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager")
def add_product(business_id):
    ...
```

Roles currently used:

- `owner`
- `admin`
- `order_manager`
- `inventory_manager`
- `support`
- `viewer`

Never trust a role sent by React. Load it from Firestore.

## 15. Why API files and service files are separate

An API route should be small:

```python
@products_blueprint.post("/businesses/<business_id>/products")
@require_firebase_user
@require_business_member("owner", "admin", "inventory_manager")
def add_product(business_id):
    product = create_product(
        get_firestore_client(),
        business_id,
        g.current_user["uid"],
        get_json_object(),
    )
    return jsonify({"product": product}), 201
```

The route handles HTTP. `product_service.py` handles validation, SKU/barcode,
Firestore documents and stock. This separation lets the same order service be
used by the dashboard and chatbot.

## 16. Firestore structure

```text
users/{uid}
businesses/{businessId}
businesses/{businessId}/members/{uid}
businesses/{businessId}/categories/{categoryId}
businesses/{businessId}/products/{productId}
businesses/{businessId}/productVariants/{variantId}
businesses/{businessId}/inventoryTransactions/{transactionId}
businesses/{businessId}/customers/{customerId}
businesses/{businessId}/couriers/{courierId}
businesses/{businessId}/orders/{orderId}
businesses/{businessId}/waybills/{orderId}
businesses/{businessId}/fraudReports/{reportId}
businesses/{businessId}/courierIssues/{issueId}
businesses/{businessId}/reviews/{reviewId}
businesses/{businessId}/notifications/{notificationId}
shortLinks/{shortCode}
publicChatSessions/{sessionId}
```

Customer identity is stored as a Firebase UID, not as a phone number or an
order number. New storefront chat sessions contain `customerUid`. Orders made
from those sessions also contain `customerUid`. This is what lets the backend
return only the signed-in customer's history.

Seller data is nested below a business. Two sellers may have products with the
same name without seeing each other's records.

Money is stored as integer minor units:

```text
LKR 1,899.00 → 189900
```

This avoids floating-point calculation errors.

## 17. Category programming

A category contains a name, slug, description, sort order and status. Product
counts and stock totals are calculated from products instead of typed manually.

Create request:

```json
{
  "name": "Footwear",
  "description": "Shoes and sandals",
  "sortOrder": 1
}
```

Delete archives the category instead of physically erasing it. This preserves
historical references.

## 18. Product and variant programming

Each colour is a separate product. A product may optionally have one variant
layer such as shoe size. Even a product without sizes receives one default
variant so stock and order code follows one consistent path.

Example product request:

```json
{
  "name": "Daisy Running Shoes",
  "colourName": "Pink",
  "categoryId": "CATEGORY_DOCUMENT_ID",
  "brand": "Daisy Fashion",
  "warrantyPeriod": "6 months",
  "description": "Breathable daily running shoes.",
  "hasVariants": true,
  "sku": "DFS-PNK",
  "barcode": "890123456000",
  "costPrice": 1200,
  "sellingPrice": 1899,
  "weightKg": 0.45,
  "lowStockThreshold": 2,
  "variants": [
    {
      "name": "36",
      "sku": "DFS-PNK-36",
      "barcode": "890123456001",
      "stock": 5,
      "costPrice": 1200,
      "sellingPrice": 1899
    }
  ]
}
```

The backend validates unique SKU/barcode values, creates the product and
variant documents, calculates total stock, and creates initial inventory
transactions. Generated SKU and barcode values are conveniences; Firestore
document IDs remain the true internal identifiers.

When stock changes, never only overwrite `stockAvailable`. Use an adjustment
service that also creates an immutable `inventoryTransactions` document:

```json
{
  "quantity": 10,
  "mode": "increase",
  "reason": "New supplier delivery"
}
```

## 19. Product media and AI descriptions

Product files are uploaded as `multipart/form-data` to Flask. Flask validates
the type and size, uploads to Cloudinary and stores the secure URL in Firestore.

```javascript
const form = new FormData();
selectedFiles.forEach((file) => form.append("files", file));

await apiRequest(`/businesses/${businessId}/products/${productId}/media`, {
  method: "POST",
  body: form,
});
```

AI description generation sends product facts to Flask, not the API key:

```json
{
  "name": "Zeblaze GTS 3 Smart Watch",
  "category": "Smart Watches",
  "brand": "Zeblaze",
  "colour": "Black",
  "warranty": "6 months",
  "specifications": "IP68, Bluetooth calling, heart-rate monitor"
}
```

If AI is unavailable, Flask returns a safe template. Seller-entered facts
remain authoritative; AI must not invent warranty or technical specifications.

## 20. Customer programming

Customers store normalized phones, addresses, private notes, tags, order counts,
total spending and risk level. Example:

```json
{
  "name": "Kamal Perera",
  "phoneNumber": "0771234567",
  "secondaryPhoneNumber": "0112345678",
  "email": "kamal@example.com",
  "defaultAddress": {
    "line1": "45 Park Road",
    "line2": "",
    "city": "Dehiwala",
    "district": "Colombo",
    "postalCode": "10350",
    "country": "Sri Lanka"
  }
}
```

Private notes must never appear in public store/chat responses.

## 21. Courier and delivery calculation

Courier document fields include:

```text
name
code
firstKgPriceMinor
extraKgPriceMinor
districtSurchargesMinor
averageDeliveryDays
waybillPrefix
waybillStart
waybillEnd
nextWaybillSequence
successRate
returnRate
districtIssueCounts
status
```

Delivery calculation:

```text
0–1000 g        = first kilogram price
each extra kg   = ceil(extra grams / 1000) × extra kilogram price
delivery fee    = base price + district surcharge
```

Courier recommendation starts with deterministic data: active status, price,
success rate, return rate and recorded district problems. AI should not replace
these factual rules.

## 22. Order creation — the most important workflow

React only submits IDs, quantities and customer/delivery choices:

```json
{
  "customerId": "CUSTOMER_ID",
  "items": [
    { "variantId": "VARIANT_1", "quantity": 2 },
    { "variantId": "VARIANT_2", "quantity": 1 }
  ],
  "courierId": "COURIER_ID",
  "deliveryAddress": {
    "line1": "45 Park Road",
    "city": "Dehiwala",
    "district": "Colombo",
    "country": "Sri Lanka"
  },
  "discountAmount": 0,
  "paymentMethod": "cod",
  "depositAmount": 0,
  "source": "dashboard",
  "privateNote": "Call before dispatch"
}
```

React must not submit authoritative product prices or the final total.

Inside one Firestore transaction Flask:

1. verifies the business, customer and courier;
2. loads every requested variant and product;
3. checks active status and available stock;
4. calculates item subtotal from database prices;
5. calculates total weight;
6. calculates delivery fee from courier and district;
7. applies valid discount/deposit rules;
8. allocates `VD-000001` from `nextOrderSequence`;
9. allocates a waybill from the courier range;
10. stores immutable item snapshots;
11. reserves each variant's stock;
12. updates product summary stock;
13. creates inventory transaction records;
14. advances order/waybill sequences;
15. creates the waybill record and seller notification;
16. commits everything together.

If any validation fails, Firestore cancels the entire transaction. It cannot
create an order while forgetting to reserve stock.

The order stores snapshots (name, price, cost, weight, SKU and image). Editing
a product next month must not change an old receipt.

## 23. Order status workflow

```text
needs-confirmation → confirmed → packed → shipped → delivered
        |                |          |         |
        +---- cancelled -+----------+         +→ returned
```

The backend, not a `<select>`, enforces allowed transitions. Cancelling releases
reserved stock. Delivery converts reserved stock into sold stock. Returns and
courier outcomes update customer/courier history.

Use `PATCH` because status changes only one part of the order:

```json
{
  "status": "confirmed",
  "note": "Customer confirmed by phone"
}
```

## 24. Automatic and manual waybill numbers

When an order is created, the backend reads the courier:

```python
sequence = courier.get("nextWaybillSequence", courier.get("waybillStart", 1))
end = courier.get("waybillEnd", 999999)

if sequence > end:
    raise ApiError("waybill_range_exhausted", "Add a new waybill range.", 409)

waybill_number = f"{courier.get('waybillPrefix', 'VWB')}-{sequence:08d}"
```

The order and `waybills/{orderId}` record receive the number, and the courier's
next sequence becomes `sequence + 1` in the same transaction.

For a manual correction, React sends:

```javascript
await updateOrder(businessId, orderId, {
  waybillNumber: enteredWaybill.trim(),
});
```

Flask validates it and updates both records.

## 25. Public store and chatbot

Seller link:

```text
https://vendly.lk/s/V7k92M
```

Product link:

```text
https://vendly.lk/p/P8x43K
```

The short code resolves to one active seller/product. The browser never uses a
seller-entered business ID as proof of public access.

Chat session creation returns a `sessionId` and secret session token. Later
requests include:

```http
X-Chat-Session-Token: secret-token
```

The chatbot flow:

1. resolve seller/product short code;
2. create restricted chat session;
3. load only that seller's active catalogue;
4. answer product/category/feature questions from stored facts;
5. show product cards with image, price and stock;
6. maintain multiple cart items and quantities;
7. collect and validate customer contact/address;
8. show subtotal, delivery and total;
9. ask for explicit confirmation;
10. call the same trusted `create_order` workflow;
11. return an order receipt.

AI may interpret language and phrase answers, but it may not directly write an
order or stock value.

For a product with variants, the product-detail reply renders one row per
variant. After the customer selects a row, the UI shows minus, number input and
plus controls. The number input is clamped between 1 and that variant's
`availableStock`; zero removes the row from the draft. Quantity changes update
the same React cart used by the Live Order Draft and checkout request.

```jsx
<input
  type="number"
  min="1"
  max={availableStock}
  value={quantity}
  onChange={(event) =>
    onSetItemQuantity(variant.id, event.target.value)
  }
/>
```

Do not trust the browser's quantity limit. React limits it for usability, and
Flask checks stock again inside the order transaction for security.

### Customer login, guest history and tracking

The storefront supports three customer identity methods:

1. email/password with email verification;
2. Google login;
3. Firebase anonymous authentication for **Continue as guest**.

Enable all three providers in Firebase Console under **Authentication >
Sign-in method**. Anonymous authentication gives a guest a real, unguessable
Firebase UID. It persists in that browser until the customer logs out or clears
browser storage. Email and Google accounts work across devices.

The relevant frontend files are:

```text
frontend/src/components/CustomerAccountModal.jsx
frontend/src/components/CustomerAccountModal.css
frontend/src/pages/StorefrontPage.jsx
frontend/src/services/authService.js
frontend/src/services/publicService.js
frontend/src/services/apiClient.js
```

The relevant backend files are:

```text
backend/app/core/auth.py
backend/app/api/public.py
backend/app/services/public_chat_service.py
backend/app/services/customer_portal_service.py
backend/app/services/order_service.py
```

`optional_firebase_user` accepts a public request with no login, but verifies
and loads the user when an Authorization header exists. This is used when a
chat is first created and when a public checkout is submitted. Customer-history
routes use `require_firebase_user`, because history must never be public.

When the customer logs in after opening the store, React claims the current
chat:

```javascript
await claimPublicChatSession(session.sessionId, session.sessionToken);
```

Flask verifies both credentials:

- Firebase ID token proves the customer UID;
- `X-Chat-Session-Token` proves possession of that chat session.

The backend refuses to claim a chat already owned by another UID. If the chat
already created an order, claiming it also connects that order to the customer.

At checkout, `create_public_chat_order` passes the session's `customerUid` to
the shared `create_order` transaction. The order document therefore contains:

```json
{
  "customerUid": "firebase-customer-uid",
  "customerId": "seller-customer-record-id",
  "orderNumber": "VD-000123",
  "fulfilmentStatus": "needs-confirmation",
  "waybillNumber": "KMB-00001234"
}
```

These two customer identifiers have different purposes:

- `customerId` links the seller's CRM customer record;
- `customerUid` authorizes the storefront account to see the order.

`customer_portal_service.py` always filters using the verified Firebase UID.
The browser cannot send an arbitrary UID in a query parameter. Public order
responses use `public_order_confirmation`, which removes private notes, costs,
fraud information and internal staff data.

The customer account modal provides:

- account creation and login;
- Google and guest access;
- saved conversations;
- order item and total summaries;
- fulfilment status progress;
- courier and waybill/tracking information.

Orders created before this field existed are not automatically shown. Do not
link old orders using only a phone number because that could expose another
person's order. A future migration should use a verified ownership process.

## 26. Complete current REST API

Local base URL:

```text
http://127.0.0.1:5000/api/v1
```

Authenticated endpoints require `Authorization: Bearer <Firebase-ID-token>`.

### System and account

```text
GET    /health
GET    /me
POST   /businesses
```

### Staff

```text
GET    /businesses/{businessId}/members
POST   /businesses/{businessId}/members
PATCH  /businesses/{businessId}/members/{memberUid}
```

### Categories

```text
GET    /businesses/{businessId}/categories
POST   /businesses/{businessId}/categories
PATCH  /businesses/{businessId}/categories/{categoryId}
DELETE /businesses/{businessId}/categories/{categoryId}
```

### Products and stock

```text
GET    /businesses/{businessId}/products?categoryId=&status=
POST   /businesses/{businessId}/products
POST   /businesses/{businessId}/products/generate-description
GET    /businesses/{businessId}/products/{productId}
PATCH  /businesses/{businessId}/products/{productId}
DELETE /businesses/{businessId}/products/{productId}
POST   /businesses/{businessId}/products/{productId}/media
POST   /businesses/{businessId}/products/{productId}/variants/{variantId}/image
POST   /businesses/{businessId}/products/{productId}/variants/{variantId}/adjust-stock
```

### Customers

```text
GET    /businesses/{businessId}/customers?phone=&search=
POST   /businesses/{businessId}/customers
GET    /businesses/{businessId}/customers/{customerId}
PATCH  /businesses/{businessId}/customers/{customerId}
```

### Couriers

```text
GET    /businesses/{businessId}/couriers
POST   /businesses/{businessId}/couriers
PATCH  /businesses/{businessId}/couriers/{courierId}
POST   /businesses/{businessId}/couriers/recommend
```

Recommendation request:

```json
{ "totalWeightGrams": 1450, "district": "Colombo" }
```

### Orders and operations

```text
GET    /businesses/{businessId}/orders?status=&search=&dateFrom=&dateTo=&courierId=
POST   /businesses/{businessId}/orders
GET    /businesses/{businessId}/orders/{orderId}
PATCH  /businesses/{businessId}/orders/{orderId}
DELETE /businesses/{businessId}/orders/{orderId}
PATCH  /businesses/{businessId}/orders/{orderId}/status
POST   /businesses/{businessId}/orders/{orderId}/waybill
POST   /businesses/{businessId}/orders/{orderId}/fraud-report
POST   /businesses/{businessId}/orders/{orderId}/courier-issues
GET    /businesses/{businessId}/orders-export.xlsx?status=&search=
```

`DELETE` currently performs a safe cancellation and stock release instead of
permanently deleting the historical order.

### Reviews, notifications, analytics and search

```text
GET    /businesses/{businessId}/reviews?status=&productId=
PATCH  /businesses/{businessId}/reviews/{reviewId}
GET    /businesses/{businessId}/notifications?unread=true
PATCH  /businesses/{businessId}/notifications/{notificationId}/read
GET    /businesses/{businessId}/analytics/overview
GET    /businesses/{businessId}/search?q={query}
```

### Public catalogue and chat endpoints

```text
GET    /public/stores/{storeShortCode}
GET    /public/products/{productShortCode}
GET    /public/products/{productShortCode}/reviews
POST   /public/stores/{storeShortCode}/reviews
POST   /public/chat/sessions
POST   /public/chat/sessions/{sessionId}/messages
POST   /public/chat/sessions/{sessionId}/orders
```

Public chat message and order endpoints require `X-Chat-Session-Token`. Session
creation and checkout optionally accept a Firebase bearer token so the chat and
order can be attached to the signed-in customer.

### Customer storefront account endpoints

```text
POST   /public/chat/sessions/{sessionId}/claim
GET    /public/stores/{storeShortCode}/customer/orders
GET    /public/stores/{storeShortCode}/customer/orders/{orderId}
GET    /public/stores/{storeShortCode}/customer/chats
```

All four require `Authorization: Bearer <Firebase-ID-token>`. The claim route
also requires `X-Chat-Session-Token`. Order and chat queries derive the UID from
the verified token; they never accept `customerUid` from the URL or request
body.

## 27. HTTP method meanings

| Method | Meaning |
|---|---|
| GET | Read without changing data |
| POST | Create a resource or run an operation |
| PATCH | Change selected fields |
| PUT | Replace an entire resource (not currently needed) |
| DELETE | Remove/archive/cancel a resource |

Typical status codes:

```text
200 success
201 resource created
400 malformed request
401 login missing/invalid
403 user lacks permission
404 resource not found
409 state conflict, insufficient stock or exhausted range
413 upload too large
422 validation failed
429 too many requests
500 unexpected server error
```

Error format:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Enter a valid phone number."
  }
}
```

## 28. How one API request travels through the system

Example: seller clicks **Add Product**.

1. The React modal stores fields in `useState`.
2. Submit handler validates basic required fields.
3. `productService.createProduct()` calls `apiRequest()`.
4. `apiRequest()` obtains the Firebase ID token.
5. Browser sends `POST /api/v1/businesses/.../products`.
6. Flask CORS accepts the configured frontend origin.
7. `require_firebase_user` verifies the token.
8. `require_business_member` verifies role and business membership.
9. API function extracts a JSON object.
10. `create_product()` validates values and executes Firestore writes.
11. Flask serializes timestamps and returns `{ "product": ... }`.
12. React inserts the returned product into page state.
13. The table rerenders automatically.

## 29. Firestore security

For this architecture, seller business writes must go through Flask. Firestore
browser rules should deny unrestricted writes. Public catalogue reads should
also go through the restricted public API so private notes/costs never leak.

Backend protections:

- verify every authenticated token;
- check membership for every business route;
- restrict roles per operation;
- validate all JSON and file uploads;
- calculate totals server-side;
- use transactions for orders/stock/sequences;
- rate-limit public chat and review endpoints;
- restrict CORS to known frontend domains;
- never return private notes publicly.

## 30. Start and test locally

Terminal 1:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\backend
.\.venv\Scripts\python.exe run.py
```

Terminal 2:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\frontend
npm.cmd run dev
```

Open:

```text
Frontend: http://localhost:5173
API health: http://127.0.0.1:5000/api/v1/health
```

Run checks:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\backend
.\.venv\Scripts\python.exe -m pytest -q

cd D:\Documents\orderflow\vendly-lk-web\frontend
npm.cmd run lint
npm.cmd run build
```

## 31. Recommended development order

Do not build every feature at once. Use these milestones:

1. Empty React screen and Flask health endpoint.
2. Firebase email/Google login.
3. `/me` and one-time business setup.
4. Shared header/sidebar and protected routes.
5. Categories CRUD.
6. Products, default variant and inventory table.
7. Media upload and stock adjustment audit.
8. Customers and structured addresses.
9. Couriers, price rules and waybill ranges.
10. Manual multi-item orders in one transaction.
11. Status transitions, stock release/sale and receipts.
12. Seller storefront and cart.
13. Chat session and deterministic catalogue answers.
14. Chat checkout through the existing order service.
15. Reviews, notifications, export and analytics.
16. Optional AI enhancements.

For each milestone:

```text
design → data shape → backend validation → API route → frontend service
→ component/page → loading/error states → tests → commit
```

## 32. Common beginner mistakes

1. Putting Firebase Admin credentials in React.
2. Storing money as floating-point values.
3. Trusting totals sent by the browser.
4. Updating stock without an inventory transaction.
5. Creating an order through a separate chatbot implementation.
6. Using product data by name instead of stable document IDs.
7. Deleting historical orders/products permanently.
8. Forgetting business membership checks.
9. Using `window.location.reload()` instead of updating React state.
10. Mixing page UI, API calls and database logic in one file.
11. Committing `.env` or service-account JSON.
12. Adding AI before deterministic catalogue/order logic works.

## 33. How to study the existing implementation

Read in this order:

1. `frontend/src/main.jsx`
2. `frontend/src/App.jsx`
3. `frontend/src/context/AuthContext.jsx`
4. `frontend/src/services/apiClient.js`
5. one page, such as `InventoryPage.jsx`
6. its service, `productService.js`
7. matching route, `backend/app/api/products.py`
8. matching logic, `backend/app/services/product_service.py`
9. authentication and authorization decorators
10. order service last, because it is the most complex transaction.

When reading a function, answer:

```text
What values enter it?
What validation happens?
What database documents are read?
What documents are changed?
What value or error is returned?
Which React state is updated with that response?
```

## 34. Final rule

There should be one trusted implementation for each business operation:

```text
Dashboard order ─┐
Chatbot order  ──┼──> Flask create_order() ──> Firestore transaction
Future mobile app┘
```

The web dashboard, chatbot and future mobile application are different user
interfaces. They should all use the same backend API and the same Firestore
database. This is how Vendly remains consistent as it grows.

## 35. Exact file-creation sequence

The explanations above teach the concepts. Use the sequence below when
rebuilding the application. After completing a phase, run the checks and make a
Git commit before starting the next phase.

The complete current content of every source file listed below is included in
`COMPLETE_SOURCE_CODE.md`. Search that document for the exact path heading,
create the file at that path, and copy its code block.

### Phase 1 — repository and frontend foundation

Create/copy in this order:

```text
frontend/package.json
frontend/index.html
frontend/vite.config.js
frontend/src/main.jsx
frontend/src/index.css
frontend/src/App.jsx
frontend/src/App.css
```

Run `npm install`, then `npm.cmd run dev`. At this point React must render before
you continue.

### Phase 2 — Firebase login

```text
frontend/src/firebase/firebase.js
frontend/src/services/authService.js
frontend/src/context/authContextValue.js
frontend/src/context/AuthContext.jsx
frontend/src/components/ProtectedRoute.jsx
frontend/src/pages/LoginPage.jsx
frontend/src/pages/LoginPage.css
```

Add Firebase web variables to `.env.local`. Test email registration, email
verification, login, Google login and logout.

### Phase 3 — Flask foundation and authenticated API

```text
backend/requirements.txt
backend/run.py
backend/app/__init__.py
backend/app/core/config.py
backend/app/core/firebase.py
backend/app/core/errors.py
backend/app/core/requests.py
backend/app/core/serialization.py
backend/app/core/auth.py
backend/app/core/authorization.py
backend/app/core/rate_limit.py
backend/app/api/health.py
backend/app/api/me.py
```

Create the backend virtual environment and `.env`, start Flask, check `/health`,
then sign in through React and check `/me`.

### Phase 4 — business onboarding and dashboard shell

```text
backend/app/services/text.py
backend/app/services/business_service.py
backend/app/api/businesses.py
frontend/src/services/apiClient.js
frontend/src/services/accountService.js
frontend/src/services/businessService.js
frontend/src/pages/BusinessSetupPage.jsx
frontend/src/pages/ManagementPage.css
frontend/src/components/Header.jsx
frontend/src/components/Header.css
frontend/src/components/Sidebar.jsx
frontend/src/components/Sidebar.css
```

Verify that business setup is shown only once and the saved business name
appears in the header, welcome message and sidebar.

### Phase 5 — reusable dashboard components

```text
frontend/src/components/ActionMenu.jsx
frontend/src/components/ActionMenu.css
frontend/src/components/ModalShell.jsx
frontend/src/components/ModalShell.css
frontend/src/components/ConfirmDialog.jsx
frontend/src/components/ConfirmDialog.css
frontend/src/components/StatCard.jsx
frontend/src/components/StatCard.css
frontend/src/components/StatCard2.jsx
frontend/src/components/StatCard2.css
frontend/src/pages/OverviewPage.jsx
```

### Phase 6 — categories

```text
backend/app/services/category_service.py
backend/app/api/categories.py
frontend/src/services/categoryService.js
frontend/src/components/AddCategoryModal.jsx
frontend/src/components/CategoryTable.jsx
frontend/src/components/CategoryTable.css
```

Test create, edit and archive before adding products.

### Phase 7 — products, variants and inventory

```text
backend/app/services/numbers.py
backend/app/services/product_service.py
backend/app/services/media_service.py
backend/app/services/ai_service.py
backend/app/api/products.py
frontend/src/utils/inventory.js
frontend/src/services/productService.js
frontend/src/components/InventoryForm.css
frontend/src/components/AddProductModal.jsx
frontend/src/components/EditProductModal.jsx
frontend/src/components/ProductVariantsTable.jsx
frontend/src/components/AdjustStockModal.jsx
frontend/src/components/AdjustStockModal.css
frontend/src/components/InventoryFilters.jsx
frontend/src/components/InventoryFilters.css
frontend/src/components/InventoryTable.jsx
frontend/src/components/InventoryTable.css
frontend/src/pages/InventoryPage.jsx
frontend/src/pages/InventoryPage.css
```

Test products without variants, products with sizes, generated SKU/barcode,
media, AI description fallback, editing, stock adjustment, export and archive.

### Phase 8 — customers and couriers

```text
backend/app/services/customer_service.py
backend/app/api/customers.py
backend/app/services/courier_service.py
backend/app/api/couriers.py
frontend/src/services/customerService.js
frontend/src/services/courierService.js
frontend/src/pages/CustomersPage.jsx
frontend/src/components/AddCourierModal.jsx
frontend/src/pages/CouriersPage.jsx
```

Test address validation, phone normalization, delivery prices, district
surcharges, recommendation results and waybill ranges.

### Phase 9 — orders and stock transactions

```text
backend/app/services/order_service.py
backend/app/api/orders.py
frontend/src/services/orderService.js
frontend/src/components/OrderFilters.jsx
frontend/src/components/OrderFilters.css
frontend/src/components/AddOrderModal.jsx
frontend/src/components/AddOrderModal.css
frontend/src/components/EditOrderModal.jsx
frontend/src/components/OrderTable.jsx
frontend/src/components/OrderTable.css
frontend/src/components/OrderDetails.jsx
frontend/src/components/OrderDetails.css
frontend/src/pages/OrdersPage.jsx
frontend/src/pages/OrdersPage.css
```

Test multiple items, stock reservation, calculated totals, automatic order and
waybill numbers, editing, cancellation and every allowed status transition.

### Phase 10 — order operations and receipts

```text
backend/app/services/operations_service.py
backend/app/api/operations.py
frontend/src/services/operationService.js
frontend/src/services/notificationService.js
frontend/src/services/receiptService.js
frontend/src/components/OrderReceipt.jsx
frontend/src/components/OrderReceipt.css
```

Test fraud reports, courier issues, notifications, Excel export, waybill print
and PDF receipt.

### Phase 11 — storefront and chatbot

```text
backend/app/services/public_catalog_service.py
backend/app/services/public_chat_service.py
backend/app/api/public.py
frontend/src/services/publicService.js
frontend/src/pages/StorefrontPage.jsx
frontend/src/pages/StorefrontPage.css
frontend/src/components/CustomerAccountModal.jsx
frontend/src/components/CustomerAccountModal.css
backend/app/services/customer_portal_service.py
```

Test `/s/{storeCode}`, `/p/{productCode}`, product/category questions, multiple
cart items, contact validation, confirmation, customer email/Google/guest
login, chat claiming, private history access, tracking and database order
creation.

### Phase 12 — reviews, analytics, staff and search

```text
backend/app/services/review_service.py
backend/app/api/reviews.py
backend/app/services/analytics_service.py
backend/app/api/analytics.py
backend/app/services/member_service.py
backend/app/api/members.py
backend/app/services/search_service.py
backend/app/api/search.py
frontend/src/services/reviewService.js
frontend/src/services/analyticsService.js
frontend/src/services/memberService.js
frontend/src/services/searchService.js
frontend/src/components/ReviewsModal.jsx
frontend/src/components/ReviewsModal.css
frontend/src/components/StaffSettings.jsx
frontend/src/components/StaffSettings.css
frontend/src/pages/AnalyticsPage.jsx
frontend/src/pages/AnalyticsPage.css
```

### Phase 13 — security, indexes and tests

```text
firestore.rules
firestore.indexes.json
storage.rules
firebase.json
backend/tests/*.py
```

Run the full backend test suite, frontend lint and production build. Only after
all three pass should deployment configuration be added.

## 36. Full source-code companion

This guide intentionally explains how and why the system is built. The exact
line-by-line implementation is kept in:

```text
COMPLETE_SOURCE_CODE.md
```

That companion contains the current safe source/configuration files, but
excludes:

- `.env` and `.env.local` secrets;
- Firebase Admin service-account JSON;
- `node_modules`, `.venv`, `dist` and caches;
- binary images, fonts and videos;
- Git internals.

Do not blindly paste the entire appendix at once. Follow Phase 1 through Phase
13, create each named file, test the milestone, then move forward.
# Latest storefront authentication and chat-history update

Storefront links are now protected by `CustomerAuthGate`. The gate waits for Firebase's `onAuthStateChanged`, displays the customer sign-in/register/Google/guest screen automatically, and only mounts the storefront after a customer is authenticated. This prevents a public session from being created before login. Enable **Anonymous** in Firebase Authentication > Sign-in method for guest login; the frontend now reports a clear error when that provider is disabled.

After authentication, the storefront creates a new chat session with the customer's Firebase UID and calls `GET /api/v1/public/stores/{storeCode}/customer/chats`. The newest previous chat with messages is mapped back into the chat window. Orders created by the session carry `customerUid`, so `GET /customer/orders` can show the signed-in customer's history and tracking information. Guest users use Firebase anonymous accounts and are treated like normal authenticated customers until they sign out or clear their device session.

New files: `frontend/src/pages/CustomerAuthGate.jsx` and `frontend/src/pages/CustomerAuthGate.css`. The route flow is `/s/:storeCode` or `/p/:productCode` -> `CustomerAuthGate` -> `StorefrontPage`. Keep authentication loading separate from storefront loading, and include the Firebase `user` in the storefront loading effect dependencies.

## Updated learning references

For a beginner-friendly feature-by-feature path use `PROGRAMMING_LEARNING_PATH.md`.
For database and server implementation use `FIREBASE_DATABASE_GUIDE.md` and
`BACKEND_API_FROM_SCRATCH.md`. They introduce small fragments first—authentication,
a route, a product document and a transactional order—before showing how the
pieces connect.

## Implementing the latest chatbot fields

Add one state handler per question instead of parsing all contact details in one message. Validate the primary and optional secondary Sri Lankan numbers, then save `address.line1`, `address.city`, `address.district`, and `deliveryNote` in the session draft. Render the returned draft in React so the seller/customer can verify it before confirmation. The order POST must send both phone fields and the delivery note; Flask validates them again before writing Firestore.

## 37. Build a safe first-loading sequence

Do not show the dashboard, setup route or protected navigation until Firebase
and the initial Flask account request have both completed. The important state
is:

```jsx
const [isAuthLoading, setIsAuthLoading] = useState(true);
const [authenticationError, setAuthenticationError] = useState(null);
const [accountError, setAccountError] = useState(null);
```

The Firebase listener sets `isAuthLoading` before calling `loadAccount()`, and
clears it in `finally`. `App.jsx` renders one full-screen `AppLoadingScreen`
while it is true. If Firebase initialization or the first account request fails,
the same component shows the relevant error and a retry button. This avoids the
old problems where setup appeared repeatedly or pages needed a manual refresh.

## 38. Analytics and transaction-ledger implementation

Vendly keeps analytics as a server-derived read model:

```text
orders + products + customers + notifications + warrantyClaims
                              -> get_business_analytics()
orders + shopSales + warrantyClaims + inventoryTransactions
                              -> get_business_ledger()
```

The current overview includes revenue, cost of goods, gross profit, average
order value, gross margin, order status, daily orders, monthly revenue,
top-selling products, inventory health and work-centre counts. The ledger shows
money in, money out and a running movement balance and can be exported with its
current search, type and date filters.

Never calculate trusted financial results only in React. Store all currency as
integer minor units, derive the figures in Flask, and format them in the UI.
The current endpoints are:

```text
GET /api/v1/businesses/{businessId}/analytics/overview
GET /api/v1/businesses/{businessId}/analytics/ledger
GET /api/v1/businesses/{businessId}/analytics/ledger-export.xlsx
```

## 39. One animation setting for the complete application

`App.jsx` stores `vendly-animations-enabled` in local storage and writes the
choice to `html[data-animations]`. Put page entrance rules under
`html[data-animations="enabled"]`; do not give components a hidden initial
state outside that selector.

When animations are disabled, `MotionPreferences.css` must restore the final
visible state for any component that normally starts with `opacity: 0` or a
transform. This includes dashboard sections, sidebar elements and the courier
fee map. Otherwise disabling motion makes content disappear instead of merely
stopping animation.
