import { apiRequest } from "./apiClient";


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


export function formatAnalyticsMoney(minorUnits = 0) {
  return `LKR ${(minorUnits / 100).toLocaleString("en-LK", {
    maximumFractionDigits: 0,
  })}`;
}
