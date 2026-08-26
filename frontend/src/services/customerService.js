import { apiRequest } from "./apiClient";

export async function getCustomers(businessId, search = "") {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  const response = await apiRequest(`/businesses/${businessId}/customers${query}`);
  return response.customers;
}

// Export the customer records already returned by the secured business API.
export function downloadCustomersCsv(customers = []) {
  const columns = [
    "Customer",
    "Primary phone",
    "Secondary phone",
    "Email",
    "Address",
    "City",
    "District",
    "Orders",
    "Total spent",
    "Risk level",
  ];
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const rows = customers.map((customer) => {
    const address = customer.defaultAddress || customer.address || {};
    return [
      customer.name,
      customer.normalizedPhone || customer.phoneNumber,
      customer.normalizedSecondaryPhone || customer.secondaryPhoneNumber,
      customer.email,
      [address.line1, address.line2, address.postalCode].filter(Boolean).join(", "),
      address.city,
      address.district,
      customer.totalOrders ?? customer.orderCount ?? 0,
      customer.totalSpentMinor != null
        ? `LKR ${(customer.totalSpentMinor / 100).toFixed(2)}`
        : customer.totalSpent ?? "",
      customer.riskLevel || "low",
    ];
  });
  const csv = [columns, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `vendly-customers-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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

export async function changeFraudRiskLevel(businessId, customerId, riskLevel) {
  const response = await apiRequest(
    `/businesses/${businessId}/customers/${customerId}/fraud-risk`,
    { method: "PATCH", body: { riskLevel } },
  );
  return response.customer;
}

export async function removeFromFraudList(businessId, customerId) {
  return apiRequest(
    `/businesses/${businessId}/customers/${customerId}/fraud-profile`,
    { method: "DELETE" },
  );
}
