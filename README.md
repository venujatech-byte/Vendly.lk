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
