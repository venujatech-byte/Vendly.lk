# Vendly Backend and API From Scratch

Vendly uses Flask as its application tier and Firestore as its data tier.
React is the presentation tier. The browser displays data and collects input;
Flask authenticates the caller, validates the request, calculates totals,
updates stock and writes the final record.

## 1. Create and run the backend

```powershell
cd D:\Documents\orderflow\vendly-lk-web\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

`run.py` should expose a Flask app on port 5000. A minimal factory is:

```python
from flask import Flask

def create_app():
    app = Flask(__name__)

    @app.get("/api/v1/health")
    def health():
        return {"ok": True}

    return app
```

## 2. Configuration and Firebase Admin

```env
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_SERVICE_ACCOUNT_PATH=C:\secrets\vendly-service-account.json
FRONTEND_ORIGINS=http://localhost:5173
```

Initialize Admin once at application startup:

```python
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate(settings.service_account_path)
firebase_admin.initialize_app(cred, {"projectId": settings.project_id})
db = firestore.client()
```

Never send the service-account file to the frontend or commit it to Git.

## 3. Authentication decorator

The frontend sends `Authorization: Bearer <Firebase ID token>`. Flask verifies
the token and attaches the Firebase user to the request.

```python
from functools import wraps
from flask import request, jsonify, g
from firebase_admin import auth

def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        value = request.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            return jsonify(error="Authentication required"), 401
        try:
            g.user = auth.verify_id_token(value[7:])
        except Exception:
            return jsonify(error="Invalid or expired token"), 401
        return view(*args, **kwargs)
    return wrapped
```

After authentication, check the member document for `businessId` and required
permission. Authentication answers “who”; authorization answers “what may
they do”.

## 4. API conventions

Base URL: `http://127.0.0.1:5000/api/v1`.

```text
GET    /businesses/{businessId}/products
POST   /businesses/{businessId}/products
GET    /businesses/{businessId}/products/{productId}
PATCH  /businesses/{businessId}/products/{productId}
DELETE /businesses/{businessId}/products/{productId}

GET    /businesses/{businessId}/orders
POST   /businesses/{businessId}/orders
GET    /businesses/{businessId}/orders/{orderId}
PATCH  /businesses/{businessId}/orders/{orderId}/status
PATCH  /businesses/{businessId}/orders/{orderId}/waybill

GET    /businesses/{businessId}/analytics/overview
POST   /public/chat/sessions
POST   /public/chat/sessions/{sessionId}/messages
POST   /public/chat/sessions/{sessionId}/orders
```

Use `POST` for creating a resource, `PATCH` for changing selected fields and
`DELETE` for removal. Return JSON with a consistent error shape:

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Phone is invalid" } }
```

## 5. Product endpoint in small steps

```python
@app.post("/api/v1/businesses/<business_id>/products")
@require_auth
def create_product(business_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    price = data.get("sellingPrice")
    if not name or not isinstance(price, (int, float)) or price < 0:
        return error("VALIDATION_ERROR", "Name and valid price are required"), 400

    product = {
        "name": name,
        "sellingPrice": price,
        "categoryId": data.get("categoryId"),
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    ref = db.collection("businesses").document(business_id).collection("products").document()
    ref.set(product)
    return jsonify(id=ref.id, **product), 201
```

In the real service, this route calls a permission helper, validates all
fields, creates variants, and returns a serializable timestamp.

## 6. Safe multi-item order creation

The browser sends item IDs and quantities, not a trusted total:

```json
{
  "customer": {"name": "Kamal", "phone": "0771234567", "address": "Colombo"},
  "items": [{"productId": "p1", "variantId": "v36", "quantity": 2}]
}
```

The service must:

1. Load every product and variant inside a Firestore transaction.
2. Reject inactive products, missing variants or insufficient stock.
3. Calculate subtotal from current database prices.
4. Calculate delivery fee from district and total weight.
5. Allocate a unique order sequence for the business.
6. Decrease available stock and write inventory transactions.
7. Create the order and its item snapshots atomically.

```python
subtotal = sum(row["unitPrice"] * row["quantity"] for row in lines)
delivery_fee = calculate_delivery_fee(district, total_weight, courier)
total = subtotal - discount + delivery_fee
```

The API response should expose each amount separately:

```json
{
  "orderId": "ord123",
  "subtotal": 8000,
  "deliveryFee": 450,
  "discount": 0,
  "totalAmount": 8450,
  "status": "confirmed"
}
```

## 7. Frontend API helper

```js
export async function api(path, options = {}) {
  const token = await auth.currentUser?.getIdToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || "Request failed");
  return body;
}
```

## 8. Test each layer

```powershell
curl http://127.0.0.1:5000/api/v1/health
pytest
```

Test unauthorized requests, wrong-business access, invalid phone/address,
duplicate waybill numbers, concurrent stock deductions and multi-item orders.
Only after these tests pass should the frontend depend on the endpoint.
