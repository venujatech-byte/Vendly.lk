import { Calculator, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import "./ShopSales.css";

function parseItemUnitPriceMinor(item) {
  if (!item) return 0;
  if (typeof item.unitPriceMinor === "number" && !Number.isNaN(item.unitPriceMinor)) {
    return item.unitPriceMinor;
  }
  if (typeof item.lineTotalMinor === "number" && !Number.isNaN(item.lineTotalMinor)) {
    const q = Number(item.quantity) || 1;
    return Math.round(item.lineTotalMinor / q);
  }
  const raw = String(item.unitPrice || item.price || "0").replace(/[^0-9.-]/g, "");
  const num = Number(raw);
  return Number.isNaN(num) ? 0 : Math.round(num * 100);
}

export default function WarrantyClaimModal({
  source,
  businessId,
  availableSources = [],
  onSourceChange,
  onClose,
  onCreate,
}) {
  const [currentSourceId, setCurrentSourceId] = useState(source?.id || "");
  const [itemIndex, setItemIndex] = useState("0");
  const [claimQuantity, setClaimQuantity] = useState(1);
  const [claimType, setClaimType] = useState("supplier-warranty");
  const [repairCost, setRepairCost] = useState("");
  const [otherExpenses, setOtherExpenses] = useState("");
  const [otherExpensesNotes, setOtherExpensesNotes] = useState("");
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Active source resolution when modal is open
  const activeSource = (availableSources.length > 0 && availableSources.find((s) => s.id === currentSourceId)) || source;

  useEffect(() => {
    if (source?.id) {
      setCurrentSourceId(source.id);
    }
  }, [source?.id]);

  useEffect(() => {
    if (!activeSource) return;
    const firstActiveItem = activeSource?.items?.findIndex(
      (item) => item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date(),
    );
    setItemIndex(String(firstActiveItem >= 0 ? firstActiveItem : 0));
    setClaimQuantity(1);
    setClaimType("supplier-warranty");
    setRepairCost("");
    setOtherExpenses("");
    setOtherExpensesNotes("");
    setReason("");
    setDetails("");
    setError("");
  }, [activeSource]);

  useEffect(() => {
    if (!source) return;
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose?.();
    }
    window.addEventListener("keydown", handleKeyDown);
    document.body.classList.add("modal-is-open");
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("modal-is-open");
    };
  }, [source, onClose]);

  if (!source || !activeSource) return null;

  // Map all purchased line items so any sold item can have a warranty claim processed.
  const claimableItems = (activeSource.items ?? []).map((item, index) => {
    const hasActive = Boolean(item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date());
    return { item, index, hasActive };
  });
  const selectedItem = activeSource.items?.[Number(itemIndex)] ?? activeSource.items?.[0] ?? {};
  const maximumQuantity = Math.max(Number(selectedItem?.quantity) || 1, 1);

  // Calculate live financial impact & ledger debit
  const unitPriceMinor = parseItemUnitPriceMinor(selectedItem);
  const repairCostMinor = claimType === "shop-repair" ? Math.round(Math.max(Number(repairCost) || 0, 0) * 100) : 0;
  const otherExpensesMinor = Math.round(Math.max(Number(otherExpenses) || 0, 0) * 100);

  let baseImpactMinor = 0;
  if (claimType === "shop-warranty") {
    baseImpactMinor = unitPriceMinor * (Number(claimQuantity) || 1);
  } else if (claimType === "shop-repair") {
    baseImpactMinor = repairCostMinor;
  }
  const totalLedgerExpenseMinor = baseImpactMinor + otherExpensesMinor;

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await onCreate(businessId, {
        sourceType: activeSource.sourceType,
        sourceId: activeSource.id,
        itemIndex: Number(itemIndex),
        claimQuantity: Number(claimQuantity),
        claimType,
        repairCost: claimType === "shop-repair" ? repairCost : 0,
        otherExpenses: otherExpenses || 0,
        otherExpensesNotes: otherExpensesNotes || "",
        reason,
        details,
      });
      onClose?.();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return createPortal(
    <div
      className="shop-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form className="warranty-modal" onSubmit={submit}>
        <header className="warranty-modal__header">
          <div>
            <h2>New warranty claim</h2>
            <p>Record the affected item, handling method, and associated expenses.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </header>

        <div className="warranty-modal__body">
          <label>
            Original sale
            {availableSources.length > 0 ? (
              <select
                value={activeSource.id}
                onChange={(e) => {
                  const target = availableSources.find((s) => s.id === e.target.value);
                  if (target) {
                    setCurrentSourceId(target.id);
                    onSourceChange?.(target);
                  }
                }}
              >
                {availableSources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.sourceType === "shop-sale" ? "Shop Sale" : "Online Order"} #{s.orderNumber || s.saleNumber || s.id} · {s.customerName || "Customer"} ({s.items?.length || 0} items)
                  </option>
                ))}
              </select>
            ) : (
              <input value={activeSource.orderNumber || activeSource.saleNumber || ""} disabled />
            )}
          </label>

          <label>
            Item
            <select
              value={itemIndex}
              onChange={(event) => {
                setItemIndex(event.target.value);
                setClaimQuantity(1);
              }}
            >
              {claimableItems.map(({ item, index, hasActive }) => (
                <option key={`${item.variantId || item.productId || index}-${index}`} value={index}>
                  {item.name}
                  {item.size ? ` · ${item.size}` : ""} · {item.quantity} purchased {hasActive ? " (Active warranty)" : ""}
                </option>
              ))}
            </select>
          </label>

          <label>
            Quantity to claim
            <input
              type="number"
              min="1"
              max={maximumQuantity}
              value={claimQuantity}
              onChange={(event) =>
                setClaimQuantity(
                  Math.min(maximumQuantity, Math.max(1, Number(event.target.value) || 1)),
                )
              }
            />
          </label>

          <fieldset className="warranty-modal__responsibility">
            <legend>How will this claim be handled?</legend>
            <label>
              <input
                type="radio"
                name="claimType"
                value="supplier-warranty"
                checked={claimType === "supplier-warranty"}
                onChange={(event) => setClaimType(event.target.value)}
              />
              Supplier warranty <small>No seller revenue reduction for item cost.</small>
            </label>
            <label>
              <input
                type="radio"
                name="claimType"
                value="shop-warranty"
                checked={claimType === "shop-warranty"}
                onChange={(event) => setClaimType(event.target.value)}
              />
              Shop warranty <small>The claimed item value is deducted from revenue.</small>
            </label>
            <label>
              <input
                type="radio"
                name="claimType"
                value="shop-repair"
                checked={claimType === "shop-repair"}
                onChange={(event) => setClaimType(event.target.value)}
              />
              Shop repair <small>Only the repair cost is deducted from revenue.</small>
            </label>
          </fieldset>

          {claimType === "shop-repair" && (
            <label>
              Repair cost (LKR)
              <input
                type="number"
                min="0"
                step="0.01"
                value={repairCost}
                onChange={(event) => setRepairCost(event.target.value)}
                required
                placeholder="0.00"
              />
            </label>
          )}

          {/* Other Expenses Section */}
          <div className="warranty-modal__expenses-section">
            <div className="warranty-modal__expenses-header">
              <span className="warranty-modal__expenses-title">
                Other Expenses (Courier, transit, parts, etc.)
              </span>
            </div>
            <div className="warranty-modal__expenses-grid">
              <label>
                Other expenses amount (LKR)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={otherExpenses}
                  onChange={(event) => setOtherExpenses(event.target.value)}
                  placeholder="0.00"
                />
              </label>
              <label>
                Expense note / description
                <input
                  value={otherExpensesNotes}
                  onChange={(event) => setOtherExpensesNotes(event.target.value)}
                  placeholder="e.g. Return courier fee to supplier"
                />
              </label>
            </div>
          </div>

          {/* Live Ledger Total Preview */}
          <div className="warranty-modal__ledger-preview">
            <div className="warranty-modal__ledger-info">
              <div className="warranty-modal__ledger-icon">
                <Calculator size={18} />
              </div>
              <div className="warranty-modal__ledger-text">
                <strong>Total Ledger Expense: LKR {(totalLedgerExpenseMinor / 100).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
                <small>
                  {totalLedgerExpenseMinor > 0
                    ? `This total will be automatically marked as an expense debit in your Ledger.`
                    : "No expense will be debited to the ledger for this claim."}
                </small>
              </div>
            </div>
          </div>

          <label>
            Reason
            <input
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
              placeholder="Example: Product stopped working, defective battery"
            />
          </label>

          <label>
            Details
            <textarea
              value={details}
              onChange={(event) => setDetails(event.target.value)}
              placeholder="Condition, serial number, receipt information, or requested resolution..."
            />
          </label>

          {error && <p className="shop-modal__error" role="alert">{error}</p>}
        </div>

        <footer className="warranty-modal__footer">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" disabled={saving || !claimableItems.length}>
            {saving ? "Saving..." : "Create claim"}
          </button>
        </footer>
      </form>
    </div>,
    document.body,
  );
}

