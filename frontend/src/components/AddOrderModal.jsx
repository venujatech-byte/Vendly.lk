import { useEffect, useMemo, useState } from "react";
import { Minus, Package, Plus, Search, Trash2, X } from "lucide-react";

import { createCustomer, getCustomers } from "../services/customerService";
import { getCouriers } from "../services/courierService";
import { createOrder } from "../services/orderService";
import { getProducts } from "../services/productService";
import ModalShell from "./ModalShell";
import OrderReceipt from "./OrderReceipt";
import "./AddOrderModal.css";

const emptyAddress = { line1: "", line2: "", city: "", district: "", postalCode: "" };
const emptyCustomer = { name: "", phoneNumber: "", secondaryPhoneNumber: "", email: "", address: { ...emptyAddress } };

function money(amount) {
  return `LKR ${Number(amount || 0).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function AddOrderModal({ isOpen, businessId, business, onClose, onCreated }) {
  const [customers, setCustomers] = useState([]);
  const [products, setProducts] = useState([]);
  const [couriers, setCouriers] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [customer, setCustomer] = useState(emptyCustomer);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [source, setSource] = useState("dashboard");
  const [privateNote, setPrivateNote] = useState("");
  const [courierId, setCourierId] = useState("");
  const [discountAmount, setDiscountAmount] = useState("0");
  const [paymentMethod, setPaymentMethod] = useState("cod");
  const [depositAmount, setDepositAmount] = useState("0");
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [receiptOrder, setReceiptOrder] = useState(null);

  useEffect(() => {
    if (!isOpen || !businessId) return undefined;
    let current = true;
    setIsLoading(true);
    setCustomerId(""); setCustomer(emptyCustomer); setItems([]); setSearch("");
    setCategoryId(""); setSelectedProductId(""); setSelectedVariantId("");
    setSource("dashboard"); setPrivateNote(""); setCourierId("");
    setDiscountAmount("0"); setPaymentMethod("cod"); setDepositAmount("0");
    setIsCheckoutOpen(false); setReceiptOrder(null); setErrorMessage("");

    Promise.all([getCustomers(businessId), getProducts(businessId), getCouriers(businessId)])
      .then(([customerRows, productRows, courierRows]) => {
        if (!current) return;
        setCustomers(customerRows);
        setProducts(productRows);
        const activeCouriers = courierRows.filter((courier) => courier.status === "active");
        setCouriers(activeCouriers);
        setCourierId(activeCouriers[0]?.id || "");
      })
      .catch((error) => current && setErrorMessage(error.message))
      .finally(() => current && setIsLoading(false));
    return () => { current = false; };
  }, [businessId, isOpen]);

  const variants = useMemo(() => products.flatMap((product) =>
    (product.sizes || []).map((variant) => ({
      ...variant,
      productId: product.id,
      productName: product.name,
      colour: product.colourName || product.colour || "",
      sellingPrice: variant.sellingPrice ?? product.sellingPrice,
      weightKg: product.weightKg,
      image: product.images?.[0] || "",
    }))), [products]);

  const categories = useMemo(() => Array.from(new Map(products.filter((product) => product.categoryId)
    .map((product) => [product.categoryId, product.categoryName || product.category]))), [products]);
  const matchingProducts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return products.filter((product) => !categoryId || product.categoryId === categoryId)
      .filter((product) => !query || [product.name, product.sku, product.barcode, ...(product.sizes || []).flatMap((variant) => [variant.sku, variant.barcode])]
        .some((value) => String(value || "").toLowerCase().includes(query))).slice(0, 5);
  }, [products, search, categoryId]);

  const selectedProduct = products.find((product) => product.id === selectedProductId);
  const selectedVariant = variants.find((variant) => variant.id === selectedVariantId);
  const subtotal = items.reduce((sum, item) => sum + item.sellingPrice * item.quantity, 0);
  const discount = Math.max(0, Number(discountAmount) || 0);
  const totalWeightKg = items.reduce((sum, item) => sum + item.weightKg * item.quantity, 0);
  const selectedCourier = couriers.find((courier) => courier.id === courierId) || couriers[0];
  const extraKg = Math.max(0, Math.ceil(totalWeightKg) - 1);
  const districtKey = customer.address.district.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const deliveryFee = selectedCourier
    ? (selectedCourier.firstKgPriceMinor || 0) / 100 + extraKg * (selectedCourier.extraKgPriceMinor || 0) / 100
      + ((selectedCourier.districtSurchargesMinor || {})[districtKey] || 0) / 100
    : 0;
  const estimatedTotal = Math.max(0, subtotal - discount + deliveryFee);

  function chooseCustomer(event) {
    const id = event.target.value;
    setCustomerId(id);
    const selected = customers.find((row) => row.id === id);
    if (!selected) return;
    setCustomer({
      name: selected.name || "",
      phoneNumber: selected.phoneNumber || selected.normalizedPhone || "",
      secondaryPhoneNumber: selected.secondaryPhoneNumber || selected.normalizedSecondaryPhone || "",
      email: selected.email || "",
      address: { ...emptyAddress, ...(selected.defaultAddress || {}) },
    });
  }

  function startNewCustomer() {
    setCustomerId("");
    setCustomer(emptyCustomer);
  }

  function updateCustomer(event) {
    const { name, value } = event.target;
    if (name.startsWith("address.")) {
      const field = name.slice(8);
      setCustomer((current) => ({ ...current, address: { ...current.address, [field]: value } }));
    } else setCustomer((current) => ({ ...current, [name]: value }));
  }

  function chooseProduct(product) {
    const first = variants.find((variant) => variant.productId === product.id && variant.stock > 0);
    setSelectedProductId(product.id);
    setSelectedVariantId(first?.id || "");
    setQuantity(1);
  }

  function addItem() {
    if (!selectedVariant) return setErrorMessage("Choose an available product variant.");
    const amount = Math.max(1, Number(quantity) || 1);
    const existing = items.find((item) => item.variantId === selectedVariant.id);
    if ((existing?.quantity || 0) + amount > selectedVariant.stock) return setErrorMessage(`Only ${selectedVariant.stock} unit(s) are available.`);
    setItems((current) => existing
      ? current.map((item) => item.variantId === selectedVariant.id ? { ...item, quantity: item.quantity + amount } : item)
      : [...current, { ...selectedVariant, variantId: selectedVariant.id, quantity: amount }]);
    setErrorMessage("");
  }

  function changeItemQuantity(variantId, amount) {
    setItems((current) => current.map((item) => item.variantId === variantId
      ? { ...item, quantity: Math.max(1, Math.min(item.stock, item.quantity + amount)) }
      : item));
  }

  function openCheckout(event) {
    event.preventDefault();
    if (!customer.name || !customer.phoneNumber || !customer.address.line1 || !customer.address.city || !customer.address.district) return setErrorMessage("Complete the required customer and delivery fields.");
    if (!items.length) return setErrorMessage("Add at least one item to the order.");
    if (!couriers.length) return setErrorMessage("Add an active courier before creating an order.");
    setErrorMessage("");
    setIsCheckoutOpen(true);
  }

  async function createConfirmedOrder() {
    setIsSaving(true);
    setErrorMessage("");
    try {
      let finalCustomerId = customerId;
      if (!finalCustomerId) {
        const created = await createCustomer(businessId, customer);
        finalCustomerId = created.id;
      }
      const order = await createOrder(businessId, {
        customerId: finalCustomerId,
        secondaryPhoneNumber: customer.secondaryPhoneNumber,
        items: items.map((item) => ({ variantId: item.variantId, quantity: item.quantity })),
        deliveryAddress: customer.address,
        courierId,
        paymentMethod,
        depositAmount: paymentMethod === "deposit" ? depositAmount : 0,
        source,
        discountAmount,
        privateNote,
      });
      onCreated(order);
      setReceiptOrder(order);
      setIsCheckoutOpen(false);
    } catch (error) {
      setErrorMessage(error.message);
      setIsCheckoutOpen(false);
    } finally { setIsSaving(false); }
  }

  return <>
    <ModalShell isOpen={isOpen && !isCheckoutOpen && !receiptOrder} title="Add Order" onClose={onClose} size="wide">
      {isLoading ? <div className="order-dialog__loading"><Package /><span>Loading order data...</span></div> :
        <form className="order-dialog" onSubmit={openCheckout}>
          <section className="order-dialog__customer">
            <header><strong>CUSTOMER DETAILS</strong><button type="button" onClick={startNewCustomer}><Plus size={14} /> New Customer</button></header>
            <label className="order-dialog__search"><Search size={15} /><select value={customerId} onChange={chooseCustomer}><option value="">Search or choose customer...</option>{customers.map((row) => <option key={row.id} value={row.id}>{row.name} — {row.normalizedPhone}</option>)}</select></label>
            <div className="order-dialog__customer-fields">
              <label>Name <em>*</em><input name="name" value={customer.name} onChange={updateCustomer} required /></label>
              <label>1st Phone No. <em>*</em><input name="phoneNumber" value={customer.phoneNumber} onChange={updateCustomer} required /></label>
              <label>Email Address<input name="email" type="email" value={customer.email} onChange={updateCustomer} /></label>
              <label>2nd Phone No.<input name="secondaryPhoneNumber" value={customer.secondaryPhoneNumber} onChange={updateCustomer} /></label>
              <label className="order-dialog__wide">Address <em>*</em><textarea name="address.line1" value={customer.address.line1} onChange={updateCustomer} required /></label>
              <label>City <em>*</em><input name="address.city" value={customer.address.city} onChange={updateCustomer} required /></label>
              <label>District <em>*</em><input name="address.district" value={customer.address.district} onChange={updateCustomer} required /></label>
            </div>
            <div className="order-dialog__details">
              <label>Source<select value={source} onChange={(event) => setSource(event.target.value)}><option value="dashboard">Select Source</option><option value="phone">Phone</option><option value="whatsapp">WhatsApp</option><option value="facebook">Facebook</option><option value="chatbot">Chatbot</option></select></label>
              <label>Note<input value={privateNote} onChange={(event) => setPrivateNote(event.target.value)} placeholder="Add internal notes..." /></label>
            </div>
          </section>

          <section className="order-dialog__items">
            <strong>ADD ITEM</strong>
            <div className="order-dialog__filters"><label className="order-dialog__search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product..." /></label><select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Category</option>{categories.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></div>
            <div className="order-dialog__results">
              {!search && !categoryId ? <p>Search for a product above.<br />Matching items will show here.</p> : matchingProducts.map((product) => <button className={selectedProductId === product.id ? "is-selected" : ""} type="button" key={product.id} onClick={() => chooseProduct(product)}>{product.images?.[0] ? <img src={product.images[0]} alt="" /> : <Package size={20} />}<span><strong>{product.name}</strong><small>{product.stock} in stock</small></span></button>)}
            </div>
            <div className="order-dialog__picker"><select value={selectedVariantId} onChange={(event) => setSelectedVariantId(event.target.value)}><option value="">Variants (e.g., Size L, Red)</option>{(selectedProduct?.sizes || []).map((variant) => <option key={variant.id} value={variant.id} disabled={!variant.stock}>{variant.size || variant.sku} — {variant.stock} available</option>)}</select><Quantity value={quantity} onMinus={() => setQuantity(Math.max(1, quantity - 1))} onPlus={() => setQuantity(quantity + 1)} /><button type="button" onClick={addItem}>Add</button></div>
            <hr />
            <strong>ORDER ITEMS</strong>
            <div className="order-dialog__table"><div className="order-dialog__table-head"><span>ITEM</span><span>QTY</span><span>PRICE</span><span /></div>{items.map((item) => <div className="order-dialog__table-row" key={item.variantId}><div>{item.image && <img src={item.image} alt="" />}<span><strong>{item.productName}</strong><small>{item.size ? `Variant: ${item.size}` : item.sku}</small></span></div><Quantity value={item.quantity} onMinus={() => changeItemQuantity(item.variantId, -1)} onPlus={() => changeItemQuantity(item.variantId, 1)} /><strong>{money(item.sellingPrice * item.quantity)}</strong><button type="button" onClick={() => setItems((current) => current.filter((row) => row.variantId !== item.variantId))}><Trash2 size={14} /></button></div>)}</div>
            <div className="order-dialog__subtotal"><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
          </section>
          {errorMessage && <p className="order-dialog__error">{errorMessage}</p>}
          <footer className="order-dialog__footer"><button type="button" onClick={onClose}>Cancel</button><button className="order-dialog__checkout" type="submit">Checkout</button></footer>
        </form>}
    </ModalShell>

    {isOpen && isCheckoutOpen && <div className="order-summary__backdrop" role="presentation">
      <section className="order-summary" role="dialog" aria-modal="true" aria-labelledby="order-summary-title">
        <header><h2 id="order-summary-title">Order Summary</h2><button type="button" onClick={() => setIsCheckoutOpen(false)}><X size={20} /></button></header>
        <div className="order-summary__body">
          <div><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
          <label><span>Discount</span><span className="order-summary__discount">− <input type="number" min="0" max={subtotal} value={discountAmount} onChange={(event) => setDiscountAmount(event.target.value)} /></span></label>
          <div><span>Delivery fee</span><strong>{money(deliveryFee)}</strong></div>
          <div className="order-summary__total"><strong>Estimated Total</strong><strong>{money(estimatedTotal)}</strong></div>
          <fieldset><legend>Payment</legend><label><input type="radio" name="payment" checked={paymentMethod === "cod"} onChange={() => setPaymentMethod("cod")} /> COD</label><label><input type="radio" name="payment" checked={paymentMethod === "deposit"} onChange={() => setPaymentMethod("deposit")} /> Deposit</label>{paymentMethod === "deposit" && <label className="order-summary__deposit">Deposit amount<input type="number" min="0" max={estimatedTotal} value={depositAmount} onChange={(event) => setDepositAmount(event.target.value)} /></label>}</fieldset>
          <label className="order-summary__courier">Courier<select value={courierId} onChange={(event) => setCourierId(event.target.value)}>{couriers.map((courier) => <option key={courier.id} value={courier.id}>{courier.name}</option>)}</select></label>
        </div>
        <footer><button type="button" onClick={() => setIsCheckoutOpen(false)}>Cancel</button><button type="button" onClick={createConfirmedOrder} disabled={isSaving}>{isSaving ? "Creating..." : "Create order"}</button></footer>
      </section>
    </div>}
    {isOpen && receiptOrder && <OrderReceipt business={business} order={receiptOrder} closeLabel="Return to Orders" onClose={onClose} />}
  </>;
}

function Quantity({ value, onMinus, onPlus }) {
  return <span className="order-dialog__quantity"><button type="button" onClick={onMinus}><Minus size={14} /></button><b>{value}</b><button type="button" onClick={onPlus}><Plus size={14} /></button></span>;
}

export default AddOrderModal;
