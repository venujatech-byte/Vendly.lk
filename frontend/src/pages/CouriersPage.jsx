import { useEffect, useState } from "react";
import { Plus, Truck } from "lucide-react";

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

      <table className="management-table">
        <thead><tr><th>Courier</th><th>First 1 kg</th><th>Extra 1 kg</th><th>Success</th><th>Returns</th><th>Delivery</th><th>Status</th></tr></thead>
        <tbody>
          {couriers.map((courier) => (
            <tr key={courier.id}>
              <td><Truck size={17} aria-hidden="true" /> <strong>{courier.name}</strong> ({courier.code})</td>
              <td>{money(courier.firstKgPriceMinor)}</td>
              <td>{money(courier.extraKgPriceMinor)}</td>
              <td>{Math.round((courier.successRate ?? 0) * 100)}%</td>
              <td>{Math.round((courier.returnRate ?? 0) * 100)}%</td>
              <td>{courier.averageDeliveryDays} days</td>
              <td><span className="management-table__badge">{courier.status}</span></td>
            </tr>
          ))}
          {!isLoading && couriers.length === 0 && <tr><td colSpan={7}>No couriers configured yet.</td></tr>}
        </tbody>
      </table>

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
