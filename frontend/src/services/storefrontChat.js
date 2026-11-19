// Registered customers share a store key; guest and legacy keys retain their existing scope.
export function chatSessionStorageKey(storeCode, productCode, user, businessId = "") {
  const customerKey = user?.uid || "guest";
  const linkKey = businessId && user?.uid && !user.isAnonymous
    ? `business:${businessId}`
    : productCode ? `product:${productCode}` : `store:${storeCode}`;
  return `vendly-chat-session:${linkKey}:${customerKey}`;
}

// Reuse the existing cart mapping for restored conversations and normal chatbot replies.
export function chatCartFromSummary(summary, current, products) {
  return summary.map((line) => {
    const existing = current.find((item) => item.variantId === line.variantId);
    const variant = products.flatMap((product) => product.variants || [])
      .find((item) => item.id === line.variantId);
    return {
      ...existing,
      variantId: line.variantId,
      productName: line.productName,
      size: line.size,
      sku: line.sku,
      imageUrl: line.imageUrl || existing?.imageUrl || "",
      sellingPriceMinor: line.unitPriceMinor,
      availableStock: variant?.availableStock ?? existing?.availableStock ?? line.quantity,
      quantity: line.quantity,
    };
  });
}
