import { Fragment, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Pencil,
  Trash2,
  Package,
} from "lucide-react";

import { getProductStock } from "../utils/inventory";
import ActionMenu from "./ActionMenu";
import TablePagination from "./TablePagination";
import SortableHeader from "./SortableHeader";
import useTablePagination from "../hooks/useTablePagination";
import useTableSort from "../hooks/useTableSort";

import "./OrderTable.css";
import "./CategoryTable.css";

// Display the product's first image.
// A package icon appears when the image cannot be loaded.
function CategoryProductImage({ product }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageSource = product.images?.[0];

  return (
    <span className="category-table__product-image">
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

// Find all products belonging to one category.
function getProductsForCategory(category, products) {
  if (category.name === "Uncategorized") {
    return products.filter(
      (product) => !product.categoryId && !product.category,
    );
  }

  return products.filter(
    (product) =>
      product.categoryId === category.id ||
      product.category === category.name,
  );
}

const categorySortAccessors = {
  category: (category) => category.name,
  description: (category) => category.description,
  products: (category) => category.products.length,
  stock: (category) => category.totalStock,
  status: (category) => category.status,
};

const categoryProductSortAccessors = {
  image: (product) => product.name,
  product: (product) => product.name,
  sku: (product) => product.hasSizes ? "Multiple SKUs" : product.sku,
  barcode: (product) => product.hasSizes ? "Multiple barcodes" : product.barcode,
  stock: (product) => getProductStock(product),
};

function CategoryProductsTable({ products }) {
  const sorting = useTableSort(products, categoryProductSortAccessors);

  return (
    <div className="category-table__products-scroll">
      <table className="category-table__products-table">
        <thead>
          <tr>
            <SortableHeader columnKey="image" label="Product Image" sorting={sorting} />
            <SortableHeader columnKey="product" label="Product Name" sorting={sorting} />
            <SortableHeader columnKey="sku" label="SKU ID" sorting={sorting} />
            <SortableHeader columnKey="barcode" label="Barcode" sorting={sorting} />
            <SortableHeader columnKey="stock" label="Available Stock" sorting={sorting} />
          </tr>
        </thead>
        <tbody>
          {sorting.sortedItems.map((product) => (
            <tr key={product.id}>
              <td><CategoryProductImage product={product} /></td>
              <td><strong>{product.name}</strong></td>
              <td>{product.hasSizes ? "Multiple SKUs" : product.sku}</td>
              <td>{product.hasSizes ? "Multiple barcodes" : product.barcode}</td>
              <td><strong>{getProductStock(product)}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CategoryTable({ categories: categoryRecords = [], products = [], onEditCategory, onRemoveCategory }) {
  // Only one category is expanded at a time.
  const [expandedCategoryId, setExpandedCategoryId] =
    useState("category-footwear");

  // Add product count, product records and total stock to every category.
  const categories = categoryRecords.map((category) => {
    const categoryProducts = getProductsForCategory(category, products);

    const totalStock = categoryProducts.reduce(
      (stockTotal, product) =>
        stockTotal + getProductStock(product),
      0,
    );

    return {
      ...category,
      products: categoryProducts,
      totalStock,
    };
  });
  const sorting = useTableSort(categories, categorySortAccessors);
  const pagination = useTablePagination(sorting.sortedItems);

  // Open the selected category or close it when clicked again.
  function toggleCategory(categoryId) {
    setExpandedCategoryId((currentCategoryId) =>
      currentCategoryId === categoryId ? null : categoryId,
    );
  }

  return (
    <section
      className="orders-table-section category-table-section"
      aria-label="Product categories"
    >
      <div className="orders-table__scroll">
        <table className="orders-table category-table">
          <thead>
            <tr>
              <th className="orders-table__expand-column"></th>
              <SortableHeader columnKey="category" label="Category" sorting={sorting} />
              <SortableHeader columnKey="description" label="Description" sorting={sorting} />
              <SortableHeader columnKey="products" label="Products" sorting={sorting} />
              <SortableHeader columnKey="stock" label="Total Stock" sorting={sorting} />
              <SortableHeader columnKey="status" label="Status" sorting={sorting} />
              <th className="orders-table__actions-heading">
                Actions
              </th>
            </tr>
          </thead>

          <tbody>
            {pagination.pageItems.map((category) => {
              const isExpanded =
                expandedCategoryId === category.id;

              return (
                <Fragment key={category.id}>
                  {/* Main category row */}
                  <tr>
                    <td>
                      <button
                        className="orders-table__expand-button"
                        type="button"
                        onClick={() => toggleCategory(category.id)}
                        aria-expanded={isExpanded}
                        aria-label={
                          isExpanded
                            ? `Collapse ${category.name}`
                            : `Expand ${category.name}`
                        }
                      >
                        {isExpanded ? (
                          <ChevronDown
                            size={18}
                            aria-hidden="true"
                          />
                        ) : (
                          <ChevronRight
                            size={18}
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    </td>

                    <td>
                      <strong>{category.name}</strong>
                    </td>

                    <td>{category.description}</td>

                    <td>
                      <strong>{category.products.length}</strong>
                    </td>

                    <td>
                      <strong>{category.totalStock}</strong>
                    </td>

                    <td>
                      <span
                        className={`category-table__status category-table__status--${category.status}`}
                      >
                        {category.status === "active"
                          ? "Active"
                          : "Needs attention"}
                      </span>
                    </td>

                    <td>
                      <ActionMenu label={`More actions for ${category.name}`} items={[
                        { label: "Edit category", icon: <Pencil size={16} />, onClick: () => onEditCategory?.(category) },
                        { label: "Remove category", icon: <Trash2 size={16} />, danger: true, onClick: () => onRemoveCategory?.(category) },
                      ]} />
                    </td>
                  </tr>

                  {/* Products belonging to the expanded category */}
                  {isExpanded && (
                    <tr className="category-table__details-row">
                      <td
                        className="category-table__details-cell"
                        colSpan={7}
                      >
                        <div className="category-table__products">
                          <h3>
                            Products in {category.name}
                          </h3>

                          {category.products.length === 0 ? (
                            <p>
                              No products belong to this category.
                            </p>
                          ) : (
                            <CategoryProductsTable products={category.products} />
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <TablePagination pagination={pagination} label="categories" />
    </section>
  );
}

export default CategoryTable;
