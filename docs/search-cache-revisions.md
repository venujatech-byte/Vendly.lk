# Revision-aware global search cache

Prepared locally; deployment requires separate approval. This adds a bounded
browser-memory cache on top of the [bounded global search scans](global-search-reads.md).
Server-side matching, result ordering, the eight-result limit and module gates
remain the same. No UI or financial behavior changes.

## Freshness and permission checks

Before returning any cached search result, the web client calls
`GET /api/v1/businesses/{businessId}/search/cache/version`. The backend verifies
Firebase identity and current active tenant membership, then reads existing
product/customer/order revision documents for readable modules only. A stable
SHA-256 fingerprint includes both those module names and their revisions.
Different read permissions therefore produce different fingerprints even when
all data markers are unchanged or missing. Missing markers use existing `0`
bootstrap behavior. No new marker, write, dependency, index or migration is added.

The version response has `Cache-Control: no-store` so an HTTP cache cannot
substitute a stale authorization/freshness check. The fingerprint is metadata,
not a credential; authentication and tenant/module authorization remain required.

Unchanged fingerprints reuse completed results keyed by business and exact raw
query. Matching and sanitization still happen on the server, including Unicode
casefold and partial phone/SKU matching. Changed data or permissions detach old
cached entries and pending loads. Revisions already cover both web and mobile
writers through Flask. Native mobile client caching is not changed.

## Permission changes between requests

The new web client opts into `includeScope=1` on the existing search endpoint.
Only opted-in responses include the module scope authorized for that data
request; existing client response envelopes are preserved. If that scope differs
from the earlier version check, the response is returned as an ordinary current
server-authorized result but is never cached under the earlier scope. This
prevents temporarily broader permissions from poisoning a narrower cache after
permissions change back. Older responses lacking scope also remain uncached.

Failed authorization, revision checks or data loads never fall back to stale
cached results. Logout/account changes clear the shared cache. Old-session
version/data responses are rejected, cannot repopulate it and cannot evict a new
session's cache through an old scope mismatch. Each search owns its cancellation
signal; simultaneous cold requests are independent rather than sharing an abort.

## Memory and costs

At most 50 completed query results are retained per business. The oldest stored
result is evicted when that bound is exceeded; cache hits do not extend its
insertion order. Time alone does not expire retained results. Reloading the
browser clears memory, and no persistent disk cache or offline fallback is enabled.
Other module/tenant caches and pending requests are not pruned by this bound.

A repeated cached query costs one membership read plus one marker read for each
readable module: 1–4 document lookups. With no searchable modules, the web client
returns empty results after that check without another API request. Otherwise,
a new, changed or evicted query pays that validation overhead in addition to its
ordinary authenticated search scan. No extra Firebase writes are needed.

Savings depend on repeated queries and collection sizes; small datasets and
mostly new queries can cost more. Production billing/latency have not been
measured. First/new queries, data changes, cache eviction and browser reload
still cause scans; sparse/no-match scans can read the entire dataset. This is
not indexed search, delta synchronization or a fixed per-query read budget.
Already-open results refresh on the next existing search request, without new
polling or push behavior.

## Rollout and verification

Upgrade every Flask worker, including the existing product/customer/order
revision writers, before serving the updated frontend. Unsupported direct
Console/script writes or old workers can leave revisions stale. The version
route must be available on all workers; older search responses without opted-in
scope safely skip caching. Roll back compatible versions and clear client cache
state together. No production deployment is authorized by this document.

Offline tests cover allowed marker reads, permission/data fingerprint changes,
identity/tenant guards, envelope compatibility, the permission-change race,
logout, request cancellation, failed loads and the 50-query bound. Real browser/
mobile, proxy behavior, load tests and actual savings remain unverified; mobile
source is not present in this repository.
