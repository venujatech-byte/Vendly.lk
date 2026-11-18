# Private Realtime Database access (SEC-02 / SEC-07)

This is a prepared local change. No production migration or rules deployment is
authorized by this document. Obtain approval for the specific production steps.

## What changes

Before: `chatMessages/$sessionId`, business notifications and customer order
updates allow public reads when a caller knows the path. The seller inbox's
`businessChatActivity` subscription has no matching read grant.

After: all client writes remain denied. Clients can read only their own
notification-scope flags inside `_access`; other metadata remains private.

| Path | Required identity/access |
|---|---|
| `chatMessages/$sessionId` | The session's customer UID, or a current member of that business with `customers:read` |
| `businesses/$businessId/notifications` | No client reads; this legacy shared feed is closed |
| `businesses/$businessId/notificationFeeds/orders` | Active Owner/Admin, or a member with `orders:read` |
| `businesses/$businessId/notificationFeeds/customers` | Active Owner/Admin, or a member with `customers:read` |
| `businesses/$businessId/notificationFeeds/management` | Active Owner/Admin only |
| `_access/members/$businessId/$uid/notifications` | Only that authenticated UID, reading its own scope flags |
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
Notification scopes are revoked before membership changes and granted only after
commit. The header follows its own server-written flags, removes revoked groups
from its cache, and subscribes to newly granted groups. Unchanged feeds stay open.

Notification types are classified once on the backend: new orders/cancellations
belong to `orders`; customer chat and fraud alerts belong to `customers`; AI,
system and unknown types belong to `management`. Both API responses and
mark-as-read requests enforce this policy. The shared read state, existing
previews and live history are preserved. Moving a reused notification ID between
types removes its old scoped copies atomically.

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
   raw IDs, message contents, customer details or credentials. The plan now also
   counts `notificationBusinesses` and `notifications`. It moves the existing live
   history into scoped feeds, preserving preview text, timestamps and read state.
   Already migrated feed records take precedence over legacy copies. Each
   business's feeds and completion marker are written atomically; subsequent
   runs ignore retained legacy copies so resolved/deleted alerts cannot return.
   Malformed records stop the plan before it writes permissions. Legacy copies
   remain server-only; deleting that retained data needs a retention decision.

6. If the apply finishes successfully, deploy **only** `database.rules.json` to
   the verified project, then restart the updated backend workers and serve the
   updated frontend. Refresh old browser tabs so they use scoped feeds. Do not deploy
   private rules after a failed or partial backfill. No Firestore/Storage rules
   need to change for this task.
7. Check a seller, restricted staff account, anonymous guest, signed-in customer
   and a second business. Verify chat replies, notifications and order updates;
   verify that removing staff immediately ends that staff member's live reads.
   Check order-only, customer-only and no-notification-access members against
   both API routes and each live feed. Verify permission grants and revocations
   update the open bell without a browser refresh.
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


## SEC-07 rules before and after

Before this subtask, any active member with the broad notification flag could
read the shared payload feed:

```json
{
  "notifications": {
    ".read": "auth != null && root.child('_access/disabledUsers').child(auth.uid).val() !== true && (auth.token.firebase.sign_in_provider !== 'password' || auth.token.email_verified === true) && root.child('_access/members').child($businessId).child(auth.uid).child('notifications').val() === true",
    ".write": false
  }
}
```

After this subtask, the shared path is denied and only one of the three explicit
scopes can be read when that member's server-written scope flag is true:

```json
{
  "notifications": {
    ".read": false,
    ".write": false
  },
  "notificationFeeds": {
    "$scope": {
      ".read": "($scope === 'orders' || $scope === 'customers' || $scope === 'management') && auth != null && root.child('_access/disabledUsers').child(auth.uid).val() !== true && (auth.token.firebase.sign_in_provider !== 'password' || auth.token.email_verified === true) && root.child('_access/members').child($businessId).child(auth.uid).child('notifications').child($scope).val() === true",
      ".write": false
    }
  }
}
```

The only newly readable authorization metadata is the authenticated user's own
notification-scope map. Parent records, other users' flags, versions and edit
locks remain unreadable; clients cannot write any metadata:

```json
{
  ".read": false,
  ".write": false,
  "members": {
    "$businessId": {
      "$uid": {
        "notifications": {
          ".read": "auth != null && root.child('_access/disabledUsers').child(auth.uid).val() !== true && (auth.token.firebase.sign_in_provider !== 'password' || auth.token.email_verified === true) && auth.uid === $uid"
        }
      }
    }
  }
}
```

Use the complete repository `database.rules.json` when reviewing or deploying;
these snippets show the changed sections only. Applying this upgrade requires
the scoped permission and notification-history backfill above before the new
rules/clients are enabled. Do not restart older writers or restore a rule that
makes the legacy notification payload feed readable by all members.
