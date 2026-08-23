import { Fragment, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, MoreVertical, Plus, Truck } from "lucide-react";

import AddCourierModal from "../components/AddCourierModal";
import { useAuth } from "../context/authContextValue";
import { getCouriers } from "../services/courierService";

import "./ManagementPage.css";

function money(minor = 0) {
  return `LKR ${(minor / 100).toLocaleString("en-LK")}`;
}

function CouriersPage() {
  const { business } = useAuth();
  const [couriers, setCouriers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [isAddCourierOpen, setIsAddCourierOpen] = useState(false);
  const [expandedCourierId, setExpandedCourierId] = useState(null);

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

      <table className="management-table courier-table">
        <thead><tr><th className="management-table__expand-heading" /><th>Courier</th><th>First 1 kg</th><th>Extra 1 kg</th><th>Success</th><th>Returns</th><th>Delivery</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
          {couriers.map((courier) => {
            const isExpanded = expandedCourierId === courier.id;

            return (
              <Fragment key={courier.id}>
                <tr>
                  <td className="management-table__expand-cell">
                    <button
                      type="button"
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
                  <td><span className="management-table__badge">{courier.status}</span></td>
                  <td><button className="courier-table__actions" type="button" aria-label={`Actions for ${courier.name}`}><MoreVertical size={17} /></button></td>
                </tr>
                {isExpanded && (
                  <tr className="management-table__mobile-details-row">
                    <td colSpan={9}>
                      <div className="management-table__mobile-details">
                        <div><span>First 1 kg</span><strong>{money(courier.firstKgPriceMinor)}</strong></div>
                        <div><span>Extra 1 kg</span><strong>{money(courier.extraKgPriceMinor)}</strong></div>
                        <div><span>Success rate</span><strong>{Math.round((courier.successRate ?? 0) * 100)}%</strong></div>
                        <div><span>Return rate</span><strong>{Math.round((courier.returnRate ?? 0) * 100)}%</strong></div>
                        <div><span>Delivery time</span><strong>{courier.averageDeliveryDays} days</strong></div>
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
      {!isLoading && couriers.length > 0 && (
        <div className="courier-table__footer">
          <span>Showing 1 to {couriers.length} couriers</span>
          <div><button type="button" disabled>Previous</button><button className="is-active" type="button">1</button><button type="button" disabled>Next</button></div>
        </div>
      )}

      <AddCourierModal
        isOpen={isAddCourierOpen}
        businessId={business?.id}
        onClose={() => setIsAddCourierOpen(false)}
        onCreated={(courier) => setCouriers((current) => [...current, courier])}
      />
    </main>
  );
}

export default CouriersPage;
