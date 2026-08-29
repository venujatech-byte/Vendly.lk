import { apiFileRequest, apiRequest } from "./apiClient";

function minorUnitsToAmount(value = 0) {
  return value / 100;
}

// Convert the backend's safe storage fields into the existing inventory UI shape.
export function mapProductForInventory(product) {
  const variants = product.variantSummaries ?? [];
  const firstVariant = variants[0] ?? {};

  return {
    ...product,
    colour: product.colourName,
    category: product.categoryName || "Uncategorized",
    sku: firstVariant.sku ?? product.skuPrefix,
    barcode: firstVariant.barcode ?? "",
    costPrice: minorUnitsToAmount(product.costPriceMinor),
    sellingPrice: minorUnitsToAmount(product.sellingPriceMinor),
    compareAtPrice: minorUnitsToAmount(product.compareAtPriceMinor),
    weightKg: (product.weightGrams ?? 0) / 1000,
    lowStockThreshold: product.lowStockThreshold ?? 5,
    stock: product.availableStock ?? 0,
    approvedReviews: product.approvedReviewCount ?? 0,
    images: (product.media ?? [])
      .map((mediaItem) => mediaItem.url)
      .filter(Boolean),
    sizes: variants.map((variant) => ({
      id: variant.id,
      size: variant.size,
      sku: variant.sku,
      barcode: variant.barcode,
      // Tables show sellable stock, while the edit form must preserve the
      // complete on-hand quantity (including units reserved by open orders).
      stock: variant.stockAvailable,
      stockOnHand: variant.stockOnHand ?? variant.stockAvailable ?? 0,
      stockReserved: variant.stockReserved ?? 0,
      stockAvailable: variant.stockAvailable ?? 0,
      costPrice: minorUnitsToAmount(variant.costPriceMinor ?? product.costPriceMinor),
      sellingPrice: minorUnitsToAmount(variant.sellingPriceMinor ?? product.sellingPriceMinor),
      imageUrl: variant.imageUrl ?? "",
    })),
  };
}

export async function getProducts(businessId, filters = {}) {
  const searchParameters = new URLSearchParams();

  if (filters.categoryId) {
    searchParameters.set("categoryId", filters.categoryId);
  }
  if (filters.status) {
    searchParameters.set("status", filters.status);
  }

  const query = searchParameters.toString();
  const response = await apiRequest(
    `/businesses/${businessId}/products${query ? `?${query}` : ""}`,
  );

  return response.products.map(mapProductForInventory);
}

export async function createProduct(businessId, productData) {
  const response = await apiRequest(`/businesses/${businessId}/products`, {
    method: "POST",
    body: productData,
  });

  return mapProductForInventory(response.product);
}

export async function generateProductDescription(businessId, productDetails) {
  const response = await apiRequest(
    `/businesses/${businessId}/products/generate-description`,
    {
      method: "POST",
      body: productDetails,
    },
  );

  return response.description;
}

export async function uploadProductMedia(businessId, productId, files) {
  const formData = new FormData();

  files.forEach((file) => formData.append("files", file));

  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}/media`,
    {
      method: "POST",
      body: formData,
    },
  );

  return mapProductForInventory(response.product);
}

export async function uploadVariantImage(businessId, productId, variantId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}/variants/${variantId}/image`,
    { method: "POST", body: formData },
  );
  return mapProductForInventory(response.product);
}

export async function updateProduct(businessId, productId, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}`,
    {
      method: "PATCH",
      body: changes,
    },
  );

  return mapProductForInventory(response.product);
}

export async function removeProduct(businessId, productId) {
  const response = await apiRequest(`/businesses/${businessId}/products/${productId}`, {
    method: "DELETE",
  });
  return mapProductForInventory(response.product);
}

export async function updateProductStatus(businessId, productId, status) {
  return updateProduct(businessId, productId, { status });
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = decodeURIComponent(filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function downloadInventoryWorkbook(businessId, productIds = []) {
  const searchParameters = new URLSearchParams();
  productIds.forEach((productId) => searchParameters.append("productId", productId));
  const query = searchParameters.toString();
  const file = await apiFileRequest(
    `/businesses/${businessId}/inventory-export.xlsx${query ? `?${query}` : ""}`,
  );
  downloadBlob(file.blob, file.filename);
}

export async function importInventoryWorkbook(businessId, file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiRequest(
    `/businesses/${businessId}/inventory-import`,
    { method: "POST", body: formData },
  );
  return response.import;
}

export async function adjustProductStock(
  businessId,
  productId,
  variantId,
  adjustment,
) {
  const response = await apiRequest(
    `/businesses/${businessId}/products/${productId}/variants/${variantId}/adjust-stock`,
    {
      method: "POST",
      body: adjustment,
    },
  );

  return mapProductForInventory(response.product);
}
