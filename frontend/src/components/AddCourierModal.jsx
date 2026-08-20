import { useEffect, useState } from "react";

import { createCourier } from "../services/courierService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";

function AddCourierModal({ isOpen, businessId, onClose, onCreated }) {
  const [formData, setFormData] = useState({
    name: "",
    code: "",
    firstKgPrice: "450",
    extraKgPrice: "100",
    averageDeliveryDays: "3",
    trackingUrlTemplate: "",
    surchargeDistrict: "",
    surchargeAmount: "0",
    waybillPrefix: "VWB",
    waybillStart: "1",
    waybillEnd: "999999",
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) setErrorMessage("");
  }, [isOpen]);

  function updateField(event) {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage("");

    try {
      const districtSurcharges = formData.surchargeDistrict.trim()
        ? { [formData.surchargeDistrict.trim()]: formData.surchargeAmount }
        : {};
      const courier = await createCourier(businessId, {
        name: formData.name,
        code: formData.code,
        firstKgPrice: formData.firstKgPrice,
        extraKgPrice: formData.extraKgPrice,
        averageDeliveryDays: formData.averageDeliveryDays,
        trackingUrlTemplate: formData.trackingUrlTemplate,
        districtSurcharges,
        waybillPrefix: formData.waybillPrefix,
        waybillStart: formData.waybillStart,
        waybillEnd: formData.waybillEnd,
      });
      onCreated(courier);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell
      isOpen={isOpen}
      title="Add Courier"
      description="Configure weight-based delivery pricing for one courier."
      onClose={onClose}
    >
      <form className="inventory-form" onSubmit={handleSubmit}>
        <div className="inventory-form__two-columns">
          <label>Courier name<input name="name" value={formData.name} onChange={updateField} required /></label>
          <label>Courier code<input name="code" value={formData.code} onChange={updateField} placeholder="KMB" required /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>First 1 kg price (LKR)<input name="firstKgPrice" type="number" min="0.01" step="0.01" value={formData.firstKgPrice} onChange={updateField} required /></label>
          <label>Each extra 1 kg (LKR)<input name="extraKgPrice" type="number" min="0" step="0.01" value={formData.extraKgPrice} onChange={updateField} required /></label>
        </div>
        <label>Average delivery days<input name="averageDeliveryDays" type="number" min="0" step="1" value={formData.averageDeliveryDays} onChange={updateField} required /></label>
        <label>Tracking URL template (optional)<input name="trackingUrlTemplate" value={formData.trackingUrlTemplate} onChange={updateField} placeholder="https://courier.lk/track/{waybill}" /></label>
        <div className="inventory-form__two-columns">
          <label>Waybill prefix<input name="waybillPrefix" value={formData.waybillPrefix} onChange={updateField} placeholder="VWB" /></label>
          <label>Waybill range<input name="waybillStart" type="number" min="1" value={formData.waybillStart} onChange={updateField} placeholder="Start" /></label>
        </div>
        <label>Waybill range end<input name="waybillEnd" type="number" min="1" value={formData.waybillEnd} onChange={updateField} /></label>
        <div className="inventory-form__two-columns">
          <label>District surcharge (optional)<input name="surchargeDistrict" value={formData.surchargeDistrict} onChange={updateField} placeholder="Jaffna" /></label>
          <label>Surcharge amount (LKR)<input name="surchargeAmount" type="number" min="0" step="0.01" value={formData.surchargeAmount} onChange={updateField} /></label>
        </div>
        {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}
        <footer className="inventory-form__footer">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="inventory-form__primary" type="submit" disabled={isSaving}>{isSaving ? "Saving..." : "Add Courier"}</button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default AddCourierModal;
