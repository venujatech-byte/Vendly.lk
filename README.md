# Vendly.lk

Vendly is a multi-seller order, inventory, courier and customer-management
platform for Sri Lankan small and medium businesses. This repository contains
the React seller dashboard and mini-store, the trusted Flask API, and Firebase
security configuration.

## Architecture

- **Frontend:** React 19, Vite, Firebase Authentication
- **Backend:** Flask REST API with Firebase Admin
- **Data:** Cloud Firestore
- **Files:** Cloudinary (free plan) with media URLs stored in Firestore
- **Optional AI:** Gemini, Groq, Cerebras or another OpenAI-compatible provider

The browser authenticates with Firebase, then sends its Firebase ID token to
Flask. Flask verifies the token, checks business membership and performs all
authoritative operations such as totals, stock reservations, order numbers,
delivery pricing and role changes.

## Implemented MVP features

- Email/password and Google authentication with email verification
- Business onboarding and seller-specific short store links
- Categories, products, one size-variant layer, SKU/barcode and stock audit
- Cloudinary product image/video uploads with Firestore media metadata
- Customers, structured addresses, loyalty totals and return/fraud risk
- Multi-product COD orders with atomic stock reservation
- Weight/district delivery calculation and courier recommendation
- Order status workflow, waybill numbers and printable waybills
- Courier branch issue history and fake-order reporting
- Excel order export and seller notifications
- Store/product public links, catalogue, cart and chatbot checkout
- Optional provider-switchable product AI with deterministic fallback
- Verified purchase product reviews with seller moderation
- Revenue, gross-profit, daily/monthly and product analytics
- Owner/admin staff-role management

The larger approved feature list remains in
[`docs/product-roadmap.md`](docs/product-roadmap.md).

## 1. Firebase project setup

Enable these Firebase products:

1. Authentication: Email/Password and Google providers.
2. Cloud Firestore.

For the Flask API, generate a Firebase Admin service-account JSON file. Keep it
outside this repository and never add it to React, GitHub or a `VITE_*`
variable.

Create a free Cloudinary account and copy the cloud name, API key and API
secret into the backend environment. Cloudinary receives product media; only
the resulting secure URLs and metadata are stored in Firestore. Firebase
Storage is not required.

Deploy the included rules from the repository root after installing the
Firebase CLI:

```powershell
firebase login
firebase use YOUR_FIREBASE_PROJECT_ID
firebase deploy --only firestore:rules
```

## 2. Frontend environment

Copy `frontend/.env.example` to `frontend/.env.local` and add the Firebase web
application values. Set the local API URL to:

```text
VITE_API_BASE_URL=http://127.0.0.1:5000/api/v1
```

Run the frontend:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\frontend
npm install
npm run dev
```

If PowerShell blocks `npm.ps1`, use `npm.cmd run dev`.

## 3. Backend environment

From the backend directory:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in `backend/.env`:

```text
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=D:\secure\vendly-firebase-admin.json
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-cloudinary-api-key
CLOUDINARY_API_SECRET=your-cloudinary-api-secret
FRONTEND_ORIGINS=http://localhost:5173
```

Start Flask:

```powershell
.\.venv\Scripts\python.exe run.py
```

Health check: `http://127.0.0.1:5000/api/v1/health`

## 4. Optional chatbot AI

The chatbot works without an AI provider and answers from seller-entered facts.
To enable a provider, configure `backend/.env`; never put provider keys in the
frontend.

```text
AI_PROVIDER=gemini
AI_API_KEY=your-key
AI_MODEL=your-supported-model
```

Supported provider values are `none`, `gemini`, `groq`, `cerebras` and
`openai-compatible`. An external failure safely falls back to deterministic
catalogue answers.

## 5. Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm.cmd run lint
npm.cmd run build
```

See [`docs/api-endpoints.md`](docs/api-endpoints.md) for the current REST API.

### Chatbot checkout fields

The public chatbot collects a customer name, one required phone number, an optional second phone number, street address, district, nearest city, and an optional delivery note. It keeps these values in the active Firestore chat session and asks the customer to confirm before creating the order. See `FEATURE_BY_FEATURE_IMPLEMENTATION_GUIDE.md`, `BACKEND_API_FROM_SCRATCH.md`, and `FIREBASE_DATABASE_GUIDE.md` for the implementation details.

## Current dashboard lifecycle and analytics

Protected pages wait for both Firebase authentication restoration and backend seller-account bootstrap before rendering. This prevents temporary Viewer roles, repeated business-setup redirects and empty dashboards during login. If startup fails, the user receives a retryable loading error rather than an automatic page reload.

The Analytics page currently provides business overview metrics, product-level gross profitability, a filterable transaction ledger with Excel export, and COD courier reconciliation. COD reconciliation tracks expected collection, courier charges, expected and received settlements, variance, overdue items and disputes without changing delivery status. Product profitability allocates order discounts across delivered line items, uses the recorded product cost and subtracts product-linked warranty costs. Revenue, COGS, gross profit, order status, delivery performance, top products and inventory health are derived from operational Firestore data through protected Flask endpoints.

Detailed references: [`docs/system-architecture.md`](docs/system-architecture.md), [`docs/api-endpoints.md`](docs/api-endpoints.md), [`BACKEND_API_FROM_SCRATCH.md`](BACKEND_API_FROM_SCRATCH.md), [`FIREBASE_DATABASE_GUIDE.md`](FIREBASE_DATABASE_GUIDE.md), [`PROGRAMMING_FROM_SCRATCH_GUIDE.md`](PROGRAMMING_FROM_SCRATCH_GUIDE.md), and [`MOBILE_FRIENDLY_GUIDE.md`](MOBILE_FRIENDLY_GUIDE.md).
