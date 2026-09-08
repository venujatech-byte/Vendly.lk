# Vendly Firestore Read Optimization — Actual Code Plan

This is the short implementation plan based on the current repository. The frontend calls Flask APIs; Firestore reads are performed in `backend/app/services`.

## Actual architecture

```text
React services → Flask API → backend/app/services → Firestore
```

Do not add direct Firestore queries to React. Local `useTablePagination()` only paginates data that has already been read.

## Confirmed hotspots

| Feature | Current code | Problem |
|---|---|---|
| Orders | `backend/app/services/order_service.py:227-255` | Up to 200 read, then Python filtering |
| Products | `backend/app/services/product_service.py:227-239` | Up to 200 read |
| Customers | `backend/app/services/customer_service.py:84-115` | Up to 200 read, then Python search |
| Chat sessions | `backend/app/services/message_service.py:65-99` | Entire business session list streamed |
| Chat messages | `backend/app/services/message_service.py:17-19` | Entire message subcollection read |
| Chat polling | `frontend/src/components/CustomerMessages.jsx:85-111` | Full lists reloaded every 8/5 seconds |
| Analytics | `backend/app/services/analytics_service.py:813-856` | Several collections read up to 1,000 |
| Ledger | `backend/app/services/analytics_service.py:1083-1110` | Multiple large collections rebuilt |

## Implementation order

### Phase 1 — Chat

Update:

- `backend/app/services/message_service.py`
- `backend/app/api/messages.py`
- `frontend/src/services/messageService.js`
- `frontend/src/components/CustomerMessages.jsx`

Use a descending, bounded message query:

```python
reference.collection("messages") \
    .order_by("createdAt", direction="DESCENDING") \
    .limit(20)
```

Return a cursor based on the last document. Add a “Show more history” request using `start_after()`. Reverse the descending result for display.

For seller conversations use:

```python
database.collection("publicChatSessions") \
    .where("businessId", "==", business_id) \
    .order_by("updatedAt", direction="DESCENDING") \
    .limit(10)
```

Backfill missing session summary fields before deleting the legacy full-message fallback at `message_service.py:75-80`.

### Phase 2 — Orders, inventory, and customers

Update the backend list functions, API endpoints, and frontend callers:

- Orders: `order_service.py:227-255`, `api/orders.py`, `orderService.js`, `OrdersPage.jsx:193-237`.
- Products: `product_service.py:227-239`, `api/products.py`, `productService.js`, `InventoryPage.jsx:154-180`.
- Customers: `customer_service.py:84-115`, `api/customers.py`, `customerService.js`, `CustomersPage.jsx:263-273`.

The API should return:

```json
{
  "rows": [],
  "nextCursor": "encoded-cursor-or-null",
  "hasMore": true
}
```

Use `page_size + 1` internally to determine `hasMore` without a count query. Replace local-only pagination in `OrderTable.jsx:93`, `InventoryTable.jsx:246`, and `CustomersPage.jsx:203`.

### Phase 3 — Reviews, fraud, analytics, and ledger

Reviews read up to 200 at `backend/app/services/review_service.py:197-225`. Fraud listing streams customers and reports at `backend/app/services/fraud_service.py:202-208`. Add backend pagination first.

Analytics and ledger need date-bounded reads short-term and persisted summary/ledger data long-term. Frontend table pagination alone will not fix these backend reads.

## Search limitations

Orders and customers currently filter free text after reading documents. Firestore cannot efficiently perform arbitrary substring matching. Use normalized prefix fields or a search service; do not claim that browser-side `.filter()` reduces reads.

## Index policy

`firestore.indexes.json` is empty. Add only indexes required by implemented queries, such as `businessId ASC, updatedAt DESC` for chat sessions. Do not blindly add all suggested indexes.

## Do not implement the old recommendations as written

- Direct Firestore access from React.
- `enableMultiTabIndexedDbPersistence()` as the main optimization.
- Unbounded client-side collection loading followed by local pagination.
- Generic root `orders`/`products` collections; this project uses nested business collections.
- Blindly adding every suggested index.

## Success criteria

- Chat sessions: at most 10 documents per request.
- Chat history: at most 20 messages per request.
- Orders/products/customers: one bounded backend query per requested page.
- Filter changes reset cursors.
- No complete chat-history reload every 5 seconds.
- No complete chat-list reload every 8 seconds.
- Analytics and ledger read volume is measured and bounded.
