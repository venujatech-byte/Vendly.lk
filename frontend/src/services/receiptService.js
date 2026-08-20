import { jsPDF } from "jspdf";

function amount(value = 0) {
  return `LKR ${(Number(value) / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function safeText(value) {
  return String(value || "").replace(/[^\x20-\x7E]/g, "-");
}

export function downloadReceiptPdf(business, order) {
  const pdf = new jsPDF({ unit: "mm", format: "a4" });
  const left = 18;
  const right = 192;
  let y = 18;

  pdf.setFillColor(8, 115, 151);
  pdf.circle(105, y + 3, 7, "F");
  pdf.setDrawColor(255, 255, 255);
  pdf.setLineWidth(1.2);
  pdf.line(101.5, y + 3, 104, y + 5.5);
  pdf.line(104, y + 5.5, 108.5, y);
  y += 18;
  pdf.setTextColor(29, 41, 57);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(19);
  pdf.text("Order Confirmed", 105, y, { align: "center" });
  y += 7;
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(91, 103, 120);
  pdf.text(`Thank you for your purchase from ${safeText(business?.name || "Vendly.lk")}.`, 105, y, { align: "center" });
  y += 12;

  pdf.setFillColor(243, 246, 249);
  pdf.roundedRect(left, y, right - left, 18, 2, 2, "F");
  pdf.setTextColor(71, 84, 103);
  pdf.setFontSize(7);
  pdf.text("ORDER NUMBER", left + 6, y + 6);
  pdf.text("ORDER DATE", right - 6, y + 6, { align: "right" });
  pdf.setTextColor(29, 41, 57);
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(12);
  pdf.text(`#${safeText(order.orderNumber)}`, left + 6, y + 13);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(8);
  const date = order.createdAt ? new Date(order.createdAt) : new Date();
  pdf.text(date.toLocaleDateString("en-LK"), right - 6, y + 13, { align: "right" });
  y += 27;

  pdf.setFont("helvetica", "bold"); pdf.setFontSize(12); pdf.text("Order Status", left + 6, y);
  y += 9;
  pdf.setDrawColor(8, 115, 151); pdf.setLineWidth(1); pdf.line(left + 8, y, 105, y);
  pdf.setDrawColor(220, 226, 232); pdf.line(105, y, right - 8, y);
  pdf.setFontSize(8); pdf.setTextColor(29, 41, 57);
  pdf.text("Confirmed", left + 8, y + 7); pdf.text("Processing", 105, y + 7, { align: "center" }); pdf.text("Delivered", right - 8, y + 7, { align: "right" });
  y += 14;
  pdf.setFillColor(226, 235, 250); pdf.roundedRect(left + 6, y, right - left - 12, 18, 2, 2, "F");
  pdf.setFont("helvetica", "bold"); pdf.setFontSize(7); pdf.setTextColor(71, 84, 103); pdf.text("TRACKING INFO", left + 12, y + 6);
  pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.text("Your items are being prepared for shipping. Tracking will be available after dispatch.", left + 12, y + 12);
  y += 28;

  pdf.setFont("helvetica", "bold"); pdf.setFontSize(12); pdf.setTextColor(29, 41, 57); pdf.text("Items in your order", left + 6, y);
  y += 8;
  (order.items || []).forEach((item) => {
    if (y > 244) { pdf.addPage(); y = 18; }
    pdf.setFillColor(247, 249, 251); pdf.roundedRect(left + 6, y, 16, 16, 2, 2, "F");
    pdf.setFont("helvetica", "bold"); pdf.setFontSize(9); pdf.text(safeText(item.name || item.productName || "Product"), left + 27, y + 6);
    pdf.setFont("helvetica", "normal"); pdf.setFontSize(7); pdf.setTextColor(91, 103, 120); pdf.text(`${item.size ? `Variant: ${safeText(item.size)} | ` : ""}Qty: ${item.quantity}`, left + 27, y + 12);
    pdf.setFont("helvetica", "bold"); pdf.setFontSize(9); pdf.setTextColor(29, 41, 57); pdf.text(amount(item.lineTotalMinor ?? Number(item.sellingPrice || 0) * item.quantity * 100), right - 6, y + 9, { align: "right" });
    y += 20;
  });
  y += 3;

  const address = order.deliveryAddress || order.deliveryAddressObject || {};
  const addressText = [address.line1, address.line2, address.city, address.district, address.postalCode, address.country].filter(Boolean).join(", ");
  pdf.setDrawColor(220, 226, 232); pdf.line(left + 6, y, right - 6, y); y += 8;
  pdf.setFont("helvetica", "bold"); pdf.setFontSize(7); pdf.setTextColor(71, 84, 103); pdf.text("SHIPPING ADDRESS", left + 6, y); pdf.text("PAYMENT METHOD", 112, y);
  pdf.setFont("helvetica", "normal"); pdf.setFontSize(8); pdf.setTextColor(29, 41, 57);
  const addressLines = pdf.splitTextToSize(safeText(addressText), 75); pdf.text(addressLines, left + 6, y + 6);
  pdf.text(order.paymentMethod === "deposit" ? "Deposit / balance due" : order.paymentMethod === "paid" ? "Paid" : "Cash on delivery", 112, y + 6);
  y += Math.max(22, addressLines.length * 4 + 10);

  pdf.setFillColor(243, 246, 249); pdf.roundedRect(left, y, right - left, 42, 2, 2, "F");
  const rows = [["Subtotal", order.subtotalMinor], ["Discount", -Number(order.discountTotalMinor || 0)], ["Delivery", order.deliveryFeeMinor], ["Tax", order.taxTotalMinor]];
  pdf.setFontSize(8); rows.forEach(([label, value], index) => { pdf.setFont("helvetica", "normal"); pdf.setTextColor(71, 84, 103); pdf.text(label, left + 7, y + 7 + index * 6); pdf.setTextColor(29, 41, 57); pdf.text(amount(value), right - 7, y + 7 + index * 6, { align: "right" }); });
  pdf.setDrawColor(210, 218, 227); pdf.line(left + 7, y + 31, right - 7, y + 31);
  pdf.setFont("helvetica", "bold"); pdf.setFontSize(12); pdf.text("Total", left + 7, y + 39); pdf.setTextColor(8, 115, 151); pdf.text(amount(order.totalAmountMinor), right - 7, y + 39, { align: "right" });
  pdf.save(`${safeText(order.orderNumber || "vendly-order")}-receipt.pdf`);
}
