import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  Info,
  Minus,
  Package,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import { createCustomer, getCustomers } from "../services/customerService";
import { getCouriers, recommendCouriers } from "../services/courierService";
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
  const [variantQuantities, setVariantQuantities] = useState({});
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [source, setSource] = useState("dashboard");
  const [privateNote, setPrivateNote] = useState("");
  const [courierId, setCourierId] = useState("");
  const [isCourierPickerOpen, setIsCourierPickerOpen] = useState(false);
  const [courierQuotes, setCourierQuotes] = useState([]);
  const [isLoadingQuotes, setIsLoadingQuotes] = useState(false);
  const [discountAmount, setDiscountAmount] = useState("0");
  const [paymentMethod, setPaymentMethod] = useState("cod");
  const [depositAmount, setDepositAmount] = useState("0");
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [receiptOrder, setReceiptOrder] = useState(null);
  const courierPickerRef = useRef(null);

  useEffect(() => {
    if (!isOpen || !businessId) return undefined;
    let current = true;
    setIsLoading(true);
    setCustomerId(""); setCustomer(emptyCustomer); setItems([]); setSearch("");
    setCategoryId(""); setSelectedProductId(""); setVariantQuantities({});
    setSource("dashboard"); setPrivateNote(""); setCourierId(""); setCourierQuotes([]);
    setDiscountAmount("0"); setPaymentMethod("cod"); setDepositAmount("0");
    setIsCheckoutOpen(false); setReceiptOrder(null); setErrorMessage("");

    Promise.all([getCustomers(businessId), getProducts(businessId), getCouriers(businessId)])
      .then(([customerRows, productRows, courierRows]) => {
        if (!current) return;
        setCustomers(customerRows);
        setProducts(productRows);
        setCouriers(courierRows.filter((courier) => courier.status === "active"));
      })
      .catch((error) => current && setErrorMessage(error.message))
      .finally(() => current && setIsLoading(false));
    return () => { current = false; };
  }, [businessId, isOpen]);

  // Close the courier popover on an outside click.
  useEffect(() => {
    if (!isCourierPickerOpen) return undefined;
    function handleClick(event) {
      if (courierPickerRef.current && !courierPickerRef.current.contains(event.target)) {
        setIsCourierPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isCourierPickerOpen]);

  const categories = useMemo(() => Array.from(new Map(products.filter((product) => product.categoryId)
    .map((product) => [product.categoryId, product.categoryName || product.category]))), [products]);
  const matchingProducts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return products.filter((product) => !categoryId || product.categoryId === categoryId)
      .filter((product) => !query || [product.name, product.sku, product.barcode, ...(product.sizes || []).flatMap((variant) => [variant.sku, variant.barcode])]
        .some((value) => String(value || "").toLowerCase().includes(query))).slice(0, 8);
  }, [products, search, categoryId]);

  const selectedProduct = products.find((product) => product.id === selectedProductId);
  const subtotal = items.reduce((sum, item) => sum + item.sellingPrice * item.quantity, 0);
  const discount = Math.min(Math.max(0, Number(discountAmount) || 0), subtotal);
  const totalWeightGrams = items.reduce((sum, item) => sum + (item.weightKg || 0) * 1000 * item.quantity, 0);
  const matrixTotal = Object.entries(variantQuantities).reduce((sum, [variantId, quantity]) => {
    const variant = selectedProduct?.sizes.find((row) => row.id === variantId);
    return sum + (variant ? variant.sellingPrice * quantity : 0);
  }, 0);
  const matrixUnitCount = Object.values(variantQuantities).reduce((sum, quantity) => sum + quantity, 0);

  // Re-quote couriers whenever the weight or district that drives the fee
  // changes, so the chip always shows a live, backend-calculated price.
  useEffect(() => {
    const district = customer.address.district.trim();
    if (!businessId || !district || totalWeightGrams <= 0) {
      setCourierQuotes([]);
      return undefined;
    }

    let current = true;
    setIsLoadingQuotes(true);
    const timeout = setTimeout(() => {
      recommendCouriers(businessId, totalWeightGrams, district)
        .then((recommendations) => {
          if (!current) return;
          setCourierQuotes(recommendations);
          if (!recommendations.some((row) => row.courier.id === courierId)) {
            setCourierId(recommendations[0]?.courier.id || "");
          }
        })
        .catch(() => current && setCourierQuotes([]))
        .finally(() => current && setIsLoadingQuotes(false));
    }, 300);

    return () => { current = false; clearTimeout(timeout); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId, totalWeightGrams, customer.address.district]);

  const selectedQuote = courierQuotes.find((row) => row.courier.id === courierId);

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
    setSelectedProductId(product.id);
    setVariantQuantities({});
  }

  function changeVariantQuantity(variant, delta) {
    setVariantQuantities((current) => {
      const next = Math.max(0, Math.min(variant.stock, (current[variant.id] || 0) + delta));
      const updated = { ...current, [variant.id]: next };
      if (next === 0) delete updated[variant.id];
      return updated;
    });
  }

  function addMatrixToOrder() {
    if (!selectedProduct || matrixUnitCount === 0) return;
    setItems((current) => {
      let next = current;
      for (const variant of selectedProduct.sizes) {
        const quantity = variantQuantities[variant.id];
        if (!quantity) continue;
        const existing = next.find((item) => item.variantId === variant.id);
        const row = {
          ...variant,
          variantId: variant.id,
          productName: selectedProduct.name,
          image: selectedProduct.images?.[0] || "",
          weightKg: selectedProduct.weightKg,
        };
        next = existing
          ? next.map((item) => item.variantId === variant.id ? { ...item, quantity: item.quantity + quantity } : item)
          : [...next, { ...row, quantity }];
      }
      return next;
    });
    setSelectedProductId("");
    setVariantQuantities({});
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
    if (!courierId) return setErrorMessage("Choose a courier before checking out.");
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

  const deliveryFee = (selectedQuote?.deliveryFeeMinor ?? 0) / 100;
  const total = Math.max(0, subtotal - discount + deliveryFee);
  const paidAmount = paymentMethod === "paid" ? total : paymentMethod === "deposit" ? Math.min(Math.max(0, Number(depositAmount) || 0), total) : 0;
  const balanceDue = Math.max(0, total - paidAmount);

  return <>
    <ModalShell isOpen={isOpen && !isCheckoutOpen && !receiptOrder} title="Add Order" onClose={onClose} size="full">
      {isLoading ? <div className="order-dialog__loading"><Package /><span>Loading order data...</span></div> :
        <form className="order-dialog order-dialog--fit" onSubmit={openCheckout}>
          <div className="order-dialog__body">
            <section className="order-dialog__customer">
              <header><strong>CUSTOMER</strong><button type="button" onClick={startNewCustomer}><Plus size={14} /> New</button></header>
              <label className="order-dialog__search"><Search size={15} /><select value={customerId} onChange={chooseCustomer}><option value="">Search or choose customer...</option>{customers.map((row) => <option key={row.id} value={row.id}>{row.name} — {row.normalizedPhone}</option>)}</select></label>
              <div className="order-dialog__customer-fields">
                <label>Name <em>*</em><input name="name" value={customer.name} onChange={updateCustomer} required /></label>
                <label>Email Address<input name="email" type="email" value={customer.email} onChange={updateCustomer} /></label>
                <label>1st Phone No. <em>*</em><input name="phoneNumber" value={customer.phoneNumber} onChange={updateCustomer} placeholder="07XXXXXXXX" required /></label>
                <label>2nd Phone No.<input name="secondaryPhoneNumber" value={customer.secondaryPhoneNumber} onChange={updateCustomer} placeholder="Optional" /></label>
                <label className="order-dialog__wide">Address <em>*</em><textarea name="address.line1" value={customer.address.line1} onChange={updateCustomer} required /></label>
                <label>City <em>*</em><input name="address.city" value={customer.address.city} onChange={updateCustomer} required /></label>
                <label>District <em>*</em><input name="address.district" value={customer.address.district} onChange={updateCustomer} required /></label>
              </div>

              <div className="order-dialog__courier" ref={courierPickerRef}>
                <span className="order-dialog__section-label">Courier</span>
                <button
                  type="button"
                  className="order-dialog__courier-chip"
                  onClick={() => setIsCourierPickerOpen((open) => !open)}
                  disabled={courierQuotes.length === 0}
                >
                  <span className="order-dialog__courier-dot" />
                  <span className="order-dialog__courier-name">
                    {selectedQuote
                      ? selectedQuote.courier.name
                      : couriers.length === 0
                        ? "No couriers configured"
                        : isLoadingQuotes
                          ? "Fetching rates…"
                          : "Add items & address for rates"}
                  </span>
                  {selectedQuote && <strong>{money(deliveryFee)}</strong>}
                  <ChevronDown size={14} />
                </button>

                {isCourierPickerOpen && courierQuotes.length > 0 && (
                  <div className="order-dialog__courier-popover">
                    {courierQuotes.map((quote, index) => (
                      <button
                        type="button"
                        key={quote.courier.id}
                        className={quote.courier.id === courierId ? "is-active" : ""}
                        onClick={() => { setCourierId(quote.courier.id); setIsCourierPickerOpen(false); }}
                      >
                        <span className="order-dialog__courier-radio" />
                        <span className="order-dialog__courier-info">
                          <strong>{quote.courier.name}</strong>
                          <small>{quote.courier.averageDeliveryDays ? `${quote.courier.averageDeliveryDays} day(s)` : ""}{index === 0 ? " · Recommended" : ""}</small>
                        </span>
                        <b>{money(quote.deliveryFeeMinor / 100)}</b>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <p className="order-dialog__hint"><Info size={13} /> District sets the courier surcharge.</p>
            </section>

            <section className="order-dialog__items">
              <strong>ADD ITEM</strong>
              <div className="order-dialog__filters"><label className="order-dialog__search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product..." /></label><select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Category</option>{categories.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></div>

              {!selectedProduct ? (
                <div className="order-dialog__results">
                  {!search && !categoryId ? <p>Search for a product above.<br />Matching items will show here.</p> : matchingProducts.map((product) => <button type="button" key={product.id} onClick={() => chooseProduct(product)}>{product.images?.[0] ? <img src={product.images[0]} alt="" /> : <Package size={20} />}<span><strong>{product.name}</strong><small>{product.sizes.length} sizes · {product.stock} in stock</small></span></button>)}
                </div>
              ) : (
                <div className="order-dialog__matrix">
                  <header>
                    <div className="order-dialog__matrix-thumb">{selectedProduct.images?.[0] ? <img src={selectedProduct.images[0]} alt="" /> : <Package size={18} />}</div>
                    <span><strong>{selectedProduct.name}{selectedProduct.colour ? ` · ${selectedProduct.colour}` : ""}</strong><small>{selectedProduct.sizes.length} sizes · {selectedProduct.stock} in stock</small></span>
                    <button type="button" onClick={() => { setSelectedProductId(""); setVariantQuantities({}); }}>Change</button>
                  </header>
                  <div className="order-dialog__matrix-head">
                    <span>Size</span><span>SKU / barcode</span><span>Stock</span><span>Price</span><span>Qty</span><span>Line total</span>
                  </div>
                  {selectedProduct.sizes.map((variant) => {
                    const quantity = variantQuantities[variant.id] || 0;
                    const soldOut = variant.stock <= 0;
                    return (
                      <div className={`order-dialog__matrix-row${soldOut ? " is-sold-out" : ""}${quantity > 0 ? " is-selected" : ""}`} key={variant.id}>
                        <span>{variant.size || "—"}</span>
                        <span><small className="mono">{variant.sku}</small>{variant.barcode && <small className="mono order-dialog__barcode">{variant.barcode}</small>}</span>
                        <span>{soldOut ? <em className="order-dialog__soldout-tag">Sold out</em> : variant.stock <= 5 ? <em className="order-dialog__low-tag">{variant.stock}</em> : variant.stock}</span>
                        <span>{money(variant.sellingPrice)}</span>
                        <span className="order-dialog__quantity"><button type="button" disabled={soldOut} onClick={() => changeVariantQuantity(variant, -1)}><Minus size={12} /></button><b>{quantity}</b><button type="button" disabled={soldOut || quantity >= variant.stock} onClick={() => changeVariantQuantity(variant, 1)}><Plus size={12} /></button></span>
                        <span>{quantity > 0 ? money(variant.sellingPrice * quantity) : "—"}</span>
                      </div>
                    );
                  })}
                  <footer>
                    <span>{matrixUnitCount > 0 ? `${matrixUnitCount} unit(s) selected · ${money(matrixTotal)}` : "Choose a size to add it"}</span>
                    <button type="button" className="order-dialog__add-item" disabled={matrixUnitCount === 0} onClick={addMatrixToOrder}>Add to order</button>
                  </footer>
                </div>
              )}

              <strong className="order-dialog__items-heading">ORDER ITEMS</strong>
              <div className="order-dialog__table">
                <div className="order-dialog__table-head"><span>ITEM</span><span>QTY</span><span>PRICE</span><span /></div>
                <div className="order-dialog__table-body">
                  {items.length === 0 && <p className="order-dialog__empty">No items added yet.</p>}
                  {items.map((item) => <div className="order-dialog__table-row" key={item.variantId}><div>{item.image && <img src={item.image} alt="" />}<span><strong>{item.productName}</strong><small>{item.size ? `Size ${item.size}` : item.sku}</small></span></div><span className="order-dialog__quantity"><button type="button" onClick={() => changeItemQuantity(item.variantId, -1)}><Minus size={14} /></button><b>{item.quantity}</b><button type="button" onClick={() => changeItemQuantity(item.variantId, 1)}><Plus size={14} /></button></span><strong>{money(item.sellingPrice * item.quantity)}</strong><button type="button" onClick={() => setItems((current) => current.filter((row) => row.variantId !== item.variantId))}><Trash2 size={14} /></button></div>)}
                </div>
              </div>
              <div className="order-dialog__subtotal"><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
            </section>
          </div>

          {errorMessage && <p className="order-dialog__error">{errorMessage}</p>}
          <footer className="order-dialog__footer">
            <div className="order-dialog__footer-total"><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
            <div className="order-dialog__footer-delivery"><span>Delivery</span><strong>{selectedQuote ? money(deliveryFee) : "Calculated at checkout"}</strong></div>
            <div className="order-dialog__footer-actions"><button type="button" onClick={onClose}>Cancel</button><button className="order-dialog__checkout" type="submit">Checkout</button></div>
          </footer>
        </form>}
    </ModalShell>

    {isOpen && isCheckoutOpen && <div className="order-summary__backdrop" role="presentation">
      <section className="order-summary" role="dialog" aria-modal="true" aria-labelledby="order-summary-title">
        <header><h2 id="order-summary-title">Order Summary</h2><button type="button" onClick={() => setIsCheckoutOpen(false)}><X size={20} /></button></header>
        <div className="order-summary__body">
          <div className="order-summary__recap">
            <div className="order-summary__recap-card">
              <strong>{customer.name}</strong>
              <small>{customer.phoneNumber}</small>
              <small>{[customer.address.line1, customer.address.city, customer.address.district].filter(Boolean).join(", ")}</small>
            </div>
            <div className="order-summary__recap-card">
              <strong>{selectedQuote?.courier.name || "No courier"}</strong>
              <small>{(totalWeightGrams / 1000).toFixed(2)} kg to {customer.address.district}</small>
              <small>{selectedQuote?.courier.averageDeliveryDays ? `${selectedQuote.courier.averageDeliveryDays} day(s)` : ""}</small>
            </div>
          </div>

          <div className="order-summary__items">
            {items.map((item) => (
              <div key={item.variantId} className="order-summary__item-row">
                <span><strong>{item.productName}{item.size ? ` · ${item.size}` : ""}</strong><small className="mono">{item.sku} · {item.quantity} × {money(item.sellingPrice)}</small></span>
                <strong>{money(item.sellingPrice * item.quantity)}</strong>
              </div>
            ))}
          </div>

          <div><span>Items subtotal</span><strong>{money(subtotal)}</strong></div>
          <label><span>Discount</span><span className="order-summary__discount">− <input type="number" min="0" max={subtotal} value={discountAmount} onChange={(event) => setDiscountAmount(event.target.value)} /></span></label>
          <div><span>Delivery fee <small className="order-summary__confirmed">✓ confirmed</small></span><strong>{money(deliveryFee)}</strong></div>
          <div className="order-summary__total"><strong>Order total</strong><strong>{money(total)}</strong></div>

          <fieldset><legend>Payment</legend>
            <label><input type="radio" name="payment" checked={paymentMethod === "cod"} onChange={() => setPaymentMethod("cod")} /> Cash on delivery</label>
            <label><input type="radio" name="payment" checked={paymentMethod === "deposit"} onChange={() => setPaymentMethod("deposit")} /> Deposit paid</label>
            {paymentMethod === "deposit" && <label className="order-summary__deposit">Deposit amount<input type="number" min="0" max={total} value={depositAmount} onChange={(event) => setDepositAmount(event.target.value)} /></label>}
            <label><input type="radio" name="payment" checked={paymentMethod === "paid"} onChange={() => setPaymentMethod("paid")} /> Fully paid</label>
          </fieldset>

          {paidAmount > 0 && (
            <div className="order-summary__balance">
              <span>Balance to collect</span>
              <strong>{money(balanceDue)}</strong>
              <small>{money(total)} total less {money(paidAmount)} already paid</small>
            </div>
          )}
        </div>
        <footer>
          <button type="button" onClick={() => setIsCheckoutOpen(false)}>Back to items</button>
          <div className="order-summary__submit">
            <span>{paidAmount > 0 ? `Collect ${money(balanceDue)}` : money(total)}</span>
            <button type="button" onClick={createConfirmedOrder} disabled={isSaving}>{isSaving ? "Creating..." : "Create order"}</button>
          </div>
        </footer>
      </section>
    </div>}
    {isOpen && receiptOrder && <OrderReceipt business={business} order={receiptOrder} closeLabel="Return to Orders" onClose={onClose} />}
  </>;
}

export default AddOrderModal;
