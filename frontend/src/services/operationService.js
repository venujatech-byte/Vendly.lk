import { apiFileRequest, apiRequest } from "./apiClient";
import { mapOrderForTable } from "./orderService";


export async function generateOrderWaybill(businessId, orderId) {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/waybill`,
    { method: "POST" },
  );
  return mapOrderForTable(response.order);
}


export async function reportFraudOrder(businessId, orderId, reason, note = "") {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/fraud-report`,
    { method: "POST", body: { type: reason, note } },
  );
  return response.fraudReport;
}


export async function reportCourierIssue(
  businessId,
  orderId,
  issueType,
  note = "",
) {
  const response = await apiRequest(
    `/businesses/${businessId}/orders/${orderId}/courier-issues`,
    { method: "POST", body: { type: issueType, note } },
  );
  return response.courierIssue;
}


export async function downloadOrderExport(businessId) {
  const { blob, filename } = await apiFileRequest(
    `/businesses/${businessId}/orders-export.xlsx`,
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = decodeURIComponent(filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


export function printWaybill(order, printWindow = window.open("", "_blank")) {
  if (!printWindow) {
    throw new Error("Allow pop-ups to print the waybill.");
  }

  const itemRows = (order.items ?? [])
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.name)}</td>
          <td>${escapeHtml(item.size || "-")}</td>
          <td>${escapeHtml(item.quantity)}</td>
        </tr>`,
    )
    .join("");

  printWindow.document.write(`<!doctype html>
    <html><head><title>${escapeHtml(order.waybillNumber)}</title>
    <style>
      body{font:14px Arial,sans-serif;color:#0b2440;margin:32px}
      header{display:flex;justify-content:space-between;border-bottom:2px solid #0b3b6e;padding-bottom:16px}
      h1{margin:0;color:#0b3b6e} section{margin-top:22px}
      table{width:100%;border-collapse:collapse} th,td{padding:9px;border:1px solid #cbd5e1;text-align:left}
      .total{font-size:20px;font-weight:700}.muted{color:#64748b}
      @media print{button{display:none}}
    </style></head><body>
      <header><div><h1>Vendly.lk Waybill</h1><div class="muted">${escapeHtml(order.orderNumber)}</div></div>
      <strong>${escapeHtml(order.waybillNumber)}</strong></header>
      <section><h2>Delivery</h2><strong>${escapeHtml(order.customerName)}</strong><br>
      ${escapeHtml(order.phoneNumber)}${order.secondaryPhoneNumber ? `<br>${escapeHtml(order.secondaryPhoneNumber)}` : ""}<br>${escapeHtml(order.deliveryAddress)}</section>
      <section><h2>Courier</h2>${escapeHtml(order.courier)}</section>
      <section><table><thead><tr><th>Item</th><th>Size</th><th>Qty</th></tr></thead>
      <tbody>${itemRows}</tbody></table></section>
      <section class="total">Collect: ${escapeHtml(
        order.paidAmountMinor > 0 ? order.balanceDue : order.total,
      )}</section>
      ${
        order.paidAmountMinor > 0
          ? `<section class="muted">Order total ${escapeHtml(order.total)} less ${escapeHtml(order.paidAmount)} already paid.</section>`
          : ""
      }
      <script>window.onload=()=>window.print()</script>
    </body></html>`);
  printWindow.document.close();
}
