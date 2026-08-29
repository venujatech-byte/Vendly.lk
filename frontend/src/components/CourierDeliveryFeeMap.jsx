import { useEffect, useMemo, useState } from "react";
import { MapPinned, Truck } from "lucide-react";

import sriLankaMapMarkup from "../assets/sri-lanka-districts.svg?raw";

import "./CourierDeliveryFeeMap.css";

// The SVG uses transliterated district names. This map connects those names to
// the same district keys stored in each courier document.
const SVG_DISTRICT_SLUGS = {
  Mahanuwara: "kandy",
  Matale: "matale",
  "Nuwara Eliya": "nuwara-eliya",
  Ampara: "ampara",
  Madakalapuwa: "batticaloa",
  Polonnaruwa: "polonnaruwa",
  Tricunamalaya: "trincomalee",
  Anuradhapura: "anuradhapura",
  Vavniyawa: "vavuniya",
  Mannarama: "mannar",
  Mulativ: "mullaitivu",
  Yapanaya: "jaffna",
  Kilinochchi: "kilinochchi",
  Kurunegala: "kurunegala",
  Puththalama: "puttalam",
  Rathnapura: "ratnapura",
  Galle: "galle",
  Hambanthota: "hambantota",
  Mathara: "matara",
  Badulla: "badulla",
  Monaragala: "monaragala",
  Kegalla: "kegalle",
  Colombo: "colombo",
  Gampaha: "gampaha",
  Kaluthara: "kalutara",
};

const DISTRICT_LABELS = Object.fromEntries(
  Object.entries(SVG_DISTRICT_SLUGS).map(([label, slug]) => [slug, label]),
);

function money(minor) {
  if (!Number.isFinite(minor)) return "Not configured";
  return `LKR ${(minor / 100).toLocaleString("en-LK")}`;
}

function districtFee(courier, districtSlug) {
  if (!courier) return null;

  const districtPrices = courier.districtFirstKgPricesMinor ?? {};
  if (Object.prototype.hasOwnProperty.call(districtPrices, districtSlug)) {
    return districtPrices[districtSlug];
  }

  return Number.isFinite(courier.firstKgPriceMinor)
    ? courier.firstKgPriceMinor
    : null;
}

function hasDistrictFee(courier, districtSlug) {
  return Object.prototype.hasOwnProperty.call(
    courier?.districtFirstKgPricesMinor ?? {},
    districtSlug,
  );
}

function feeFill(amount, minimum, maximum) {
  if (!Number.isFinite(amount)) return "#cbd5e1";
  if (minimum === maximum) return "#4ca8f7";

  const position = (amount - minimum) / (maximum - minimum);
  const lightness = 76 - position * 33;
  return `hsl(207 88% ${lightness}%)`;
}

function CourierDeliveryFeeMap({ couriers }) {
  const [selectedCourierId, setSelectedCourierId] = useState("");
  const [selectedDistrict, setSelectedDistrict] = useState("colombo");

  useEffect(() => {
    if (!couriers.length) {
      setSelectedCourierId("");
      return;
    }

    if (!couriers.some((courier) => courier.id === selectedCourierId)) {
      const firstActiveCourier = couriers.find((courier) => courier.status === "active");
      setSelectedCourierId((firstActiveCourier ?? couriers[0]).id);
    }
  }, [couriers, selectedCourierId]);

  const selectedCourier = couriers.find(
    (courier) => courier.id === selectedCourierId,
  );

  const feeRange = useMemo(() => {
    const fees = Object.values(SVG_DISTRICT_SLUGS)
      .map((districtSlug) => districtFee(selectedCourier, districtSlug))
      .filter(Number.isFinite);

    return {
      minimum: fees.length ? Math.min(...fees) : 0,
      maximum: fees.length ? Math.max(...fees) : 0,
    };
  }, [selectedCourier]);

  const mapMarkup = useMemo(() => {
    return sriLankaMapMarkup
      .replace(/<\?xml[^>]*>/g, "")
      .replace(/<!--[^]*?-->/g, "")
      .replace(/<path\b([^>]*?)name="([^"]+)"([^>]*)>/g, (
        fullMatch,
        beforeName,
        svgDistrictName,
        afterName,
      ) => {
        const districtSlug = SVG_DISTRICT_SLUGS[svgDistrictName];
        if (!districtSlug) return fullMatch;

        const amount = districtFee(selectedCourier, districtSlug);
        const fill = feeFill(amount, feeRange.minimum, feeRange.maximum);
        const isSelected = selectedDistrict === districtSlug;
        const label = `${DISTRICT_LABELS[districtSlug]}: ${money(amount)} for the first 1 kg`;

        return `<path${beforeName}name="${svgDistrictName}"${afterName} data-district="${districtSlug}" data-selected="${isSelected}" tabindex="0" role="button" aria-label="${label}" style="--district-fill:${fill}">`;
      });
  }, [feeRange.maximum, feeRange.minimum, selectedCourier, selectedDistrict]);

  function selectMapDistrict(event) {
    const districtPath = event.target.closest?.("path[data-district]");
    if (districtPath) setSelectedDistrict(districtPath.dataset.district);
  }

  function selectMapDistrictWithKeyboard(event) {
    if (event.key !== "Enter" && event.key !== " ") return;
    const districtPath = event.target.closest?.("path[data-district]");
    if (!districtPath) return;

    event.preventDefault();
    setSelectedDistrict(districtPath.dataset.district);
  }

  const districtLabel = DISTRICT_LABELS[selectedDistrict] ?? "District";

  return (
    <section className="courier-fee-map" aria-labelledby="courier-fee-map-title">
      <div className="courier-fee-map__header">
        <div>
          <span className="courier-fee-map__eyebrow">
            <MapPinned size={15} aria-hidden="true" /> District pricing
          </span>
          <h3 id="courier-fee-map-title">Sri Lanka delivery fee map</h3>
          <p>Choose a courier, then select a district to compare first-1 kg delivery fees.</p>
        </div>

        <label className="courier-fee-map__courier-select">
          <span>Courier shown on map</span>
          <select
            value={selectedCourierId}
            onChange={(event) => setSelectedCourierId(event.target.value)}
            disabled={!couriers.length}
          >
            {!couriers.length && <option value="">No couriers configured</option>}
            {couriers.map((courier) => (
              <option key={courier.id} value={courier.id}>
                {courier.name} ({courier.code})
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="courier-fee-map__body">
        <div className="courier-fee-map__visual-card">
          <div className="courier-fee-map__selected-summary">
            <span>{selectedCourier?.name ?? "Select a courier"}</span>
            <strong>{districtLabel}: {money(districtFee(selectedCourier, selectedDistrict))}</strong>
          </div>

          <div
            className="courier-fee-map__svg"
            onClick={selectMapDistrict}
            onKeyDown={selectMapDistrictWithKeyboard}
            dangerouslySetInnerHTML={{ __html: mapMarkup }}
          />

          <div className="courier-fee-map__legend" aria-label="Delivery fee colour scale">
            <span>Lower fee</span>
            <i aria-hidden="true" />
            <span>Higher fee</span>
          </div>
        </div>

        <aside className="courier-fee-map__comparison">
          <div className="courier-fee-map__comparison-heading">
            <div>
              <span>Selected district</span>
              <h4>{districtLabel}</h4>
            </div>
            <MapPinned size={20} aria-hidden="true" />
          </div>

          <p className="courier-fee-map__comparison-help">
            First-1 kg delivery fee for every courier. Extra weight is charged separately.
          </p>

          <div className="courier-fee-map__courier-list">
            {couriers.map((courier) => {
              const amount = districtFee(courier, selectedDistrict);
              const usesDistrictPrice = hasDistrictFee(courier, selectedDistrict);

              return (
                <button
                  type="button"
                  key={courier.id}
                  className={courier.id === selectedCourierId ? "is-selected" : ""}
                  onClick={() => setSelectedCourierId(courier.id)}
                >
                  <span className="courier-fee-map__courier-icon">
                    <Truck size={16} aria-hidden="true" />
                  </span>
                  <span className="courier-fee-map__courier-name">
                    <strong>{courier.name}</strong>
                    <small>
                      {usesDistrictPrice ? "District fee" : "Common fee"}
                      {Number.isFinite(courier.extraKgPriceMinor)
                        ? ` · +${money(courier.extraKgPriceMinor)} / extra kg`
                        : ""}
                    </small>
                  </span>
                  <strong className="courier-fee-map__amount">{money(amount)}</strong>
                </button>
              );
            })}

            {!couriers.length && (
              <div className="courier-fee-map__empty">
                Add a courier to display its district delivery fees.
              </div>
            )}
          </div>

          <div className="courier-fee-map__note">
            <span className="courier-fee-map__note-dot" aria-hidden="true" />
            A “common fee” is the courier’s fallback first-1 kg price when that district has no custom price.
          </div>
        </aside>
      </div>
    </section>
  );
}

export default CourierDeliveryFeeMap;
