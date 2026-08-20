# Vendly Backend: Learn It and Rebuild It

This guide explains the backend in this folder in the order a beginner should study it. The backend is a **Flask REST API**. It uses **Firebase Admin SDK** to read and write Firestore. The React frontend never talks directly to Firestore; it calls Flask, and Flask checks the user and performs the database operation.

## 1. Request flow

```text
React page
  -> fetch('/api/...')
Flask route (backend/app/api)
  -> authentication and permission checks
Service function (backend/app/services)
  -> validation, calculations, Firestore reads/writes
Firestore
  -> serialized JSON response
React updates its state and re-renders
```

Keep this separation: routes should receive HTTP data, services should contain business rules, and database access should stay inside services.

## 2. Important folders

| Folder/file | Purpose |
|---|---|
| `run.py` | Local development entry point. |
| `app/__init__.py` | Creates Flask, enables CORS, initializes Firebase, registers routes. |
| `app/api/` | HTTP endpoints grouped by feature: products, orders, customers, couriers, etc. |
| `app/services/` | Business logic and Firestore operations. |
| `app/core/` | Shared errors, authorization, authentication, rate limiting, serialization. |
| `app/config.py` | Reads environment variables. |
| `tests/` | API and service tests. |
| `.env` | Local secrets; never commit this file. |

## 3. Start locally

From `backend` in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

The API normally runs at `http://127.0.0.1:5000`. Install dependencies with:

```powershell
pip install -r requirements.txt
```

## 4. Environment and Firebase

The backend reads values such as Firebase project ID, service-account credentials, CORS origins, and API settings from `.env`. The service-account JSON must stay private. A production host should receive these values as platform secrets instead of using a committed file.

The Firebase Admin SDK is initialized once when Flask starts. It creates a Firestore client. Every service receives that client as `database` and uses paths scoped to a business:

```text
businesses/{businessId}
  products/{productId}
  productVariants/{variantId}
  orders/{orderId}
  customers/{customerId}
  couriers/{courierId}
  categories/{categoryId}
  notifications/{notificationId}
```

This structure prevents one seller from seeing another seller's records.

## 5. Authentication and permissions

The React app signs the seller in with Firebase Authentication and sends a Firebase ID token in the `Authorization: Bearer <token>` header. Flask verifies that token in `app/core/authentication.py`.

The authorization layer then:

1. gets the authenticated Firebase UID;
2. finds the seller membership for the requested business;
3. checks the membership status;
4. checks a permission such as `products:read`, `products:write`, or `orders:write`;
5. passes the verified user to the route.

Never trust a `businessId` supplied by the browser without checking membership.

## 6. How to create an endpoint

### Route

In `app/api/products.py`:

```python
@products_blueprint.get("/businesses/<business_id>/products")
@require_permission("products:read")
def list_products_route(business_id):
    user = current_user()
    products = list_products(get_database(), business_id)
    return jsonify({"products": products})
```

The route is intentionally small. It does not calculate stock or construct Firestore paths itself.

### Service

```python
def list_products(database, business_id, category_id=None, status=None):
    reference = (
        database.collection("businesses")
        .document(business_id)
        .collection("products")
    )
    snapshots = reference.stream()
    products = [serialize_snapshot(snapshot) for snapshot in snapshots]
    if category_id:
        products = [p for p in products if p.get("categoryId") == category_id]
    if status:
        products = [p for p in products if p.get("status") == status]
    return products
```

For a new feature: add validation, calculations, and database writes to a service; expose it with a route; then add a frontend service function.

## 7. Validation and errors

Validation helpers in `app/services/numbers.py` and `app/services/text.py` reject empty, oversized, negative, or malformed input. Convert `ValueError` into `ApiError` with a safe public message. The Flask error handler converts `ApiError` into JSON such as:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Selling price must be greater than zero."
  }
}
```

Do not return Python tracebacks or Firebase credentials to the browser.

## 8. Products, variants, and inventory

`product_service.py` validates the main product, then validates each size variant. A variant owns its SKU, barcode, size, price, cost, weight, and stock. A product's total stock is calculated from its variants.

Important rules:

- product and variant barcodes must be unique within a seller;
- stock must not become negative;
- stock changes go through an adjustment function;
- every adjustment creates an inventory audit record;
- deleting a product archives it instead of permanently deleting history;
- media is stored as a URL and the URL is saved in the product's `media` array.

Use Firestore transactions whenever an operation changes both stock and an order, because two customers could order the same item at the same time.

## 9. Creating an order

`order_service.py` follows this sequence:

1. validate customer, address, phone, items, payment, and discount;
2. load every requested variant;
3. choose a courier or validate the selected courier;
4. calculate subtotal, delivery fee, tax, discount, total, and total weight;
5. run a Firestore transaction;
6. re-read variants inside the transaction;
7. verify available stock;
8. decrease available stock and increase reserved stock;
9. save an item snapshot (name, SKU, price, and image URL) inside the order;
10. create the order and notification;
11. update the seller's order sequence;
12. return the serialized order.

Store prices in minor units (for example, LKR 1,899.00 becomes `189900`) to avoid floating-point money errors.

## 10. Order status changes

`update_order_status` checks allowed transitions, for example `confirmed -> packed -> shipped -> delivered`. It updates the order and writes a status-history record. When an order is delivered or returned, courier statistics are updated. Stock restoration for a returned order must happen in the same transaction as the status change.

## 11. Couriers and delivery fees

Each courier stores first-kilogram price, extra-kilogram price, district surcharges, delivery time, success rate, and return rate. The delivery calculation is:

```text
fee = first 1 kg price
    + ceil(extra grams / 1000) * extra 1 kg price
    + district surcharge
```

Courier recommendation scores price, success rate, return rate, and courier branch problems. Keep this calculation in `courier_service.py`, not in a React component.

## 12. Waybills

Waybills are generated transactionally. The backend checks that the order is ready, obtains the next courier sequence, creates a waybill record, stores the number on the order, and increments the sequence. The order page can then print the waybill. A waybill search is just an order search because `order_service.py` includes `waybillNumber` in its search fields.

## 13. Chatbot and public storefront

Public routes use a seller short code instead of a seller ID. The public catalog service verifies that the link is active and returns only that seller's active products. The chat service keeps a session containing messages, selected items, customer details, and the current conversation stage.

The normal flow is:

```text
welcome -> product information -> product/category cards
        -> selection and quantity -> customer details
        -> validation -> order summary -> customer confirmation
        -> transactional order creation
```

The AI may explain a product, but product price, stock, delivery fee, and order creation must come from the database and validated backend code.

## 14. Frontend-to-backend connection

The React service files in `frontend/src/services` call the API. `apiClient.js` adds the base URL and Firebase token, parses JSON, and throws a readable error. A page should call a service function and update React state; it should not construct Firestore paths.

Example:

```javascript
const response = await apiRequest(`/businesses/${businessId}/products`, {
  method: "POST",
  body: productData,
});
return mapProductForInventory(response.product);
```

## 15. Testing your own feature

For every new backend feature:

1. test validation failures;
2. test permission failures;
3. test the successful service function with a fake database;
4. test concurrent/transaction-sensitive code;
5. test the Flask route response shape;
6. run:

```powershell
\.venv\Scripts\python.exe -m pytest -q
```

## 16. Recommended coding order for future features

1. Write the Firestore document shape.
2. Write validation helpers.
3. Write the service function.
4. Add permission names.
5. Add the API route.
6. Add a frontend service wrapper.
7. Connect page state and loading/error UI.
8. Add tests.
9. Run the backend tests and frontend lint/build.

## 17. Security checklist

- Keep `.env` and Firebase service-account keys out of Git.
- Verify Firebase ID tokens on every protected request.
- Check seller membership and permission for every business request.
- Never trust client-side prices, totals, stock, or seller IDs.
- Recalculate totals on the server.
- Use Firestore transactions for stock, order sequences, and waybills.
- Validate uploaded file type and size.
- Rate-limit public chat endpoints.
- Return safe error messages.
- Use HTTPS in production and restrict CORS to your real domains.

The best way to study this backend is to trace one feature end-to-end: start at `frontend/src/services/productService.js`, follow the matching route in `backend/app/api/products.py`, then read the called function in `backend/app/services/product_service.py` and its tests.
