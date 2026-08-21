import { apiRequest } from "./apiClient";

function formatCurrency(minorUnits = 0) {
  return `LKR ${(minorUnits / 100).toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function displayStatus(status) {
  return status === "needs-confirmation" ? "pending" : status;
}

export function mapOrderForTable(order) {
  const createdAt = order.createdAt ? new Date(order.createdAt) : null;

  return {
    ...order,
    customerName: order.customerSnapshot?.name ?? "Customer",
    phoneNumber: order.customerSnapshot?.normalizedPhone ?? "",
    secondaryPhoneNumber:
      order.customerSnapshot?.secondaryPhoneNumber
      ?? order.customerSnapshot?.normalizedSecondaryPhone
      ?? "",
    email: order.customerSnapshot?.email ?? "",
    courier: order.courierSnapshot?.name ?? "Not assigned",
    status: displayStatus(order.fulfilmentStatus),
    fulfilmentStatus: order.fulfilmentStatus,
    paymentMethod: order.paymentMethod ?? "cod",
    privateNote: order.privateNote ?? "",
    total: formatCurrency(order.totalAmountMinor),
    subtotal: formatCurrency(order.subtotalMinor),
    deliveryFee: formatCurrency(order.deliveryFeeMinor),
    deliveryAddress: [
      order.deliveryAddress?.line1,
      order.deliveryAddress?.line2,
      order.deliveryAddress?.city,
      order.deliveryAddress?.district,
      order.deliveryAddress?.postalCode,
      order.deliveryAddress?.country,
    ]
      .filter(Boolean)
      .join(", "),
    deliveryAddressObject: order.deliveryAddress ?? {},
    date: createdAt
      ? createdAt.toLocaleDateString("en-LK", {
          year: "numeric",
          month: "short",
          day: "numeric",
        })
      : "",
    time: createdAt
      ? createdAt.toLocaleTimeString("en-LK", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "",
    items: (order.items ?? []).map((item) => ({
      ...item,
      id: item.variantId,
      unitPrice: formatCurrency(item.unitPriceMinor),
      price: formatCurrency(item.lineTotalMinor),
      imageUrl: item.mediaUrl ?? item.imageUrl ?? "",
    })),
  };
}

export async function getOrders(businessId, filters = {}) {
  const parameters = new URLSearchParams();

  if (filters.status) parameters.set("status", filters.status);
  if (filters.search) parameters.set("search", filters.search);
  if (filters.dateFrom) parameters.set("dateFrom", filters.dateFrom);
  if (filters.dateTo) parameters.set("dateTo", filters.dateTo);
  if (filters.courierId) parameters.set("courierId", filters.courierId);
  const query = parameters.toString();
  const response = await apiRequest(
    `/businesses/${businessId}/orders${query ? `?${query}` : ""}`,
  );
  return response.orders.map(mapOrderForTable);
}

export async function createOrder(businessId, orderData) {
  const response = await apiRequest(`/businesses/${businessId}/orders`, {
    method: "POST",
    body: orderData,
  });
  return mapOrderForTable(response.order);
}

export async function updateOrderStatus(businessId, orderId, status, note = "") {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/status`,
    {
      method: "PATCH",
      body: { status, note },
    },
  );
  return mapOrderForTable(response.order);
}

export async function removeOrder(businessId, orderId) {
  const response = await apiRequest(`/businesses/${businessId}/orders/${orderId}`, {
    method: "DELETE",
  });
  return mapOrderForTable(response.order);
}

export async function updateOrder(businessId, orderId, changes) {
  const response = await apiRequest(`/businesses/${businessId}/orders/${orderId}`, { method: "PATCH", body: changes });
  return mapOrderForTable(response.order);
}
