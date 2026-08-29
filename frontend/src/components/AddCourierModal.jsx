import { useEffect, useMemo, useState } from "react";

import { SRI_LANKA_DISTRICTS, districtSlug } from "../data/districts";
import { createCourier, updateCourier } from "../services/courierService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";

const DEFAULT_FIRST_KG_PRICE = "450";

const emptyForm = {
  name: "",
  code: "",
  extraKgPrice: "100",
  averageDeliveryDays: "3",
  trackingUrlTemplate: "",
  waybillPrefix: "VWB",
  waybillStart: "1",
  waybillEnd: "999999",
};

function formFromCourier(courier) {
  if (!courier) return emptyForm;

  return {
    name: courier.name ?? "",
    code: courier.code ?? "",
    extraKgPrice: String((courier.extraKgPriceMinor ?? 0) / 100),
    averageDeliveryDays: String(courier.averageDeliveryDays ?? 3),
    trackingUrlTemplate: courier.trackingUrlTemplate ?? "",
    waybillPrefix: courier.waybillPrefix ?? "VWB",
    waybillStart: String(courier.waybillStart ?? 1),
    waybillEnd: String(courier.waybillEnd ?? 999999),
  };
}

// Every district gets a price. A courier saved before per-district pricing has
// its single first-kilogram price copied across, so one save migrates it.
function districtPricesFromCourier(courier) {
  const stored = courier?.districtFirstKgPricesMinor ?? {};
  const fallback = courier?.firstKgPriceMinor
    ? String(courier.firstKgPriceMinor / 100)
    : DEFAULT_FIRST_KG_PRICE;

  return Object.fromEntries(
    SRI_LANKA_DISTRICTS.map((district) => {
      const priceMinor = stored[districtSlug(district)];
      return [
        district,
        priceMinor === undefined ? fallback : String(priceMinor / 100),
      ];
    }),
  );
}

// The courier table shows one first-kilogram price: the one most districts
// share. The backend derives the stored value the same way.
function commonPrice(districtPrices) {
  const counts = new Map();

  Object.values(districtPrices).forEach((price) => {
    counts.set(price, (counts.get(price) ?? 0) + 1);
  });

  let common = "";
  let highest = 0;

  counts.forEach((count, price) => {
    if (count > highest) {
      highest = count;
      common = price;
    }
  });

  return { price: common, districtCount: highest };
}

function AddCourierModal({ isOpen, businessId, courier = null, onClose, onCreated, onUpdated }) {
  const [formData, setFormData] = useState({ ...emptyForm });
  const [districtPrices, setDistrictPrices] = useState(() =>
    districtPricesFromCourier(null),
  );
  const [basePrice, setBasePrice] = useState(DEFAULT_FIRST_KG_PRICE);
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setFormData(formFromCourier(courier));
    setDistrictPrices(districtPricesFromCourier(courier));
    setBasePrice(
      courier?.firstKgPriceMinor
        ? String(courier.firstKgPriceMinor / 100)
        : DEFAULT_FIRST_KG_PRICE,
    );
    setErrorMessage("");
  }, [courier, isOpen]);

  const summary = useMemo(() => commonPrice(districtPrices), [districtPrices]);

  function updateField(event) {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  }

  function updateDistrictPrice(district, value) {
    setDistrictPrices((current) => ({ ...current, [district]: value }));
  }

  function applyBasePriceToAll() {
    setDistrictPrices(
      Object.fromEntries(
        SRI_LANKA_DISTRICTS.map((district) => [district, basePrice]),
      ),
    );
  }

  async function handleSubmit(event) {
    event.preventDefault();

    const missing = SRI_LANKA_DISTRICTS.filter(
      (district) => !(Number(districtPrices[district]) > 0),
    );

    if (missing.length) {
      setErrorMessage(
        `Enter a first-kilogram price greater than zero for: ${missing.join(", ")}.`,
      );
      return;
    }

    setIsSaving(true);
    setErrorMessage("");

    try {
      const payload = {
        name: formData.name,
        code: formData.code,
        extraKgPrice: formData.extraKgPrice,
        averageDeliveryDays: formData.averageDeliveryDays,
        trackingUrlTemplate: formData.trackingUrlTemplate,
        districtFirstKgPrices: districtPrices,
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
      description="Set the first-kilogram price for every district and one shared extra-kilogram price."
      onClose={onClose}
    >
      <form className="inventory-form" onSubmit={handleSubmit}>
        <div className="inventory-form__two-columns">
          <label>Courier name<input name="name" value={formData.name} onChange={updateField} required /></label>
          <label>Courier code<input name="code" value={formData.code} onChange={updateField} placeholder="KMB" required /></label>
        </div>
        <div className="inventory-form__two-columns">
          <label>Each extra 1 kg (LKR)<input name="extraKgPrice" type="number" min="0" step="0.01" value={formData.extraKgPrice} onChange={updateField} required /></label>
          <label>Average delivery days<input name="averageDeliveryDays" type="number" min="0" step="1" value={formData.averageDeliveryDays} onChange={updateField} required /></label>
        </div>

        <fieldset className="courier-districts">
          <legend>First 1 kg price by district (LKR)</legend>
          <div className="courier-districts__base">
            <label>
              Price for most districts
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={basePrice}
                onChange={(event) => setBasePrice(event.target.value)}
              />
            </label>
            <button type="button" onClick={applyBasePriceToAll}>
              Apply to all 25
            </button>
          </div>
          <p className="courier-districts__hint">
            Apply the common price first, then change only the districts that
            cost more. The courier list shows LKR {summary.price || "0.00"} —
            the price shared by {summary.districtCount} district(s).
          </p>
          <div className="courier-districts__grid">
            {SRI_LANKA_DISTRICTS.map((district) => (
              <label key={district}>
                {district}
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={districtPrices[district] ?? ""}
                  onChange={(event) =>
                    updateDistrictPrice(district, event.target.value)
                  }
                  required
                />
              </label>
            ))}
          </div>
        </fieldset>

        <label>Tracking URL template (optional)<input name="trackingUrlTemplate" value={formData.trackingUrlTemplate} onChange={updateField} placeholder="https://courier.lk/track/{waybill}" /></label>
        <div className="inventory-form__two-columns">
          <label>Waybill prefix<input name="waybillPrefix" value={formData.waybillPrefix} onChange={updateField} placeholder="VWB" /></label>
          <label>Waybill range<input name="waybillStart" type="number" min="1" value={formData.waybillStart} onChange={updateField} placeholder="Start" /></label>
        </div>
        <label>Waybill range end<input name="waybillEnd" type="number" min="1" value={formData.waybillEnd} onChange={updateField} /></label>
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
