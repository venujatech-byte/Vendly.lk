import { useEffect, useState } from "react";
import { updateProduct, uploadProductMedia } from "../services/productService";
import ModalShell from "./ModalShell";
import "./InventoryForm.css";

const emptyForm = {
  name: "",
  colourName: "",
  colourHex: "#f36f8d",
  productType: "",
  categoryId: "",
  brand: "",
  supplierId: "",
  description: "",
  aiDescription: "",
  costPrice: "",
  sellingPrice: "",
  compareAtPrice: "0",
  weightKg: "",
  lowStockThreshold: "5",
  taxCategory: "standard",
};

function EditProductModal({ isOpen, businessId, product, categories = [], onClose, onUpdated }) {
  const [form, setForm] = useState(emptyForm);
  const [mediaFiles, setMediaFiles] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen || !product) return;
    setForm({
      ...emptyForm,
      name: product.name ?? "",
      colourName: product.colourName ?? product.colour ?? "",
      colourHex: product.colourHex ?? "#f36f8d",
      productType: product.productType ?? "",
      categoryId: product.categoryId ?? "",
      brand: product.brand ?? "",
      supplierId: product.supplierId ?? "",
      description: product.description ?? "",
      aiDescription: product.aiDescription ?? "",
      costPrice: product.costPrice ?? "",
      sellingPrice: product.sellingPrice ?? "",
      compareAtPrice: product.compareAtPrice ?? "0",
      weightKg: product.weightKg ?? "",
      lowStockThreshold: product.lowStockThreshold ?? "5",
      taxCategory: product.taxCategory ?? "standard",
    });
    setMediaFiles([]);
    setError("");
  }, [isOpen, product]);

  function change(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!product) return;
    setSaving(true);
    setError("");
    try {
      let updated = await updateProduct(businessId, product.id, form);
      if (mediaFiles.length) updated = await uploadProductMedia(businessId, product.id, mediaFiles);
      onUpdated?.(updated);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <ModalShell isOpen={isOpen} title="Edit Product" description="Update every catalogue field. Stock quantities remain in Adjust stock so each change is audited." onClose={onClose} size="wide">
      <form className="inventory-form" onSubmit={submit}>
        <div className="inventory-form__two-columns">
          <label>Product name<input name="name" value={form.name} onChange={change} required /></label>
          <label>Product type<input name="productType" value={form.productType} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Colour name<input name="colourName" value={form.colourName} onChange={change} /></label>
          <label>Colour<input className="inventory-form__colour" name="colourHex" type="color" value={form.colourHex} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Category <small>(optional)</small><select name="categoryId" value={form.categoryId} onChange={change}><option value="">Uncategorized - assign later</option>{categories.filter((category) => category.status === "active").map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
          <label>Brand<input name="brand" value={form.brand} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Supplier ID<input name="supplierId" value={form.supplierId} onChange={change} /></label>
          <label>Tax category<select name="taxCategory" value={form.taxCategory} onChange={change}><option value="standard">Standard</option><option value="zero-rated">Zero rated</option><option value="exempt">Exempt</option></select></label>
        </div>
        <label>Description for chatbot<textarea name="description" value={form.description} onChange={change} rows={4} /></label>
        <label>AI description<textarea name="aiDescription" value={form.aiDescription} onChange={change} rows={3} /></label>
        <div className="inventory-form__three-columns">
          <label>Cost price (LKR)<input name="costPrice" type="number" min="0" step="0.01" value={form.costPrice} onChange={change} required /></label>
          <label>Selling price (LKR)<input name="sellingPrice" type="number" min="0.01" step="0.01" value={form.sellingPrice} onChange={change} required /></label>
          <label>Compare-at price<input name="compareAtPrice" type="number" min="0" step="0.01" value={form.compareAtPrice} onChange={change} /></label>
        </div>
        <div className="inventory-form__three-columns">
          <label>Weight (kg)<input name="weightKg" type="number" min="0.001" step="0.001" value={form.weightKg} onChange={change} required /></label>
          <label>Low-stock alert<input name="lowStockThreshold" type="number" min="0" step="1" value={form.lowStockThreshold} onChange={change} required /></label>
          <label>Replace/add media<input type="file" accept="image/*,video/*" multiple onChange={(event) => setMediaFiles(Array.from(event.target.files).slice(0, 12))} /></label>
        </div>
        {error && <p className="inventory-form__error" role="alert">{error}</p>}
        <footer className="inventory-form__footer"><button type="button" onClick={onClose}>Cancel</button><button className="inventory-form__primary" type="submit" disabled={saving}>{saving ? "Saving..." : "Save product"}</button></footer>
      </form>
    </ModalShell>
  );
}

export default EditProductModal;
