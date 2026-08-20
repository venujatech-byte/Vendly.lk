# Vendly REST API

Base URL during local development:

```text
http://127.0.0.1:5000/api/v1
```

Seller endpoints require a Firebase ID token:

```http
Authorization: Bearer FIREBASE_ID_TOKEN
```

## Account and staff

```text
GET    /me
POST   /businesses
GET    /businesses/{businessId}/members
POST   /businesses/{businessId}/members
PATCH  /businesses/{businessId}/members/{memberUid}
```

## Categories and inventory

```text
GET    /businesses/{businessId}/categories
POST   /businesses/{businessId}/categories
PATCH  /businesses/{businessId}/categories/{categoryId}

GET    /businesses/{businessId}/products
POST   /businesses/{businessId}/products
GET    /businesses/{businessId}/products/{productId}
PATCH  /businesses/{businessId}/products/{productId}
POST   /businesses/{businessId}/products/{productId}/media
POST   /businesses/{businessId}/products/{productId}/variants/{variantId}/adjust-stock
```

## Customers, couriers and orders

```text
GET    /businesses/{businessId}/customers
POST   /businesses/{businessId}/customers
GET    /businesses/{businessId}/customers/{customerId}
PATCH  /businesses/{businessId}/customers/{customerId}

GET    /businesses/{businessId}/couriers
POST   /businesses/{businessId}/couriers
PATCH  /businesses/{businessId}/couriers/{courierId}
POST   /businesses/{businessId}/couriers/recommend

GET    /businesses/{businessId}/orders
POST   /businesses/{businessId}/orders
GET    /businesses/{businessId}/orders/{orderId}
PATCH  /businesses/{businessId}/orders/{orderId}/status
POST   /businesses/{businessId}/orders/{orderId}/waybill
POST   /businesses/{businessId}/orders/{orderId}/fraud-report
POST   /businesses/{businessId}/orders/{orderId}/courier-issues
GET    /businesses/{businessId}/orders-export.xlsx
```

The order list accepts these optional query parameters:

```text
status, search, dateFrom, dateTo, courierId
```

## Reviews, notifications and analytics

```text
GET    /businesses/{businessId}/reviews
PATCH  /businesses/{businessId}/reviews/{reviewId}
GET    /businesses/{businessId}/notifications
PATCH  /businesses/{businessId}/notifications/{notificationId}/read
GET    /businesses/{businessId}/analytics/overview
GET    /businesses/{businessId}/search?q={query}
```

## Public mini-store and chatbot

```text
GET    /public/stores/{storeShortCode}
GET    /public/products/{productShortCode}
GET    /public/products/{productShortCode}/reviews
POST   /public/stores/{storeShortCode}/reviews
POST   /public/chat/sessions
POST   /public/chat/sessions/{sessionId}/messages
POST   /public/chat/sessions/{sessionId}/orders
```

Chat message and checkout requests must include the secret returned when the
session was created:

```http
X-Chat-Session-Token: SESSION_TOKEN
```
