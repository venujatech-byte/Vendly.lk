import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import { getCustomers } from "../services/customerService";

import { Mail, Repeat2, ShieldAlert, UsersRound } from "lucide-react";

import StatCard from "../components/StatCard";

import "./ManagementPage.css";
import "./CustomersPage.css";

function CustomersPage() {
  const [searchParameters] = useSearchParams();
  const routeSearch = (searchParameters.get("search") ?? "")
    .trim()
    .toLowerCase();
  const { business } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const visibleCustomers = routeSearch
    ? customers.filter((customer) =>
        [customer.name, customer.normalizedPhone, customer.email].some(
          (value) =>
            String(value ?? "")
              .toLowerCase()
              .includes(routeSearch),
        ),
      )
    : customers;

  const customerStats = [
    {
      label: "Total Customers",
      value: customers.length.toLocaleString("en-LK"),
      icon: UsersRound,
      tone: "blue",
    },
    {
      label: "Repeat Customers",
      value: customers
        .filter((customer) => (customer.completedOrderCount ?? 0) > 1)
        .length.toLocaleString("en-LK"),
      icon: Repeat2,
      tone: "green",
    },
    {
      label: "Unread Messages",
      value: "0",
      icon: Mail,
      tone: "orange",
    },
    {
      label: "Fraud Reports",
      value: customers
        .filter((customer) => customer.riskLevel === "fraud")
        .length.toLocaleString("en-LK"),
      icon: ShieldAlert,
      tone: "red",
    },
  ];

  useEffect(() => {
    if (!business?.id) {
      setIsLoading(false);
      return;
    }

    getCustomers(business.id)
      .then(setCustomers)
      .catch((error) => setErrorMessage(error.message))
      .finally(() => setIsLoading(false));
  }, [business?.id]);

  return (
    <main className="dashboard">
      <div className="dashboard__intro">
        <h2>Customer Management</h2>
        <p>Review customer loyalty, order history and return risk.</p>
      </div>

      <section
        className="customers-summary"
        aria-labelledby="customer-management-title"
      >

        <div className="stats-grid">
          {customerStats.map((stat) => (
            <StatCard
              key={stat.label}
              label={stat.label}
              value={stat.value}
              icon={stat.icon}
              tone={stat.tone}
            />
          ))}
        </div>
      </section>

      {isLoading && (
        <p className="management-page__notice">Loading customers...</p>
      )}
      {errorMessage && (
        <p className="management-page__notice" role="alert">
          {errorMessage}
        </p>
      )}

      <table className="management-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th>Phone</th>
            <th>Completed</th>
            <th>Returned</th>
            <th>Total spent</th>
            <th>Risk</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {visibleCustomers.map((customer) => (
            <tr key={customer.id}>
              <td>
                <strong>{customer.name}</strong>
                <br />
                <small>{customer.email || "No email"}</small>
              </td>
              <td>+{customer.normalizedPhone}</td>
              <td>{customer.completedOrderCount}</td>
              <td>{customer.returnedOrderCount}</td>
              <td>
                LKR{" "}
                {((customer.totalSpentMinor ?? 0) / 100).toLocaleString(
                  "en-LK",
                )}
              </td>
              <td>
                <span
                  className={`management-table__badge management-table__badge--${customer.riskLevel}`}
                >
                  {customer.riskLevel}
                </span>
              </td>
              <td>{customer.status}</td>
            </tr>
          ))}
          {!isLoading && visibleCustomers.length === 0 && (
            <tr>
              <td colSpan={7}>No matching customers found.</td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}

export default CustomersPage;
