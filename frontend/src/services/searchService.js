import { apiRequest } from "./apiClient";


export async function searchBusiness(businessId, query, signal) {
  const response = await apiRequest(
    `/businesses/${businessId}/search?q=${encodeURIComponent(query)}`,
    { signal },
  );
  return response.results;
}
