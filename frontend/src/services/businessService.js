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

// Update the contact details that customers see on the public storefront.
export function updatePublicContact(businessId, { phone, email, storefrontFaq, bankDetails }) {
  return apiRequest(`/businesses/${businessId}/public-contact`, {
    method: "PATCH",
    body: { phone, email, storefrontFaq, bankDetails },
  });
}
