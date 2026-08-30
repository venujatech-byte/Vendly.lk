import { apiFileRequest, apiRequest } from "./apiClient";


export async function getAnalyticsOverview(businessId) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/overview`,
  );
  return response.analytics;
}


export async function getAnalyticsLedger(businessId) {
  const response = await apiRequest(
    `/businesses/${businessId}/analytics/ledger`,
  );
  return response.ledger;
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
