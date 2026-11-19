import { apiFileRequest, apiRequest } from "./apiClient";
import { cachedRequest, getReadCacheSession, invalidateReadCache } from "./readCache";


export async function getAnalyticsOverview(businessId) {
  // Check current read access and shared source revisions before reusing a private analytics report.
  const session = getReadCacheSession();
  const { analyticsRevision } = await apiRequest(`/businesses/${businessId}/analytics/version?includeRevision=1`);
  if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
  if (typeof analyticsRevision !== "string" || !/^[a-f0-9]{64}$/.test(analyticsRevision)) {
    throw new Error("Analytics freshness could not be verified.");
  }
  const prefix = `analytics:${businessId}:${analyticsRevision}:`;
  invalidateReadCache(`analytics:${businessId}:`, prefix);
  // Retain the existing expiry because forecast periods and stock age change even without writes.
  const analytics = await cachedRequest(`${prefix}overview`, async () => {
    const response = await apiRequest(`/businesses/${businessId}/analytics/overview`);
    if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
    return response.analytics;
  }, 30 * 60 * 1000);
  if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
  return analytics;
}


export async function getAnalyticsLedger(businessId) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/ledger`,
  );
  return response.ledger;
}


export async function createLedgerEntry(businessId, entryData) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/ledger/entries`,
    {
      method: "POST",
      body: entryData,
    },
  );
  return response.entry;
}


export async function deleteLedgerEntry(businessId, entryId) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/ledger/entries/${entryId}`,
    {
      method: "DELETE",
    },
  );
  return response;
}


export async function saveMonthlyRevenueTarget(businessId, monthlyTargetMinor) {
  return apiRequest(`/businesses/${businessId}/analytics/monthly-target`, {
    method: "PATCH",
    body: { monthlyTargetMinor },
  });
}


export async function getCodReconciliation(businessId) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/cod-reconciliation`,
  );
  return response.reconciliation;
}


export async function saveCodSettlement(businessId, orderId, settlement) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/cod-reconciliation/${orderId}`,
    { method: "PATCH", body: settlement },
  );
  return response.reconciliation;
}


export async function saveBulkCodSettlements(businessId, payload) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/cod-reconciliation/bulk`,
    { method: "POST", body: payload },
  );
  return response.reconciliation;
}



export async function downloadAnalyticsLedger(businessId, filters = {}) {
  const searchParameters = new URLSearchParams();
  if (filters.search?.trim()) searchParameters.set("search", filters.search.trim());
  if (filters.type && filters.type !== "all") searchParameters.set("type", filters.type);
  if (filters.dateFrom) searchParameters.set("dateFrom", filters.dateFrom);
  if (filters.dateTo) searchParameters.set("dateTo", filters.dateTo);
  const query = searchParameters.toString();
  const file = await apiFileRequest(
    `/businesses/${businessId}/analytics/ledger-export.xlsx${query ? `?${query}` : ""}`,
  );
  const url = URL.createObjectURL(file.blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = decodeURIComponent(file.filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}


export function formatAnalyticsMoney(minorUnits = 0) {
  return `LKR ${(minorUnits / 100).toLocaleString("en-LK", {
    maximumFractionDigits: 0,
  })}`;
}
