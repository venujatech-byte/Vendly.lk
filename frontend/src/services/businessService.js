import { apiRequest } from "./apiClient";

// Create the seller's first business. Repeating the request returns the same one.
export function createBusiness({ ownerName, businessName }) {
  return apiRequest("/businesses", {
    method: "POST",
    body: {
      ownerName,
      businessName,
    },
  });
}
