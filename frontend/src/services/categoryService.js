import { apiRequest } from "./apiClient";

export function getCategories(businessId) {
  return apiRequest(`/businesses/${businessId}/categories`);
}

export function createCategory(businessId, categoryData) {
  return apiRequest(`/businesses/${businessId}/categories`, {
    method: "POST",
    body: categoryData,
  });
}

export function updateCategory(businessId, categoryId, changes) {
  return apiRequest(
    `/businesses/${businessId}/categories/${categoryId}`,
    {
      method: "PATCH",
      body: changes,
    },
  );
}

export function removeCategory(businessId, categoryId) {
  return apiRequest(`/businesses/${businessId}/categories/${categoryId}`, {
    method: "DELETE",
  });
}
