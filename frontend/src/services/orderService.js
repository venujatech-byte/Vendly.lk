import { apiRequest } from "./apiClient";
import { customerNoteFromPrivateNote } from "./orderNotes";

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
  const fraudWarning = order.fraudRiskSnapshot?.matched
    ? {
        score: order.fraudRiskSnapshot.score ?? 0,
        riskLevel: order.fraudRiskSnapshot.riskLevel ?? "high",
        reportCount: order.fraudRiskSnapshot.reportCount ?? 0,
        returnedOrderCount: order.fraudRiskSnapshot.returnedOrderCount ?? 0,
        message:
          "This customer matches the shared fraud registry. Review the order details before dispatch.",
      }
    : null;

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
    // Keep the courier's short code available for compact order-table views.
    courierCode: order.courierSnapshot?.code ?? "",
    status: displayStatus(order.fulfilmentStatus),
    fulfilmentStatus: order.fulfilmentStatus,
    paymentMethod: order.paymentMethod ?? "cod",
    privateNote: order.privateNote ?? "",
    // Grams below a kilo, kilograms above: couriers price by the kilo, and
    // "1250 g" makes the seller do the conversion at the counter.
    totalWeightGrams: order.totalWeightGrams ?? 0,
    totalWeight:
      (order.totalWeightGrams ?? 0) >= 1000
        ? `${((order.totalWeightGrams ?? 0) / 1000).toFixed(2)} kg`
        : `${order.totalWeightGrams ?? 0} g`,
    // The customer's own instruction, kept separate from the seller's private
    // note so the two are never shown as one another's words. Orders placed
    // before the field existed still have it, concatenated into privateNote by
    // the chatbot - recovered here so those notes are not lost to the seller.
    customerNote: order.customerNote || customerNoteFromPrivateNote(order.privateNote),
    fraudWarning,
    total: formatCurrency(order.totalAmountMinor),
    subtotal: formatCurrency(order.subtotalMinor),
    deliveryFee: formatCurrency(order.deliveryFeeMinor),
    discount: formatCurrency(order.discountTotalMinor),
    deposit: formatCurrency(order.depositAmountMinor),
    paidAmount: formatCurrency(order.paidAmountMinor),
    // What the courier still has to collect once any deposit is deducted.
    balanceDue: formatCurrency(order.balanceAmountMinor),
    // Keep the raw minor units so callers can test "is there a discount?"
    // without having to parse a formatted currency string.
    discountMinor: order.discountTotalMinor ?? 0,
    depositMinor: order.depositAmountMinor ?? 0,
    paidAmountMinor: order.paidAmountMinor ?? 0,
    balanceMinor: order.balanceAmountMinor ?? 0,
    paymentStatus: order.paymentStatus ?? "unpaid",
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
      warrantyPeriodMonths: item.warrantyPeriodMonths ?? item.warrantyMonths ?? 0,
      warrantyExpiresAt: item.warrantyExpiresAt ?? null,
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
