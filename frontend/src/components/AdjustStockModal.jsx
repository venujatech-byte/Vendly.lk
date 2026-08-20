import { useEffect, useMemo, useState } from "react";
import { PackagePlus, TriangleAlert } from "lucide-react";

import { adjustProductStock } from "../services/productService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";
import "./AdjustStockModal.css";

function AdjustStockModal({ businessId, product, initialVariantId, onClose, onUpdated }) {
  const [variantId, setVariantId] = useState("");
  const [operation, setOperation] = useState("add");
  const [quantity, setQuantity] = useState("1");
  const [reason, setReason] = useState("New stock received");
  const [reference, setReference] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!product) return;

    setVariantId(initialVariantId || product.sizes?.[0]?.id || "");
    setOperation("add");
    setQuantity("1");
    setReason("New stock received");
    setReference("");
    setErrorMessage("");
  }, [initialVariantId, product]);

  const selectedVariant = useMemo(
    () => product?.sizes?.find((variant) => variant.id === variantId),
    [product, variantId],
  );

  async function handleSubmit(event) {
    event.preventDefault();

    const cleanQuantity = Number(quantity);

    if (!selectedVariant || !Number.isInteger(cleanQuantity) || cleanQuantity < 1) {
      setErrorMessage("Choose a SKU and enter a positive whole quantity.");
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      const updatedProduct = await adjustProductStock(
        businessId,
        product.id,
        selectedVariant.id,
        {
          quantityChange: operation === "add" ? cleanQuantity : -cleanQuantity,
          reason,
          reference,
        },
      );
      onUpdated(updatedProduct);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  const projectedStock = selectedVariant
    ? selectedVariant.stock + (operation === "add" ? Number(quantity) || 0 : -(Number(quantity) || 0))
    : 0;

  return (
    <ModalShell
      isOpen={Boolean(product)}
      title="Adjust Stock"
      description="Record a stock change and keep a complete inventory audit trail."
      onClose={onClose}
    >
      {product && (
        <form className="inventory-form adjust-stock" onSubmit={handleSubmit}>
          <div className="adjust-stock__product">
            <span><PackagePlus size={22} aria-hidden="true" /></span>
            <div><strong>{product.name}</strong><small>{product.category}</small></div>
            <b>{product.stock} total units</b>
          </div>

          <section className="inventory-form__panel">
            <label>
              Product size / SKU
              <select value={variantId} onChange={(event) => setVariantId(event.target.value)} required>
                {(product.sizes ?? []).map((variant) => (
                  <option key={variant.id} value={variant.id}>
                    {variant.size ? `Size ${variant.size} · ` : ""}{variant.sku} · {variant.stock} available
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="adjust-stock__operation">
              <legend>Adjustment type</legend>
              <button className={operation === "add" ? "adjust-stock__operation--active" : ""} type="button" onClick={() => { setOperation("add"); setReason("New stock received"); }}>Add stock</button>
              <button className={operation === "remove" ? "adjust-stock__operation--remove" : ""} type="button" onClick={() => { setOperation("remove"); setReason("Damaged, lost or corrected stock"); }}>Remove stock</button>
            </fieldset>

            <div className="inventory-form__two-columns">
              <label>
                Quantity
                <input type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
              </label>
              <label>
                Reference (optional)
                <input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Supplier invoice or note" />
              </label>
            </div>

            <label>
              Reason
              <textarea rows={3} maxLength={300} value={reason} onChange={(event) => setReason(event.target.value)} required />
            </label>

            <div className={`adjust-stock__preview ${projectedStock < 0 ? "adjust-stock__preview--error" : ""}`}>
              {projectedStock < 0 && <TriangleAlert size={18} aria-hidden="true" />}
              <span>Available stock after adjustment</span>
              <strong>{projectedStock}</strong>
            </div>
          </section>

          {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}

          <footer className="inventory-form__footer">
            <button type="button" onClick={onClose}>Cancel</button>
            <button className="inventory-form__primary" type="submit" disabled={isSaving || projectedStock < 0}>
              {isSaving ? "Updating stock..." : "Update Stock"}
            </button>
          </footer>
        </form>
      )}
    </ModalShell>
  );
}

export default AdjustStockModal;
