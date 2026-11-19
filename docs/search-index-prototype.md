# Offline search index prototype and backfill plan

Status: experiment only. Production routes, records, Firebase configuration and
indexes are unchanged. No library or service was installed. Neither layout is
selected for production. The prototype has no Firebase client, file-data input,
project option or apply mode.

## Run the synthetic comparison

From the repository root, use the existing backend environment:

```bash
backend/.venv/bin/python backend/scripts/probe_search_index.py
```

This checks twelve fixed query cases against the current matcher on 6,003
synthetic records. It prints aggregate counts and fixed case labels only, with
no customer rows, query strings, identities or credentials. Other command-line
arguments, including `--apply`, are rejected.

The pure model reuses `search_records`, its sanitizer and permission helper.
Two-character tokens use exactly the existing string casefolding. Candidates
are checked by the original matcher; they do not become matches just because a
token exists. Sources must be supplied in existing server order. The model does
not implement Firestore collation, the physical queries or browser table sorting.

## Layouts compared

| Layout | Modeled data work | Additional work outside the read model |
|---|---|---|
| Current scan | Read complete 500-record pages until eight matches or exhaustion. | Existing metadata/permission checks. |
| Embedded tokens | Candidate query returns the source record with its token metadata. | Larger source documents/indexes; fields must be hidden from API responses; writer integration and readiness control. |
| Separate index records | Candidate index pages return source IDs; each page also fetches authoritative source records. | A separate record write/delete when searchable fields or rank change, plus storage, index and readiness work. |

The prototype counts full fetched pages, including records unused after the
eighth match. It also counts empty queries separately. The separate-record model
fetches source IDs per candidate page; it is not a denormalized result cache.

### Synthetic results

| Case label | Scan source records | Embedded source records | Separate index + source records |
|---|---:|---:|---:|
| SKU fragment | 6,003 | 2 | 4 |
| Multiple words | 6,003 | 2 | 4 |
| Phone fragment | 5,502 | 780 | 1,560 |
| Broad no-match | 6,003 | 6,000 | 12,000 |
| Common match | 1,500 | 1,500 | 3,000 |

These are modeled document counts, **not a Firebase bill or live benchmark**.
They exclude authentication/revision/manifest reads, index-entry work, network
latency and edition-specific billing. Empty queries are not free and their
counts are included separately in the JSON output; even equal document counts
can have different costs. No production savings percentage is established.

The fixture index contains 68,846 stored tokens and 137,806 raw UTF-8 token bytes
across 6,003 records. Raw token bytes exclude document/index overhead, existing
fields and names; they do not establish storage cost or quota compliance. Both
layouts model 6,003 initial backfill row writes. Embedded metadata can accompany
an existing source write; a separate index adds a record write for a searchable
field/rank change. Manifest writes and physical index-entry costs remain unknown.

## Fallback and safety checks in the model

- Missing, partial or mismatched-generation indexes use the complete source scan.
  Readiness must be the boolean `true`, not a truthy string.
- Oversized token sets use an overflow stream instead of truncation. Overflow
  and ordinary candidates merge by original rank, preserving the first eight.
- Overflow is not always cheap: a compact stress test reads 10 source records
  for a scan, 20 for embedded metadata and 40 combined for separate records,
  while returning the same eight matches. Both stream heads can prefetch pages.
- Source records with missing ordering fields keep their existing exclusion;
  archived customers consume reads but never result slots.
- Modeled membership lookup precedes data access. Tenant IDs come from the
  selected source container; record fields cannot select another tenant.
- Inactive/missing memberships and forbidden modules remain inaccessible in
  the model. Later-page failures raise rather than return a partial result.
- Failed draft builds do not mutate the source or previous index snapshot.

These checks assume accurate readiness/generation metadata and trusted source
snapshots. They do not verify a real distributed transaction, real Firebase
ID-token verification or complete production writer coverage. A writer bypassing
the metadata contract can still leave an index incomplete. Authentication stays
with the existing Flask gates if a future implementation is approved.

The 4,096-token threshold is experimental. A production design must account for
[Firestore document and index limits](https://firebase.google.com/docs/firestore/quotas),
including existing fields and index definitions. It must not reject previously
valid large records or silently hide matches. The field schema currently mirrors
the matcher for this experiment; production promotion requires a shared schema.

## Dry-run backfill plan — future work requiring approval

No live dry-run or backfill runner is included in this task. A read-only dry-run
still incurs reads and must target an explicitly approved project/database and
business set. Before implementing that runner:

1. Verify database edition, actual indexes and an approximate read/write budget.
   Confirm the chosen model is valid for that target. The installed SDK is not
   evidence of the live database edition or index settings.
2. Inventory only approved source collections with bounded snapshot reads.
   Count eligible records, missing ordering fields, invalid shapes, reserved-field
   collisions, token distributions, overflows and existing document sizes.
   Keep source values in process and print aggregate categories/counts only.
3. Compare layouts using representative query distributions and existing data
   shapes. Include common fragments, no matches, Unicode, repeated queries and
   peak write rates. Account for empty queries, source verification, metadata,
   index expansion and storage; do not select a layout from rare-query results.
4. Choose a schema and manifest protocol. Existing `mark_cache_changed` replaces
   a marker with `revision`; adding readiness fields there without changing all
   relevant writers would lose them. Readiness/generation fields in this model
   are illustrative, not a deployable schema or a free metadata operation.
5. Draft every affected writer change and tests before enabling indexed reads:
   creation, rename/contact/SKU/barcode/rank changes, archive/unarchive and
   deletion, including guest/import/mobile paths. Source/index publication must
   be atomic where required; all backend workers must participate. Do not send
   network requests inside Firestore transaction callbacks. Do not activate a
   design that rejects previously valid business writes when indexing fails;
   fallback/recovery must be tested first. Never blindly retry a committed
   stock/payment operation to repair an index.
6. A future apply runner must remain disabled by default and require explicit
   approval. It should update derived metadata only, use source version checks
   and retry concurrent changes, skip deleted records, keep resumable checkpoints
   and leave readiness false until coverage/parity is established. A backfill of
   metadata alone should not invalidate user-data caches for every processed row.
7. Gate activation on actual capacity/index tests, complete coverage, approved
   costs and parity with full-scan results at a controlled read point. Do not
   substitute a limited sample for complete backfill coverage. Keep a correct
   full-scan fallback and retain the existing response projections and ranking.
8. Roll back by disabling indexed reads first. Preserve source business data;
   cleanup of derived metadata/records requires its own approved plan. A backend
   rollback must not leave indexed reads active with incompatible writers.

Table paging, browser locale sorting, summary cards and financial aggregation
remain separate work. No top-level record cap or UI/feature change is part of
this experiment.

## Current limits

The live edition, record volumes, field distributions, physical index plans,
quotas, pricing, contention and mobile client code remain unverified. No external
search engine or Enterprise upgrade is approved. Continue using the committed
cache/scan implementation until a measured production design is approved.


Validation for this prototype: 59 focused checks and 1,078 backend tests pass;
all 12 frontend test files and build pass; lint retains 41 warnings.
