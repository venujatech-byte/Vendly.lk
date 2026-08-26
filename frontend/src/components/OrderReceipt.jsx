import { Check, CircleHelp, Download, Home, Info, Package, Truck } from "lucide-react";
import { downloadReceiptPdf } from "../services/receiptService";
import { storefrontText } from "../data/storefrontText";
import "./OrderReceipt.css";

function money(minorUnits = 0) {
  return `LKR ${(Number(minorUnits) / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dateLabel(value) {
  const date = value ? new Date(value) : new Date();
  return Number.isNaN(date.getTime()) ? new Date().toLocaleDateString("en-LK") : date.toLocaleDateString("en-LK", { year: "numeric", month: "long", day: "numeric" });
}

export default function OrderReceipt({ business, order, onClose, closeLabel = "Return", chatLanguage = "en" }) {
  const text = storefrontText(chatLanguage);
  const address = order.deliveryAddress || order.deliveryAddressObject || {};
  const customer = order.customerSnapshot || {};
  const payment = order.paymentMethod === "deposit" ? "Deposit / balance due" : order.paymentMethod === "paid" ? "Paid" : "Cash on delivery";

  return <div className="receipt-layer">
    <section className="receipt-page">
      <div className="receipt-success-mark"><Check size={25} strokeWidth={3} /></div>
      <h1>{text.orderConfirmed}</h1>
      <p>{text.orderConfirmedHint}</p>

      <article className="receipt-card">
        <header><div><small>{text.orderNumber}</small><strong>#{order.orderNumber}</strong></div><div><small>{text.orderDate}</small><span>{dateLabel(order.createdAt)}</span></div></header>
        <section className="receipt-status">
          <h2>{text.orderStatus}</h2>
          <div className="receipt-status__track"><span><Package size={15} />{text.statusConfirmed}</span><span><Truck size={15} />{text.statusProcessing}</span><span className="is-muted"><Home size={15} />{text.statusDelivered}</span></div>
          <div className="receipt-info"><Info size={18} /><span><strong>{text.trackingInfo}</strong>{text.trackingHint}</span></div>
        </section>

        <section className="receipt-items"><h2>{text.itemsInOrder}</h2>{(order.items || []).map((item) => <div key={item.variantId || item.id}><span className="receipt-item__image">{item.mediaUrl || item.imageUrl ? <img src={item.mediaUrl || item.imageUrl} alt="" /> : <Package size={25} />}</span><span><strong>{item.name || item.productName}</strong><small>{item.size ? `${text.variant}: ${item.size} | ` : ""}{text.qty}: {item.quantity}</small></span><strong>{money(item.lineTotalMinor ?? Number(item.sellingPrice || 0) * item.quantity * 100)}</strong></div>)}</section>

        <section className="receipt-details"><div><small>SHIPPING ADDRESS</small><strong>{customer.name || order.customerName || "Customer"}</strong><span>{[address.line1, address.line2, address.city, address.district, address.postalCode, address.country].filter(Boolean).join(", ")}</span></div><div><small>PAYMENT METHOD</small><strong>{payment}</strong><span>{order.paymentStatus === "partially-paid" ? `${money(order.balanceAmountMinor)} balance remaining` : "Payment details saved with this order."}</span></div></section>

        <section className="receipt-totals"><div><span>{text.subtotal}</span><strong>{money(order.subtotalMinor)}</strong></div>{order.discountTotalMinor > 0 && <div><span>{text.discount}</span><strong>- {money(order.discountTotalMinor)}</strong></div>}<div><span>{text.delivery}</span><strong>{money(order.deliveryFeeMinor)}</strong></div><div><span>{text.tax}</span><strong>{money(order.taxTotalMinor)}</strong></div><div className="receipt-total"><strong>{text.total}</strong><strong>{money(order.totalAmountMinor)}</strong></div></section>
      </article>

      <div className="receipt-actions"><button type="button" onClick={() => downloadReceiptPdf(business, order)}><Download size={17} /> {text.downloadReceipt}</button><button type="button" onClick={onClose}><CircleHelp size={17} /> {closeLabel}</button></div>
    </section>
  </div>;
}
