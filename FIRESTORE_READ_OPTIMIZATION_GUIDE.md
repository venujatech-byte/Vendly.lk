# Firestore Read Optimization Guide — Vendly

This guide is based on the current Vendly codebase. The earlier version assumed React queried Firestore directly. Vendly actually uses:

```text
React services → Flask API → backend/app/services → Firestore
```

Frontend entry points are `frontend/src/services/orderService.js`, `productService.js`, `customerService.js`, and `messageService.js`. Firestore reads are mainly in `backend/app/services`.

## Confirmed read hotspots

- Orders: `backend/app/services/order_service.py:227-255` reads up to 200 orders, then filters in Python. `frontend/src/components/OrderTable.jsx:93` paginates locally.
- Products: `backend/app/services/product_service.py:227-239` reads up to 200 products. `frontend/src/components/InventoryTable.jsx:246` paginates locally.
- Customers: `backend/app/services/customer_service.py:84-115` reads up to 200 customers, then filters search in Python. `frontend/src/pages/CustomersPage.jsx:203` paginates locally.
- Chat sessions: `backend/app/services/message_service.py:65-99` streams every session. `frontend/src/components/CustomerMessages.jsx:85-89` repeats this every 8 seconds.
- Chat messages: `backend/app/services/message_service.py:17-19` reads the complete message subcollection. `CustomerMessages.jsx:91-111` repeats this every 5 seconds.
- Analytics: `backend/app/services/analytics_service.py:813-856` reads several collections up to 1,000 documents each.
- Ledger: `backend/app/services/analytics_service.py:1083-1110` reads multiple collections up to 1,000/2,000 documents.

Local React pagination does not reduce Firestore reads.

## Required implementation pattern

Implement pagination in the Flask API and Firestore service functions:

1. Receive `limit` and a cursor from the frontend.
2. Apply Firestore filters and ordering before `limit()`.
3. Use `start_after()` with the last `DocumentSnapshot`.
4. Return rows, `nextCursor`, and `hasMore`.
5. Store the cursor for the active filter/sort combination.
6. Reset the cursor when filters or sorting change.

Example backend shape:

```python
query = (
    database.collection("businesses")
    .document(business_id)
    .collection("orders")
    .order_by("createdAt", direction="DESCENDING")
)
if status:
    query = query.where("fulfilmentStatus", "==", status)
if cursor:
    query = query.start_after(cursor)
snapshots = list(query.limit(page_size + 1).stream())
```

Use a serialized Firestore document cursor, not only a timestamp, when duplicate timestamps are possible.

## Chat: highest priority

Modify:

- `backend/app/services/message_service.py:17-19,65-116`
- `backend/app/api/messages.py`
- `frontend/src/services/messageService.js`
- `frontend/src/components/CustomerMessages.jsx:85-111`

### Chat sessions

Replace the unbounded session stream with a bounded query:

```python
query = (
    database.collection("publicChatSessions")
    .where("businessId", "==", business_id)
    .order_by("updatedAt", direction="DESCENDING")
    .limit(10)
)
```

Add cursor pagination and return `nextCursor`. Remove full-list polling or make it bounded and active-chat-only.

### Chat messages

Replace `_message_rows()` with a latest-20 query:

```python
messages_query = (
    reference.collection("messages")
    .order_by("createdAt", direction="DESCENDING")
    .limit(20)
)
```

Reverse the result for display. Add a `before` cursor to the messages endpoint and load older messages only after “Show more history”. Do not reload the full conversation every 5 seconds.

The legacy fallback at `message_service.py:75-80` reads all messages for sessions without `lastMessage`. Backfill `lastMessage`, `lastMessageRole`, `lastMessageAt`, and `updatedAt` before removing that fallback.

## Orders, products, and customers

Update these backend functions and their API/frontend callers:

- Orders: `order_service.py:227-255`, `api/orders.py`, `orderService.js`, `OrdersPage.jsx:193-237`.
- Products: `product_service.py:227-239`, `api/products.py`, `productService.js`, `InventoryPage.jsx:154-180`.
- Customers: `customer_service.py:84-115`, `api/customers.py`, `customerService.js`, `CustomersPage.jsx:263-273`.

Move supported equality/date filters into Firestore before `limit()`. Replace local-only pagination in `OrderTable.jsx:93`, `InventoryTable.jsx:246`, and `CustomersPage.jsx:203` with API pagination.

The current free-text filters run after reading documents (`order_service.py:248-255` and `customer_service.py:106-115`). Arbitrary substring search requires normalized prefix fields or a dedicated search service; a browser `.filter()` does not reduce reads.

## Reviews, fraud, analytics, and ledger

Reviews read up to 200 records at `backend/app/services/review_service.py:197-225`. Fraud listing streams customers and reports at `backend/app/services/fraud_service.py:202-208`. Add backend pagination before changing the React tables.

Analytics and ledger cannot be fixed by frontend pagination. Short-term, add date-bounded queries where product behavior permits. Long-term, maintain summary documents/daily aggregates and persist ledger entries so requests do not rebuild data from several large collections.

## What not to apply from the old guide

- Do not add direct Firestore queries to React.
- Do not add `enableMultiTabIndexedDbPersistence()` as the main fix; application data is loaded through Flask.
- Do not use root-level `orders` or `products`; this project uses `businesses/{businessId}/...` subcollections.
- Do not rely on `useTablePagination()` to reduce reads.
- Do not add every suggested index in advance.

## Indexes

`firestore.indexes.json` is currently empty. Add indexes only after implementing actual queries and confirming requirements. Likely candidates include `publicChatSessions: businessId ASC, updatedAt DESC` and equality-filter-plus-sort indexes for orders/products. Normal Firestore indexes do not solve arbitrary substring search.

## Validation checklist

1. Orders/products/customers read one bounded backend page, not 200 documents for local pagination.
2. The next page performs one cursor query and filter changes reset the cursor.
3. Opening a chat reads at most 20 messages.
4. Older messages are fetched only after the history action.
5. The chat list does not reload all sessions every 8 seconds.
6. Typing in the message box causes no Firestore operation.
7. Analytics and ledger read counts are measured separately.
