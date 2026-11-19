# Order cache revisions

Prepared locally; deployment requires separate approval. This reuses the
[product](product-cache-revisions.md) and [customer](customer-cache-revisions.md)
revision mechanism for the Orders list. No UI, table control, search field,
summary formula, payment calculation or cancellation policy is changed.

## Cache behavior

Before using cached orders, the web client calls
`GET /api/v1/businesses/{businessId}/orders/cache/version`. The endpoint verifies
the Firebase identity and current `orders:read` membership before reading
`businesses/{businessId}/_cacheVersions/orders`. This nested path preserves
lookup of an order whose ID is `version`.

The cache holds complete mapped lists per business, revision and existing
search/status/date/courier filter combination. Unchanged revisions reuse those
lists in session memory; a changed revision detaches previous cached/pending
entries and loads the requested list again. Each reuse rechecks read permission.
Failed authorization or revision checks reject the load rather than return
cached private contacts or payment data. Logout/account changes clear cache
state, including protection against late pre-logout version responses.

Orders retain independent in-flight requests so aborting an obsolete view or
filter cannot cancel another consumer's load. Completed values are shared, but
simultaneous cold loads can issue duplicate reads. Other cache users keep their
existing pending-request deduplication. A cancelled/failed paginated load does
not cache a partial list, and invalidated late responses cannot refill cache.
Successful web order/waybill/fraud/courier-issue mutations also invalidate local
order lists; failed mutations retain completed data.

## Write coverage

Each tracked order write publishes one opaque revision in the same existing
transaction or batch:

- Order creation, seller edits, all status transitions and item additions.
- Recorded payments, conversion to cash on delivery and receipt attachments.
- Order fraud reports, courier issues and generated waybills.
- Guest receipt email changes, verified guest-history links and chat claims
  that update an order's customer identity/email.

The guest email ownership update-time precondition is retained on the batch
write. Existing no-op operations do not create revisions without order writes.
Customer/product-only changes do not alter the order marker. COD settlements
remain separate documents and do not alter order-list records or this marker.

Both web and mobile writers use Flask, as confirmed by the user. Native mobile
cache adoption requires its source, which is absent from this repository.

## Costs and limits

An unchanged-list validation performs two document lookups: membership and the
revision. An order-changing commit adds one marker write and no marker read.
An order reservation may now write three markers: products, customers and orders.
Actual savings and contention on the per-business markers are unmeasured.

The first load, a previously unseen filter/search combination and a changed
revision still fetch all matching data through bounded scan pages. Browser
reload clears session memory. This does not implement page-only loading,
indexed substring search, per-record updates, disk persistence or offline access.
It checks freshness on the next existing Orders-load request, without background
polling or live refresh of an already-open view. Search, full-list sorting,
summary cards and exports keep their existing behavior.

## Rollout

Upgrade **every** Flask worker/writer before serving the new frontend. Console
edits, scripts or old workers bypassing the revision helper can leave cached
orders stale. Existing businesses start at revision `0`; the next supported
order write creates the marker. No migration, dependency, index or Firebase
rule change is required. Roll back compatible frontend/backend versions together.

Before production use, verify mobile/web order edits, payment/receipt updates,
waybills, guest email/history, search, totals, logout and revoked membership in
real clients. Automated offline tests exercise SDK commits, failures, ownership
preconditions, endpoint authorization/read counts and cache/cancellation behavior.
Real browser/mobile, production load tests and deployment remain pending.
