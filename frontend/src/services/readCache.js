const cache = new Map();
const pending = new Map();
const DEFAULT_TTL = 60 * 1000;
let sessionGeneration = 0;

// Async version checks must not recreate a cache after logout/account change cleared it.
export function getReadCacheSession() {
  return sessionGeneration;
}

export function cachedRequest(key, loader, ttl = DEFAULT_TTL, deduplicate = true) {
  // Prune expired keys even when callers move on to different searches or report versions.
  const now = Date.now();
  for (const [cachedKey, entry] of cache) {
    if (entry.expiresAt <= now) cache.delete(cachedKey);
  }
  const existing = cache.get(key);
  if (existing) return Promise.resolve(existing.value);
  // Independently cancellable callers must not inherit another caller's aborted request.
  if (deduplicate && pending.has(key)) return pending.get(key);

  const request = Promise.resolve().then(loader).then((value) => {
    // An invalidated request must neither repopulate data nor remove its replacement request.
    if (pending.get(key) === request) {
      cache.set(key, { value, expiresAt: Date.now() + ttl });
      pending.delete(key);
    }
    return value;
  }).catch((error) => {
    if (pending.get(key) === request) pending.delete(key);
    throw error;
  });
  pending.set(key, request);
  return request;
}

export function invalidateReadCache(prefix, keepPrefix) {
  if (prefix === "") sessionGeneration += 1;
  for (const key of cache.keys()) {
    if (key.startsWith(prefix) && (keepPrefix == null || !key.startsWith(keepPrefix))) cache.delete(key);
  }
  // Detach invalidated loads so late responses cannot restore stale data or displace current requests.
  for (const key of pending.keys()) {
    if (key.startsWith(prefix) && (keepPrefix == null || !key.startsWith(keepPrefix))) pending.delete(key);
  }
}
