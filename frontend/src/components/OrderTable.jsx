// React state controls selected and expanded order rows.
import { Fragment, useState } from "react";
import OrderDetails from "./OrderDetails";

import {
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Package,
  Download,
  Flag,
  Hash,
  Pencil,
  Printer,
  RefreshCw,
  Trash2,
  ShieldCheck,
} from "lucide-react";
import ActionMenu from "./ActionMenu";
import TablePagination from "./TablePagination";
import SortableHeader from "./SortableHeader";
import useTablePagination from "../hooks/useTablePagination";
import useTableSort from "../hooks/useTableSort";
import { printWaybill } from "../services/operationService";

import "./OrderTable.css";

// Capitalize an order status for display inside its coloured status badge.
function formatStatus(status) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

// Only valid next states are offered in the row action menu.
const nextStatuses = {
  pending: ["confirmed", "cancelled"],
  "needs-confirmation": ["confirmed", "cancelled"],
  confirmed: ["packed", "cancelled"],
  packed: ["shipped", "cancelled"],
  shipped: ["delivered", "returned"],
};

function readableStatus(status) {
  return status
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function hasActiveWarranty(order) {
  return (order.items ?? []).some(
    (item) => item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date(),
  );
}

const orderSortAccessors = {
  order: (order) => order.orderNumber,
  customer: (order) => order.customerName,
  items: (order) => order.itemCount ?? order.items?.length ?? 0,
  total: (order) => Number(String(order.total ?? "0").replace(/[^0-9.-]/g, "")),
  courier: (order) => order.courierCode || order.courier,
  status: (order) => order.fulfilmentStatus || order.status,
  date: (order) => new Date(`${order.date ?? ""} ${order.time ?? ""}`),
  waybill: (order) => order.waybillNumber,
};

function OrderTable({
  orders = [],
  onStatusChange,
  onGenerateWaybill,
  onFraudReport,
  onCourierIssue,
  onEditOrder,
  onRemoveOrder,
  onBulkStatusChange,
  onExportSelected,
  onWaybillSave,
  onWarrantyClaim,
}) {
  // Remember which row is expanded and which rows are checkbox-selected.
  const [expandedOrderId, setExpandedOrderId] = useState(null);
  const [selectedOrderIds, setSelectedOrderIds] = useState([]);
  const sorting = useTableSort(orders, orderSortAccessors);
  const pagination = useTablePagination(sorting.sortedItems);

  // Expand one order at a time, or close the row when clicked again.
  function toggleExpandedOrder(orderId) {
    if (expandedOrderId === orderId) {
      setExpandedOrderId(null);
      return;
    }

    setExpandedOrderId(orderId);
  }

  // Add or remove a single order ID from the selected-order list.
  function toggleSelectedOrder(orderId) {
    setSelectedOrderIds((currentIds) => {
      const isAlreadySelected = currentIds.includes(orderId);

      if (isAlreadySelected) {
        return currentIds.filter((id) => id !== orderId);
      }

      return [...currentIds, orderId];
    });
  }

  // Select every order or clear the full selection.
  function toggleAllOrders() {
    const visibleOrderIds = pagination.pageItems.map((order) => order.id);
    const allOrdersAreSelected =
      visibleOrderIds.length > 0 && visibleOrderIds.every((id) => selectedOrderIds.includes(id));

    if (allOrdersAreSelected) {
      setSelectedOrderIds((currentIds) => currentIds.filter((id) => !visibleOrderIds.includes(id)));
      return;
    }

    setSelectedOrderIds((currentIds) => [...new Set([...currentIds, ...visibleOrderIds])]);
  }

  function showActionError(error) {
    window.alert(error?.message || "The order action could not be completed.");
  }

  async function printOrderWaybill(order) {
    const printWindow = window.open("", "_blank", "width=900,height=700");

    try {
      const printableOrder = order.waybillNumber
        ? order
        : await onGenerateWaybill?.(order.id);
      printWaybill(printableOrder, printWindow);
    } catch (error) {
      printWindow?.close();
      showActionError(error);
    }
  }

  async function editOrderWaybill(order) {
    const waybillNumber = window.prompt(
      "Enter the waybill number:",
      order.waybillNumber ?? "",
    );

    if (waybillNumber === null) return;
    if (!waybillNumber.trim()) {
      window.alert("Enter a waybill number before saving.");
      return;
    }

    try {
      await onWaybillSave?.(order.id, waybillNumber.trim());
    } catch (error) {
      showActionError(error);
    }
  }

  async function reportOrderCourierIssue(order) {
    const note = window.prompt(
      "Describe the courier branch problem:",
      "Delivery was affected by a courier branch problem.",
    );

    if (note === null) return;

    try {
      await onCourierIssue?.(order.id, note);
    } catch (error) {
      showActionError(error);
    }
  }

  async function reportOrderAsFake(order) {
    const note = window.prompt(
      "Add a private note explaining why this appears to be a fake order:",
      "Customer details could not be verified.",
    );

    if (note === null) return;

    try {
      await onFraudReport?.(order.id, note);
    } catch (error) {
      showActionError(error);
    }
  }

  return (
    <section className="orders-table-section" aria-label="Orders list">
      {selectedOrderIds.length > 0 && (
        <div className="inventory-table__bulk-actions">
          <strong>{selectedOrderIds.length} orders selected</strong>
          <select
            className="inventory-table__bulk-status"
            defaultValue=""
            aria-label="Change status for selected orders"
            onChange={(event) => {
              if (event.target.value) {
                onBulkStatusChange?.(selectedOrderIds, event.target.value);
                event.target.value = "";
              }
            }}
          >
            <option value="" disabled>Change status</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="packed">Packed</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="returned">Returned</option>
          </select>
          <button type="button" onClick={() => onExportSelected?.(selectedOrderIds)}>
            <Download size={16} aria-hidden="true" />
            Export selected
          </button>
        </div>
      )}
      {/* Horizontal scrolling protects the table layout on narrow screens. */}
      <div className="orders-table__scroll">
        <table className="orders-table orders-table--orders">
          <thead>
            <tr>
              <th className="orders-table__checkbox-column">
                <input
                  type="checkbox"
                  checked={
                    orders.length > 0 && selectedOrderIds.length === orders.length
                  }
                  onChange={toggleAllOrders}
                  aria-label="Select all orders"
                />
              </th>

              <th className="orders-table__expand-column"></th>
              <SortableHeader columnKey="order" label="Order" sorting={sorting} />
              <SortableHeader columnKey="customer" label="Customer" sorting={sorting} />
              <SortableHeader columnKey="items" label="Items" sorting={sorting} />
              <SortableHeader columnKey="total" label="Total" sorting={sorting} />
              <SortableHeader columnKey="courier" label="Courier Code" sorting={sorting} />
              <SortableHeader columnKey="status" label="Status" sorting={sorting} />
              <SortableHeader columnKey="date" label="Date" sorting={sorting} />
              <SortableHeader columnKey="waybill" label="Waybill ID" sorting={sorting} />
              <th className="orders-table__actions-heading">Actions</th>
            </tr>
          </thead>

          <tbody>
            {pagination.pageItems.map((order) => {
              // Row-specific display values for the current order.
              const isExpanded = expandedOrderId === order.id;
              const isSelected = selectedOrderIds.includes(order.id);
              const hasWarning = Boolean(order.fraudWarning?.matched ?? order.fraudWarning);
              const currentStatus = order.fulfilmentStatus || order.status || "pending";
              const availableStatuses = nextStatuses[currentStatus] ?? [];

              return (
              <Fragment key={order.id}>
              <tr
               className={[
                 isSelected ? "orders-table__row--selected" : "",
                 hasWarning ? "orders-table__row--warning" : "",
               ].filter(Boolean).join(" ")}
              >
                  <td>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelectedOrder(order.id)}
                      aria-label={`Select order ${order.orderNumber}`}
                    />
                  </td>

                  <td>
                    <button
                      className="orders-table__expand-button"
                      type="button"
                      onClick={() => toggleExpandedOrder(order.id)}
                      aria-expanded={isExpanded}
                      aria-label={
                        isExpanded
                          ? `Collapse order ${order.orderNumber}`
                          : `Expand order ${order.orderNumber}`
                      }
                    >
                      {isExpanded ? (
                        <ChevronDown size={18} />
                      ) : (
                        <ChevronRight size={18} />
                      )}
                    </button>
                  </td>

                  <td>
                    <strong className="orders-table__order-number">
                      #{order.orderNumber}
                    </strong>

                    <span className="orders-table__item-count">
                      {order.itemCount}{" "}
                      {order.itemCount === 1 ? "item" : "items"}
                    </span>
                  </td>

                  <td>
                    <strong>{order.customerName}</strong>
                    <span className="orders-table__secondary">
                      {order.phoneNumber}
                    </span>
                  </td>

                  <td>
                    <div className="orders-table__items">
                      {(order.items ?? []).slice(0, 3).map((item, index) => (
                        <span
                          className="orders-table__product-preview"
                          key={item.id ?? index}
                        >
                          {item.imageUrl ? (
                            <img src={item.imageUrl} alt="" />
                          ) : (
                            <Package size={18} aria-hidden="true" />
                          )}
                        </span>
                      ))}
                      {order.itemCount > 3 && <span className="orders-table__product-more">+{order.itemCount - 3}</span>}
                    </div>
                  </td>

                  <td className="orders-table__total">{order.total}</td>

                  <td>
                    <strong>{order.courierCode || order.courier || "Not assigned"}</strong>
                  </td>

                  <td>
                    <span
                      className={`orders-table__status orders-table__status--${order.status}`}
                    >
                      {formatStatus(order.status)}
                    </span>
                  </td>

                  <td>
                    <span>{order.date}</span>
                    <span className="orders-table__secondary">
                      {order.time}
                    </span>
                  </td>

                  <td>{order.waybillNumber || "—"}</td>

                  <td>
                    <ActionMenu
                      label={`More actions for ${order.orderNumber}`}
                      items={[
                        {
                          label: "Edit order",
                          icon: <Pencil size={16} aria-hidden="true" />,
                          onClick: () => onEditOrder?.(order),
                        },
                        {
                          label: "Edit waybill number",
                          icon: <Hash size={16} aria-hidden="true" />,
                          onClick: () => editOrderWaybill(order),
                        },
                        {
                          label: "Print waybill",
                          icon: <Printer size={16} aria-hidden="true" />,
                          onClick: () => printOrderWaybill(order),
                        },
                        ...availableStatuses.map((status) => ({
                          label: `Mark as ${readableStatus(status)}`,
                          icon: <RefreshCw size={16} aria-hidden="true" />,
                          onClick: () => onStatusChange?.(order.id, status),
                        })),
                        {
                          label: "Report courier issue",
                          icon: <CircleAlert size={16} aria-hidden="true" />,
                          onClick: () => reportOrderCourierIssue(order),
                        },
                        ...(hasActiveWarranty(order) ? [{
                          label: "Warranty claim",
                          icon: <ShieldCheck size={16} aria-hidden="true" />,
                          onClick: () => onWarrantyClaim?.(order),
                        }] : []),
                        {
                          label: order.fraudReport ? "Fraud already reported" : "Report fake order",
                          icon: <Flag size={16} aria-hidden="true" />,
                          disabled: Boolean(order.fraudReport),
                          danger: true,
                          onClick: () => reportOrderAsFake(order),
                        },
                        {
                          label: "Remove order",
                          icon: <Trash2 size={16} aria-hidden="true" />,
                          danger: true,
                          onClick: () => onRemoveOrder?.(order),
                        },
                      ]}
                    />
                  </td>
                </tr>
                {/* Insert the detailed order information directly below its row. */}
                {isExpanded && (
  <tr className="orders-table__details-row">
    <td className="orders-table__details-cell" colSpan={11}>
                  <OrderDetails
                    order={order}
                    onStatusChange={onStatusChange}
                    onGenerateWaybill={onGenerateWaybill}
                    onFraudReport={onFraudReport}
                    onCourierIssue={onCourierIssue}
                    onWaybillSave={onWaybillSave}
                    onWarrantyClaim={onWarrantyClaim}
                  />
    </td>
  </tr>
)}
  </Fragment>

              );
            })}
          </tbody>
        </table>
      </div>

      <TablePagination pagination={pagination} label="orders" />
    </section>
  );
}

export default OrderTable;
