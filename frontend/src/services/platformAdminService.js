import { apiRequest } from "./apiClient";

export function getPlatformSellerDashboard(after = "") {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  return apiRequest(`/admin/sellers${query}`);
}

export function getPlatformSellerDetail(businessId) {
  return apiRequest(`/admin/sellers/${encodeURIComponent(businessId)}`);
}

export function getPlatformServerHealth() {
  return apiRequest("/admin/server-health");
}
