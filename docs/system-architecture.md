# Vendly.lk System Architecture

## 1. Architecture decision

Vendly uses a three-tier architecture:

1. **Presentation tier** — React and Vite seller dashboard, mini-store, and chatbot UI.
2. **Application tier** — Flask REST API for validation, permissions, calculations, workflows, notifications, and AI-provider access.
3. **Data tier** — Firebase Authentication, Cloud Firestore, and Firebase Storage.

The React application may read authentication state, but it must not authoritatively generate order numbers, calculate payable totals, change stock, assign permissions, or make fraud decisions. Those operations belong to Flask.

## 2. Repository layout

```text
vendly-lk-web/
├── docs/
│   ├── product-roadmap.md
│   └── system-architecture.md
├── frontend/
│   ├── assets/designs/
│   └── src/
└── backend/
    ├── app/
    │   ├── api/
    │   ├── core/
    │   ├── repositories/
    │   ├── schemas/
    │   └── services/
    ├── tests/
    ├── .env.example
    ├── requirements.txt
    └── run.py
```

## 3. Authentication and tenancy

- Firebase Authentication identifies a person with a stable `uid`.
- A person can later belong to one or more businesses.
- Every seller-owned record contains a `businessId` or lives below `businesses/{businessId}`.
- Membership documents define the user's role and permissions.
- Flask verifies every Firebase ID token and business membership before accessing business data.
- Public catalogue and chatbot requests use short public codes. They never accept an unrestricted `businessId` from the browser as proof of access.

Initial roles:

- `owner`
- `admin`
- `order_manager`
- `inventory_manager`
- `support`
- `viewer`

## 4. Firestore collections

```text
users/{uid}
businesses/{businessId}
businesses/{businessId}/members/{uid}
businesses/{businessId}/categories/{categoryId}
businesses/{businessId}/products/{productId}
businesses/{businessId}/productVariants/{variantId}
businesses/{businessId}/inventoryTransactions/{transactionId}
businesses/{businessId}/customers/{customerId}
businesses/{businessId}/orders/{orderId}
businesses/{businessId}/payments/{paymentId}
businesses/{businessId}/couriers/{courierId}
businesses/{businessId}/courierEvents/{eventId}
businesses/{businessId}/conversations/{conversationId}
businesses/{businessId}/conversations/{conversationId}/messages/{messageId}
businesses/{businessId}/reviews/{reviewId}
businesses/{businessId}/notifications/{notificationId}
businesses/{businessId}/auditLogs/{auditLogId}
shortLinks/{shortCode}
publicChatSessions/{sessionId}
```

## 5. Core document shapes

### User

```text
uid
displayName
email
photoUrl
defaultBusinessId
status
createdAt
updatedAt
```

### Business

```text
name
ownerUid
shortCode
logoPath
phone
email
address
currency                 "LKR"
timezone                 "Asia/Colombo"
status                   "active"
nextOrderSequence
createdAt
updatedAt
```

### Membership

```text
uid
role
permissions[]
status
joinedAt
```

### Category

```text
name
slug
description
status
sortOrder
createdAt
updatedAt
```

Product count and stock totals are calculated or maintained by trusted backend processes. They are not manually entered into a category.

### Product

Each colour is a separate product. Size is the only initial variant layer.

```text
name
slug
colourName
colourHex
categoryId
brand
supplierId
description
aiDescription
taxCategory
hasSizes
skuPrefix
costPrice
sellingPrice
compareAtPrice
weightKg
lowStockThreshold
totalStock
reservedStock
availableStock
primaryMediaPath
media[]
status
shortCode
createdAt
updatedAt
```

### Product variant

```text
productId
size
sku
barcode
costPrice
sellingPrice
weightKg
stockOnHand
stockReserved
stockAvailable
status
createdAt
updatedAt
```

A product without sizes receives one default variant. This keeps stock and order-item logic consistent.

### Inventory transaction

Inventory transactions are immutable.

```text
productId
variantId
type                     receive, reserve, release, sell, return, adjust, transfer
quantity
stockBefore
stockAfter
orderId
reference
reason
performedBy
createdAt
```

### Customer

```text
name
normalizedPhone
email
addresses[]
tags[]
privateNotes
completedOrderCount
returnedOrderCount
totalSpent
riskLevel
status
createdAt
updatedAt
```

Private notes must never be returned by public APIs or chatbot catalogue endpoints.

### Order

```text
orderNumber
customerId
customerSnapshot
items[]
subtotal
discountTotal
deliveryFee
taxTotal
totalAmount
paidAmount
balanceAmount
paymentMethod
paymentStatus
fulfilmentStatus
deliveryAddress
district
courierId
courierSnapshot
totalWeightKg
source
privateNote
assignedStaffUid
waybillNumber
stockReservationStatus
createdBy
createdAt
updatedAt
```

Every order item stores product, variant, SKU, price, cost, weight, tax, and discount snapshots. Historical orders must not change when a product is edited.

## 6. Order creation transaction

Flask creates an order in one trusted workflow:

1. Verify Firebase token and business membership.
2. Validate the customer and delivery address.
3. Load active product variants from Firestore.
4. Check available stock.
5. Calculate subtotal, discounts, taxes, weight, and delivery fee.
6. Allocate the next order number in a Firestore transaction.
7. Create the order with immutable item snapshots.
8. Reserve stock and create inventory-transaction records.
9. Create a seller notification.
10. Return the server-calculated order.

React submits requested product IDs, variant IDs, and quantities. It never submits authoritative prices or totals.

## 7. Media storage

Firebase Storage paths:

```text
businesses/{businessId}/products/{productId}/images/{fileId}
businesses/{businessId}/products/{productId}/videos/{fileId}
businesses/{businessId}/reviews/{reviewId}/{fileId}
businesses/{businessId}/returns/{returnId}/{fileId}
businesses/{businessId}/chat/{conversationId}/{fileId}
```

Firestore stores file metadata and Storage paths, not base64 file content.

## 8. Chatbot architecture

Public entry points:

- `/s/{sellerShortCode}` — seller mini-store and seller-specific chatbot.
- `/p/{productShortCode}` — product page and product-specific chatbot context.

Chat flow:

1. Resolve the short code through Flask.
2. Confirm that the business and product are active.
3. Create or resume a restricted public chat session.
4. Load only approved catalogue, media, reviews, delivery rules, and public seller information.
5. Use deterministic application logic for catalogue selection, cart contents, customer details, validation, totals, and order submission.
6. Use an AI provider only for natural-language understanding and product-information responses.
7. Revalidate every cart item and amount in Flask before creating the order.

The chatbot AI may not directly write orders, change stock, or decide fraud status.

## 9. API boundaries

Initial authenticated seller endpoints:

```text
GET    /api/v1/me
POST   /api/v1/businesses
GET    /api/v1/businesses/{businessId}

GET    /api/v1/businesses/{businessId}/categories
POST   /api/v1/businesses/{businessId}/categories
PATCH  /api/v1/businesses/{businessId}/categories/{categoryId}

GET    /api/v1/businesses/{businessId}/products
POST   /api/v1/businesses/{businessId}/products
GET    /api/v1/businesses/{businessId}/products/{productId}
PATCH  /api/v1/businesses/{businessId}/products/{productId}

GET    /api/v1/businesses/{businessId}/customers
POST   /api/v1/businesses/{businessId}/customers

GET    /api/v1/businesses/{businessId}/orders
POST   /api/v1/businesses/{businessId}/orders
GET    /api/v1/businesses/{businessId}/orders/{orderId}
PATCH  /api/v1/businesses/{businessId}/orders/{orderId}/status
```

Initial public endpoints:

```text
GET    /api/v1/public/stores/{shortCode}
GET    /api/v1/public/products/{shortCode}
POST   /api/v1/public/chat/sessions
POST   /api/v1/public/chat/sessions/{sessionId}/messages
POST   /api/v1/public/chat/sessions/{sessionId}/orders
```

## 10. Security rules

- Firebase ID tokens are verified by Firebase Admin in Flask.
- The backend service account is never placed in React or a `VITE_*` variable.
- Browser Firestore rules deny authoritative business-data writes.
- Storage rules restrict seller media by business membership and public reads to explicitly published media.
- Secrets are loaded from backend environment variables or the deployment secret manager.
- CORS permits only configured local, preview, and production frontend origins.
- Rate limiting applies to authentication-sensitive and public chatbot endpoints.
- Audit logs record status, stock, permission, courier, and payment changes.

## 11. First end-to-end milestone

The first milestone is deliberately small but production-shaped:

1. Existing Firebase login and business onboarding.
2. Flask token verification and `/api/v1/me`.
3. Category CRUD through Flask.
4. Product creation matching the approved Add Product design.
5. Firestore-backed inventory table.
6. Manual multi-item order creation matching the approved Add Order design.
7. Server-calculated totals and stock reservation.
8. Firestore-backed order table.

After this milestone is verified, the chatbot will use the same product, customer, order, and stock services instead of implementing a separate order system.

## 12. Authenticated application bootstrap

The dashboard must not render protected pages while its identity and business
context are unresolved. Startup follows this sequence:

```text
React mounts
  -> Firebase onAuthStateChanged resolves
  -> if signed in, Flask /me loads account, business and membership
  -> AuthContext publishes one complete state
  -> App renders login, setup, or the protected dashboard
```

`isAuthLoading` covers both the Firebase check and the first Flask account
request. Firebase listener errors and Flask account errors are stored
separately, because a backend outage does not invalidate a Firebase session.
During either check, `AppLoadingScreen` owns the full viewport. An error uses
the same screen with a retry action; do not solve bootstrap races with a forced
browser refresh.

## 13. Analytics read model

Analytics is a read-only projection over operational records, not a second
source of truth. `analytics_service.py` derives the overview from orders,
products, customers, notifications and warranty claims. The transaction ledger
combines online orders, shop sales, warranty deductions and inventory purchase
transactions into a chronological balance. React obtains these through
`/analytics/overview` and `/analytics/ledger`; workbook generation remains in
Flask so permissions and monetary formatting are consistent.

## Public chatbot checkout state

The chatbot stores its current state and contact draft in Firestore. The draft includes one required phone, an optional second phone, street address, district, nearest city, and an optional delivery note. Flask owns validation and order creation; React only sends replies and renders the returned draft. The confirmed order reuses the standard customer, order, delivery-price, fraud-warning, and stock transaction services.
