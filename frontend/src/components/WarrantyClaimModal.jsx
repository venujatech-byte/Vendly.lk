import { X } from "lucide-react";
import { useEffect, useState } from "react";
import "./ShopSales.css";

export default function WarrantyClaimModal({ source, businessId, onClose, onCreate }) {
  const [variantId, setVariantId] = useState("");
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { setVariantId(source?.items?.[0]?.variantId ?? ""); setReason(""); setDetails(""); }, [source]);
  if (!source) return null;
  async function submit(event) {
    event.preventDefault(); setSaving(true); setError("");
    try { await onCreate(businessId, { sourceType: source.sourceType, sourceId: source.id, variantId, reason, details }); onClose(); }
    catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }
  return <div className="shop-modal-backdrop"><form className="warranty-modal" onSubmit={submit}>
    <header><div><h2>New warranty claim</h2><p>Record the affected item and customer issue.</p></div><button type="button" onClick={onClose}><X size={20}/></button></header>
    <label>Original sale<input value={source.orderNumber || source.saleNumber} disabled /></label>
    <label>Item<select value={variantId} onChange={(e) => setVariantId(e.target.value)}>{source.items.map((item) => <option key={item.variantId} value={item.variantId}>{item.name}{item.size ? ` · ${item.size}` : ""}</option>)}</select></label>
    <label>Reason<input value={reason} onChange={(e) => setReason(e.target.value)} required placeholder="Example: Product stopped working" /></label>
    <label>Details<textarea value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Condition, receipt information and action requested..." /></label>
    {error && <p className="shop-modal__error">{error}</p>}
    <footer><button type="button" onClick={onClose}>Cancel</button><button className="primary" disabled={saving}>{saving ? "Saving..." : "Create claim"}</button></footer>
  </form></div>;
}
