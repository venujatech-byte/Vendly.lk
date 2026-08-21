import { apiRequest } from "./apiClient";


export async function getReviews(businessId, status = "") {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const response = await apiRequest(`/businesses/${businessId}/reviews${query}`);
  return response.reviews;
}


export async function getProductReviews(businessId, productId) {
  const response = await apiRequest(
    `/businesses/${businessId}/reviews?productId=${encodeURIComponent(productId)}`,
  );
  return response.reviews;
}


export async function moderateReview(businessId, reviewId, status) {
  const response = await apiRequest(
    `/businesses/${businessId}/reviews/${reviewId}`,
    { method: "PATCH", body: { status } },
  );
  return response.review;
}
