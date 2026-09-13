import { useEffect, useMemo, useState } from "react";
import { PackagePlus, TriangleAlert } from "lucide-react";

import { adjustProductStock } from "../services/productService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";
import "./AdjustStockModal.css";

function formatMoney(amount = 0) {
  return `LKR ${Number(amount || 0).toLocaleString("en-LK", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function AdjustStockModal({ businessId, product, initialVariantId, onClose, onUpdated }) {
  const [variantId, setVariantId] = useState("");
  const [operation, setOperation] = useState("add"); // "add" | "remove"
  const [quantity, setQuantity] = useState("1");
  const [unitCost, setUnitCost] = useState("");
  const [updateCostPrice, setUpdateCostPrice] = useState(true);
  const [recordInLedger, setRecordInLedger] = useState(true);
  const [removalType, setRemovalType] = useState("damaged"); // "damaged" | "supplier-return" | "correction"
  const [reason, setReason] = useState("New stock received");
  const [reference, setReference] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const selectedVariant = useMemo(
    () => product?.sizes?.find((variant) => variant.id === variantId) || product?.sizes?.[0],
    [product, variantId],
  );

  useEffect(() => {
    if (!product) return;

    const initialVarId = initialVariantId || product.sizes?.[0]?.id || "";
    setVariantId(initialVarId);
    setOperation("add");
    setQuantity("1");

    const currentVariant = product.sizes?.find((v) => v.id === initialVarId) || product.sizes?.[0];
    const initialPrice = currentVariant?.costPrice ?? product.costPrice ?? 0;
    setUnitCost(initialPrice ? String(initialPrice) : "");

    setUpdateCostPrice(true);
    setRecordInLedger(true);
    setRemovalType("damaged");
    setReason("New stock received");
    setReference("");
    setErrorMessage("");
  }, [initialVariantId, product]);

  // When variant changes, update unit price default if empty or matches previous variant
  function handleVariantChange(newVariantId) {
    setVariantId(newVariantId);
    const newVariant = product?.sizes?.find((v) => v.id === newVariantId);
    const price = newVariant?.costPrice ?? product?.costPrice ?? 0;
    setUnitCost(price ? String(price) : "");
  }

  function handleOperationChange(newOp) {
    setOperation(newOp);
    if (newOp === "add") {
      setReason("New stock received");
      setRecordInLedger(true);
    } else {
      setReason("Damaged, lost or corrected stock");
      setRemovalType("damaged");
      setRecordInLedger(false);
    }
  }

  function handleRemovalTypeChange(type) {
    setRemovalType(type);
    if (type === "supplier-return") {
      setReason("Returned stock to supplier");
      setRecordInLedger(true);
    } else if (type === "damaged") {
      setReason("Damaged, expired or lost stock write-off");
      setRecordInLedger(true);
    } else {
      setReason("Stocktake recount / inventory count correction");
      setRecordInLedger(false);
    }
  }

  const numericQuantity = Math.max(0, parseInt(quantity, 10) || 0);
  const numericUnitCost = Math.max(0, parseFloat(unitCost) || 0);
  const totalCost = numericQuantity * numericUnitCost;

  const currentStock = selectedVariant ? selectedVariant.stock : (product?.stock ?? 0);
  const projectedStock = operation === "add"
    ? currentStock + numericQuantity
    : currentStock - numericQuantity;

  async function handleSubmit(event) {
    event.preventDefault();

    if (!selectedVariant || numericQuantity < 1) {
      setErrorMessage("Choose a SKU and enter a positive whole quantity.");
      return;
    }

    if (operation === "remove" && projectedStock < 0) {
      setErrorMessage("Stock cannot be reduced below available quantity.");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    let ledgerImpact = "none";
    if (recordInLedger) {
      if (operation === "add") {
        ledgerImpact = "inventory-debit";
      } else if (removalType === "supplier-return") {
        ledgerImpact = "inventory-credit";
      } else if (removalType === "damaged") {
        ledgerImpact = "inventory-debit";
      }
    }

    try {
      const updatedProduct = await adjustProductStock(
        businessId,
        product.id,
        selectedVariant.id,
        {
          quantityChange: operation === "add" ? numericQuantity : -numericQuantity,
          unitCost: numericUnitCost,
          unitCostMinor: Math.round(numericUnitCost * 100),
          updateCostPrice: operation === "add" ? updateCostPrice : false,
          ledgerImpact,
          removalType: operation === "remove" ? removalType : null,
          reason: reason.trim(),
          reference: reference.trim(),
        },
      );
      onUpdated(updatedProduct);
      onClose();
    } catch (error) {
      setErrorMessage(error.message || "Failed to adjust stock.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell
      isOpen={Boolean(product)}
      title="Adjust Stock & Pricing"
      description="Record stock changes with unit purchase cost for accurate profit and ledger tracking."
      onClose={onClose}
    >
      {product && (
        <form className="inventory-form adjust-stock" onSubmit={handleSubmit}>
          <div className="adjust-stock__product">
            <span><PackagePlus size={22} aria-hidden="true" /></span>
            <div>
              <strong>{product.name}</strong>
              <small>{product.category || "Uncategorized"} · SKU: {selectedVariant?.sku || product.skuPrefix || "—"}</small>
            </div>
            <b>{product.stock} total units</b>
          </div>

          <section className="inventory-form__panel">
            <label>
              Product size / SKU
              <select value={variantId} onChange={(event) => handleVariantChange(event.target.value)} required>
                {(product.sizes ?? []).map((variant) => (
                  <option key={variant.id} value={variant.id}>
                    {variant.size ? `Size ${variant.size} · ` : ""}{variant.sku} · {variant.stock} in stock · Current Cost: {formatMoney(variant.costPrice || product.costPrice || 0)}
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="adjust-stock__operation">
              <legend>Adjustment type</legend>
              <button
                className={operation === "add" ? "adjust-stock__operation--active" : ""}
                type="button"
                onClick={() => handleOperationChange("add")}
              >
                + Add stock (Goods received)
              </button>
              <button
                className={operation === "remove" ? "adjust-stock__operation--remove" : ""}
                type="button"
                onClick={() => handleOperationChange("remove")}
              >
                − Remove stock (Write-off / Return)
              </button>
            </fieldset>

            {operation === "remove" && (
              <label>
                Removal reason / category
                <select value={removalType} onChange={(e) => handleRemovalTypeChange(e.target.value)}>
                  <option value="damaged">Damaged, expired or lost goods (Write-off expense)</option>
                  <option value="supplier-return">Returned to supplier for refund / credit</option>
                  <option value="correction">Inventory recount / stocktake correction</option>
                </select>
              </label>
            )}

            <div className="inventory-form__two-columns">
              <label>
                Quantity *
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                  required
                />
              </label>

              <label>
                {operation === "add" ? "Batch Unit Cost / Purchase Price (LKR)" : "Unit Cost / Value (LKR)"}
                <div className="adjust-stock__unit-price-wrapper">
                  <span className="adjust-stock__currency-tag">LKR</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={unitCost}
                    onChange={(event) => setUnitCost(event.target.value)}
                  />
                </div>
              </label>
            </div>

            {/* Total Cost & Stock Impact Summary Card */}
            <div className="adjust-stock__total-card">
              <div className="adjust-stock__total-stat">
                <span>Total {operation === "add" ? "Batch Cost" : "Value Impact"}</span>
                <strong className={operation === "add" ? "is-red" : removalType === "supplier-return" ? "is-green" : "is-red"}>
                  {formatMoney(totalCost)}
                </strong>
              </div>
              <div className="adjust-stock__total-stat">
                <span>Stock On Hand Change</span>
                <strong>{currentStock} ➔ {projectedStock} units</strong>
              </div>
            </div>

            {/* Checkbox Options */}
            <div className="adjust-stock__checkbox-group">
              {operation === "add" && (
                <label className="adjust-stock__checkbox-label">
                  <input
                    type="checkbox"
                    checked={updateCostPrice}
                    onChange={(e) => setUpdateCostPrice(e.target.checked)}
                  />
                  <div className="adjust-stock__checkbox-desc">
                    <span>Update catalog default unit cost price to {formatMoney(numericUnitCost)}</span>
                    <small>Future sales will calculate profit margin using this new purchase cost.</small>
                  </div>
                </label>
              )}

              <label className="adjust-stock__checkbox-label">
                <input
                  type="checkbox"
                  checked={recordInLedger}
                  onChange={(e) => setRecordInLedger(e.target.checked)}
                />
                <div className="adjust-stock__checkbox-desc">
                  <span>
                    {operation === "add"
                      ? `Record ${formatMoney(totalCost)} as Inventory Purchase in Transaction Ledger`
                      : removalType === "supplier-return"
                      ? `Record ${formatMoney(totalCost)} as Supplier Refund (Money In) in Ledger`
                      : removalType === "damaged"
                      ? `Record ${formatMoney(totalCost)} as Stock Loss Write-off in Ledger`
                      : "Record adjustment in Transaction Ledger"}
                  </span>
                  <small>
                    {recordInLedger
                      ? "Reflects this stock movement in business cashflow and financial reports."
                      : "Inventory count will update without recording a ledger transaction."}
                  </small>
                </div>
              </label>
            </div>

            <div className="inventory-form__two-columns">
              <label>
                Reference / Invoice # (Optional)
                <input
                  value={reference}
                  onChange={(event) => setReference(event.target.value)}
                  placeholder="e.g. GRN-1082 or Supplier Invoice #"
                  maxLength={100}
                />
              </label>

              <label>
                Audit note / Reason *
                <input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Reason for adjustment"
                  maxLength={250}
                  required
                />
              </label>
            </div>

            <div className={`adjust-stock__preview ${projectedStock < 0 ? "adjust-stock__preview--error" : ""}`}>
              {projectedStock < 0 && <TriangleAlert size={18} aria-hidden="true" />}
              <span>Available stock after adjustment</span>
              <strong>{projectedStock} units</strong>
            </div>
          </section>

          {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}

          <footer className="inventory-form__footer">
            <button type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
            <button className="inventory-form__primary" type="submit" disabled={isSaving || projectedStock < 0}>
              {isSaving ? "Updating stock..." : operation === "add" ? "Add Stock & Update Cost" : "Remove Stock"}
            </button>
          </footer>
        </form>
      )}
    </ModalShell>
  );
}

export default AdjustStockModal;
