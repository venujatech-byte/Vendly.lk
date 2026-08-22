import { useEffect, useMemo, useState } from "react";
import { Image as ImageIcon, Plus, Trash2, Upload, WandSparkles } from "lucide-react";

import {
  createProduct,
  generateProductDescription,
  updateProduct,
  uploadProductMedia,
  uploadVariantImage,
} from "../services/productService";
import ModalShell from "./ModalShell";
import "./InventoryForm.css";

function randomCode(length = 5) {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({ length }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join("");
}

function skuPart(value, fallback = "ITEM") {
  const cleaned = String(value || "").toUpperCase().replace(/[^A-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  return cleaned.slice(0, 12) || fallback;
}

function generateSku(name, option = "") {
  return [skuPart(name), option && skuPart(option), randomCode(4)].filter(Boolean).join("-");
}

function generateBarcode() {
  const body = Array.from({ length: 12 }, () => Math.floor(Math.random() * 10)).join("");
  const weightedTotal = [...body].reduce(
    (total, digit, index) => total + Number(digit) * (index % 2 === 0 ? 1 : 3),
    0,
  );
  return `${body}${(10 - (weightedTotal % 10)) % 10}`;
}

function newVariant(prices = {}, existing = {}) {
  return {
    id: existing.id || crypto.randomUUID(),
    size: existing.size || "",
    sku: existing.sku || "",
    barcode: existing.barcode || "",
    stock: String(existing.stock ?? 0),
    sellingPrice: String(existing.sellingPrice ?? prices.sellingPrice ?? ""),
    costPrice: String(existing.costPrice ?? prices.costPrice ?? ""),
    imageUrl: existing.imageUrl || "",
    imageFile: null,
  };
}

function initialFormData(product = null) {
  return {
    name: product?.name || "",
    colourName: product?.colourName || product?.colour || "",
    productSize: product?.productSize || "",
    categoryId: product?.categoryId || "",
    brand: product?.brand || "",
    warrantyPeriodMonths: String(product?.warrantyPeriodMonths ?? 0),
    baseSku: product?.sku || "",
    baseBarcode: product?.barcode || "",
    stock: String(product?.stock ?? 0),
    costPrice: String(product?.costPrice ?? ""),
    sellingPrice: String(product?.sellingPrice ?? ""),
    weightKg: String(product?.weightKg ?? ""),
    description: product?.description || "",
    hasSizes: Boolean(product?.hasSizes),
    variants: (product?.sizes || []).map((variant) => newVariant(product, variant)),
  };
}

function AddProductModal({ isOpen, businessId, categories, product = null, onClose, onCreated, onUpdated }) {
  const [formData, setFormData] = useState(initialFormData);
  const [mediaFiles, setMediaFiles] = useState([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData(initialFormData(product));
      setMediaFiles([]);
      setErrorMessage("");
    }
  }, [isOpen, product]);

  const activeCategories = categories.filter((category) => category.status === "active");
  const selectedCategory = activeCategories.find((category) => category.id === formData.categoryId);
  const previews = useMemo(
    () => mediaFiles.map((file) => ({ file, url: file.type.startsWith("image/") ? URL.createObjectURL(file) : null })),
    [mediaFiles],
  );

  useEffect(() => () => previews.forEach(({ url }) => url && URL.revokeObjectURL(url)), [previews]);

  function updateField(event) {
    const { name, value, type, checked } = event.target;
    setFormData((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
  }

  function updateVariant(id, field, value) {
    setFormData((current) => ({
      ...current,
      variants: current.variants.map((variant) => variant.id === id ? { ...variant, [field]: value } : variant),
    }));
  }

  function addVariant() {
    setFormData((current) => ({
      ...current,
      variants: [...current.variants, newVariant(current)],
    }));
  }

  function toggleVariants(event) {
    const checked = event.target.checked;
    setFormData((current) => ({
      ...current,
      hasSizes: checked,
      variants: checked && current.variants.length === 0 ? [newVariant(current)] : current.variants,
    }));
  }

  function fillBaseIdentifier(field) {
    setFormData((current) => ({
      ...current,
      [field]: field === "baseSku" ? generateSku(current.name, current.productSize) : generateBarcode(),
    }));
  }

  function fillVariantIdentifier(id, field) {
    setFormData((current) => ({
      ...current,
      variants: current.variants.map((variant) => variant.id === id ? {
        ...variant,
        [field]: field === "sku" ? generateSku(current.name, variant.size) : generateBarcode(),
      } : variant),
    }));
  }

  async function handleGenerateDescription() {
    if (!formData.name.trim()) {
      setErrorMessage("Enter the product name before generating a description.");
      return;
    }
    setErrorMessage("");
    setIsGenerating(true);
    try {
      const description = await generateProductDescription(businessId, {
        name: formData.name,
        brand: formData.brand,
        colourName: formData.colourName,
        productSize: formData.productSize,
        categoryName: selectedCategory?.name || "",
        warrantyPeriodMonths: Number(formData.warrantyPeriodMonths),
        weightKg: formData.weightKg,
        costPrice: formData.hasSizes ? undefined : formData.costPrice,
        sellingPrice: formData.hasSizes ? undefined : formData.sellingPrice,
        variants: formData.hasSizes ? formData.variants.map(({ size, sku, barcode, stock, costPrice, sellingPrice }) => ({ size, sku, barcode, stock, costPrice, sellingPrice })) : [],
      });
      setFormData((current) => ({ ...current, description }));
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");
    setIsSaving(true);

    const existingBaseVariant = formData.variants[0] || {};
    const variants = formData.hasSizes
      ? formData.variants
      : [{
          id: existingBaseVariant.id,
          size: formData.productSize,
          sku: formData.baseSku,
          barcode: formData.baseBarcode,
          stock: formData.stock,
          sellingPrice: formData.sellingPrice,
          costPrice: formData.costPrice,
          imageUrl: existingBaseVariant.imageUrl || "",
        }];

    try {
      const baseCost = formData.hasSizes ? formData.variants[0]?.costPrice : formData.costPrice;
      const baseSelling = formData.hasSizes ? formData.variants[0]?.sellingPrice : formData.sellingPrice;
      const payload = {
        ...formData,
        productType: "",
        colourHex: "",
        supplierId: "",
        skuPrefix: formData.baseSku,
        compareAtPrice: "0",
        lowStockThreshold: "5",
        taxCategory: "standard",
        warrantyNotes: "",
        costPrice: baseCost,
        sellingPrice: baseSelling,
        variants: variants.map(({ imageFile: _imageFile, ...variant }) => variant),
        media: [],
      };
      let savedProduct = product
        ? await updateProduct(businessId, product.id, payload)
        : await createProduct(businessId, payload);
      if (mediaFiles.length) savedProduct = await uploadProductMedia(businessId, savedProduct.id, mediaFiles);
      for (const [index, variant] of formData.variants.entries()) {
        if (!variant.imageFile) continue;
        const savedVariant = savedProduct.sizes.find((item) => item.id === variant.id) || savedProduct.sizes[index];
        if (savedVariant) savedProduct = await uploadVariantImage(businessId, savedProduct.id, savedVariant.id, variant.imageFile);
      }
      if (product) onUpdated?.(savedProduct); else onCreated?.(savedProduct);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell isOpen={isOpen} title={product ? "Edit Product" : "Add Product"} onClose={onClose} size="wide">
      <form className="stitch-product-form" onSubmit={handleSubmit}>
        <div className="stitch-product__top">
          <div className="stitch-product__details">
            <label className="stitch-product__full">Product Name
              <input name="name" value={formData.name} onChange={updateField} placeholder="Enter product name" required />
            </label>
            <label>Product color
              <input name="colourName" value={formData.colourName} onChange={updateField} placeholder="Select color..." />
            </label>
            <label>Product Size
              <input name="productSize" value={formData.productSize} onChange={updateField} placeholder="Select size..." />
            </label>
            <label>Category <small>(optional)</small>
              <select name="categoryId" value={formData.categoryId} onChange={updateField}>
                <option value="">Uncategorized - assign later</option>
                {activeCategories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
            </label>
            <label>Brand
              <input name="brand" value={formData.brand} onChange={updateField} placeholder="Select brand..." />
            </label>
            <label>Warranty
              <select name="warrantyPeriodMonths" value={formData.warrantyPeriodMonths} onChange={updateField}>
                <option value="0">None</option><option value="1">1 month</option><option value="3">3 months</option>
                <option value="6">6 months</option><option value="12">1 year</option><option value="24">2 years</option>
              </select>
            </label>
          </div>

          <section className="stitch-product__photos">
            <strong>Product Photos</strong>
            <label className="stitch-product__upload"><Upload size={15} /> Upload
              <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple onChange={(event) => setMediaFiles(Array.from(event.target.files).slice(0, 12))} />
            </label>
            <div className="stitch-product__photo-grid">
              {previews.slice(0, 3).map((preview, index) => (
                <span key={`${preview.file.name}-${index}`}>{preview.url ? <img src={preview.url} alt="" /> : <ImageIcon size={19} />}</span>
              ))}
              {Array.from({ length: Math.max(0, 3 - previews.length) }, (_, index) => <span key={`empty-${index}`}><ImageIcon size={19} /></span>)}
              <label className="stitch-product__photo-add"><Plus size={22} />
                <input type="file" accept="image/*" multiple onChange={(event) => setMediaFiles((current) => [...current, ...Array.from(event.target.files)].slice(0, 12))} />
              </label>
            </div>
          </section>
        </div>

        <div className="stitch-product__identifiers">
          <IdentifierField label="SKU ID" name="baseSku" value={formData.baseSku} placeholder="Generate or enter SKU" onChange={updateField} onGenerate={() => fillBaseIdentifier("baseSku")} disabled={formData.hasSizes} />
          <IdentifierField label="Barcode" name="baseBarcode" value={formData.baseBarcode} placeholder="Scan or enter barcode" onChange={updateField} onGenerate={() => fillBaseIdentifier("baseBarcode")} disabled={formData.hasSizes} />
        </div>

        <section className={`stitch-product__panel ${formData.hasSizes ? "stitch-product__panel--weight-only" : ""}`}>
          <strong>{formData.hasSizes ? "Product Weight" : "Pricing"}</strong>
          <div className="stitch-product__pricing">
            {!formData.hasSizes && <label>Cost price<input name="costPrice" type="number" min="0" step="0.01" value={formData.costPrice} onChange={updateField} placeholder="LKR 0.00" required /></label>}
            {!formData.hasSizes && <label>Selling price<input name="sellingPrice" type="number" min="0.01" step="0.01" value={formData.sellingPrice} onChange={updateField} placeholder="LKR 0.00" required /></label>}
            <label>Weight<input name="weightKg" type="number" min="0.001" step="0.001" value={formData.weightKg} onChange={updateField} placeholder="0.00 kg" required /></label>
            {!formData.hasSizes && <label>Stock<input name="stock" type="number" min="0" step="1" value={formData.stock} onChange={updateField} required /></label>}
          </div>
        </section>

        <section className="stitch-product__panel stitch-product__variants">
          <div className="stitch-product__section-title"><strong>Variants</strong><label><input type="checkbox" checked={formData.hasSizes} onChange={toggleVariants} /> This product has variants</label></div>
          {formData.hasSizes && <>
            <div className="stitch-product__variant-head"><span>Variant</span><span>Image</span><span>SKU</span><span>Barcode</span><span>Stock</span><span>Selling price</span><span>Cost price</span><span /></div>
            {formData.variants.map((variant, index) => (
              <div className="stitch-product__variant-row" key={variant.id}>
                <input value={variant.size} onChange={(event) => updateVariant(variant.id, "size", event.target.value)} placeholder="e.g. Red, Small" aria-label={`Variant ${index + 1}`} required />
                <label className="stitch-product__variant-image">{variant.imageFile ? <img src={URL.createObjectURL(variant.imageFile)} alt="" /> : variant.imageUrl ? <img src={variant.imageUrl} alt="" /> : <ImageIcon size={16} />}<input type="file" accept="image/*" onChange={(event) => updateVariant(variant.id, "imageFile", event.target.files[0] || null)} /></label>
                <GeneratedInput value={variant.sku} onChange={(value) => updateVariant(variant.id, "sku", value)} onGenerate={() => fillVariantIdentifier(variant.id, "sku")} label={`SKU ${index + 1}`} />
                <GeneratedInput value={variant.barcode} onChange={(value) => updateVariant(variant.id, "barcode", value)} onGenerate={() => fillVariantIdentifier(variant.id, "barcode")} label={`Barcode ${index + 1}`} />
                <input type="number" min="0" value={variant.stock} onChange={(event) => updateVariant(variant.id, "stock", event.target.value)} aria-label={`Stock ${index + 1}`} required />
                <input type="number" min="0.01" step="0.01" value={variant.sellingPrice} onChange={(event) => updateVariant(variant.id, "sellingPrice", event.target.value)} aria-label={`Selling price ${index + 1}`} required />
                <input type="number" min="0" step="0.01" value={variant.costPrice} onChange={(event) => updateVariant(variant.id, "costPrice", event.target.value)} aria-label={`Cost price ${index + 1}`} required />
                <button type="button" onClick={() => setFormData((current) => ({ ...current, variants: current.variants.filter(({ id }) => id !== variant.id) }))} aria-label={`Remove variant ${index + 1}`}><Trash2 size={15} /></button>
              </div>
            ))}
            <button className="stitch-product__add-variant" type="button" onClick={addVariant}><Plus size={15} /> Add variant</button>
          </>}
        </section>

        <section className="stitch-product__description">
          <div><strong>Description</strong><button type="button" onClick={handleGenerateDescription} disabled={isGenerating}><WandSparkles size={14} /> {isGenerating ? "Generating..." : "Generate"}</button></div>
          <textarea name="description" value={formData.description} onChange={updateField} placeholder="Write a detailed product description..." rows="4" />
        </section>

        {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}
        <footer className="stitch-product__footer"><button type="button" onClick={onClose}>Cancel</button><button className="stitch-product__save" type="submit" disabled={isSaving}>{isSaving ? "Saving..." : product ? "Save Product" : "Add Product"}</button></footer>
      </form>
    </ModalShell>
  );
}

function IdentifierField({ label, onGenerate, disabled, ...inputProps }) {
  return <label>{label}<span className="stitch-product__generated"><input {...inputProps} disabled={disabled} required={!disabled} /><button type="button" onClick={onGenerate} disabled={disabled} aria-label={`Generate ${label}`}><WandSparkles size={15} /></button></span></label>;
}

function GeneratedInput({ value, onChange, onGenerate, label }) {
  return <span className="stitch-product__generated"><input value={value} onChange={(event) => onChange(event.target.value)} aria-label={label} required /><button type="button" onClick={onGenerate} aria-label={`Generate ${label}`}><WandSparkles size={14} /></button></span>;
}

export default AddProductModal;
