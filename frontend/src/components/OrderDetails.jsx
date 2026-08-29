// Icons used in the customer information and order action areas.
import {
  Receipt,
  ChevronDown,
  CircleAlert,
  Flag,
  MapPin,
  Phone,
  Printer,
  User,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { printWaybill } from "../services/operationService";

import "./OrderDetails.css";

const nextStatuses = {
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

function OrderDetails({
  order,
  onStatusChange,
  onGenerateWaybill,
  onFraudReport,
  onRecordPayment,
  onCourierIssue,
  onWaybillSave,
  onWarrantyClaim,
}) {
  const [actionError, setActionError] = useState("");
  const [isWorking, setIsWorking] = useState(false);
  const [waybillNumber, setWaybillNumber] = useState(order.waybillNumber ?? "");

  useEffect(() => {
    setWaybillNumber(order.waybillNumber ?? "");
  }, [order.id, order.waybillNumber]);
  // Use real order items when available, otherwise show a safe placeholder row.
  const items = order.items ?? [
    {
      id: `${order.id}-item`,
      name: "Order items",
      quantity: order.itemCount,
      price: order.total,
    },
  ];
  const hasActiveWarranty = items.some(
    (item) => item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date(),
  );

  async function handlePrintWaybill() {
    const printWindow = window.open("", "_blank", "width=900,height=700");
    setActionError("");
    setIsWorking(true);

    try {
      const printableOrder = order.waybillNumber
        ? order
        : await onGenerateWaybill?.(order.id);
      printWaybill(printableOrder, printWindow);
    } catch (error) {
      printWindow?.close();
      setActionError(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleFraudReport() {
    const note = window.prompt(
      "Add a private note explaining why this appears to be a fake order:",
      "Customer details could not be verified.",
    );

    if (note === null) return;
    setActionError("");
    setIsWorking(true);

    try {
      await onFraudReport?.(order.id, note);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleCourierIssue() {
    const note = window.prompt(
      "Describe the courier branch problem:",
      "Delivery was affected by a courier branch problem.",
    );

    if (note === null) return;
    setActionError("");
    setIsWorking(true);

    try {
      await onCourierIssue?.(order.id, note);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  async function handleWaybillSave() {
    const trimmedWaybill = waybillNumber.trim();
    if (!trimmedWaybill) {
      setActionError("Enter a waybill number before saving.");
      return;
    }

    setActionError("");
    setIsWorking(true);
    try {
      await onWaybillSave?.(order.id, trimmedWaybill);
    } catch (error) {
      setActionError(error.message);
      window.alert(error.message);
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div className="order-details">
      {order.fraudWarning && (
        <section className="order-details__warning" role="alert">
          <CircleAlert size={19} aria-hidden="true" />
          <div>
            <strong>Fraud warning</strong>
            <p>{order.fraudWarning.message}</p>
            <span>
              Risk: {order.fraudWarning.riskLevel} · Score: {order.fraudWarning.score}
              {order.fraudWarning.reportCount
                ? ` · ${order.fraudWarning.reportCount} report(s)`
                : ""}
              {order.fraudWarning.returnedOrderCount
                ? ` · ${order.fraudWarning.returnedOrderCount} return(s)`
                : ""}
            </span>
          </div>
        </section>
      )}
      {/* These values replace the columns hidden from the compact phone row. */}
      <section className="order-details__mobile-meta" aria-label="Order summary details">
        <div>
          <span>Courier</span>
          <strong>{order.courier || "Not assigned"}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>
            {readableStatus(order.status || order.fulfilmentStatus || "pending")}
          </strong>
        </div>
        <div>
          <span>Order date</span>
          <strong>{order.date} {order.time}</strong>
        </div>
      </section>

      {/* Products included in this order. */}
      <section className="order-details__section order-details__items-section">
        <h3>Items in this order</h3>

        <div className="order-details__items">
          {items.map((item) => (
            <div className="order-details__item" key={item.id}>
              {item.imageUrl ? <img className="order-details__item-image" src={item.imageUrl} alt="" /> : null}
              <div>
                <strong>{item.name}</strong>

                <span>
                  Qty: {item.quantity} × {item.unitPrice ?? item.price}
                </span>
                {item.warrantyPeriodMonths > 0 && (
                  <span>
                    Warranty: {item.warrantyPeriodMonths} month{item.warrantyPeriodMonths === 1 ? "" : "s"}
                    {item.warrantyExpiresAt ? ` · expires ${new Date(item.warrantyExpiresAt).toLocaleDateString("en-LK")}` : ""}
                  </span>
                )}
              </div>

              <strong>{item.price}</strong>
            </div>
          ))}
        </div>
      </section>

      {/* Customer contact information and delivery address. */}
      <section className="order-details__section order-details__address">
        <h3>Delivery Address</h3>

        <div className="order-details__information">
          <div>
            <User size={17} />
            <span>{order.customerName}</span>
          </div>

          <div>
            <Phone size={17} />
            <span>{order.phoneNumber}</span>
          </div>

          {order.secondaryPhoneNumber && (
            <div>
              <Phone size={17} />
              <span>{order.secondaryPhoneNumber}</span>
            </div>
          )}

          <div>
            <MapPin size={17} />
            <span>{order.deliveryAddress ?? "Address not available"}</span>
          </div>
        </div>
      </section>

      {/* Product subtotal, delivery fee, final total, and waybill number. */}
      <section className="order-details__section order-details__summary">
        <div>
          <span>Subtotal</span>
          <strong>{order.subtotal ?? order.total}</strong>
        </div>

        {order.discountMinor > 0 && (
          <div>
            <span>Discount</span>
            <strong>-{order.discount}</strong>
          </div>
        )}

        <div>
          <span>Delivery Fee</span>
          <strong>{order.deliveryFee ?? "Not calculated"}</strong>
        </div>

        {/* What the courier is charging for, and what the parcel must weigh on
            their scale. A mismatch is a surcharge the seller pays. */}
        {order.totalWeightGrams > 0 && (
          <div>
            <span>Total Weight</span>
            {/* Formatted here from the raw grams. Depending on a second
                pre-formatted field meant the label could render with nothing
                beside it if that field was ever missing. */}
            <strong>
              {order.totalWeightGrams >= 1000
                ? `${(order.totalWeightGrams / 1000).toFixed(2)} kg`
                : `${order.totalWeightGrams} g`}
            </strong>
          </div>
        )}

        <div className="order-details__total">
          <span>Total</span>
          <strong>{order.total}</strong>
        </div>

        {/* Anything already paid is deducted, so the courier only collects
            the remaining balance. */}
        {order.paidAmountMinor > 0 && (
          <>
            <div>
              <span>
                {order.paymentMethod === "deposit" ? "Deposit paid" : "Paid"}
              </span>
              <strong>-{order.paidAmount}</strong>
            </div>

            <div className="order-details__total">
              <span>Balance to collect</span>
              <strong>{order.balanceDue}</strong>
            </div>
          </>
        )}

        <div className="order-details__waybill-row">
          <label htmlFor={`waybill-${order.id}`}>Waybill No</label>
          <div className="order-details__waybill-editor">
            <input
              id={`waybill-${order.id}`}
              type="text"
              value={waybillNumber}
              onChange={(event) => setWaybillNumber(event.target.value)}
              placeholder="Enter waybill number"
              disabled={isWorking}
            />
            <button type="button" onClick={handleWaybillSave} disabled={isWorking}>
              Save
            </button>
          </div>
        </div>
      </section>

      {/* Proof of payment, kept on the order so the seller can check it long
          after the conversation has scrolled away. */}
      {order.paymentReceipts?.length > 0 && (
        <section className="order-details__section order-details__receipts">
          <h3>Payment receipts</h3>
          <div>
            {order.paymentReceipts.map((receipt) => (
              <a
                key={receipt.url}
                href={receipt.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <img src={receipt.url} alt="Payment receipt" loading="lazy" />
                <small>
                  LKR {((receipt.amountMinor ?? 0) / 100).toLocaleString("en-LK")}
                </small>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Seller actions for status, waybill printing, and fraud reporting. */}
      <section className="order-details__section order-details__actions">
        <h3>Order Actions</h3>

        <label className="order-details__status-control">
          <span>Update Status</span>
          <div>
            <select
              defaultValue=""
              onChange={(event) => {
                if (event.target.value) {
                  onStatusChange?.(order.id, event.target.value);
                  event.target.value = "";
                }
              }}
              disabled={(nextStatuses[order.fulfilmentStatus] ?? []).length === 0}
            >
              <option value="">Choose next status</option>
              {(nextStatuses[order.fulfilmentStatus] ?? []).map((status) => (
                <option
                  key={status}
                  value={status}
                  // The server refuses this too. Disabling it here means the
                  // seller learns before choosing rather than after.
                  disabled={status === "confirmed" && order.paymentPending}
                >
                  {readableStatus(status)}
                  {status === "confirmed" && order.paymentPending
                    ? " - payment not received"
                    : ""}
                </option>
              ))}
            </select>
            <ChevronDown size={17} aria-hidden="true" />
          </div>
        </label>

        {order.paymentPending && (
          <p className="order-details__payment-hold">
            This order is waiting on a bank transfer. Record the payment, or
            change it to cash on delivery, before confirming it.
          </p>
        )}

        <button
          className="order-details__print-button"
          type="button"
          onClick={handlePrintWaybill}
          disabled={isWorking}
        >
          <Printer size={17} />
          Print Waybill
        </button>

        <button
          className="order-details__print-button"
          type="button"
          onClick={handleCourierIssue}
          disabled={isWorking}
        >
          <CircleAlert size={17} />
          Report Courier Issue
        </button>

        {hasActiveWarranty && <button
          className="order-details__print-button"
          type="button"
          onClick={() => onWarrantyClaim?.(order)}
          disabled={isWorking}
        >
          <ShieldCheck size={17} />
          Warranty Claim
        </button>}

        {/* Money the seller has received. Offered while anything is still
            outstanding, and on any order - a cash-on-delivery customer who
            transfers early is not a different kind of order. */}
        {order.balanceMinor > 0 && (
          <button
            className="order-details__payment-button"
            type="button"
            onClick={() => onRecordPayment?.(order)}
            disabled={isWorking}
          >
            <Receipt size={17} />
            {order.paymentPending ? "Record payment" : "Mark as paid"}
          </button>
        )}

        <button
          className="order-details__fraud-button"
          type="button"
          onClick={handleFraudReport}
          disabled={isWorking || Boolean(order.fraudReport)}
        >
          <Flag size={17} />
          {order.fraudReport ? "Fraud Reported" : "Report Fake Order"}
        </button>

        {actionError && (
          <p className="order-details__action-error" role="alert">{actionError}</p>
        )}
      </section>
      {/* The customer's own instruction for this delivery - a landmark, a time
          to call, gift wrapping. Given its own block rather than a line in the
          address, because it is the one thing here nobody can guess. */}
      {/* Always rendered, even when empty. Showing it only for orders that
          have one made those orders lay out differently from the rest, and a
          seller scanning a list of orders reads the shape before the words. */}
      <section
        className={`order-details__section order-details__customer-note ${
          order.customerNote ? "" : "is-empty"
        }`}
      >
        <h3>Customer note</h3>
        <p>{order.customerNote || "No note from the customer for this order."}</p>
      </section>

    </div>
  );
}

export default OrderDetails;
