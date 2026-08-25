import { useEffect, useState } from "react";

import { createCourier, updateCourier } from "../services/courierService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";

const emptyForm = {
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
};

function formFromCourier(courier) {
  if (!courier) return emptyForm;

  const [surchargeDistrict = "", surchargeMinor = 0] = Object.entries(
    courier.districtSurchargesMinor ?? {},
  )[0] ?? [];

  return {
    name: courier.name ?? "",
    code: courier.code ?? "",
    firstKgPrice: String((courier.firstKgPriceMinor ?? 0) / 100),
    extraKgPrice: String((courier.extraKgPriceMinor ?? 0) / 100),
    averageDeliveryDays: String(courier.averageDeliveryDays ?? 3),
    trackingUrlTemplate: courier.trackingUrlTemplate ?? "",
    surchargeDistrict,
    surchargeAmount: String(surchargeMinor / 100),
    waybillPrefix: courier.waybillPrefix ?? "VWB",
    waybillStart: String(courier.waybillStart ?? 1),
    waybillEnd: String(courier.waybillEnd ?? 999999),
  };
}

function AddCourierModal({ isOpen, businessId, courier = null, onClose, onCreated, onUpdated }) {
  const [formData, setFormData] = useState({
    ...emptyForm,
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setFormData(formFromCourier(courier));
    setErrorMessage("");
  }, [courier, isOpen]);

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
      const payload = {
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
      };
      const savedCourier = courier
        ? await updateCourier(businessId, courier.id, payload)
        : await createCourier(businessId, payload);
      if (courier) onUpdated?.(savedCourier);
      else onCreated?.(savedCourier);
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
      title={courier ? "Edit Courier" : "Add Courier"}
      description="Configure weight-based delivery pricing and waybill allocation."
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
          <button className="inventory-form__primary" type="submit" disabled={isSaving}>{isSaving ? "Saving..." : courier ? "Save Courier" : "Add Courier"}</button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default AddCourierModal;
