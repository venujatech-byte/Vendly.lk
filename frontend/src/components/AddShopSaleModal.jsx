import { Minus, Package, Plus, Search, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getProducts } from "../services/productService";
import { createShopSale } from "../services/shopSaleService";
import "./ShopSales.css";

export default function AddShopSaleModal({ isOpen, businessId, onClose, onCreated }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedProductId, setSelectedProductId] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [items, setItems] = useState([]);
  const [customerName, setCustomerName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("cash");
  const [discount, setDiscount] = useState(0);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen || !businessId) return;
    getProducts(businessId).then(setProducts).catch((requestError) => setError(requestError.message));
  }, [isOpen, businessId]);
  const matches = useMemo(() => products.filter((product) => `${product.name} ${product.sku} ${product.barcode}`.toLowerCase().includes(search.toLowerCase())).slice(0, 8), [products, search]);
  const selectedProduct = products.find((product) => product.id === selectedProductId);
  const selectedVariant = selectedProduct?.sizes?.find((variant) => variant.id === selectedVariantId);
  const subtotal = items.reduce((sum, item) => sum + item.sellingPrice * item.quantity, 0);
  const total = Math.max(0, subtotal - Number(discount || 0));
  if (!isOpen) return null;

  function chooseProduct(product) {
    setSelectedProductId(product.id);
    setSelectedVariantId(product.sizes?.[0]?.id ?? "");
    setQuantity(1);
  }
  function addItem() {
    if (!selectedVariant) return setError("Choose an available product option.");
    if (quantity > selectedVariant.stockAvailable) return setError(`Only ${selectedVariant.stockAvailable} unit(s) are available.`);
    setItems((current) => {
      const existing = current.find((item) => item.variantId === selectedVariant.id);
      if (existing) return current.map((item) => item.variantId === selectedVariant.id ? { ...item, quantity: item.quantity + quantity } : item);
      return [...current, { variantId: selectedVariant.id, name: selectedProduct.name, size: selectedVariant.size, sku: selectedVariant.sku, sellingPrice: selectedVariant.sellingPrice, imageUrl: selectedVariant.imageUrl || selectedProduct.images?.[0], quantity }];
    });
    setSelectedProductId(""); setSelectedVariantId(""); setSearch(""); setError("");
  }
  async function submit() {
    if (!items.length) return setError("Add at least one product to this sale.");
    setSaving(true); setError("");
    try {
      const sale = await createShopSale(businessId, { items: items.map(({ variantId, quantity: itemQuantity }) => ({ variantId, quantity: itemQuantity })), customerName, phoneNumber, paymentMethod, discountAmount: Number(discount || 0), note });
      onCreated(sale); onClose();
    } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }

  return <div className="shop-modal-backdrop"><div className="shop-sale-modal">
    <header><div><h2>Add shop sale</h2><p>Record a sale made at your physical shop.</p></div><button type="button" onClick={onClose}><X size={21}/></button></header>
    <div className="shop-sale-modal__body">
      <section className="shop-sale-modal__catalog"><h3>Add items</h3>
        <label className="shop-sale-modal__search"><Search size={17}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search product, SKU or barcode..."/></label>
        {search && !selectedProduct && <div className="shop-sale-modal__results">{matches.map((product) => <button key={product.id} type="button" onClick={() => chooseProduct(product)}>{product.images?.[0] ? <img src={product.images[0]} alt=""/> : <Package size={25}/>}<span><strong>{product.name}</strong><small>{product.stock} available</small></span></button>)}</div>}
        {selectedProduct && <div className="shop-sale-modal__selection"><div><strong>{selectedProduct.name}</strong><button type="button" onClick={() => setSelectedProductId("")}>Change</button></div>
          <select value={selectedVariantId} onChange={(e) => setSelectedVariantId(e.target.value)}>{selectedProduct.sizes.map((variant) => <option key={variant.id} value={variant.id}>{variant.size || "Standard option"} · {variant.stockAvailable} available · LKR {variant.sellingPrice.toLocaleString()}</option>)}</select>
          <div className="shop-sale-modal__quantity"><button type="button" onClick={() => setQuantity(Math.max(1, quantity - 1))}><Minus size={15}/></button><span>{quantity}</span><button type="button" onClick={() => setQuantity(quantity + 1)}><Plus size={15}/></button><button className="primary" type="button" onClick={addItem}>Add to sale</button></div>
        </div>}
        <h3>Sale items ({items.length})</h3><div className="shop-sale-modal__items">{items.map((item) => <div key={item.variantId}>{item.imageUrl ? <img src={item.imageUrl} alt=""/> : <Package/>}<span><strong>{item.name}</strong><small>{item.size || "Standard"} · {item.sku}</small></span><span>{item.quantity} × LKR {item.sellingPrice.toLocaleString()}</span><button type="button" onClick={() => setItems((current) => current.filter((record) => record.variantId !== item.variantId))}><Trash2 size={16}/></button></div>)}{!items.length && <p>No items added yet.</p>}</div>
      </section>
      <aside className="shop-sale-modal__summary"><h3>Sale details</h3><div className="shop-sale-modal__two"><label>Customer name <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Optional"/></label><label>Phone <input value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} placeholder="Optional"/></label></div>
        <label>Payment method<select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}><option value="cash">Cash</option><option value="card">Card</option><option value="bank-transfer">Bank transfer</option></select></label>
        <label>Private note<textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional sale note..."/></label>
        <div className="shop-sale-modal__totals"><p><span>Items subtotal</span><strong>LKR {subtotal.toLocaleString()}</strong></p><label><span>Discount</span><input type="number" min="0" max={subtotal} value={discount} onChange={(e) => setDiscount(e.target.value)}/></label><p className="total"><span>Total</span><strong>LKR {total.toLocaleString()}</strong></p></div>
      </aside>
    </div>
    {error && <p className="shop-modal__error">{error}</p>}
    <footer><button type="button" onClick={onClose}>Cancel</button><button className="primary" type="button" onClick={submit} disabled={saving}>{saving ? "Saving sale..." : "Complete sale"}</button></footer>
  </div></div>;
}
