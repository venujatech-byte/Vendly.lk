import { useEffect, useState } from "react";
import {
  BanknoteArrowDown,
  BanknoteArrowUp,
  CircleAlert,
  Loader2,
  ReceiptText,
} from "lucide-react";

import { createLedgerEntry } from "../services/analyticsService";
import ModalShell from "./ModalShell";
import "./AddLedgerEntryModal.css";

const EXPENSE_CATEGORIES = [
  "Rent & Facilities",
  "Salaries & Wages",
  "Advertising & Marketing",
  "Courier & Shipping Fees",
  "Packaging & Supplies",
  "Utilities & Internet",
  "Software & Subscriptions",
  "Repairs & Maintenance",
  "Taxes & Levies",
  "Inventory / Goods Purchase",
  "Other Expense",
];

const INCOME_CATEGORIES = [
  "Direct Bank Transfer",
  "Cash Deposit",
  "Capital / Investment",
  "Vendor Refund",
  "Commission / Service",
  "Interest / Royalty",
  "Other Income",
];

function getTodayString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function AddLedgerEntryModal({
  isOpen,
  businessId,
  onClose,
  onSuccess,
}) {
  const [type, setType] = useState("expense"); // "expense" | "income"
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(EXPENSE_CATEGORIES[0]);
  const [customCategory, setCustomCategory] = useState("");
  const [description, setDescription] = useState("");
  const [payee, setPayee] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [date, setDate] = useState(getTodayString());
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");

  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setType("expense");
      setAmount("");
      setCategory(EXPENSE_CATEGORIES[0]);
      setCustomCategory("");
      setDescription("");
      setPayee("");
      setPaymentMethod("cash");
      setDate(getTodayString());
      setReference("");
      setNotes("");
      setErrorMessage("");
    }
  }, [isOpen]);

  function handleTypeChange(newType) {
    setType(newType);
    if (newType === "expense") {
      setCategory(EXPENSE_CATEGORIES[0]);
    } else {
      setCategory(INCOME_CATEGORIES[0]);
    }
    setCustomCategory("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");

    const parsedAmount = parseFloat(amount);
    if (Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setErrorMessage("Please enter a valid amount greater than 0.");
      return;
    }

    if (!description.trim()) {
      setErrorMessage("Please enter a description for this transaction.");
      return;
    }

    const finalCategory =
      (category === "Other Expense" || category === "Other Income") && customCategory.trim()
        ? customCategory.trim()
        : category;

    setIsSubmitting(true);

    try {
      const payload = {
        type,
        amount: parsedAmount,
        amountMinor: Math.round(parsedAmount * 100),
        category: finalCategory,
        description: description.trim(),
        payee: payee.trim(),
        paymentMethod,
        date: date || getTodayString(),
        reference: reference.trim(),
        notes: notes.trim(),
      };

      const newEntry = await createLedgerEntry(businessId, payload);
      if (onSuccess) {
        onSuccess(newEntry);
      }
      onClose();
    } catch (error) {
      setErrorMessage(error.message || "Failed to record transaction.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const categoryList = type === "expense" ? EXPENSE_CATEGORIES : INCOME_CATEGORIES;

  return (
    <ModalShell
      isOpen={isOpen}
      title="Record Transaction"
      description="Add a manual income or expense entry to your transaction ledger."
      icon={ReceiptText}
      iconTone={type === "expense" ? "danger" : "success"}
      onClose={onClose}
      size="medium"
    >
      <form className="add-ledger-entry-modal" onSubmit={handleSubmit}>
        <div className="add-ledger-entry__type-selector" role="radiogroup" aria-label="Transaction Type">
          <button
            type="button"
            className={`add-ledger-entry__type-btn ${type === "expense" ? "is-active-expense" : ""}`}
            onClick={() => handleTypeChange("expense")}
            aria-checked={type === "expense"}
            role="radio"
          >
            <BanknoteArrowDown size={16} />
            <span>Expense (Money out)</span>
          </button>
          <button
            type="button"
            className={`add-ledger-entry__type-btn ${type === "income" ? "is-active-income" : ""}`}
            onClick={() => handleTypeChange("income")}
            aria-checked={type === "income"}
            role="radio"
          >
            <BanknoteArrowUp size={16} />
            <span>Income (Money in)</span>
          </button>
        </div>

        <div className="add-ledger-entry__grid">
          <div className="add-ledger-entry__field">
            <label htmlFor="ledger-amount">Amount (LKR) *</label>
            <div className="add-ledger-entry__amount-wrapper">
              <span className="add-ledger-entry__currency-tag">LKR</span>
              <input
                id="ledger-amount"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="0.00"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                autoFocus
                required
              />
            </div>
          </div>

          <div className="add-ledger-entry__field">
            <label htmlFor="ledger-date">Date *</label>
            <input
              id="ledger-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          <div className="add-ledger-entry__field">
            <label htmlFor="ledger-category">Category</label>
            <select
              id="ledger-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {categoryList.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {(category === "Other Expense" || category === "Other Income") && (
            <div className="add-ledger-entry__field">
              <label htmlFor="ledger-custom-category">Custom Category Name</label>
              <input
                id="ledger-custom-category"
                type="text"
                placeholder="e.g. Licensing fees"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                maxLength={60}
              />
            </div>
          )}

          <div className="add-ledger-entry__field">
            <label htmlFor="ledger-payment-method">Payment Method</label>
            <select
              id="ledger-payment-method"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
            >
              <option value="cash">Cash</option>
              <option value="bank-transfer">Bank Transfer</option>
              <option value="card">Card / POS</option>
              <option value="cheque">Cheque</option>
              <option value="online">Online Payment Gateway</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div className="add-ledger-entry__field add-ledger-entry__field--full">
            <label htmlFor="ledger-description">Description *</label>
            <input
              id="ledger-description"
              type="text"
              placeholder={
                type === "expense"
                  ? "e.g. September Shop Rent or Facebook Ad campaign"
                  : "e.g. Direct customer bank settlement or capital deposit"
              }
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={150}
              required
            />
          </div>

          <div className="add-ledger-entry__field">
            <label htmlFor="ledger-payee">
              {type === "expense" ? "Payee / Paid To" : "Payer / Received From"}
            </label>
            <input
              id="ledger-payee"
              type="text"
              placeholder={type === "expense" ? "e.g. Landlord or Meta Platforms" : "e.g. Bank of Ceylon or Investor"}
              value={payee}
              onChange={(e) => setPayee(e.target.value)}
              maxLength={100}
            />
          </div>

          <div className="add-ledger-entry__field">
            <label htmlFor="ledger-reference">Reference / Invoice # (Optional)</label>
            <input
              id="ledger-reference"
              type="text"
              placeholder={type === "expense" ? "e.g. EXP-1049 or INV-0092" : "e.g. TXN-9481 or REC-002"}
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              maxLength={50}
            />
          </div>

          <div className="add-ledger-entry__field add-ledger-entry__field--full">
            <label htmlFor="ledger-notes">Additional Notes (Optional)</label>
            <textarea
              id="ledger-notes"
              rows={2}
              placeholder="Add any internal details, cheque number, or notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={300}
            />
          </div>
        </div>

        {errorMessage && (
          <div className="add-ledger-entry__error" role="alert">
            <CircleAlert size={16} />
            <span>{errorMessage}</span>
          </div>
        )}

        <footer className="add-ledger-entry__footer">
          <button
            type="button"
            className="add-ledger-entry__cancel-btn"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className={`add-ledger-entry__submit-btn ${
              type === "expense"
                ? "add-ledger-entry__submit-btn--expense"
                : "add-ledger-entry__submit-btn--income"
            }`}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="spinner" />
                <span>Recording...</span>
              </>
            ) : type === "expense" ? (
              "Record Expense"
            ) : (
              "Record Income"
            )}
          </button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default AddLedgerEntryModal;
