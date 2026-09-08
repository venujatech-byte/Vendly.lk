import { apiRequest } from "./apiClient";
import { cachedRequest, invalidateReadCache } from "./readCache";

export async function getCouriers(businessId) {
  return cachedRequest(`couriers:${businessId}`, async () => {
    const response = await apiRequest(`/businesses/${businessId}/couriers`);
    return response.couriers;
  }, 5 * 60 * 1000);
}

export async function createCourier(businessId, courierData) {
  const response = await apiRequest(`/businesses/${businessId}/couriers`, {
    method: "POST",
    body: courierData,
  });
  invalidateReadCache(`couriers:${businessId}`);
  return response.courier;
}

export async function updateCourier(businessId, courierId, courierData) {
  const response = await apiRequest(
    `/businesses/${businessId}/couriers/${courierId}`,
    {
      method: "PATCH",
      body: courierData,
    },
  );
  invalidateReadCache(`couriers:${businessId}`);
  return response.courier;
}

export async function uploadCourierExportTemplate(
  businessId,
  courierId,
  file,
) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiRequest(
    `/businesses/${businessId}/couriers/${courierId}/order-export-template`,
    {
      method: "POST",
      body: formData,
    },
  );
  return response.courier;
}

export async function recommendCouriers(businessId, totalWeightGrams, district) {
  const response = await apiRequest(
    `/businesses/${businessId}/couriers/recommend`,
    {
      method: "POST",
      body: { totalWeightGrams, district },
    },
  );
  return response.recommendations;
}
