# Vendly Flask API

This service is the trusted application layer between the React dashboard and
Firebase. It verifies Firebase Authentication tokens before accessing business
data in Firestore. Product media is uploaded to Cloudinary and its secure URL
is saved in Firestore.

The complete project setup and implemented feature list are documented in the
repository root `README.md`.

## Local setup

1. Create a Firebase service-account JSON file from the Firebase console.
2. Keep that JSON file outside the repository.
3. Copy `.env.example` to `.env`.
4. Set `FIREBASE_SERVICE_ACCOUNT_PATH` to the JSON file's absolute path.
5. Set `FIREBASE_PROJECT_ID` and the allowed frontend origins.
6. Create a free Cloudinary account and set `CLOUDINARY_CLOUD_NAME`,
   `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET`.

Run the API from this directory:

```powershell
.\.venv\Scripts\python.exe run.py
```

The local API starts at `http://127.0.0.1:5000`. Its health endpoint is:

```text
GET http://127.0.0.1:5000/api/v1/health
```

Never put the service-account JSON contents in React, a `VITE_*` variable, or
GitHub.

## PayHere sandbox billing

The dashboard Settings menu can start a PayHere sandbox checkout for a paid
Vendly plan. Add these values to `backend/.env`:

```env
PAYHERE_SANDBOX=true
PAYHERE_MERCHANT_ID=your_sandbox_merchant_id
PAYHERE_MERCHANT_SECRET=your_sandbox_merchant_secret
FRONTEND_PUBLIC_URL=http://localhost:5173
BACKEND_PUBLIC_URL=https://your-public-backend.example.com
```

`PAYHERE_MERCHANT_SECRET` must remain in Flask and must never be added to a
`VITE_*` variable. PayHere posts the signed payment result to
`/api/v1/billing/payhere/notify`. Because PayHere cannot call a localhost URL,
use a deployed backend or a temporary HTTPS tunnel while testing the complete
callback flow. The return URL only reopens Billing; the signed callback is what
activates the paid plan.

## Public endpoint rate limits

The catalogue, chatbot and public checkout endpoints are rate limited. The
default `memory://` storage is suitable for local development and one API
process. Before scaling the API to multiple processes or servers, configure a
shared rate-limit storage service through `RATE_LIMIT_STORAGE_URI`.

### Chatbot checkout contact fields

The public chat endpoint collects a required primary phone and an optional `secondaryPhoneNumber` (customers may reply `skip`), followed by `address.line1`, `address.district`, `address.city`, and optional `deliveryNote`. The session draft is saved after each message and the order is created only after an explicit confirmation.
