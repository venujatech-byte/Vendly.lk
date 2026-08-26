import { X } from "lucide-react";
import { useEffect, useState } from "react";
import "./ShopSales.css";

// A claim belongs to one purchased line item. This keeps warranty costs accurate
// when an order contains several different products.
export default function WarrantyClaimModal({ source, businessId, onClose, onCreate }) {
  const [itemIndex, setItemIndex] = useState("0");
  const [claimQuantity, setClaimQuantity] = useState(1);
  const [claimType, setClaimType] = useState("supplier-warranty");
  const [repairCost, setRepairCost] = useState("");
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const firstActiveItem = source?.items?.findIndex(
      (item) => item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date(),
    );
    setItemIndex(String(firstActiveItem >= 0 ? firstActiveItem : 0)); setClaimQuantity(1); setClaimType("supplier-warranty");
    setRepairCost(""); setReason(""); setDetails(""); setError("");
  }, [source]);

  if (!source) return null;
  // Keep the original index because the backend uses it to find the exact
  // line item in the saved order. Expired/no-warranty items are not claimable.
  const claimableItems = (source.items ?? [])
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date());
  const selectedItem = source.items?.[Number(itemIndex)] ?? source.items?.[0];
  const maximumQuantity = selectedItem?.quantity ?? 1;

  async function submit(event) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      await onCreate(businessId, {
        sourceType: source.sourceType,
        sourceId: source.id,
        itemIndex: Number(itemIndex),
        claimQuantity: Number(claimQuantity),
        claimType,
        repairCost: claimType === "shop-repair" ? repairCost : 0,
        reason,
        details,
      });
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally { setSaving(false); }
  }

  return <div className="shop-modal-backdrop"><form className="warranty-modal" onSubmit={submit}>
    <header><div><h2>New warranty claim</h2><p>Record the affected item and how your shop will handle it.</p></div><button type="button" onClick={onClose}><X size={20}/></button></header>
    <label>Original sale<input value={source.orderNumber || source.saleNumber} disabled /></label>
    {!claimableItems.length && <p className="shop-modal__error">No item in this sale has an active warranty.</p>}
    <label>Item
      <select value={itemIndex} disabled={!claimableItems.length} onChange={(event) => { setItemIndex(event.target.value); setClaimQuantity(1); }}>
        {claimableItems.map(({ item, index }) => <option key={`${item.variantId}-${index}`} value={index}>{item.name}{item.size ? ` · ${item.size}` : ""} · {item.quantity} purchased</option>)}
      </select>
    </label>
    <label>Quantity to claim<input type="number" min="1" max={maximumQuantity} value={claimQuantity} onChange={(event) => setClaimQuantity(Math.min(maximumQuantity, Math.max(1, Number(event.target.value) || 1)))} /></label>
    <fieldset className="warranty-modal__responsibility">
      <legend>How will this claim be handled?</legend>
      <label><input type="radio" name="claimType" value="supplier-warranty" checked={claimType === "supplier-warranty"} onChange={(event) => setClaimType(event.target.value)} /> Supplier warranty <small>No seller revenue reduction.</small></label>
      <label><input type="radio" name="claimType" value="shop-warranty" checked={claimType === "shop-warranty"} onChange={(event) => setClaimType(event.target.value)} /> Shop warranty <small>The claimed item value is deducted from revenue.</small></label>
      <label><input type="radio" name="claimType" value="shop-repair" checked={claimType === "shop-repair"} onChange={(event) => setClaimType(event.target.value)} /> Shop repair <small>Only the repair cost is deducted from revenue.</small></label>
    </fieldset>
    {claimType === "shop-repair" && <label>Repair cost (LKR)<input type="number" min="0" step="0.01" value={repairCost} onChange={(event) => setRepairCost(event.target.value)} required placeholder="0.00" /></label>}
    <label>Reason<input value={reason} onChange={(event) => setReason(event.target.value)} required placeholder="Example: Product stopped working" /></label>
    <label>Details<textarea value={details} onChange={(event) => setDetails(event.target.value)} placeholder="Condition, receipt information and action requested..." /></label>
    {error && <p className="shop-modal__error">{error}</p>}
    <footer><button type="button" onClick={onClose}>Cancel</button><button className="primary" disabled={saving || !claimableItems.length}>{saving ? "Saving..." : "Create claim"}</button></footer>
  </form></div>;
}
