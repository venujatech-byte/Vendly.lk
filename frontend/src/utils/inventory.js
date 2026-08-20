// Return direct stock for simple products or add all size stocks together.
export function getProductStock(product) {
  if (!product.hasSizes) {
    return product.stock;
  }

  return product.sizes.reduce(
    (totalStock, sizeOption) => totalStock + sizeOption.stock,
    0,
  );
}

// Convert a stock number into one of the three status names used by the UI.
export function getStockStatus(stock, lowStockThreshold = 5) {
  if (stock === 0) {
    return "out-of-stock";
  }

  if (stock <= lowStockThreshold) {
    return "low-stock";
  }

  return "in-stock";
}

// Calculate a complete product's status using its own low-stock threshold.
export function getProductStockStatus(product) {
  return getStockStatus(
    getProductStock(product),
    product.lowStockThreshold,
  );
}
