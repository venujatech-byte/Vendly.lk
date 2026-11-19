# COD reconciliation order reads

Prepared locally as a BUG-07 cost-reduction follow-up. Deployment requires
separate approval.

COD reconciliation previously fetched every order and discarded non-delivered
orders in its builder. Its Firestore scan now applies the same exact
`fulfilmentStatus == "delivered"` check before fetching documents. The builder
retains its payment-method, positive-balance, settlement, overdue and total
calculations. Delivered orders without `createdAt` remain eligible.

The query remains scoped to the requested business. All delivered orders are
read through the existing 500-document snapshot pages, with no new total cap.
Orders and settlements retain one shared server read time, cursor ordering and
failure behavior; a failed later page cannot return a partial financial report.
The settlement collection is still scanned completely. Existing routes,
authorization, frontend/UI, exports and write behavior are unchanged.

An offline SDK test seeds 1,001 orders, including 10 delivered orders. The new
query returns those 10 order documents instead of 1,001, and produces the exact
same eight eligible reconciliation rows and summary as the original full-data
builder. The other two delivered orders remain excluded by the original
payment/balance checks. Metadata and settlement lookups are additional and
unchanged. These are synthetic returned-document counts, not production billing.

This saves order reads only when non-delivered orders exist. Businesses whose
orders are mostly delivered still scan most of that history. This does not add
stored aggregates, settlement filtering, report caching or page-only tables.
There are no new writes, dependencies, rules, indexes or migrations. The query
uses single-field equality; repository index configuration has no field
exemptions. Live index settings, actual savings and real clients remain unverified.

Validation includes complete reports past 2,000 records, snapshot consistency
under concurrent status/data changes, later-page errors and comparison against
the old builder for mixed statuses, missing status/date fields and paid orders.
Before deploying, verify the query in the target environment and compare the
same business's COD summary/rows with its current report. No production records
were read or changed for this task.
