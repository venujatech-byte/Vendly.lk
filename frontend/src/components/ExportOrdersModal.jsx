import { useEffect, useMemo, useState } from "react";
import { FileSpreadsheet, PackageCheck } from "lucide-react";

import ModalShell from "./ModalShell";

import "./ExportOrdersModal.css";

function ExportOrdersModal({
  isOpen,
  couriers,
  orders,
  selectedOrderCount = 0,
  isExporting,
  onClose,
  onExport,
}) {
  const availableCouriers = useMemo(
    () => couriers.filter((courier) => courier.status === "active"),
    [couriers],
  );
  const [courierId, setCourierId] = useState("");
  const selectedCourier = availableCouriers.find(
    (courier) => courier.id === courierId,
  );
  const matchingOrderCount = orders.filter(
    (order) => order.courierId === courierId,
  ).length;

  useEffect(() => {
    if (!isOpen) return;
    setCourierId((current) => (
      availableCouriers.some((courier) => courier.id === current)
        ? current
        : availableCouriers[0]?.id ?? ""
    ));
  }, [availableCouriers, isOpen]);

  async function submit(event) {
    event.preventDefault();
    if (
      !selectedCourier?.exportTemplateFilename
      || (selectedOrderCount > 0 && matchingOrderCount === 0)
    ) return;
    const succeeded = await onExport(courierId);
    if (succeeded) onClose();
  }

  return (
    <ModalShell
      isOpen={isOpen}
      title={selectedOrderCount > 0 ? "Export selected orders" : "Export courier orders"}
      description={selectedOrderCount > 0
        ? `Choose a courier. Only the ${selectedOrderCount} selected order(s) assigned to it will use its saved Excel format.`
        : "Choose one courier. Only its matching orders will be written into its saved Excel format."}
      onClose={onClose}
      size="small"
    >
      <form className="export-orders-form" onSubmit={submit}>
        <label className="export-orders-form__field">
          <span>Courier</span>
          <select
            value={courierId}
            onChange={(event) => setCourierId(event.target.value)}
          >
            {availableCouriers.map((courier) => (
              <option key={courier.id} value={courier.id}>
                {courier.name} ({courier.code})
              </option>
            ))}
          </select>
        </label>

        {selectedCourier && (
          <div className="export-orders-form__summary">
            <div>
              <FileSpreadsheet size={20} aria-hidden="true" />
              <span>
                <small>Excel format</small>
                <strong>
                  {selectedCourier.exportTemplateFilename ?? "Not uploaded"}
                </strong>
              </span>
            </div>
            <div>
              <PackageCheck size={20} aria-hidden="true" />
              <span>
                <small>{selectedOrderCount > 0 ? "Selected matching orders" : "Visible matching orders"}</small>
                <strong>{matchingOrderCount}</strong>
              </span>
            </div>
          </div>
        )}

        {selectedCourier && !selectedCourier.exportTemplateFilename && (
          <p className="export-orders-form__warning" role="alert">
            Upload this courier&apos;s Excel format from the Couriers page first.
          </p>
        )}

        {selectedOrderCount > 0 && selectedCourier && matchingOrderCount === 0 && (
          <p className="export-orders-form__warning" role="alert">
            None of the selected orders are assigned to this courier.
          </p>
        )}

        {!availableCouriers.length && (
          <p className="export-orders-form__warning" role="alert">
            Add or activate a courier before exporting orders.
          </p>
        )}

        <footer className="export-orders-form__footer">
          <button type="button" onClick={onClose}>Cancel</button>
          <button
            type="submit"
            disabled={
              isExporting
              || !selectedCourier
              || !selectedCourier.exportTemplateFilename
              || (selectedOrderCount > 0 && matchingOrderCount === 0)
            }
          >
            {isExporting ? "Exporting..." : "Export Excel"}
          </button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default ExportOrdersModal;
