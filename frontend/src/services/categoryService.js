import { apiRequest } from "./apiClient";
import { cachedRequest, invalidateReadCache } from "./readCache";

export function getCategories(businessId) {
  return cachedRequest(`categories:${businessId}`, () =>
    apiRequest(`/businesses/${businessId}/categories`), 5 * 60 * 1000);
}

export function createCategory(businessId, categoryData) {
  return apiRequest(`/businesses/${businessId}/categories`, {
    method: "POST",
    body: categoryData,
  }).then((result) => { invalidateReadCache(`categories:${businessId}`); return result; });
}

export function updateCategory(businessId, categoryId, changes) {
  return apiRequest(
    `/businesses/${businessId}/categories/${categoryId}`,
    {
      method: "PATCH",
      body: changes,
    },
  ).then((result) => { invalidateReadCache(`categories:${businessId}`); return result; });
}

export function removeCategory(businessId, categoryId) {
  return apiRequest(`/businesses/${businessId}/categories/${categoryId}`, {
    method: "DELETE",
  }).then((result) => { invalidateReadCache(`categories:${businessId}`); return result; });
}
