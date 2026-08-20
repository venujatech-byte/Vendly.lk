// React state controls selected and expanded order rows.
import { Fragment, useState } from "react";
import OrderDetails from "./OrderDetails";

import {
  ChevronDown,
  ChevronRight,
  Package,
  Download,
  Pencil,
  Trash2,
} from "lucide-react";
import ActionMenu from "./ActionMenu";

import "./OrderTable.css";

// Capitalize an order status for display inside its coloured status badge.
function formatStatus(status) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

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
}) {
  // Remember which row is expanded and which rows are checkbox-selected.
  const [expandedOrderId, setExpandedOrderId] = useState(null);
  const [selectedOrderIds, setSelectedOrderIds] = useState([]);

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
    const allOrdersAreSelected =
      orders.length > 0 && selectedOrderIds.length === orders.length;

    if (allOrdersAreSelected) {
      setSelectedOrderIds([]);
      return;
    }

    setSelectedOrderIds(orders.map((order) => order.id));
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
              <th>Order</th>
              <th>Customer</th>
              <th>Items</th>
              <th>Total</th>
              <th>Courier</th>
              <th>Status</th>
              <th>Date</th>
              <th className="orders-table__actions-heading">Actions</th>
            </tr>
          </thead>

          <tbody>
            {orders.map((order) => {
              // Row-specific display values for the current order.
              const isExpanded = expandedOrderId === order.id;
              const isSelected = selectedOrderIds.includes(order.id);

              return (
              <Fragment key={order.id}>
              <tr
               className={isSelected ? "orders-table__row--selected" : ""}
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

                  <td>{order.courier}</td>

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

                  <td>
                      <ActionMenu label={`More actions for ${order.orderNumber}`} items={[
                        { label: "Edit order", icon: <Pencil size={16} />, onClick: () => onEditOrder?.(order) },
                        { label: "Remove order", icon: <Trash2 size={16} />, danger: true, onClick: () => onRemoveOrder?.(order) },
                      ]} />
                  </td>
                </tr>
                {/* Insert the detailed order information directly below its row. */}
                {isExpanded && (
  <tr className="orders-table__details-row">
    <td className="orders-table__details-cell" colSpan={10}>
                  <OrderDetails
                    order={order}
                    onStatusChange={onStatusChange}
                    onGenerateWaybill={onGenerateWaybill}
                    onFraudReport={onFraudReport}
                    onCourierIssue={onCourierIssue}
                    onWaybillSave={onWaybillSave}
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

      {/* Temporary record count and pagination controls. */}
      <footer className="orders-table__footer">
        <span>
          Showing {orders.length === 0 ? 0 : 1} to {orders.length} of{" "}
          {orders.length} orders
        </span>

        <div className="orders-table__pagination">
          <button type="button" disabled>
            Previous
          </button>

          <button className="orders-table__page--active" type="button">
            1
          </button>

          <button type="button">2</button>
          <button type="button">3</button>
          <button type="button">Next</button>
        </div>
      </footer>
    </section>
  );
}

export default OrderTable;
