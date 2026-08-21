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

export async function reportCustomer(businessId, customerId) {
  const response = await apiRequest(
    `/businesses/${businessId}/customers/${customerId}/fraud-report`,
    {
      method: "POST",
      body: {
        reason: "seller-reported",
        note: "Customer reported from the customer management page.",
      },
    },
  );
  return response.fraudReport;
}

export async function getFraudCustomers(businessId) {
  const response = await apiRequest(
    `/businesses/${businessId}/fraud-customers`,
  );
  return response.customers;
}
