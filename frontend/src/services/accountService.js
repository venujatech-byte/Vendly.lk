import { apiRequest } from "./apiClient";

// Load the authenticated Firebase identity and its Vendly profile from Flask.
export function getCurrentAccount() {
  return apiRequest("/me");
}
