import { useEffect, useState } from "react";
import ModalShell from "./ModalShell";
import { getCouriers } from "../services/courierService";
import { updateOrder, updateOrderStatus } from "../services/orderService";
import "./InventoryForm.css";

const emptyAddress = { line1: "", line2: "", city: "", district: "", postalCode: "" };
const nextStatuses = {
  "needs-confirmation": ["confirmed", "cancelled"],
  confirmed: ["packed", "cancelled"],
  packed: ["shipped", "cancelled"],
  shipped: ["delivered", "returned"],
  delivered: ["returned"],
};

function EditOrderModal({ isOpen, businessId, order, onClose, onUpdated }) {
  const [couriers, setCouriers] = useState([]);
  const [form, setForm] = useState({ customerName: "", phoneNumber: "", email: "", deliveryAddress: emptyAddress, courierId: "", paymentMethod: "cod", privateNote: "", status: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen || !businessId || !order) return;
    setForm({
      customerName: order.customerName ?? "",
      phoneNumber: order.phoneNumber ?? "",
      email: order.email ?? "",
      deliveryAddress: { ...emptyAddress, ...(order.deliveryAddressObject ?? {}) },
      courierId: order.courierId ?? "",
      paymentMethod: order.paymentMethod ?? "cod",
      privateNote: order.privateNote ?? "",
      status: "",
    });
    setError("");
    getCouriers(businessId).then(setCouriers).catch(() => setCouriers([]));
  }, [businessId, isOpen, order]);

  function change(event) {
    const { name, value } = event.target;
    if (name.startsWith("address.")) {
      const field = name.slice("address.".length);
      setForm((current) => ({ ...current, deliveryAddress: { ...current.deliveryAddress, [field]: value } }));
      return;
    }
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    if (!order) return;
    setSaving(true);
    setError("");
    try {
      let updated = await updateOrder(businessId, order.id, {
        customerName: form.customerName,
        phoneNumber: form.phoneNumber,
        email: form.email,
        deliveryAddress: form.deliveryAddress,
        courierId: form.courierId,
        paymentMethod: form.paymentMethod,
        privateNote: form.privateNote,
      });
      if (form.status && form.status !== order.fulfilmentStatus) {
        updated = await updateOrderStatus(businessId, order.id, form.status);
      }
      onUpdated?.(updated);
      onClose();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  const statusOptions = nextStatuses[order?.fulfilmentStatus] ?? [];

  return (
    <ModalShell isOpen={isOpen} title={`Edit Order ${order?.orderNumber ?? ""}`} description="Update customer, delivery, payment, courier, status, and internal notes." onClose={onClose} size="wide">
      <form className="inventory-form" onSubmit={submit}>
        <section className="inventory-form__panel"><h3>Customer details</h3>
          <div className="inventory-form__two-columns"><label>Customer name<input name="customerName" value={form.customerName} onChange={change} required /></label><label>Phone number<input name="phoneNumber" value={form.phoneNumber} onChange={change} required /></label></div>
          <label>Email<input name="email" type="email" value={form.email} onChange={change} /></label>
        </section>
        <section className="inventory-form__panel"><h3>Delivery address</h3>
          <label>Address line 1<input name="address.line1" value={form.deliveryAddress.line1} onChange={change} required /></label>
          <div className="inventory-form__two-columns"><label>Address line 2<input name="address.line2" value={form.deliveryAddress.line2} onChange={change} /></label><label>City<input name="address.city" value={form.deliveryAddress.city} onChange={change} required /></label></div>
          <div className="inventory-form__two-columns"><label>District<input name="address.district" value={form.deliveryAddress.district} onChange={change} required /></label><label>Postal code<input name="address.postalCode" value={form.deliveryAddress.postalCode} onChange={change} /></label></div>
        </section>
        <section className="inventory-form__panel"><h3>Order settings</h3>
          <div className="inventory-form__two-columns"><label>Courier<select name="courierId" value={form.courierId} onChange={change}><option value="">Choose courier</option>{couriers.map((courier) => <option key={courier.id} value={courier.id}>{courier.name}</option>)}</select></label><label>Payment<select name="paymentMethod" value={form.paymentMethod} onChange={change}><option value="cod">Cash on delivery</option><option value="paid">Paid</option><option value="deposit">Deposit</option></select></label></div>
          <label>Next status<select name="status" value={form.status} onChange={change}><option value="">Keep {order?.status ?? "current status"}</option>{statusOptions.map((status) => <option key={status} value={status}>{status.replaceAll("-", " ")}</option>)}</select></label>
          <label>Private order note<textarea name="privateNote" value={form.privateNote} onChange={change} rows={4} placeholder="Visible only to your team" /></label>
        </section>
        {error && <p className="inventory-form__error" role="alert">{error}</p>}
        <footer className="inventory-form__footer"><button type="button" onClick={onClose}>Cancel</button><button className="inventory-form__primary" type="submit" disabled={saving}>{saving ? "Saving..." : "Save order"}</button></footer>
      </form>
    </ModalShell>
  );
}

export default EditOrderModal;
