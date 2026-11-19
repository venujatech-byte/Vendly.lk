# Analytics cache source revisions

Prepared locally; deployment requires separate approval. This BUG-16 follow-up
keeps cached analytics responsive to shared service writes, including guest
checkout and product/customer changes that do not bump the older route counter.

## Freshness contract

The web client opts into
`GET /api/v1/businesses/{businessId}/analytics/version?includeRevision=1`.
The endpoint retains Firebase identity, tenant membership and `analytics:read`
checks. It returns the existing numeric `analyticsVersion` plus an opaque
`analyticsRevision` fingerprint. Requests without the flag keep the original
numeric response and read cost, preserving existing client contracts.

The fingerprint combines the legacy business counter and the existing
`orders`, `products` and `customers` markers. Root metadata and the three markers
are read at the same server read time; markers use one batched SDK request.
Missing markers start at `0`, requiring no backfill. Version responses for the
new client prohibit HTTP caching. No report collection is scanned by this check.

The web cache uses business ID and fingerprint, detaches old revisions and
retains the existing 30-minute expiry. Time-dependent forecast periods and stock
age can change without a write, so this task does not extend the expiry.
Unchanged reports remain reusable until expiry; changed sources or the legacy
counter reload the report on the next existing analytics request. No background
refresh/polling or calculation, layout, text, API mutation or permission change
is introduced.

Identity changes reject late metadata/report responses, preventing stale
session data from being returned or cached. Failed metadata/permission checks
do not serve cached private reports. Complete report loads retain their existing
pending-request deduplication. No persistent disk cache or offline fallback is
added.

## Cost and coverage

An opted-in validation now reads five documents: membership, business metadata
and three markers, using three SDK RPCs. This adds three document reads compared
with the previous two-document check. There are no added Firebase writes; the
markers are already published atomically by the tracked service writers.
A changed/expired report still performs its existing complete report scans.
Actual billing and latency are not measured.

This covers changes tracked by those three source markers and the legacy
counter, including the monthly target fix. Other inputs without these markers,
such as notification-only changes, retain their existing counter/expiry policy
and need separate review. This is not stored aggregation or a fixed report read
budget. No dependency, index, Firebase rule or data migration is required.

## Rollout and verification

Upgrade every backend worker and existing source-marker writer before serving
the new web client. Old workers without the optional fingerprint will cause the
new client to reject freshness checks. Keep compatible versions together on
rollback and clear client cache state. Unsupported Console/script edits that
bypass markers remain outside the app-only write contract.

Both web and mobile use Flask, per user confirmation. Writes from either client
therefore affect the web fingerprint. Adopting this fingerprint in native
mobile caching requires its source, which is absent from this repository.

Offline SDK/API/client tests cover source changes without counter bumps,
legacy target invalidation, missing/unordered markers, pinned-time consistency,
read counts, authorization failures, expiry and logout races. Existing report
calculations/scans remain under the full regression suite. Real browser/mobile,
proxy behavior, production load and actual costs remain unverified. No
production deployment or live data access was performed.
