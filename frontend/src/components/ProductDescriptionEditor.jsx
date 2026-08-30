import { Plus, Trash2, WandSparkles } from "lucide-react";

import ModalShell from "./ModalShell";
import "./ProductDescriptionEditor.css";

function updateListItem(list, index, value) {
  return list.map((item, itemIndex) => (itemIndex === index ? value : item));
}

export function buildProductDescription(productInfo) {
  const sections = [];
  const description = String(productInfo.description || "").trim();
  if (description) sections.push(description);

  const highlights = (productInfo.highlights || []).map((item) => String(item).trim()).filter(Boolean);
  if (highlights.length) sections.push(`Highlights: ${highlights.join("; ")}.`);

  const identitySpecifications = [
    ["Brand", productInfo.brand],
    ["Model", productInfo.model],
    ["Category", productInfo.category],
  ];
  const generatedSpecifications = (productInfo.specifications || []).map((item) => [item.name, item.value]);
  const seen = new Set();
  const specifications = [...identitySpecifications, ...generatedSpecifications]
    .map(([name, value]) => [String(name || "").trim(), value == null ? "" : String(value).trim()])
    .filter(([name, value]) => name && value)
    .filter(([name]) => {
      const key = name.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  if (specifications.length) {
    sections.push(`Specifications: ${specifications.map(([name, value]) => `${name}: ${value}`).join("; ")}.`);
  }

  // Product descriptions are stored with a 4,000-character backend limit.
  return sections.join("\n\n").slice(0, 4000).trim();
}

function ProductDescriptionEditor({ productInfo, onChange, onCancel, onApply }) {
  if (!productInfo) return null;

  function updateField(field, value) {
    onChange({ ...productInfo, [field]: value });
  }

  return (
    <ModalShell
      isOpen
      title="Review generated product information"
      description="Check every AI-generated value before adding it to the product description. Unknown details may stay empty."
      onClose={onCancel}
      size="large"
    >
      <div className="product-info-editor">
        <div className="product-info-editor__notice">
          <WandSparkles size={18} aria-hidden="true" />
          <span>AI confidence: <strong>{productInfo.confidence}</strong>. You remain in control of the saved information.</span>
        </div>

        <section className="product-info-editor__identity">
          <label>Product name<input value={productInfo.product_name || ""} onChange={(event) => updateField("product_name", event.target.value)} /></label>
          <label>Brand<input value={productInfo.brand || ""} onChange={(event) => updateField("brand", event.target.value || null)} placeholder="Unknown" /></label>
          <label>Model<input value={productInfo.model || ""} onChange={(event) => updateField("model", event.target.value || null)} placeholder="Unknown" /></label>
          <label>Category<input value={productInfo.category || ""} onChange={(event) => updateField("category", event.target.value)} /></label>
          <label>Confidence
            <select value={productInfo.confidence || "low"} onChange={(event) => updateField("confidence", event.target.value)}>
              <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select>
          </label>
        </section>

        <label className="product-info-editor__description">Description
          <textarea rows="4" maxLength="1600" value={productInfo.description || ""} onChange={(event) => updateField("description", event.target.value)} />
        </label>

        <EditableTextList
          title="Highlights"
          values={productInfo.highlights || []}
          placeholder="Add a confirmed product highlight"
          onChange={(values) => updateField("highlights", values)}
        />

        <section className="product-info-editor__section">
          <div className="product-info-editor__section-title">
            <strong>Specifications</strong>
            <button type="button" onClick={() => updateField("specifications", [...(productInfo.specifications || []), { name: "", value: "" }])}><Plus size={15} /> Add specification</button>
          </div>
          <div className="product-info-editor__specifications">
            {(productInfo.specifications || []).map((item, index) => (
              <div className="product-info-editor__specification" key={`specification-${index}`}>
                <input aria-label={`Specification name ${index + 1}`} value={item.name || ""} placeholder="Name" onChange={(event) => updateField("specifications", updateListItem(productInfo.specifications, index, { ...item, name: event.target.value }))} />
                <input aria-label={`Specification value ${index + 1}`} value={item.value || ""} placeholder="Value or leave empty if unknown" onChange={(event) => updateField("specifications", updateListItem(productInfo.specifications, index, { ...item, value: event.target.value || null }))} />
                <button type="button" aria-label={`Remove specification ${index + 1}`} onClick={() => updateField("specifications", productInfo.specifications.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={15} /></button>
              </div>
            ))}
            {!productInfo.specifications?.length && <p>No confirmed specifications were returned. Add only details you can verify.</p>}
          </div>
        </section>

        <EditableTextList
          title="Missing information"
          values={productInfo.missing_information || []}
          placeholder="Information still needed"
          onChange={(values) => updateField("missing_information", values)}
        />

        <section className="product-info-editor__preview">
          <strong>Description preview</strong>
          <p>{buildProductDescription(productInfo) || "Add or confirm some product information first."}</p>
        </section>

        <footer className="product-info-editor__footer">
          <button type="button" onClick={onCancel}>Back to product</button>
          <button className="product-info-editor__apply" type="button" onClick={() => onApply(buildProductDescription(productInfo))}>Use this description</button>
        </footer>
      </div>
    </ModalShell>
  );
}

function EditableTextList({ title, values, placeholder, onChange }) {
  return (
    <section className="product-info-editor__section">
      <div className="product-info-editor__section-title">
        <strong>{title}</strong>
        <button type="button" onClick={() => onChange([...values, ""])}><Plus size={15} /> Add</button>
      </div>
      <div className="product-info-editor__list">
        {values.map((value, index) => (
          <div key={`${title}-${index}`}>
            <input value={value} placeholder={placeholder} onChange={(event) => onChange(updateListItem(values, index, event.target.value))} />
            <button type="button" aria-label={`Remove ${title.toLowerCase()} ${index + 1}`} onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={15} /></button>
          </div>
        ))}
        {!values.length && <p>None</p>}
      </div>
    </section>
  );
}

export default ProductDescriptionEditor;
