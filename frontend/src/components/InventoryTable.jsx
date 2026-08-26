// React tools manage repeated table rows and interactive component state.
import { Fragment, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Download,
  Package,
  PackagePlus,
  Pencil,
  Star,
  Trash2,
} from "lucide-react";
import ActionMenu from "./ActionMenu";
import TablePagination from "./TablePagination";
import useTablePagination from "../hooks/useTablePagination";

// Product data, stock calculation helpers, and the nested size table.
import {
  getProductStock,
  getProductStockStatus,
} from "../utils/inventory";
import ProductSizesTable from "./ProductVariantsTable";

import "./OrderTable.css";
import "./InventoryTable.css";

// Convert a number into Sri Lankan Rupee text for table prices.
function formatCurrency(amount) {
  return `LKR ${amount.toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// Convert "in-stock" style values into readable labels such as "In Stock".
function formatStatus(status) {
  return status
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Show a product photo and fall back to a package icon if the image fails.
function ProductImage({ product, imageNumber = 0 }) {
  // Each photo component remembers whether its own image failed to load.
  const [imageFailed, setImageFailed] = useState(false);
  const imageSource = product.images?.[imageNumber];

  return (
    <span
      className="inventory-table__product-image"
      style={product.colourHex ? { color: product.colourHex } : undefined}
    >
      {imageSource && !imageFailed ? (
        <img
          src={imageSource}
          alt={product.name}
          onError={() => setImageFailed(true)}
        />
      ) : (
        <Package size={21} aria-hidden="true" />
      )}
    </span>
  );
}

// Expanded content used only by products that have size variants.
function SizeStockDetails({ product, onViewReviews, onAdjustStock, onEditProduct, onRemoveProduct }) {
  return (
    <div className="inventory-table__size-details">
      {/* Size summary and seller actions. */}
      <header className="inventory-table__size-header">
        <div>
          <h3>Sizes &amp; Stock</h3>
          <span>
            {product.sizes.length} sizes • {getProductStock(product)} total units
          </span>
        </div>

        <div className="inventory-table__size-actions">
          <button type="button" onClick={() => onAdjustStock?.(product)}>
            <PackagePlus size={16} aria-hidden="true" />
            Adjust Stock
          </button>
          <button type="button" onClick={() => onEditProduct?.(product)}>
            <Pencil size={16} aria-hidden="true" />
            Edit Product
          </button>
          <button type="button" className="inventory-table__danger-button" onClick={() => onRemoveProduct?.(product)}>
            <Trash2 size={16} aria-hidden="true" />
            Remove Product
          </button>
          <button type="button" onClick={() => onViewReviews?.(product)}>
            <Star size={16} aria-hidden="true" />
            View Reviews
          </button>
        </div>
      </header>

      {/* Shared description and photos for every size of this product. */}
      <div className="inventory-table__size-overview">
        <section>
          <h4>Product Description</h4>
          <p>{product.description}</p>
        </section>

        <section>
          <h4>Product Photos</h4>
          <div className="inventory-table__images">
            {(product.images ?? []).map((image, index) => (
              <ProductImage
                key={image}
                product={product}
                imageNumber={index}
              />
            ))}
          </div>
        </section>

        <section>
          <h4>Warranty</h4>
          <p>
            {product.warrantyPeriodMonths
              ? `${product.warrantyPeriodMonths} month${product.warrantyPeriodMonths === 1 ? "" : "s"} warranty for future sales.`
              : "No warranty is currently offered."}
          </p>
        </section>
      </div>

      {/* Size-level SKU, barcode, stock, and status rows. */}
      <ProductSizesTable
        sizes={product.sizes}
        onAdjustStock={(variantId) => onAdjustStock?.(product, variantId)}
      />
    </div>
  );
}

// Expanded content for a simple product that does not have sizes.
function SimpleProductDetails({ product, onViewReviews, onAdjustStock, onEditProduct, onRemoveProduct }) {
  return (
    <div className="inventory-table__details">
      {/* Product description and photo gallery. */}
      <section className="inventory-table__description">
        <h3>Product Description</h3>
        <p>{product.description}</p>

        <h3>Product Images</h3>
        <div className="inventory-table__images">
          {(product.images ?? []).map((image, index) => (
            <ProductImage
              key={image}
              product={product}
              imageNumber={index}
            />
          ))}
        </div>
      </section>

      {/* Pricing, barcode, and weight information. */}
      <section className="inventory-table__information">
        <div>
          <span>Barcode</span>
          <strong>{product.barcode}</strong>
        </div>
        <div>
          <span>Cost Price</span>
          <strong>{formatCurrency(product.costPrice)}</strong>
        </div>
        <div>
          <span>Selling Price</span>
          <strong>{formatCurrency(product.sellingPrice)}</strong>
        </div>
        <div>
          <span>Weight</span>
          <strong>{product.weightKg.toFixed(2)} kg</strong>
        </div>
        <div>
          <span>Warranty</span>
          <strong>{product.warrantyPeriodMonths ? `${product.warrantyPeriodMonths} month${product.warrantyPeriodMonths === 1 ? "" : "s"}` : "No warranty"}</strong>
        </div>
      </section>

      {/* Current stock and approved review count. */}
      <section className="inventory-table__information">
        <div>
          <span>Available Stock</span>
          <strong>{getProductStock(product)}</strong>
        </div>
        <div>
          <span>Approved Reviews</span>
          <strong>
            {product.approvedReviews}
            <Star
              className="inventory-table__star"
              size={15}
              fill="currentColor"
              aria-hidden="true"
            />
          </strong>
        </div>
      </section>

      {/* Actions available to the seller for this product. */}
      <section className="inventory-table__actions">
        <button type="button" onClick={() => onEditProduct?.(product)}>
          <Pencil size={17} aria-hidden="true" />
          Edit Product
        </button>
        <button type="button" className="inventory-table__danger-button" onClick={() => onRemoveProduct?.(product)}>
          <Trash2 size={17} aria-hidden="true" />
          Remove Product
        </button>
        <button type="button" onClick={() => onAdjustStock?.(product)}>
          <PackagePlus size={17} aria-hidden="true" />
          Adjust Stock
        </button>
        <button type="button" onClick={() => onViewReviews?.(product)}>
          <Star size={17} aria-hidden="true" />
          View Reviews
        </button>
      </section>
    </div>
  );
}

function InventoryTable({ products = [], categories = [], onViewReviews, onAdjustStock, onEditProduct, onRemoveProduct, onChangeStatus, onChangeCategory, onExportSelected }) {
  // Track the one expanded row and all checkbox-selected products.
  const [expandedProductId, setExpandedProductId] = useState(
    null,
  );
  const [selectedProductIds, setSelectedProductIds] = useState([]);
  const pagination = useTablePagination(products);

  // True when every visible product checkbox is selected.
  const allProductsSelected =
    products.length > 0 && selectedProductIds.length === products.length;

  // Open the clicked product, or close it if it is already open.
  function toggleExpandedProduct(productId) {
    setExpandedProductId((currentProductId) =>
      currentProductId === productId ? null : productId,
    );
  }

  // Add or remove one product ID from the selected ID array.
  function toggleSelectedProduct(productId) {
    setSelectedProductIds((currentIds) => {
      if (currentIds.includes(productId)) {
        return currentIds.filter((id) => id !== productId);
      }

      return [...currentIds, productId];
    });
  }

  // Select every product or clear the complete selection.
  function toggleAllProducts() {
    if (allProductsSelected) {
      setSelectedProductIds([]);
      return;
    }

    setSelectedProductIds(products.map((product) => product.id));
  }

  return (
    <section
      className="orders-table-section inventory-table-section"
      aria-label="Inventory products"
    >
      {/* Bulk actions appear only after one or more products are selected. */}
      {selectedProductIds.length > 0 && (
        <div className="inventory-table__bulk-actions">
          <strong>{selectedProductIds.length} products selected</strong>
          <button
            type="button"
            onClick={() => {
              if (selectedProductIds.length === 1) {
                onAdjustStock?.(
                  products.find((product) => product.id === selectedProductIds[0]),
                );
              }
            }}
            disabled={selectedProductIds.length !== 1}
            title={selectedProductIds.length === 1 ? "Adjust selected product" : "Select one product to adjust stock"}
          >
            <PackagePlus size={16} aria-hidden="true" />
            Adjust stock
          </button>
          <select
            className="inventory-table__bulk-status"
            defaultValue=""
            aria-label="Change status for selected products"
            onChange={(event) => {
              if (event.target.value) {
                onChangeStatus?.(selectedProductIds, event.target.value);
                event.target.value = "";
              }
            }}
          >
            <option value="" disabled>Change status</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
          <select
            className="inventory-table__bulk-status"
            defaultValue=""
            aria-label="Add selected products to a category"
            onChange={(event) => {
              if (event.target.value) {
                onChangeCategory?.(selectedProductIds, event.target.value);
                event.target.value = "";
              }
            }}
          >
            <option value="" disabled>Add to category</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <button type="button" onClick={() => onChangeStatus?.(selectedProductIds, "archived")}>
            Delete selected
          </button>
          <button type="button" onClick={() => onExportSelected?.(selectedProductIds)}>
            <Download size={16} aria-hidden="true" />
            Export selected
          </button>
        </div>
      )}

      {/* Scroll wrapper keeps the wide inventory table usable on small screens. */}
      <div className="orders-table__scroll">
        <table className="orders-table inventory-table">
          <thead>
            <tr>
              <th className="orders-table__checkbox-column">
                <input
                  type="checkbox"
                  checked={allProductsSelected}
                  onChange={toggleAllProducts}
                  aria-label="Select all products"
                />
              </th>
              <th className="orders-table__expand-column"></th>
              <th>Product</th>
              <th>SKU / Barcode</th>
              <th>Category</th>
              <th>Price</th>
              <th>Weight</th>
              <th>Stock</th>
              <th>Status</th>
              <th className="orders-table__actions-heading">Actions</th>
            </tr>
          </thead>

          <tbody>
            {pagination.pageItems.map((product) => {
              // Values calculated separately for the current product row.
              const isExpanded = expandedProductId === product.id;
              const isSelected = selectedProductIds.includes(product.id);
              const stockStatus = getProductStockStatus(product);

              return (
                <Fragment key={product.id}>
                  <tr
                    className={
                      isSelected ? "orders-table__row--selected" : ""
                    }
                  >
                    <td>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelectedProduct(product.id)}
                        aria-label={`Select ${product.name}`}
                      />
                    </td>

                    <td>
                      <button
                        className="orders-table__expand-button"
                        type="button"
                        onClick={() => toggleExpandedProduct(product.id)}
                        aria-expanded={isExpanded}
                        aria-label={
                          isExpanded
                            ? `Collapse ${product.name}`
                            : `Expand ${product.name}`
                        }
                      >
                        {isExpanded ? (
                          <ChevronDown size={18} aria-hidden="true" />
                        ) : (
                          <ChevronRight size={18} aria-hidden="true" />
                        )}
                      </button>
                    </td>

                    <td>
                      <div className="inventory-table__product">
                        <ProductImage product={product} />
                        <div>
                          <strong>{product.name}</strong>
                          <span className="orders-table__secondary">
                            {product.productType}
                          </span>
                          {product.hasSizes && (
                            <span className="inventory-table__variant-count">
                              {product.sizes.length} sizes
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    <td>
                      <strong>
                        {product.hasSizes ? "Multiple SKUs" : product.sku}
                      </strong>
                      <span className="orders-table__secondary">
                        {product.hasSizes
                          ? "View size details"
                          : product.barcode}
                      </span>
                    </td>

                    <td>{product.category || "Uncategorized"}</td>
                    <td className="orders-table__total">
                      {formatCurrency(product.sellingPrice)}
                    </td>
                    <td>{product.weightKg.toFixed(2)} kg</td>
                    <td>
                      <strong>{getProductStock(product)}</strong>
                    </td>
                    <td>
                      <span
                        className={`inventory-table__status inventory-table__status--${stockStatus}`}
                      >
                        {formatStatus(stockStatus)}
                      </span>
                    </td>
                    <td>
                      <ActionMenu label={`More actions for ${product.name}`} items={[
                        { label: "Edit product", icon: <Pencil size={16} />, onClick: () => onEditProduct?.(product) },
                        { label: "Adjust stock", icon: <PackagePlus size={16} />, onClick: () => onAdjustStock?.(product) },
                        { label: "View reviews", icon: <Star size={16} />, onClick: () => onViewReviews?.(product) },
                        { label: "Remove product", icon: <Trash2 size={16} />, danger: true, onClick: () => onRemoveProduct?.(product) },
                      ]} />
                    </td>
                  </tr>

                  {/* Show the correct expanded layout for sized or simple products. */}
                  {isExpanded && (
                    <tr className="inventory-table__details-row">
                      <td className="inventory-table__details-cell" colSpan={10}>
                        {product.hasSizes ? (
                          <SizeStockDetails
                            product={product}
                            onViewReviews={onViewReviews}
                            onAdjustStock={onAdjustStock}
                            onEditProduct={onEditProduct}
                            onRemoveProduct={onRemoveProduct}
                          />
                        ) : (
                          <SimpleProductDetails
                            product={product}
                            onViewReviews={onViewReviews}
                            onAdjustStock={onAdjustStock}
                            onEditProduct={onEditProduct}
                            onRemoveProduct={onRemoveProduct}
                          />
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <TablePagination pagination={pagination} label="products" />
    </section>
  );
}

export default InventoryTable;
