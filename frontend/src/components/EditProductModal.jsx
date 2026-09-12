import { useEffect, useState } from "react";
import { WandSparkles } from "lucide-react";
import {
  generateProductDescription,
  updateProduct,
  uploadProductMedia,
} from "../services/productService";
import ModalShell from "./ModalShell";
import CustomSelect from "./CustomSelect";
import ProductDescriptionEditor from "./ProductDescriptionEditor";
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
  const [generating, setGenerating] = useState(false);
  const [generatedProductInfo, setGeneratedProductInfo] = useState(null);

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
    setGeneratedProductInfo(null);
  }, [isOpen, product]);

  function change(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function handleGenerateDescription() {
    if (!form.name?.trim()) {
      setError("Enter the product name before generating a description.");
      return;
    }
    setError("");
    setGenerating(true);
    try {
      const activeCat = categories.find((c) => c.id === form.categoryId);
      const productInfo = await generateProductDescription(businessId, {
        name: form.name,
        brand: form.brand,
        colourName: form.colourName,
        productSize: product?.productSize || "",
        categoryName: activeCat?.name || "",
        warrantyPeriodMonths: Number(product?.warrantyPeriodMonths || 0),
        weightKg: form.weightKg,
        costPrice: form.costPrice,
        sellingPrice: form.sellingPrice,
      });
      setGeneratedProductInfo(productInfo);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setGenerating(false);
    }
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
    <>
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
          <label>Category <small>(optional)</small>
            <CustomSelect name="categoryId" value={form.categoryId} onChange={change}>
              <option value="">Uncategorized - assign later</option>
              {categories.filter((category) => category.status === "active").map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </CustomSelect>
          </label>
          <label>Brand<input name="brand" value={form.brand} onChange={change} /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Supplier ID<input name="supplierId" value={form.supplierId} onChange={change} /></label>
          <label>Tax category
            <CustomSelect name="taxCategory" value={form.taxCategory} onChange={change}>
              <option value="standard">Standard</option>
              <option value="zero-rated">Zero rated</option>
              <option value="exempt">Exempt</option>
            </CustomSelect>
          </label>
        </div>
        <div className="inventory-form__desc-group">
          <div className="inventory-form__desc-header">
            <label htmlFor="edit-product-desc">Description for customers & chat</label>
            <button
              type="button"
              className="inventory-form__ai-btn"
              onClick={handleGenerateDescription}
              disabled={generating}
            >
              <WandSparkles size={14} />
              <span>{generating ? "Researching..." : "Generate with AI"}</span>
            </button>
          </div>
          <textarea
            id="edit-product-desc"
            name="description"
            value={form.description}
            onChange={change}
            rows={4}
            placeholder="Detailed description shown to customers..."
          />
        </div>
        <label>AI description (internal reference)<textarea name="aiDescription" value={form.aiDescription} onChange={change} rows={3} /></label>
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
    <ProductDescriptionEditor
      productInfo={generatedProductInfo}
      onChange={setGeneratedProductInfo}
      onCancel={() => setGeneratedProductInfo(null)}
      onApply={(description) => {
        setForm((current) => ({ ...current, description }));
        setGeneratedProductInfo(null);
      }}
    />
    </>
  );
}

export default EditProductModal;
