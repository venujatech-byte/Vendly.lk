import { apiRequest } from "./apiClient";

const money = (minor = 0) => `LKR ${(Number(minor) / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function mapShopSale(sale) {
  const created = sale.createdAt ? new Date(sale.createdAt) : new Date();
  return {
    ...sale,
    orderNumber: sale.saleNumber,
    items: (sale.items ?? []).map((item, index) => ({
      ...item, id: `${sale.id}-${index}`, imageUrl: item.mediaUrl,
      unitPrice: money(item.unitPriceMinor), price: money(item.lineTotalMinor),
    })),
    total: money(sale.totalAmountMinor), subtotal: money(sale.subtotalMinor),
    discount: money(sale.discountTotalMinor),
    date: created.toLocaleDateString("en-LK", { month: "short", day: "numeric", year: "numeric" }),
    time: created.toLocaleTimeString("en-LK", { hour: "2-digit", minute: "2-digit" }),
  };
}

export async function getShopSales(businessId, filters = {}) {
  const search = new URLSearchParams();
  if (filters.search) search.set("search", filters.search);
  if (filters.dateFrom) search.set("dateFrom", filters.dateFrom);
  if (filters.dateTo) search.set("dateTo", filters.dateTo);
  const response = await apiRequest(`/businesses/${businessId}/shop-sales?${search}`);
  return response.shopSales.map(mapShopSale);
}

export async function createShopSale(businessId, data) {
  const response = await apiRequest(`/businesses/${businessId}/shop-sales`, { method: "POST", body: data });
  return mapShopSale(response.shopSale);
}

export async function removeShopSale(businessId, saleId) {
  const response = await apiRequest(`/businesses/${businessId}/shop-sales/${saleId}`, { method: "DELETE" });
  return mapShopSale(response.shopSale);
}

export async function getWarrantyClaims(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/warranty-claims`);
  return response.warrantyClaims;
}

export async function createWarrantyClaim(businessId, data) {
  const response = await apiRequest(`/businesses/${businessId}/warranty-claims`, { method: "POST", body: data });
  return response.warrantyClaim;
}
