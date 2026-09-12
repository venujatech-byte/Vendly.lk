import { useEffect, useState } from "react";
import { Check, CircleHelp, Download, Home, Info, Mail, Package, Truck } from "lucide-react";
import { useAuth } from "../context/authContextValue";
import { downloadReceiptPdf } from "../services/receiptService";
import { submitGuestOrderEmail } from "../services/publicService";
import { storefrontText } from "../data/storefrontText";
import "./OrderReceipt.css";

function money(minorUnits = 0) {
  return `LKR ${(Number(minorUnits) / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value) {
  if (!value) return new Date().toLocaleDateString("en-LK", { year: "numeric", month: "long", day: "numeric" });
  let date;
  if (typeof value?.toDate === "function") {
    date = value.toDate();
  } else if (value?.seconds || value?._seconds) {
    date = new Date((value.seconds || value._seconds) * 1000);
  } else {
    date = new Date(value);
  }
  return Number.isNaN(date.getTime())
    ? new Date().toLocaleDateString("en-LK")
    : date.toLocaleDateString("en-LK", { year: "numeric", month: "long", day: "numeric" });
}

export default function OrderReceipt({ business, order, onClose, closeLabel = "Return", chatLanguage = "en" }) {
  const text = storefrontText(chatLanguage);
  const { user } = useAuth();
  const address = order.deliveryAddress || order.deliveryAddressObject || {};
  const customer = order.customerSnapshot || {};
  const payment = order.paymentMethod === "deposit" ? "Deposit / balance due" : order.paymentMethod === "paid" ? "Paid" : "Cash on delivery";

  const loggedInUserEmail = (!user?.isAnonymous && user?.email) ? user.email : "";
  const initialEmail = customer.email || order.customerEmail || order.email || loggedInUserEmail || "";
  const [emailInput, setEmailInput] = useState("");
  const [emailSubmitting, setEmailSubmitting] = useState(false);
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const [emailError, setEmailError] = useState("");

  const isDashboardOrder = closeLabel === "Return to Orders";
  const hasEmail = Boolean(initialEmail || emailSubmitted);
  const shouldPromptForEmail = !hasEmail && !isDashboardOrder && (user?.isAnonymous || !user);

  useEffect(() => {
    // If order was created without an email, but the customer is signed in with email:
    const targetEmail = loggedInUserEmail;
    const orderHasEmail = Boolean(customer.email || order.customerEmail || order.email);
    if (targetEmail && !orderHasEmail && !emailSubmitted && business?.shortCode && (order.id || order.orderId)) {
      submitGuestOrderEmail(business.shortCode, order.id || order.orderId, targetEmail)
        .then(() => setEmailSubmitted(true))
        .catch((err) => console.warn("Auto-attaching user email to order failed:", err));
    }
  }, [loggedInUserEmail, customer.email, order, business?.shortCode, emailSubmitted]);

  async function handleEmailSubmit(event) {
    event.preventDefault();
    if (!emailInput.trim() || !business?.shortCode || !(order.id || order.orderId)) return;
    setEmailSubmitting(true);
    setEmailError("");
    try {
      await submitGuestOrderEmail(business.shortCode, order.id || order.orderId, emailInput.trim());
      setEmailSubmitted(true);
    } catch (err) {
      setEmailError(err.message || "Could not save email. Please try again.");
    } finally {
      setEmailSubmitting(false);
    }
  }

  return <div className="receipt-layer">
    <section className="receipt-page">
      <div className="receipt-success-mark"><Check size={25} strokeWidth={3} /></div>
      <h1>{text.orderConfirmed}</h1>
      <p>{text.orderConfirmedHint}</p>

      {shouldPromptForEmail ? (
        <div className="receipt-email-prompt">
          <div className="receipt-email-prompt__icon"><Mail size={20} /></div>
          <div className="receipt-email-prompt__content">
            <h3>Get Order Tracking & Receipt by Email</h3>
            <p>Enter your email to receive live dispatch updates, courier tracking, and an itemized receipt.</p>
            <form onSubmit={handleEmailSubmit} className="receipt-email-prompt__form">
              <input
                type="email"
                placeholder="your.email@example.com"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                required
                disabled={emailSubmitting}
              />
              <button type="submit" disabled={emailSubmitting || !emailInput.trim()}>
                {emailSubmitting ? "Sending..." : "Send Live Updates"}
              </button>
            </form>
            {emailError && <span className="receipt-email-prompt__error">{emailError}</span>}
          </div>
        </div>
      ) : (emailSubmitted || hasEmail) && !isDashboardOrder ? (
        <div className="receipt-email-prompt is-success">
          <Check size={20} />
          <div className="receipt-email-prompt__content">
            <span style={{ fontSize: "0.92rem", fontWeight: 600 }}>
              Order confirmation & tracking details sent to <strong>{initialEmail || emailInput}</strong>!
            </span>
          </div>
        </div>
      ) : null}

      <article className="receipt-card">
        <header><div><small>{text.orderNumber}</small><strong>#{order.orderNumber}</strong></div><div><small>{text.orderDate}</small><span>{dateLabel(order.createdAt)}</span></div></header>
        <section className="receipt-status">
          <h2>{text.orderStatus}</h2>
          <div className="receipt-status__track"><span><Package size={15} />{text.statusConfirmed}</span><span><Truck size={15} />{text.statusProcessing}</span><span className="is-muted"><Home size={15} />{text.statusDelivered}</span></div>
          <div className="receipt-info"><Info size={18} /><span><strong>{text.trackingInfo}</strong>{text.trackingHint}</span></div>
        </section>

        <section className="receipt-items"><h2>{text.itemsInOrder}</h2>{(order.items || []).map((item) => <div key={item.variantId || item.id}><span className="receipt-item__image">{item.mediaUrl || item.imageUrl ? <img src={item.mediaUrl || item.imageUrl} alt="" /> : <Package size={25} />}</span><span><strong>{item.name || item.productName}</strong><small>{item.size ? `${text.variant}: ${item.size} | ` : ""}{text.qty}: {item.quantity}</small></span><strong>{money(item.lineTotalMinor ?? Number(item.sellingPrice || 0) * item.quantity * 100)}</strong></div>)}</section>

        <section className="receipt-details"><div><small>SHIPPING ADDRESS</small><strong>{customer.name || order.customerName || "Customer"}</strong><span>{[address.line1, address.line2, address.city, address.district, address.postalCode, address.country].filter(Boolean).join(", ")}</span></div><div><small>PAYMENT METHOD</small><strong>{payment}</strong><span>{order.paymentStatus === "partially-paid" ? `${money(order.balanceAmountMinor)} balance remaining` : "Payment details saved with this order."}</span></div></section>

        {/* Where to send the transfer. Shown on the confirmation because this
            is the moment the customer acts on it - the same details also go to
            the chat, so they survive after this page is closed. */}
        {order.paymentPending && order.bankDetails?.accountNumber && (
          <section className="receipt-bank">
            <h2>{text.bankTransferDetails}</h2>
            <dl>
              {[
                [text.bankName, order.bankDetails.bankName],
                [text.accountName, order.bankDetails.accountName],
                [text.accountNumber, order.bankDetails.accountNumber],
                [text.branch, order.bankDetails.branch],
              ].filter(([, value]) => value).map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <p>
              {order.paymentMethod === "deposit"
                ? text.transferPartThenBalance
                : text.transferFullAmount}
            </p>
          </section>
        )}

        <section className="receipt-totals"><div><span>{text.subtotal}</span><strong>{money(order.subtotalMinor)}</strong></div>{order.discountTotalMinor > 0 && <div><span>{text.discount}</span><strong>- {money(order.discountTotalMinor)}</strong></div>}<div><span>{text.delivery}</span><strong>{money(order.deliveryFeeMinor)}</strong></div><div><span>{text.tax}</span><strong>{money(order.taxTotalMinor)}</strong></div><div className="receipt-total"><strong>{text.total}</strong><strong>{money(order.totalAmountMinor)}</strong></div></section>
      </article>

      <div className="receipt-actions"><button type="button" onClick={() => downloadReceiptPdf(business, order)}><Download size={17} /> {text.downloadReceipt}</button><button type="button" onClick={onClose}><CircleHelp size={17} /> {closeLabel}</button></div>
    </section>
  </div>;
}
