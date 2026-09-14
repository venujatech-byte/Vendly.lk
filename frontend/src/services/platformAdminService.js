import { apiRequest } from "./apiClient";

export function getPlatformSellerDashboard(after = "") {
  const query = after ? `?after=${encodeURIComponent(after)}` : "";
  return apiRequest(`/admin/sellers${query}`);
}

export function getPlatformServerHealth() {
  return apiRequest("/admin/server-health");
}
