import { Fragment, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, FileDigit, Pencil, Plus, Power, Truck } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import AddCourierModal from "../components/AddCourierModal";
import ActionMenu from "../components/ActionMenu";
import TablePagination from "../components/TablePagination";
import useTablePagination from "../hooks/useTablePagination";
import { useAuth } from "../context/authContextValue";
import { getCouriers, updateCourier } from "../services/courierService";

import "./ManagementPage.css";
import "../components/OrderTable.css";

function money(minor = 0) {
  return `LKR ${(minor / 100).toLocaleString("en-LK")}`;
}

function CouriersPage() {
  const [searchParameters, setSearchParameters] = useSearchParams();
  const assistantAction = searchParameters.get("assistantAction") ?? "";
  const { business } = useAuth();
  const [couriers, setCouriers] = useState([]);
  const pagination = useTablePagination(couriers);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [isAddCourierOpen, setIsAddCourierOpen] = useState(false);
  const [editingCourier, setEditingCourier] = useState(null);
  const [expandedCourierId, setExpandedCourierId] = useState(null);

  function replaceCourier(updatedCourier) {
    setCouriers((current) => current.map((courier) => (
      courier.id === updatedCourier.id ? updatedCourier : courier
    )));
  }

  async function changeCourierStatus(courier) {
    setErrorMessage("");
    try {
      const updatedCourier = await updateCourier(business.id, courier.id, {
        status: courier.status === "active" ? "inactive" : "active",
      });
      replaceCourier(updatedCourier);
    } catch (error) {
      setErrorMessage(error.message);
    }
  }

  async function manageWaybillRange(courier) {
    const prefix = window.prompt("Waybill prefix", courier.waybillPrefix ?? "VWB");
    if (prefix === null) return;
    const start = window.prompt("Waybill range start", String(courier.waybillStart ?? 1));
    if (start === null) return;
    const end = window.prompt("Waybill range end", String(courier.waybillEnd ?? 999999));
    if (end === null) return;

    const startNumber = Number(start);
    const endNumber = Number(end);
    if (!prefix.trim() || !Number.isInteger(startNumber) || !Number.isInteger(endNumber) || startNumber < 1 || endNumber < startNumber) {
      setErrorMessage("Enter a prefix and a valid waybill range.");
      return;
    }

    setErrorMessage("");
    try {
      const updatedCourier = await updateCourier(business.id, courier.id, {
        waybillPrefix: prefix.trim(),
        waybillStart: startNumber,
        waybillEnd: endNumber,
      });
      replaceCourier(updatedCourier);
    } catch (error) {
      setErrorMessage(error.message);
    }
  }

  useEffect(() => {
    if (assistantAction !== "add-courier") return;

    setIsAddCourierOpen(true);
    const nextParameters = new URLSearchParams(searchParameters);
    nextParameters.delete("assistantAction");
    setSearchParameters(nextParameters, { replace: true });
  }, [assistantAction, searchParameters, setSearchParameters]);

  useEffect(() => {
    if (!business?.id) {
      setIsLoading(false);
      return;
    }

    getCouriers(business.id)
      .then(setCouriers)
      .catch((error) => setErrorMessage(error.message))
      .finally(() => setIsLoading(false));
  }, [business?.id]);

  return (
    <main className="dashboard">
      <div className="management-page__heading">
        <div className="dashboard__intro">
          <h2>Couriers & Delivery</h2>
          <p>Manage courier services, weight pricing and delivery quality.</p>
        </div>
        <button className="management-page__primary-button" type="button" onClick={() => setIsAddCourierOpen(true)} disabled={!business?.id}>
          <Plus size={18} /> Add Courier
        </button>
      </div>

      {isLoading && <p className="management-page__notice">Loading couriers...</p>}
      {errorMessage && <p className="management-page__notice" role="alert">{errorMessage}</p>}

      <section className="orders-table-section courier-table-card">
      <div className="orders-table__scroll courier-table__scroll">
      <table className="orders-table courier-table">
        <thead><tr><th className="management-table__expand-heading" /><th>Courier</th><th>First 1 kg</th><th>Extra 1 kg</th><th>Success</th><th>Returns</th><th>Delivery</th><th>Status</th><th className="orders-table__actions-heading">Actions</th></tr></thead>
        <tbody>
          {pagination.pageItems.map((courier) => {
            const isExpanded = expandedCourierId === courier.id;

            return (
              <Fragment key={courier.id}>
                <tr>
                  <td className="management-table__expand-cell">
                    <button
                      type="button"
                      className="orders-table__expand-button"
                      onClick={() => setExpandedCourierId(isExpanded ? null : courier.id)}
                      aria-expanded={isExpanded}
                      aria-label={`${isExpanded ? "Collapse" : "Expand"} ${courier.name}`}
                    >
                      {isExpanded ? <ChevronDown size={17} /> : <ChevronRight size={17} />}
                    </button>
                  </td>
                  <td><span className="courier-table__name"><span className="courier-table__icon"><Truck size={16} aria-hidden="true" /></span><strong>{courier.name}</strong><small>{courier.code}</small></span></td>
                  <td>{money(courier.firstKgPriceMinor)}</td>
                  <td>{money(courier.extraKgPriceMinor)}</td>
                  <td>{Math.round((courier.successRate ?? 0) * 100)}%</td>
                  <td>{Math.round((courier.returnRate ?? 0) * 100)}%</td>
                  <td>{courier.averageDeliveryDays} days</td>
                  <td><span className={`management-table__badge management-table__badge--${courier.status}`}>{courier.status}</span></td>
                  <td className="orders-table__actions-heading">
                    <ActionMenu
                      label={`Actions for ${courier.name}`}
                      items={[
                        {
                          label: "Edit courier",
                          icon: <Pencil size={16} aria-hidden="true" />,
                          onClick: () => setEditingCourier(courier),
                        },
                        {
                          label: "Manage waybill range",
                          icon: <FileDigit size={16} aria-hidden="true" />,
                          onClick: () => manageWaybillRange(courier),
                        },
                        {
                          label: courier.status === "active" ? "Deactivate courier" : "Activate courier",
                          icon: <Power size={16} aria-hidden="true" />,
                          danger: courier.status === "active",
                          onClick: () => changeCourierStatus(courier),
                        },
                      ]}
                    />
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="management-table__mobile-details-row orders-table__details-row">
                    <td className="orders-table__details-cell" colSpan={9}>
                      <div className="management-table__mobile-details">
                        <div><span>First 1 kg</span><strong>{money(courier.firstKgPriceMinor)}</strong></div>
                        <div><span>Extra 1 kg</span><strong>{money(courier.extraKgPriceMinor)}</strong></div>
                        <div><span>Success rate</span><strong>{Math.round((courier.successRate ?? 0) * 100)}%</strong></div>
                        <div><span>Return rate</span><strong>{Math.round((courier.returnRate ?? 0) * 100)}%</strong></div>
                        <div><span>Delivery time</span><strong>{courier.averageDeliveryDays} days</strong></div>
                        <div><span>Waybill range</span><strong>{courier.waybillPrefix}{courier.waybillStart} – {courier.waybillPrefix}{courier.waybillEnd}</strong></div>
                        <div><span>Delivered orders</span><strong>{courier.deliveredOrderCount ?? 0}</strong></div>
                        <div><span>Returned orders</span><strong>{courier.returnedOrderCount ?? 0}</strong></div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
          {!isLoading && couriers.length === 0 && <tr><td colSpan={9}>No couriers configured yet.</td></tr>}
        </tbody>
      </table>
      </div>
      {!isLoading && <TablePagination pagination={pagination} label="couriers" />}
      </section>

      <AddCourierModal
        isOpen={isAddCourierOpen}
        businessId={business?.id}
        onClose={() => setIsAddCourierOpen(false)}
        onCreated={(courier) => setCouriers((current) => [...current, courier])}
      />
      <AddCourierModal
        isOpen={Boolean(editingCourier)}
        businessId={business?.id}
        courier={editingCourier}
        onClose={() => setEditingCourier(null)}
        onUpdated={replaceCourier}
      />
    </main>
  );
}

export default CouriersPage;
