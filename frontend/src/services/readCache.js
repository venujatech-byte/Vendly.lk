const cache = new Map();
const pending = new Map();
const DEFAULT_TTL = 60 * 1000;

export function cachedRequest(key, loader, ttl = DEFAULT_TTL) {
  const existing = cache.get(key);
  if (existing && existing.expiresAt > Date.now()) return Promise.resolve(existing.value);
  if (pending.has(key)) return pending.get(key);

  const request = Promise.resolve().then(loader).then((value) => {
    cache.set(key, { value, expiresAt: Date.now() + ttl });
    pending.delete(key);
    return value;
  }).catch((error) => {
    pending.delete(key);
    throw error;
  });
  pending.set(key, request);
  return request;
}

export function invalidateReadCache(prefix) {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}
