# Bounded global search scans

Prepared locally as a BUG-07 cost-reduction follow-up. Deployment requires
separate approval. This changes backend read work, preserving the header's
existing eight results per permitted module, matching fields and result order.

## What changed

Global search now consumes lazy order, product and customer streams, stopping
each module after its eighth match. Streams reuse the existing consistent
500-document report batches and snapshot cursors. The batch size is not a
record cap: sparse searches keep reading later batches until eight matches are
found or the collection ends. Missing or short sanitized queries return the
same empty result without collection scans, after the API's normal identity
and tenant membership checks.

Ordering remains newest-first for orders, document-ID order for products and
name order for customers, including existing document-name tie breakers.
Matching still uses the existing Python casefold, substring and query sanitizer.
Archived customers remain excluded; archived products remain searchable.
Server-verified permissions are checked before constructing each module scan.

Existing list/export/catalogue callers exhaust these same streams into complete
lists. Public product callers retain their explicit caps. No table controls,
summary calculations, exports, browser cache policies or frontend files change.
No new cache, revision marker, write, dependency, index, schema or migration is
introduced by this task.

## Measured effect and limits

An offline SDK test seeds 1,001 documents in each module, all matching. The
previous complete scans return 3,003 documents; the new search returns the same
eight results per module after fetching 1,500 documents (one 500-document batch
per module). Membership/business metadata lookups are additional and unchanged.
These are document counts from the test transport, not production billing or
latency measurements.

A fetched batch is paid/read in full even when only its first eight rows are
needed. Sparse matches after record 1,000 and no-match searches can still scan
the entire dataset. This is not an indexed text search or a fixed per-query
read budget, and does not make repeated uncached searches free. Further savings
for sparse substring queries require the separate search/index design decision.
Page-only table loading and financial aggregation remain separate work.

## Validation and rollout

Offline tests compare results with complete-list scans, measure returned rows,
find matches past 1,000, retain equal-sort-value ordering and Unicode behavior,
and check archive exclusion, tenant scope and current module permissions.
Existing complete-list/report tests remain part of the full regression suite.
No production records are read or changed for this validation.

Deploy the backend only after approval. Older workers return the same results
but continue doing full scans. Verify ordinary, sparse, Unicode and no-match
header searches with owner/staff accounts in real clients before production
use. Real web/mobile, load tests and actual billing remain unverified.


The separate [search cache follow-up](search-cache-revisions.md) reuses repeated
queries using existing revisions and current read permissions. The scan behavior
and limits described above still apply when that cache misses.
