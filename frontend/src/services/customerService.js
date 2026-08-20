import { apiRequest } from "./apiClient";

export async function getCustomers(businessId, search = "") {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const response = await apiRequest(`/businesses/${businessId}/customers${query}`);
  return response.customers;
}

export async function createCustomer(businessId, customerData) {
  const response = await apiRequest(`/businesses/${businessId}/customers`, {
    method: "POST",
    body: customerData,
  });
  return response.customer;
}

export async function updateCustomer(businessId, customerId, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/customers/${customerId}`,
    {
      method: "PATCH",
      body: changes,
    },
  );
  return response.customer;
}
