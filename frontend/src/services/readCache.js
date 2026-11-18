const cache = new Map();
const pending = new Map();
const DEFAULT_TTL = 60 * 1000;

export function cachedRequest(key, loader, ttl = DEFAULT_TTL) {
  // Prune expired keys even when callers move on to different searches or report versions.
  const now = Date.now();
  for (const [cachedKey, entry] of cache) {
    if (entry.expiresAt <= now) cache.delete(cachedKey);
  }
  const existing = cache.get(key);
  if (existing) return Promise.resolve(existing.value);
  if (pending.has(key)) return pending.get(key);

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

export function invalidateReadCache(prefix) {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
  // Detach matching in-flight loads so the next caller starts a fresh request.
  for (const key of pending.keys()) {
    if (key.startsWith(prefix)) pending.delete(key);
  }
}
