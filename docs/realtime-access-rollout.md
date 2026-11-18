# Private Realtime Database access (SEC-02)

This is a prepared local change. No production migration or rules deployment is
authorized by this document. Obtain approval for the specific production steps.

## What changes

Before: `chatMessages/$sessionId`, business notifications and customer order
updates allow public reads when a caller knows the path. The seller inbox's
`businessChatActivity` subscription has no matching read grant.

After: all client writes remain denied. Clients cannot read or write `_access`.

| Path | Required identity/access |
|---|---|
| `chatMessages/$sessionId` | The session's customer UID, or a current member of that business with `customers:read` |
| `businesses/$businessId/notifications` | An active member of that business, matching the existing notifications API |
| `businessChatActivity/$businessId` | A current business member with `customers:read` |
| `customerOrderUpdates/$shortCode/$customerKey` | The authenticated UID must equal `$customerKey` |

Anonymous Firebase accounts continue to be valid customers. Unverified password
accounts cannot read private records. Account deletion writes a global read
revocation before cleanup, so that account's remaining ID tokens lose RTDB access.
This does not replace a separate operational process for Firebase Console/Admin
SDK account disable/revoke actions outside Vendly: mark the affected UID disabled
in `_access/disabledUsers` too, or outstanding ID tokens may remain valid until
Firebase expires them. Never grant clients write access to this metadata.

Legacy order updates indexed by customer document ID or order ID are no longer
public. The existing storefront listens at the Firebase UID path. The API
continues to verify the existing guest session token independently.

Flask mirrors authoritative membership/session snapshots into `_access/members`
and `_access/chats`. Firestore server read timestamps order writes, including
deletion tombstones, so delayed snapshots cannot restore an older grant.
Membership edits first take a server-only permission-update lock, then deny only
the rights being reduced before changing Firestore. Unchanged subscriptions stay
live. Other refreshes cannot clear a pending update; only the writer owning it
can publish the committed state. Dry-run pendingMemberships counts interrupted
updates that need reconciliation.
New and restored chat listeners wait for the server's successful ownership claim.

## Local verification

From `backend`, run `.venv/bin/python -m pytest -q`. The normal unit suite mocks
the new permission boundary; its dedicated tests restore the real code against
an in-memory store and exercise revocation, stale writes and failed syncs.

Start the official RTDB emulator on `127.0.0.1:9000` with a demo project. For
example, with an existing Firebase CLI installation, from the repository root:

```bash
firebase emulators:start --only database --project demo-vendly-rules
```

Then, from `frontend`:

```bash
FIREBASE_DATABASE_EMULATOR_HOST=127.0.0.1:9000 npm run test:rules
npm run lint
npm run build
node --test src/data/*.test.mjs src/services/*.test.mjs
```

The rules test refuses non-loopback hosts and always uses the isolated
`demo-vendly-rules` namespace. It uploads this repository's exact rules and dummy
fixtures through emulator-only admin access. It tests anonymous ownership,
other tenants, staff permissions, removed/blocked members, unverified accounts,
metadata forgery, customer updates and cancellation of an already-open listener.
It adds no new application or testing dependency.

## Production sequence — requires separate approval

1. Back up the currently deployed rules and RTDB data; confirm the target project.
2. Plan a maintenance window. Stop every backend writer, including old workers,
   scheduled jobs and manual Admin SDK scripts, and wait for in-flight writes
   to finish. Do not write memberships or chat
   ownership directly through Firebase Console during migration.
3. Stage the updated backend and frontend release without starting backend
   writers. Keep the old rules until the metadata backfill succeeds. Do not
   restart old workers after installing the private rules.
4. From `backend`, perform the explicitly approved dry run. This reads live data
   but makes no writes and prints counts only:

   ```bash
   .venv/bin/python scripts/backfill_realtime_access.py --project YOUR_PROJECT_ID
   ```

5. Review counts, then separately approve applying that plan:

   ```bash
   .venv/bin/python scripts/backfill_realtime_access.py --project YOUR_PROJECT_ID --apply --maintenance-confirmed
   ```

   The script verifies the configured project matches the supplied project. It
   includes existing metadata for removed memberships/chats and preserves global
   account revocations. Re-running under maintenance is safe. It never prints
   raw IDs, message contents, customer details or credentials.
6. If the apply finishes successfully, deploy **only** `database.rules.json` to
   the verified project, then restart the updated backend workers. Do not deploy
   private rules after a failed or partial backfill. No Firestore/Storage rules
   need to change for this task.
7. Check a seller, restricted staff account, anonymous guest, signed-in customer
   and a second business. Verify chat replies, notifications and order updates;
   verify that removing staff immediately ends that staff member's live reads.
   Old browser tabs may need a refresh to load the updated claim/listener code.

## Interrupted edits and rollback

If a process crashes or the final permission sync fails, its denial barrier
remains in place. An API failure is returned rather than claiming the operation
fully succeeded. Do not delete a barrier to restore access blindly: stop writers,
review Firestore's committed membership state, and run the approved backfill to
repair it from that state. A failed Firestore edit that can still synchronize
restores only its actual, unchanged membership rights. A listener canceled during
a failed revocation may need a browser refresh after those rights are restored.

Keep the new backend and metadata while investigating a failed rollout. Rolling
back to old writers can leave permission records stale. Restoring the old public
rules reopens the original data exposure and requires explicit risk approval;
the rollout must not automatically fall back to public reads.
