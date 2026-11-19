# Customer cache revisions

Prepared locally; production deployment requires separate approval. This extends
[product cache revisions](product-cache-revisions.md) using the same shared
`cache_revision_service.py` helper. Product endpoint behavior and marker paths
remain unchanged.

## Behavior and coverage

Before returning a cached customer list, the web client calls
`GET /api/v1/businesses/{businessId}/customers/cache/version`. Firebase identity
and current `customers:read` membership are checked before reading
`businesses/{businessId}/_cacheVersions/customers`. The extra `cache/version`
path avoids overriding lookup of a customer whose ID is `version`.

Unchanged revisions retain complete customer lists and search variants in
session memory beyond the old 15/60-second expiry. Changed revisions detach old
cached/pending data and load the requested list again. Logout/account changes
clear the cache; a late pre-logout version response cannot start a new load.
Failed authorization or revision checks reject the request rather than returning
cached personal data. No disk persistence or offline fallback is enabled.

These backend writes publish the revision in the same transaction/batch:

- Customer creation, contact edits, notes and status changes.
- Order creation, including customer order counts and saved fraud warnings.
- Delivered/returned order customer totals, spend, tags and risk changes.
- Customer fraud reports, manual fraud-risk edits and fraud-list removal.
- Fraud reports raised against an order when its customer record exists.

Product-only changes do not alter the customer revision. Confirmation, packing,
shipping and cancellation do not alter it unless they change customer data.
Both web and mobile writes through this Flask backend are covered. Mobile's own
client cache is not changed; its source is absent from this repository.

Successful web customer/fraud mutations also invalidate the local customer
cache immediately. Failed mutations retain it. Existing customer search,
Unicode name order, table controls, exports and selectors remain unchanged.
The separate fraud-list request remains uncached.

## Costs and limits

An unchanged-cache check performs two document lookups: membership and revision.
Each customer-changing commit adds one marker write, with no marker read needed
to publish a new opaque revision. Thus an order can write both a product marker
and a customer marker. This can cost more than the former zero-read cache hits
inside the TTL; it avoids full-list reloads when data remains unchanged beyond
that TTL. Actual billing and shared-marker contention have not been measured.

The first load, a new search variant and a changed-revision load still scan the
requested customer list through bounded API pages. A browser reload clears
session memory. This does not implement page-only loading, indexed substring
search, per-record delta updates or background refresh of an already-open view.
Freshness is checked on the next existing customer-load request.

## Rollout and checks

Deploy all backend workers before serving the updated frontend. Old writers,
Console edits or scripts that bypass the revision helper can leave caches
stale. Existing businesses start at revision `0`; their next supported customer
write creates the marker. No migration, dependency, index or Firebase rule
change is required. Roll back compatible frontend/backend versions together.

Before production use, check web/mobile edits, delivery/return counts, fraud
risk changes, search, exports, account switching and revoked membership in real
clients. Automated offline SDK/API/cache tests cover those service boundaries,
atomic failures and permission guards; real browser/mobile and load tests remain
pending. Production deployment is not part of this change.
