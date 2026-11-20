import { escapeCsvCell } from "../utils/csv.js";
import { apiRequest } from "./apiClient";
import { cachedRequest, getReadCacheSession, invalidateReadCache } from "./readCache";

// Match Firestore's UTF-8 name ordering without changing the table's existing locale-based sort controls.
const nameEncoder = new TextEncoder();
function compareCustomerNames(left, right) {
  if (left.name == null && right.name != null) return -1;
  if (right.name == null && left.name != null) return 1;
  const leftName = nameEncoder.encode(left.name ?? "");
  const rightName = nameEncoder.encode(right.name ?? "");
  for (let index = 0; index < Math.min(leftName.length, rightName.length); index += 1) {
    if (leftName[index] !== rightName[index]) return leftName[index] - rightName[index];
  }
  return leftName.length - rightName.length;
}

export async function getCustomers(businessId, search = "") {
  // Recheck permission and backend freshness before reusing session-memory customer data.
  const session = getReadCacheSession();
  const { revision } = await apiRequest(`/businesses/${businessId}/customers/cache/version`);
  if (session !== getReadCacheSession()) throw new DOMException("The login session changed.", "AbortError");
  if (typeof revision !== "string" || !revision || revision.length > 128) {
    throw new Error("Customer freshness could not be verified.");
  }
  const prefix = `customers:${businessId}:${encodeURIComponent(revision)}:`;
  // Keep current search variants while detaching data and pending loads from obsolete revisions.
  invalidateReadCache(`customers:${businessId}:`, prefix);
  return cachedRequest(`${prefix}${search.trim().toLowerCase()}`, async () => {
    const parameters = new URLSearchParams();
    if (search) parameters.set("search", search);
    const customers = new Map();
    const cursors = new Set();
    // Cache only the complete list so tables, exports and customer selectors never see one scan page.
    while (true) {
      const query = parameters.toString();
      const response = await apiRequest(`/businesses/${businessId}/customers${query ? `?${query}` : ""}`);
      for (const customer of response.customers) customers.set(customer.id, customer);
      if (!response.hasMore) break;
      if (typeof response.nextCursor !== "string" || !response.nextCursor || cursors.has(response.nextCursor)) {
        throw new Error("Customers could not be loaded. Reload the customers list.");
      }
      cursors.add(response.nextCursor);
      parameters.set("after", response.nextCursor);
    }
    // ID pages arrive in ID order; restore the original default name order and stable ID tie-breaker.
    return [...customers.values()].sort(compareCustomerNames);
  }, Infinity);
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
  const csv = [columns, ...rows].map((row) => row.map(escapeCsvCell).join(",")).join("\r\n");
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
  invalidateReadCache(`customers:${businessId}:`);
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
  invalidateReadCache(`customers:${businessId}:`);
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
  invalidateReadCache(`customers:${businessId}:`);
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
  invalidateReadCache(`customers:${businessId}:`);
  return response.customer;
}

export async function removeFromFraudList(businessId, customerId) {
  const response = await apiRequest(
    `/businesses/${businessId}/customers/${customerId}/fraud-profile`,
    { method: "DELETE" },
  );
  invalidateReadCache(`customers:${businessId}:`);
  return response;
}
