# Product cache revisions

Prepared locally. This document does not authorize production deployment.

## Cache behavior

Before using cached inventory, the web client calls
`GET /api/v1/businesses/{businessId}/inventory/version`. The endpoint verifies
the Firebase identity and current `inventory:read` membership, then reads
`businesses/{businessId}/_cacheVersions/products`.

An unchanged revision reuses the matching filtered product list in browser
memory. A different revision removes previous revision entries/pending loads
and fetches the requested list again. Time alone no longer expires product
data. Caches without revision tracking retain their existing expiry policy. Product mutations and
logout/account changes still invalidate cached entries; late old-session
revision responses cannot recreate them. No persistent disk cache is enabled.

Validation happens on existing product-load requests, including reopening an
inventory view or selector. This is not a background polling/push mechanism for
an already-open view. If authorization or revision verification fails, cached
inventory is not returned as an offline fallback.

## Write coverage and cost

The marker commits with the product data in the same Firestore transaction or
batch. Coverage includes product creation/edits/status/stock adjustments;
orders reserving/adding/releasing/selling stock; shop sales/reversals;
product/variant media; and approved product-review counters. Workbook imports
use the same product create/update services. Non-stock order transitions and
seller/rejected reviews do not change the product revision.

Both web and mobile writes use this Flask backend, as confirmed by the user.
Future writers must include the marker in their product write batch/transaction.
Direct Console edits or scripts bypassing these services are outside this
contract and require revision handling before being introduced.

An unchanged-cache validation reads the membership and revision documents
(two document lookups in the SDK tests), rather than the full inventory.
Each product-changing committed batch/transaction adds one small marker write.
This is a read/write cost tradeoff, not zero Firebase usage; high-volume
contention and actual billing have not been measured.

Cold caches and changed revisions still fetch the full requested list in this
phase. Page-only loading, bounded page caching, search indexing and efficient
financial summaries remain separate cost-reduction tasks. Reloading the web
app clears its memory cache and therefore requires another initial load.

## Rollout — separate approval required

1. Deploy the updated backend to **every** worker serving web/mobile writes.
   Stop/restart old workers and any older application jobs before enabling the
   new cache. Mixed old/new writers can leave the revision stale.
2. Confirm the version endpoint works for permitted staff and denies other
   tenants, removed members and members without inventory-read permission.
3. Serve the updated frontend and refresh existing tabs. Existing businesses
   start at revision `0`; the next product mutation creates their marker. No
   data backfill, new dependency, index or client-rule change is required.
4. Verify an unchanged view reuses product data; an edit, mobile order, sale,
   stock adjustment, import or image/rating update changes the marker; and
   logout/account switching removes cached data.

The mobile client source is absent from this repo. Its backend writes are
covered; adopting the version endpoint in its own cache requires its source.
Real browser/mobile tests, production load tests and deployment are pending.

Rollback must pair compatible frontend/backend versions and clear existing web
cache state. Do not keep the revision-based client active with older writers.
