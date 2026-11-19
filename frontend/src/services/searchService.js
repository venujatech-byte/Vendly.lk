import { apiRequest } from "./apiClient";
import { cachedRequest, getReadCacheSession, invalidateReadCache, limitReadCache } from "./readCache";


export async function searchBusiness(businessId, query, signal) {
  // Revalidate current permissions and all readable module revisions before returning private cached results.
  signal?.throwIfAborted();
  const session = getReadCacheSession();
  const { revision, scope } = await apiRequest(`/businesses/${businessId}/search/cache/version`, { signal });
  signal?.throwIfAborted();
  if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
  if (typeof revision !== "string" || !/^[a-f0-9]{64}$/.test(revision) || typeof scope !== "string" || scope.length > 80) {
    throw new Error("Search freshness could not be verified.");
  }
  const prefix = `search:${businessId}:${revision}:`;
  invalidateReadCache(`search:${businessId}:`, prefix);
  // A member with no searchable modules needs no second authenticated request for empty results.
  if (!scope) return { orders: [], products: [], customers: [] };
  // Each header request owns its abort signal; only completed results are shared.
  const results = await cachedRequest(`${prefix}${encodeURIComponent(query)}`, async () => {
    signal?.throwIfAborted();
    const response = await apiRequest(
      `/businesses/${businessId}/search?q=${encodeURIComponent(query)}&includeScope=1`,
      { signal },
    );
    signal?.throwIfAborted();
    if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
    // A permission change between requests must never cache broader results under an older narrow scope.
    if (response.scope !== scope) invalidateReadCache(prefix);
    return response.results;
  }, Infinity, false);
  signal?.throwIfAborted();
  if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
  // Keep at most 50 completed query results per business in session memory; logout clears them all.
  limitReadCache(`search:${businessId}:`, 50);
  return results;
}
