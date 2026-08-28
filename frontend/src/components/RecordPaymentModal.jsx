import { useState } from "react";
import { CircleAlert, Receipt, Upload, X } from "lucide-react";

import "./RecordPaymentModal.css";

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("That image could not be read."));
    reader.readAsDataURL(file);
  });
}

function money(minorUnits = 0) {
  return `LKR ${(minorUnits / 100).toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Records money the seller has actually received against an order.
 *
 * The amount is entered rather than assumed: a customer who said "half" may
 * transfer any figure, and whatever is left becomes the cash-on-delivery
 * amount the courier collects.
 */
function RecordPaymentModal({ order, onClose, onSubmit }) {
  const totalMinor = order.totalAmountMinor ?? 0;
  const [amount, setAmount] = useState("");
  const [receiptFile, setReceiptFile] = useState(null);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState("");

  const paidMinor = Math.round(Number(amount || 0) * 100);
  const balanceMinor = Math.max(0, totalMinor - paidMinor);
  const isOverpaid = paidMinor > totalMinor;

  async function submit(event) {
    event.preventDefault();

    if (paidMinor <= 0) {
      setError("Enter the amount you received.");
      return;
    }

    if (isOverpaid) {
      setError("The amount received cannot be more than the order total.");
      return;
    }

    setIsWorking(true);
    setError("");

    try {
      // Read here and uploaded by the server, the same route the chatbot
      // uses for customer images. Sent together with the amount so a failure
      // leaves neither recorded - never a payment with no proof of it.
      const receiptImage = receiptFile ? await readAsDataUrl(receiptFile) : "";

      await onSubmit({ paidAmountMinor: paidMinor, receiptImage });
      onClose();
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <div className="record-payment" role="presentation">
      <button
        className="record-payment__backdrop"
        type="button"
        aria-label="Close"
        onClick={onClose}
      />
      <form className="record-payment__panel" onSubmit={submit}>
        <header>
          <span><Receipt size={20} /></span>
          <div>
            <h2>Record payment</h2>
            <p>{order.orderNumber} · Total {money(totalMinor)}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        <label>
          <span>Amount received (LKR)</span>
          <input
            type="number"
            min="0"
            step="0.01"
            autoFocus
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder={(totalMinor / 100).toFixed(2)}
          />
        </label>

        <button
          type="button"
          className="record-payment__full"
          onClick={() => setAmount((totalMinor / 100).toFixed(2))}
        >
          Paid in full
        </button>

        <label className="record-payment__receipt">
          <span>Payment receipt</span>
          <div>
            <Upload size={16} />
            {receiptFile ? receiptFile.name : "Attach the slip or screenshot"}
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setReceiptFile(event.target.files?.[0] || null)}
            />
          </div>
        </label>

        {/* What the courier will be told to collect. Shown before confirming,
            because it is the number that ends up on the waybill. */}
        {paidMinor > 0 && !isOverpaid && (
          <p className="record-payment__balance">
            {balanceMinor > 0
              ? `Cash on delivery: ${money(balanceMinor)}`
              : "Paid in full - nothing to collect on delivery."}
          </p>
        )}

        {(error || isOverpaid) && (
          <p className="record-payment__error" role="alert">
            <CircleAlert size={15} />
            {error || "The amount received cannot be more than the order total."}
          </p>
        )}

        {/* The way out when the transfer never arrives. Without it the order
            is stuck: it cannot be confirmed while payment is pending, and
            cancelling an order the customer still wants is the wrong remedy. */}
        {order.paymentPending && (
          <button
            type="button"
            className="record-payment__cod"
            disabled={isWorking}
            onClick={async () => {
              setIsWorking(true);
              setError("");

              try {
                await onSubmit({ convertToCashOnDelivery: true });
                onClose();
              } catch (conversionError) {
                setError(conversionError.message);
              } finally {
                setIsWorking(false);
              }
            }}
          >
            Change to cash on delivery ({money(totalMinor)} collected by the courier)
          </button>
        )}

        <footer>
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={isWorking || paidMinor <= 0 || isOverpaid}>
            {isWorking ? "Saving…" : "Confirm payment"}
          </button>
        </footer>
      </form>
    </div>
  );
}

export default RecordPaymentModal;
