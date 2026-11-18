import { onValue, ref } from "firebase/database";

const SCOPES = ["orders", "customers", "management"];

// Follow only server-granted feeds and remove revoked data before processing queued callbacks.
export function subscribeNotificationFeeds(database, businessId, uid, { onPermissions, onFeed, onError }) {
  let active = true;
  let allowed = new Set();
  const subscriptions = new Map();

  function stopFeeds() {
    subscriptions.forEach((unsubscribe) => unsubscribe());
    subscriptions.clear();
  }

  const unsubscribePermissions = onValue(ref(database, `_access/members/${businessId}/${uid}/notifications`), (snapshot) => {
    if (!active) return;
    const permissions = snapshot.val() || {};
    allowed = new Set(SCOPES.filter((scope) => permissions[scope] === true));
    onPermissions([...allowed]);

    // Keep unchanged listeners open while adding grants or removing individual revoked scopes.
    for (const scope of SCOPES) {
      if (!allowed.has(scope)) {
        subscriptions.get(scope)?.();
        subscriptions.delete(scope);
      } else if (!subscriptions.has(scope)) {
        let listening = true;
        const unsubscribe = onValue(ref(database, `businesses/${businessId}/notificationFeeds/${scope}`), (feed) => {
          if (!active || !listening || !allowed.has(scope)) return;
          const records = Object.entries(feed.val() || {}).map(([id, record]) => ({ ...record, id, scope }));
          onFeed(scope, records);
        }, (error) => {
          if (!active || !listening) return;
          listening = false;
          subscriptions.delete(scope);
          allowed.delete(scope);
          onPermissions([...allowed]);
          // Losing a scope is an expected revocation; report other subscription failures.
          if (!/permission[ _-]denied/i.test(error.code || "")) onError(error);
        });
        if (listening) subscriptions.set(scope, () => { listening = false; unsubscribe(); });
        else unsubscribe();
      }
    }
  }, (error) => {
    if (!active) return;
    allowed.clear();
    stopFeeds();
    onPermissions([]);
    onError(error);
  });

  // Close permission and payload listeners together when the user or business changes.
  return () => {
    active = false;
    unsubscribePermissions();
    stopFeeds();
  };
}
