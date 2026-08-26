// Row action icon and shared stock-status helper.
import { PackagePlus } from "lucide-react";

import SortableHeader from "./SortableHeader";
import useTableSort from "../hooks/useTableSort";
import { getStockStatus } from "../utils/inventory";

// Convert a value such as "low-stock" into the readable text "Low Stock".
function formatStatus(status) {
  return status
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

// Display the size-level SKU, barcode, stock, and status for a sized product.
function ProductSizesTable({ sizes, onAdjustStock }) {
  const sorting = useTableSort(sizes, {
    size: (sizeOption) => sizeOption.size,
    sku: (sizeOption) => sizeOption.sku,
    barcode: (sizeOption) => sizeOption.barcode,
    stock: (sizeOption) => Number(sizeOption.stock || 0),
    status: (sizeOption) => getStockStatus(sizeOption.stock, 2),
  });

  return (
    <section className="product-variants">
      <div className="product-variants__scroll">
        <table className="product-variants__table">
          <thead>
            <tr>
              <SortableHeader columnKey="size" label="Size" sorting={sorting} />
              <SortableHeader columnKey="sku" label="SKU" sorting={sorting} />
              <SortableHeader columnKey="barcode" label="Barcode" sorting={sorting} />
              <SortableHeader columnKey="stock" label="Available" sorting={sorting} />
              <SortableHeader columnKey="status" label="Status" sorting={sorting} />
              <th aria-label="Size actions"></th>
            </tr>
          </thead>

          <tbody>
            {sorting.sortedItems.map((sizeOption) => {
              // Size variants use a smaller low-stock threshold than products.
              const stockStatus = getStockStatus(sizeOption.stock, 2);

              return (
                <tr key={sizeOption.id}>
                  <td>
                    <strong>EU {sizeOption.size}</strong>
                  </td>
                  <td>{sizeOption.sku}</td>
                  <td>{sizeOption.barcode}</td>
                  <td>
                    <strong>{sizeOption.stock}</strong>
                  </td>

                  <td>
                    <span
                      className={`inventory-table__status inventory-table__status--${stockStatus}`}
                    >
                      {formatStatus(stockStatus)}
                    </span>
                  </td>

                  <td className="product-variants__actions-cell">
                    <button
                      className="product-variants__adjust-button"
                      type="button"
                      onClick={() => onAdjustStock?.(sizeOption.id)}
                      aria-label={`Adjust stock for size ${sizeOption.size}`}
                    >
                      <PackagePlus size={15} aria-hidden="true" />
                      Adjust
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default ProductSizesTable;
