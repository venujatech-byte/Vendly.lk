import { useState } from "react";
import {
  getChatAttachmentLink,
  getChatPaymentReport,
  verifyChatPaymentReport,
} from "../services/messageService";
import PrivateChatAttachment from "./PrivateChatAttachment";

export default function ChatPaymentReport({ businessId, sessionId, summary }) {
  const [report, setReport] = useState(null);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Load payment status only when the seller opens a receipt for review.
  async function openReport() {
    setBusy(true);
    setError("");
    try {
      const result = await getChatPaymentReport(businessId, sessionId, summary.id);
      setReport(result.report);
      setAmount((result.report.reportedAmountMinor / 100).toFixed(2));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function verify(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await verifyChatPaymentReport(businessId, sessionId, summary.id, amount);
      setReport(result.report);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  const verified = report?.verifiedAmountMinor;
  return (
    <div className="customer-messages__payment-report">
      <strong>Payment receipt · {summary.orderNumber}</strong>
      <p>Customer reported LKR {(summary.reportedAmountMinor / 100).toFixed(2)}</p>
      {report === null ? (
        <button type="button" disabled={busy} onClick={openReport}>
          {busy ? "Loading…" : "Review payment"}
        </button>
      ) : (
        <>
          <PrivateChatAttachment
            className="customer-messages__image"
            alt="Payment receipt"
            loadLink={(signal) => getChatAttachmentLink(businessId, sessionId, report.receipt, signal)}
          />
          {verified != null ? (
            <p role="status">Verified · LKR {(verified / 100).toFixed(2)}</p>
          ) : (
            <form onSubmit={verify}>
              <label>
                Amount received for this transfer (LKR)
                <input type="number" min="0.01" step="0.01" required value={amount}
                  onChange={(event) => setAmount(event.target.value)} />
              </label>
              <button type="submit" disabled={busy}>{busy ? "Verifying…" : "Verify payment"}</button>
            </form>
          )}
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
