import { useMemo, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronDown,
  Copy,
  Eye,
  Globe,
  Info,
  Package,
  Pencil,
  Plus,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
} from "lucide-react";

import ModalShell from "./ModalShell";
import "./ProductDescriptionEditor.css";

// Preset emoji icons for quick customization
export const COMMON_ICONS = [
  "✨", "⭐", "⚡", "🔋", "🎧", "📱", "🏷️", "📶", "🛡️", "📦",
  "🎨", "⚖️", "💧", "🎙️", "🖥️", "📸", "💾", "🚀", "💎", "🚚",
  "🔹", "✅", "🔥", "👌", "💡", "🔌", "📐", "🧵", "🎮", "🌟",
];

/**
 * Intelligently suggests an appropriate emoji icon based on field name or content keywords.
 */
export function getSuggestedIcon(fieldName = "", value = "") {
  const text = `${fieldName} ${value}`.toLowerCase();
  if (/brand|make|manufacturer/i.test(text)) return "🏷️";
  if (/model|series|edition/i.test(text)) return "📱";
  if (/battery|mah|playback|runtime|battery_life/i.test(text)) return "🔋";
  if (/fast charge|power|watt|voltage|charging|charge|amp/i.test(text)) return "⚡";
  if (/bluetooth|wireless|wifi|5g|4g|nfc|connectivity/i.test(text)) return "📶";
  if (/display|screen|oled|amoled|lcd|inch|resolution/i.test(text)) return "🖥️";
  if (/camera|photo|video|megapixels|lens|sensor/i.test(text)) return "📸";
  if (/audio|sound|bass|speaker|earbud|headphone|driver|volume/i.test(text)) return "🎧";
  if (/noise|anc|enc|mic|microphone|call|calling/i.test(text)) return "🎙️";
  if (/storage|ram|rom|memory|capacity|gb|tb/i.test(text)) return "💾";
  if (/warranty|guarantee|protection|coverage/i.test(text)) return "🛡️";
  if (/water|splash|sweat|ipx|ip68|ip67|waterproof/i.test(text)) return "💧";
  if (/weight|gram|kg|weight_kg|weightkg/i.test(text)) return "⚖️";
  if (/dimension|size|length|width|height|compact/i.test(text)) return "📐";
  if (/color|colour|finish|shade/i.test(text)) return "🎨";
  if (/material|leather|aluminum|steel|plastic|fabric|build/i.test(text)) return "🧵";
  if (/box|package|includes|included|accessories|in the box/i.test(text)) return "📦";
  if (/delivery|shipping|islandwide|courier|dispatch/i.test(text)) return "🚚";
  if (/condition|sealed|original|authentic|genuine|new/i.test(text)) return "💎";
  if (/speed|cpu|processor|chip|hz|fps|performance|fast/i.test(text)) return "🚀";
  if (/os|android|ios|windows|system|compatibility|app/i.test(text)) return "⚙️";
  if (/highlight|feature|advantage|benefit/i.test(text)) return "⭐";
  return "🔹";
}

/**
 * Builds a customer-facing, visually rich product description with icons and structured sections.
 */
export function buildProductDescription(productInfo, stylePreset = "rich_icons") {
  if (!productInfo) return "";

  const sections = [];
  const title = (productInfo.product_name || "").trim();
  const description = (productInfo.description || "").trim();

  // Style: Minimalist / Clean Bullets
  if (stylePreset === "minimal") {
    if (title) sections.push(`• ${title}`);
    if (description) sections.push(description);

    const highlights = (productInfo.highlights || [])
      .filter((item) => (typeof item === "string" ? item.trim() : item?.text?.trim()))
      .map((item) => (typeof item === "string" ? item.trim() : item.text.trim()));
    if (highlights.length) {
      sections.push(`Key Features:\n${highlights.map((h) => `- ${h}`).join("\n")}`);
    }

    const specs = (productInfo.specifications || [])
      .filter((s) => s.name?.trim() && s.value?.trim())
      .map((s) => `- ${s.name}: ${s.value}`);
    if (specs.length) {
      sections.push(`Specifications:\n${specs.join("\n")}`);
    }

    return sections.join("\n\n").slice(0, 4000).trim();
  }

  // Style: Detailed Spec Sheet
  if (stylePreset === "spec_sheet") {
    if (title) sections.push(`📌 ${title.toUpperCase()}`);
    if (description) sections.push(description);

    const specs = [
      ...(productInfo.brand ? [{ name: "Brand", value: productInfo.brand, icon: "🏷️" }] : []),
      ...(productInfo.model ? [{ name: "Model", value: productInfo.model, icon: "📱" }] : []),
      ...(productInfo.category ? [{ name: "Category", value: productInfo.category, icon: "📁" }] : []),
      ...(productInfo.specifications || []),
    ].filter((s) => s.name?.trim() && s.value?.trim());

    if (specs.length) {
      sections.push(
        `📋 PRODUCT SPECIFICATIONS:\n${specs.map((s) => `${s.icon || "•"} ${s.name}: ${s.value}`).join("\n")}`
      );
    }

    const highlights = (productInfo.highlights || []).filter((h) =>
      typeof h === "string" ? h.trim() : h?.text?.trim()
    );
    if (highlights.length) {
      sections.push(
        `⭐ HIGHLIGHTS:\n${highlights.map((h) => `✔ ${typeof h === "string" ? h.trim() : h.text.trim()}`).join("\n")}`
      );
    }

    return sections.join("\n\n").slice(0, 4000).trim();
  }

  // Default Style: Rich Eye-Catching with Icons (High conversion for customer chat & storefront)
  if (title) {
    sections.push(`✨ ${title}`);
  }

  if (description) {
    sections.push(`📝 Product Overview:\n${description}`);
  }

  // Highlights
  const highlights = (productInfo.highlights || []).filter((h) => {
    const text = typeof h === "string" ? h : h?.text;
    return Boolean(text && text.trim() && (h.enabled !== false));
  });

  if (highlights.length) {
    const highlightLines = highlights.map((h) => {
      const text = typeof h === "string" ? h.trim() : h.text.trim();
      const icon = (typeof h === "object" && h.icon) ? h.icon : getSuggestedIcon("", text);
      return `• ${icon} ${text}`;
    });
    sections.push(`⭐ Key Highlights:\n${highlightLines.join("\n")}`);
  }

  // Specifications
  const identitySpecs = [];
  if (productInfo.brand) {
    identitySpecs.push({ name: "Brand", value: productInfo.brand, icon: "🏷️", enabled: true });
  }
  if (productInfo.model) {
    identitySpecs.push({ name: "Model", value: productInfo.model, icon: "📱", enabled: true });
  }

  const customSpecs = (productInfo.specifications || []).filter((s) => s.name?.trim() && s.value?.trim() && (s.enabled !== false));

  // Deduplicate specifications by lowercased name
  const seenKeys = new Set();
  const allSpecs = [...identitySpecs, ...customSpecs].filter((s) => {
    const key = s.name.trim().toLowerCase();
    if (seenKeys.has(key)) return false;
    seenKeys.add(key);
    return true;
  });

  if (allSpecs.length) {
    const specLines = allSpecs.map((s) => {
      const icon = s.icon || getSuggestedIcon(s.name, s.value);
      return `• ${icon} ${s.name}: ${s.value}`;
    });
    sections.push(`⚙️ Specifications:\n${specLines.join("\n")}`);
  }

  // Package & Warranty / Customer Trust section if provided
  const trustItems = [];
  if (productInfo.warranty) {
    trustItems.push(`• 🛡️ Warranty: ${productInfo.warranty}`);
  }
  if (productInfo.package_contents) {
    trustItems.push(`• 📦 In The Box: ${productInfo.package_contents}`);
  }
  if (productInfo.delivery_note) {
    trustItems.push(`• 🚚 Delivery: ${productInfo.delivery_note}`);
  }

  if (trustItems.length) {
    sections.push(`🛡️ Package & Guarantee:\n${trustItems.join("\n")}`);
  }

  return sections.join("\n\n").slice(0, 4000).trim();
}

/**
 * Quick inline icon picker modal/popover
 */
function IconPicker({ currentIcon, onSelect, onClose }) {
  return (
    <div className="product-icon-picker">
      <div className="product-icon-picker__header">
        <span>Choose Icon</span>
        <button type="button" onClick={onClose} aria-label="Close icon picker">
          <X size={12} />
        </button>
      </div>
      <div className="product-icon-picker__grid">
        {COMMON_ICONS.map((icon) => (
          <button
            key={icon}
            type="button"
            className={`product-icon-picker__item ${icon === currentIcon ? "is-active" : ""}`}
            onClick={() => {
              onSelect(icon);
              onClose();
            }}
          >
            {icon}
          </button>
        ))}
      </div>
    </div>
  );
}

function ProductDescriptionEditor({ productInfo, onChange, onCancel, onApply }) {
  if (!productInfo) return null;

  // Active view tab: "editor" | "internet_reference" | "preview"
  const [activeTab, setActiveTab] = useState("editor");
  const [stylePreset, setStylePreset] = useState("rich_icons");
  const [isCopied, setIsCopied] = useState(false);
  const [isManualEdit, setIsManualEdit] = useState(false);
  const [manualDescription, setManualDescription] = useState("");
  const [activeIconPicker, setActiveIconPicker] = useState(null); // { type: 'spec'|'highlight', index }

  // Original web-scraped/AI reference snapshot
  const original = useMemo(() => {
    return (
      productInfo.original_found_details || {
        product_name: productInfo.product_name || "",
        brand: productInfo.brand || "",
        model: productInfo.model || "",
        category: productInfo.category || "",
        description: productInfo.description || "",
        highlights: Array.isArray(productInfo.highlights)
          ? productInfo.highlights.map((h) => (typeof h === "string" ? h : h.text))
          : [],
        specifications: Array.isArray(productInfo.specifications)
          ? productInfo.specifications.map((s) => ({ name: s.name, value: s.value }))
          : [],
      }
    );
  }, [productInfo.original_found_details]);

  // Normalize highlights into object structure { text, icon, enabled }
  const highlights = useMemo(() => {
    return (productInfo.highlights || []).map((h) => {
      if (typeof h === "string") {
        return { text: h, icon: getSuggestedIcon("", h), enabled: true };
      }
      return {
        text: h.text || "",
        icon: h.icon || getSuggestedIcon("", h.text || ""),
        enabled: h.enabled !== false,
      };
    });
  }, [productInfo.highlights]);

  // Normalize specifications into object structure { name, value, icon, enabled }
  const specifications = useMemo(() => {
    return (productInfo.specifications || []).map((s) => ({
      name: s.name || "",
      value: s.value || "",
      icon: s.icon || getSuggestedIcon(s.name, s.value),
      enabled: s.enabled !== false,
    }));
  }, [productInfo.specifications]);

  function updateField(field, value) {
    onChange({ ...productInfo, [field]: value });
  }

  function updateHighlights(newHighlights) {
    updateField("highlights", newHighlights);
  }

  function updateSpecifications(newSpecs) {
    updateField("specifications", newSpecs);
  }

  // Check if a field was modified from the original internet-found version
  function isFieldModified(fieldName, currentValue) {
    const orig = original[fieldName];
    if (orig == null && (currentValue == null || currentValue === "")) return false;
    return String(orig || "").trim() !== String(currentValue || "").trim();
  }

  // Restore a field to its internet-found original value
  function revertField(fieldName) {
    updateField(fieldName, original[fieldName] || "");
  }

  // Toggle specification enabled state
  function toggleSpecEnabled(index) {
    const updated = specifications.map((spec, i) =>
      i === index ? { ...spec, enabled: !spec.enabled } : spec
    );
    updateSpecifications(updated);
  }

  // Edit specification item
  function editSpec(index, field, value) {
    const updated = specifications.map((spec, i) => {
      if (i !== index) return spec;
      const next = { ...spec, [field]: value };
      if (field === "name" && !spec.customIcon) {
        next.icon = getSuggestedIcon(value, spec.value);
      }
      return next;
    });
    updateSpecifications(updated);
  }

  // Remove specification
  function removeSpec(index) {
    updateSpecifications(specifications.filter((_, i) => i !== index));
  }

  // Add specification
  function addSpec(presetName = "", presetValue = "") {
    const newSpec = {
      name: presetName,
      value: presetValue,
      icon: getSuggestedIcon(presetName, presetValue),
      enabled: true,
    };
    updateSpecifications([...specifications, newSpec]);
  }

  // Toggle highlight enabled state
  function toggleHighlightEnabled(index) {
    const updated = highlights.map((h, i) =>
      i === index ? { ...h, enabled: !h.enabled } : h
    );
    updateHighlights(updated);
  }

  // Edit highlight item
  function editHighlight(index, field, value) {
    const updated = highlights.map((h, i) => {
      if (i !== index) return h;
      const next = { ...h, [field]: value };
      if (field === "text" && !h.customIcon) {
        next.icon = getSuggestedIcon("", value);
      }
      return next;
    });
    updateHighlights(updated);
  }

  // Remove highlight
  function removeHighlight(index) {
    updateHighlights(highlights.filter((_, i) => i !== index));
  }

  // Add highlight
  function addHighlight(text = "") {
    const newHighlight = {
      text,
      icon: getSuggestedIcon("", text),
      enabled: true,
    };
    updateHighlights([...highlights, newHighlight]);
  }

  // Current generated text description based on active preset
  const generatedText = useMemo(() => {
    return buildProductDescription(productInfo, stylePreset);
  }, [productInfo, stylePreset]);

  // Active description to use
  const finalDescription = isManualEdit ? manualDescription : generatedText;

  // Copy to clipboard with feedback
  function handleCopy() {
    navigator.clipboard.writeText(finalDescription);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  }

  return (
    <ModalShell
      isOpen
      title="Review & Customize Generated Product Information"
      description="Inspect details discovered online from web research. Verify or exchange any specifications below to match your actual inventory before generating the customer-ready description."
      onClose={onCancel}
      size="large"
    >
      <div className="product-desc-editor">
        {/* Source & Grounding Trust Bar */}
        <div className="product-desc-editor__trust-bar">
          <div className="product-desc-editor__trust-left">
            <span className="product-desc-editor__source-badge">
              <Globe size={14} />
              <span>Details Sourced from Web AI Research</span>
            </span>
            <span className={`product-desc-editor__confidence-badge is-${productInfo.confidence || "medium"}`}>
              <Sparkles size={13} />
              <span>Confidence: <strong>{productInfo.confidence || "medium"}</strong></span>
            </span>
          </div>

          {/* View Mode Navigation Tabs */}
          <div className="product-desc-editor__tabs">
            <button
              type="button"
              className={`product-desc-editor__tab ${activeTab === "editor" ? "is-active" : ""}`}
              onClick={() => setActiveTab("editor")}
            >
              <Pencil size={13} />
              <span>Customize for Your Stock</span>
            </button>
            <button
              type="button"
              className={`product-desc-editor__tab ${activeTab === "internet_reference" ? "is-active" : ""}`}
              onClick={() => setActiveTab("internet_reference")}
            >
              <Globe size={13} />
              <span>Internet Discovered Details</span>
            </button>
            <button
              type="button"
              className={`product-desc-editor__tab ${activeTab === "preview" ? "is-active" : ""}`}
              onClick={() => setActiveTab("preview")}
            >
              <Eye size={13} />
              <span>Customer Live Preview</span>
            </button>
          </div>
        </div>

        {/* =========================================================================
            TAB 1: CUSTOMIZE & EXCHANGE (Main Seller Workbench)
            ========================================================================= */}
        {activeTab === "editor" && (
          <div className="product-desc-editor__workbench">
            {/* Identity & Core Specs */}
            <section className="product-desc-editor__card">
              <header className="product-desc-editor__card-header">
                <div>
                  <strong>Product Identity & Essentials</strong>
                  <p>Exchange values if your actual stock differs from what was found online.</p>
                </div>
              </header>

              <div className="product-desc-editor__identity-grid">
                {/* Product Name */}
                <div className="product-desc-editor__field">
                  <div className="product-desc-editor__field-label">
                    <span>Product Name</span>
                    {isFieldModified("product_name", productInfo.product_name) && (
                      <span className="product-desc-editor__status-tag is-modified" title="Changed from web value">
                        Modified
                        <button type="button" onClick={() => revertField("product_name")} title="Revert to internet value">
                          <RotateCcw size={10} />
                        </button>
                      </span>
                    )}
                  </div>
                  <input
                    value={productInfo.product_name || ""}
                    onChange={(e) => updateField("product_name", e.target.value)}
                    placeholder="e.g. Sony WH-1000XM4 Wireless Headphones"
                  />
                </div>

                {/* Brand */}
                <div className="product-desc-editor__field">
                  <div className="product-desc-editor__field-label">
                    <span>Brand</span>
                    {isFieldModified("brand", productInfo.brand) && (
                      <span className="product-desc-editor__status-tag is-modified">
                        Modified
                        <button type="button" onClick={() => revertField("brand")}>
                          <RotateCcw size={10} />
                        </button>
                      </span>
                    )}
                  </div>
                  <input
                    value={productInfo.brand || ""}
                    onChange={(e) => updateField("brand", e.target.value || null)}
                    placeholder="e.g. Sony"
                  />
                </div>

                {/* Model */}
                <div className="product-desc-editor__field">
                  <div className="product-desc-editor__field-label">
                    <span>Model / Version</span>
                    {isFieldModified("model", productInfo.model) && (
                      <span className="product-desc-editor__status-tag is-modified">
                        Modified
                        <button type="button" onClick={() => revertField("model")}>
                          <RotateCcw size={10} />
                        </button>
                      </span>
                    )}
                  </div>
                  <input
                    value={productInfo.model || ""}
                    onChange={(e) => updateField("model", e.target.value || null)}
                    placeholder="e.g. WH-1000XM4"
                  />
                </div>

                {/* Category */}
                <div className="product-desc-editor__field">
                  <div className="product-desc-editor__field-label">
                    <span>Category</span>
                  </div>
                  <input
                    value={productInfo.category || ""}
                    onChange={(e) => updateField("category", e.target.value)}
                    placeholder="e.g. Headphones & Audio"
                  />
                </div>
              </div>

              {/* Overview / Narrative Description */}
              <div className="product-desc-editor__field" style={{ marginTop: "14px" }}>
                <div className="product-desc-editor__field-label">
                  <span>Customer Overview Paragraph</span>
                  <small>Engaging introduction shown at the top of the description.</small>
                </div>
                <textarea
                  rows="3"
                  maxLength="1600"
                  value={productInfo.description || ""}
                  onChange={(e) => updateField("description", e.target.value)}
                  placeholder="Write a clear, attractive summary of the product..."
                />
              </div>
            </section>

            {/* Key Highlights Section */}
            <section className="product-desc-editor__card">
              <header className="product-desc-editor__card-header">
                <div>
                  <strong>⭐ Key Selling Highlights</strong>
                  <p>Bullet points with eye-catching icons shown prominently to customers.</p>
                </div>
                <button
                  type="button"
                  className="product-desc-editor__add-btn"
                  onClick={() => addHighlight("")}
                >
                  <Plus size={14} />
                  <span>Add Highlight</span>
                </button>
              </header>

              <div className="product-desc-editor__items-list">
                {highlights.map((item, index) => (
                  <div
                    key={`highlight-${index}`}
                    className={`product-desc-editor__item-row ${!item.enabled ? "is-disabled" : ""}`}
                  >
                    {/* Include/Exclude Toggle */}
                    <input
                      type="checkbox"
                      className="product-desc-editor__checkbox"
                      checked={item.enabled}
                      onChange={() => toggleHighlightEnabled(index)}
                      title={item.enabled ? "Included in customer description" : "Excluded from description"}
                    />

                    {/* Icon Trigger */}
                    <div className="product-desc-editor__icon-wrapper">
                      <button
                        type="button"
                        className="product-desc-editor__icon-btn"
                        onClick={() =>
                          setActiveIconPicker(
                            activeIconPicker?.index === index && activeIconPicker?.type === "highlight"
                              ? null
                              : { type: "highlight", index }
                          )
                        }
                        title="Click to change icon"
                      >
                        {item.icon || "⭐"}
                      </button>

                      {activeIconPicker?.type === "highlight" && activeIconPicker?.index === index && (
                        <IconPicker
                          currentIcon={item.icon}
                          onSelect={(newIcon) => {
                            editHighlight(index, "icon", newIcon);
                            editHighlight(index, "customIcon", true);
                          }}
                          onClose={() => setActiveIconPicker(null)}
                        />
                      )}
                    </div>

                    {/* Highlight text input */}
                    <input
                      className="product-desc-editor__item-input"
                      value={item.text}
                      placeholder="e.g. Industry-leading Active Noise Cancellation"
                      onChange={(e) => editHighlight(index, "text", e.target.value)}
                    />

                    {/* Delete item */}
                    <button
                      type="button"
                      className="product-desc-editor__delete-btn"
                      onClick={() => removeHighlight(index)}
                      title="Remove highlight"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}

                {!highlights.length && (
                  <div className="product-desc-editor__empty">
                    <Info size={16} />
                    <span>No highlights yet. Click "Add Highlight" to list key selling features.</span>
                  </div>
                )}
              </div>

              {/* Quick Highlight Presets */}
              <div className="product-desc-editor__presets">
                <span className="product-desc-editor__presets-title">Quick Add:</span>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addHighlight("100% Brand New Original & Sealed Box")}
                >
                  💎 Brand New Sealed
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addHighlight("Long-lasting battery with all-day playback")}
                >
                  🔋 All-Day Battery
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addHighlight("Fast USB Type-C charging support")}
                >
                  ⚡ Fast Charging
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addHighlight("Official seller warranty included with peace of mind")}
                >
                  🛡️ Warranty Included
                </button>
              </div>
            </section>

            {/* Specifications Section ("Exchange to match actual stock") */}
            <section className="product-desc-editor__card">
              <header className="product-desc-editor__card-header">
                <div>
                  <strong>⚙️ Specifications & Technical Details</strong>
                  <p>Exchange values to match your exact stock (e.g. storage, color, connectivity, battery, warranty).</p>
                </div>
                <button
                  type="button"
                  className="product-desc-editor__add-btn"
                  onClick={() => addSpec("", "")}
                >
                  <Plus size={14} />
                  <span>Add Specification</span>
                </button>
              </header>

              <div className="product-desc-editor__specs-table">
                <div className="product-desc-editor__specs-head">
                  <span style={{ width: "24px" }} />
                  <span style={{ width: "36px" }}>Icon</span>
                  <span>Specification</span>
                  <span>Your Actual Value</span>
                  <span style={{ width: "32px" }} />
                </div>

                {specifications.map((spec, index) => {
                  const origSpec = original.specifications?.find(
                    (s) => s.name?.toLowerCase() === spec.name?.toLowerCase()
                  );
                  const isModified = origSpec && origSpec.value !== spec.value;

                  return (
                    <div
                      key={`spec-${index}`}
                      className={`product-desc-editor__spec-row ${!spec.enabled ? "is-disabled" : ""}`}
                    >
                      {/* Toggle Checkbox */}
                      <input
                        type="checkbox"
                        className="product-desc-editor__checkbox"
                        checked={spec.enabled}
                        onChange={() => toggleSpecEnabled(index)}
                        title={spec.enabled ? "Include in description" : "Exclude from description"}
                      />

                      {/* Icon button */}
                      <div className="product-desc-editor__icon-wrapper">
                        <button
                          type="button"
                          className="product-desc-editor__icon-btn"
                          onClick={() =>
                            setActiveIconPicker(
                              activeIconPicker?.index === index && activeIconPicker?.type === "spec"
                                ? null
                                : { type: "spec", index }
                            )
                          }
                          title="Click to change icon"
                        >
                          {spec.icon || "🔹"}
                        </button>

                        {activeIconPicker?.type === "spec" && activeIconPicker?.index === index && (
                          <IconPicker
                            currentIcon={spec.icon}
                            onSelect={(newIcon) => {
                              editSpec(index, "icon", newIcon);
                              editSpec(index, "customIcon", true);
                            }}
                            onClose={() => setActiveIconPicker(null)}
                          />
                        )}
                      </div>

                      {/* Spec Name */}
                      <input
                        className="product-desc-editor__spec-name"
                        value={spec.name}
                        placeholder="e.g. Battery Life"
                        onChange={(e) => editSpec(index, "name", e.target.value)}
                      />

                      {/* Spec Value */}
                      <div className="product-desc-editor__spec-value-col">
                        <input
                          className="product-desc-editor__spec-value"
                          value={spec.value}
                          placeholder="e.g. Up to 30 Hours"
                          onChange={(e) => editSpec(index, "value", e.target.value)}
                        />
                        {isModified && (
                          <button
                            type="button"
                            className="product-desc-editor__revert-btn"
                            onClick={() => editSpec(index, "value", origSpec.value)}
                            title={`Revert to web value: ${origSpec.value}`}
                          >
                            <RotateCcw size={11} />
                            <span>Web: {origSpec.value}</span>
                          </button>
                        )}
                      </div>

                      {/* Delete */}
                      <button
                        type="button"
                        className="product-desc-editor__delete-btn"
                        onClick={() => removeSpec(index)}
                        title="Remove specification"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  );
                })}

                {!specifications.length && (
                  <div className="product-desc-editor__empty">
                    <Info size={16} />
                    <span>No specifications configured. Click "Add Specification" or choose a preset below.</span>
                  </div>
                )}
              </div>

              {/* Quick Specification Presets */}
              <div className="product-desc-editor__presets">
                <span className="product-desc-editor__presets-title">Quick Add:</span>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addSpec("Colour", "Black")}
                >
                  🎨 Colour
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addSpec("Warranty", "6 Months Seller Warranty")}
                >
                  🛡️ Warranty
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addSpec("Package Includes", "Device, Charging Cable, Manual")}
                >
                  📦 In The Box
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addSpec("Condition", "Brand New 100% Genuine")}
                >
                  💎 Condition
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preset-pill"
                  onClick={() => addSpec("Delivery", "Fast Island-wide Delivery")}
                >
                  🚚 Delivery
                </button>
              </div>
            </section>

            {/* Additional Customer Trust & Package Section */}
            <section className="product-desc-editor__card">
              <header className="product-desc-editor__card-header">
                <div>
                  <strong>🛡️ Customer Assurance & Box Contents</strong>
                  <p>Boost buyer trust by adding warranty terms, delivery speed, or accessories.</p>
                </div>
              </header>

              <div className="product-desc-editor__identity-grid">
                <div className="product-desc-editor__field">
                  <label>
                    <span>Warranty Terms</span>
                    <input
                      value={productInfo.warranty || ""}
                      onChange={(e) => updateField("warranty", e.target.value)}
                      placeholder="e.g. 6 Months Checking & Replacement Warranty"
                    />
                  </label>
                </div>

                <div className="product-desc-editor__field">
                  <label>
                    <span>Package Includes (In the Box)</span>
                    <input
                      value={productInfo.package_contents || ""}
                      onChange={(e) => updateField("package_contents", e.target.value)}
                      placeholder="e.g. 1x Earbuds, 1x Charging Case, 1x Type-C Cable"
                    />
                  </label>
                </div>

                <div className="product-desc-editor__field">
                  <label>
                    <span>Delivery & Shipping Note</span>
                    <input
                      value={productInfo.delivery_note || ""}
                      onChange={(e) => updateField("delivery_note", e.target.value)}
                      placeholder="e.g. Cash on Delivery available islandwide within 2-3 days"
                    />
                  </label>
                </div>
              </div>
            </section>
          </div>
        )}

        {/* =========================================================================
            TAB 2: INTERNET DISCOVERED DETAILS (Reference Inspector)
            ========================================================================= */}
        {activeTab === "internet_reference" && (
          <div className="product-desc-editor__reference-view">
            <div className="product-desc-editor__ref-banner">
              <Globe size={18} />
              <div>
                <strong>Raw Web Reference Data</strong>
                <p>These are the exact details discovered from web research. You can compare them against your stock in the Customize tab.</p>
              </div>
            </div>

            <div className="product-desc-editor__ref-grid">
              <div className="product-desc-editor__ref-card">
                <h4>🏷️ Discovered Identity</h4>
                <dl>
                  <dt>Product Name:</dt>
                  <dd>{original.product_name || "—"}</dd>
                  <dt>Brand:</dt>
                  <dd>{original.brand || "Unknown"}</dd>
                  <dt>Model:</dt>
                  <dd>{original.model || "Unknown"}</dd>
                  <dt>Category:</dt>
                  <dd>{original.category || "General"}</dd>
                </dl>
              </div>

              <div className="product-desc-editor__ref-card">
                <h4>⭐ Discovered Highlights</h4>
                {original.highlights?.length ? (
                  <ul>
                    {original.highlights.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No highlights returned from web reference.</p>
                )}
              </div>
            </div>

            <div className="product-desc-editor__ref-card" style={{ marginTop: "14px" }}>
              <h4>⚙️ Discovered Technical Specifications</h4>
              {original.specifications?.length ? (
                <div className="product-desc-editor__ref-specs">
                  {original.specifications.map((s, i) => (
                    <div key={i} className="product-desc-editor__ref-spec-item">
                      <strong>{s.name}:</strong>
                      <span>{s.value || "—"}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p>No verified specifications were discovered.</p>
              )}
            </div>

            {productInfo.missing_information?.length > 0 && (
              <div className="product-desc-editor__missing-info">
                <AlertCircle size={15} />
                <div>
                  <strong>Information Still Unconfirmed:</strong>
                  <span>{productInfo.missing_information.join(", ")}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* =========================================================================
            TAB 3: LIVE CUSTOMER PREVIEW & EXPORT (Storefront Look & Feel)
            ========================================================================= */}
        {activeTab === "preview" && (
          <div className="product-desc-editor__preview-view">
            {/* Toolbar for preview styling & presets */}
            <div className="product-desc-editor__preview-bar">
              <div className="product-desc-editor__preset-selector">
                <span className="product-desc-editor__preset-label">Description Style:</span>
                <button
                  type="button"
                  className={`product-desc-editor__style-btn ${stylePreset === "rich_icons" ? "is-active" : ""}`}
                  onClick={() => {
                    setStylePreset("rich_icons");
                    setIsManualEdit(false);
                  }}
                >
                  ✨ Eye-Catching with Icons (Best)
                </button>
                <button
                  type="button"
                  className={`product-desc-editor__style-btn ${stylePreset === "minimal" ? "is-active" : ""}`}
                  onClick={() => {
                    setStylePreset("minimal");
                    setIsManualEdit(false);
                  }}
                >
                  ⚡ Clean Minimal
                </button>
                <button
                  type="button"
                  className={`product-desc-editor__style-btn ${stylePreset === "spec_sheet" ? "is-active" : ""}`}
                  onClick={() => {
                    setStylePreset("spec_sheet");
                    setIsManualEdit(false);
                  }}
                >
                  📋 Spec Sheet
                </button>
              </div>

              <div className="product-desc-editor__preview-actions">
                <button
                  type="button"
                  className="product-desc-editor__preview-action-btn"
                  onClick={() => {
                    if (!isManualEdit) {
                      setManualDescription(generatedText);
                    }
                    setIsManualEdit(!isManualEdit);
                  }}
                >
                  <Pencil size={13} />
                  <span>{isManualEdit ? "Switch to Auto-Format" : "Edit Text Directly"}</span>
                </button>
                <button
                  type="button"
                  className="product-desc-editor__preview-action-btn"
                  onClick={handleCopy}
                >
                  {isCopied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  <span>{isCopied ? "Copied!" : "Copy Text"}</span>
                </button>
              </div>
            </div>

            {/* Storefront Customer Card Simulation */}
            <div className="product-desc-editor__preview-card">
              <div className="product-desc-editor__preview-header">
                <div className="product-desc-editor__preview-store-badge">
                  <Eye size={14} />
                  <span>Customer Storefront & Chat View</span>
                </div>
                <small>{finalDescription.length} / 4000 characters</small>
              </div>

              <div className="product-desc-editor__preview-body">
                {isManualEdit ? (
                  <textarea
                    className="product-desc-editor__manual-textarea"
                    rows="14"
                    value={manualDescription}
                    onChange={(e) => setManualDescription(e.target.value)}
                    placeholder="Directly edit the final customer description text..."
                  />
                ) : (
                  <div className="product-desc-editor__formatted-output">
                    {finalDescription || "No product information configured yet."}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* =========================================================================
            PERSISTENT BOTTOM PREVIEW & ACTION FOOTER
            ========================================================================= */}
        {activeTab !== "preview" && (
          <div className="product-desc-editor__quick-preview-strip">
            <div className="product-desc-editor__quick-preview-text">
              <strong>✨ Ready for Customer View:</strong>
              <span>
                {specifications.filter((s) => s.enabled).length} specifications • {highlights.filter((h) => h.enabled).length} highlights with icons
              </span>
            </div>
            <button
              type="button"
              className="product-desc-editor__view-preview-btn"
              onClick={() => setActiveTab("preview")}
            >
              <Eye size={13} />
              <span>Preview Customer Description</span>
            </button>
          </div>
        )}

        <footer className="product-desc-editor__footer">
          <button
            type="button"
            className="product-desc-editor__cancel-btn"
            onClick={onCancel}
          >
            Back to Product
          </button>
          <button
            type="button"
            className="product-desc-editor__apply-btn"
            onClick={() => onApply(finalDescription)}
          >
            <Sparkles size={16} />
            <span>Save & Use Beautiful Description</span>
          </button>
        </footer>
      </div>
    </ModalShell>
  );
}

export default ProductDescriptionEditor;
