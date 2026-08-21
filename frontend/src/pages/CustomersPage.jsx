import { Fragment, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import { getCustomers } from "../services/customerService";

import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Clock3,
  Filter,
  Mail,
  MessageSquare,
  Repeat2,
  ShieldAlert,
  UsersRound,
  RotateCcw,
  XCircle,
} from "lucide-react";

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
  const [activeCustomerTab, setActiveCustomerTab] = useState("all");
  const [expandedCustomerId, setExpandedCustomerId] = useState(null);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
  const [filters, setFilters] = useState({ search: "", risk: "all", rating: "all", location: "all" });

  const searchedCustomers = routeSearch
    ? customers.filter((customer) =>
        [customer.name, customer.normalizedPhone, customer.email].some(
          (value) =>
            String(value ?? "")
              .toLowerCase()
              .includes(routeSearch),
        ),
      )
    : customers;

  const filteredCustomers = searchedCustomers.filter((customer) => {
    const text = filters.search.trim().toLowerCase();
    const address = customer.defaultAddress || customer.address || {};
    const location = [address.city, address.district].filter(Boolean).join(" ").toLowerCase();
    const rating = Number(customer.rating ?? 0);
    const matchesText = !text || [customer.name, customer.normalizedPhone, customer.email, address.line1, address.city].some((value) => String(value ?? "").toLowerCase().includes(text));
    const matchesRisk = filters.risk === "all" || String(customer.riskLevel ?? "low").toLowerCase() === filters.risk;
    const matchesRating = filters.rating === "all" || (filters.rating === "5" ? rating >= 5 : rating >= Number(filters.rating) && rating < Number(filters.rating) + 1);
    const matchesLocation = filters.location === "all" || location.includes(filters.location.toLowerCase());
    return matchesText && matchesRisk && matchesRating && matchesLocation;
  });

  const visibleCustomers = filteredCustomers.filter((customer) => {
    if (activeCustomerTab === "all") {
      return true;
    }

    if (activeCustomerTab === "messages") {
      return (customer.unreadMessageCount ?? 0) > 0;
    }

    if (activeCustomerTab === "reviews") {
      return (customer.reviewCount ?? 0) > 0 || (Array.isArray(customer.reviews) && customer.reviews.length > 0) || Boolean(customer.reviewText);
    }

    if (activeCustomerTab === "fraud") {
      return ["medium", "high", "fraud"].includes(customer.riskLevel);
    }

    return true;
  });

  const reviewRows = visibleCustomers.flatMap((customer) => {
    const reviews = Array.isArray(customer.reviews) ? customer.reviews : [];
    if (reviews.length === 0 && customer.reviewText) {
      return [{ ...customer, reviewText: customer.reviewText }];
    }
    return reviews.map((review) => ({ ...customer, ...review }));
  });

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

  const customerTabs = [
    {
      id: "all",
      label: "All Customers",
      icon: UsersRound,
      count: customers.length,
    },
    {
      id: "messages",
      label: "Messages",
      icon: MessageSquare,
      count: customers.filter(
        (customer) => (customer.unreadMessageCount ?? 0) > 0,
      ).length,
    },
    {
      id: "reviews",
      label: "Reviews",
      icon: Mail,
      count: customers.filter((customer) => (customer.reviewCount ?? 0) > 0)
        .length,
    },
    {
      id: "fraud",
      label: "Fraud Reports",
      icon: ShieldAlert,
      count: customers.filter((customer) =>
        ["medium", "high", "fraud"].includes(customer.riskLevel),
      ).length,
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
    <main className="dashboard customers-page">
      <div className="dashboard__intro">
        <h2>Customer Management</h2>
        <p>Review customer loyalty, order history and return risk.</p>
      </div>


      <nav className="customer-tabs" aria-label="Customer sections">
        {customerTabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeCustomerTab === tab.id;

          return (
            <button
              key={tab.id}
              className={`customer-tabs__button ${
                isActive ? "customer-tabs__button--active" : ""
              }`}
              type="button"
              onClick={() => setActiveCustomerTab(tab.id)}
              aria-current={isActive ? "page" : undefined}
            >
              <Icon size={17} aria-hidden="true" />

              <span>{tab.label}</span>

              {tab.count > 0 && (
                <small className="customer-tabs__count">{tab.count}</small>
              )}
            </button>
          );
        })}
      </nav>

      {activeCustomerTab === "all" && (
<>
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


        <section className="customers-filters" aria-label="Customer filters">
          <button
            className="customers-filters__mobile-toggle"
            type="button"
            onClick={() => setAreMobileFiltersOpen((isOpen) => !isOpen)}
            aria-expanded={areMobileFiltersOpen}
            aria-controls="customer-filter-fields"
          >
            <span><Filter size={17} /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}</span>
            {areMobileFiltersOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
          <div id="customer-filter-fields" className={`customers-filters__form ${areMobileFiltersOpen ? "is-open" : ""}`}>
          <label className="customers-filters__search">
            <input
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Search by name, phone or email..."
            />
          </label>
          <select value={filters.risk} onChange={(event) => setFilters((current) => ({ ...current, risk: event.target.value }))} aria-label="Risk level">
            <option value="all">All Risk Levels</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="fraud">Fraud</option>
          </select>
          <select value={filters.rating} onChange={(event) => setFilters((current) => ({ ...current, rating: event.target.value }))} aria-label="Rating">
            <option value="all">All Ratings</option>
            <option value="5">5 stars</option>
            <option value="4">4 stars</option>
            <option value="3">3 stars</option>
            <option value="2">2 stars</option>
            <option value="1">1 star</option>
          </select>
          <select value={filters.location} onChange={(event) => setFilters((current) => ({ ...current, location: event.target.value }))} aria-label="Location">
            <option value="all">All Locations</option>
            {[...new Set(customers.map((customer) => (customer.defaultAddress || customer.address || {}).district).filter(Boolean))].map((district) => <option key={district} value={district}>{district}</option>)}
          </select>
          <button type="button" className="customers-filters__button"><Filter size={15} /> More Filters</button>
          <button type="button" className="customers-filters__reset" onClick={() => setFilters({ search: "", risk: "all", rating: "all", location: "all" })}><RotateCcw size={15} /> Reset</button>
          </div>
        </section></>
      )}

      {isLoading && (
        <p className="management-page__notice">Loading customers...</p>
      )}
      {errorMessage && (
        <p className="management-page__notice" role="alert">
          {errorMessage}
        </p>
      )}

      {activeCustomerTab === "reviews" ? (
        <>
          <section className="customers-summary customers-review-summary" aria-label="Review summary">
            <div className="stats-grid">
              {[
                { label: "Total Reviews", value: reviewRows.length, icon: MessageSquare, tone: "blue" },
                { label: "Approved", value: reviewRows.filter((review) => review.status === "approved").length, icon: CheckCircle2, tone: "green" },
                { label: "Pending", value: reviewRows.filter((review) => !review.status || review.status === "pending").length, icon: Clock3, tone: "orange" },
                { label: "Rejected", value: reviewRows.filter((review) => review.status === "rejected").length, icon: XCircle, tone: "red" },
              ].map((stat) => (
                <StatCard key={stat.label} label={stat.label} value={String(stat.value)} icon={stat.icon} tone={stat.tone} />
              ))}
            </div>
          </section>
          <ReviewsTable reviews={reviewRows} isLoading={isLoading} />
        </>
      ) : <table className="management-table">
        <thead>
          <tr>
            <th className="management-table__expand-heading" aria-label="Expand" />
            <th aria-label="Select" />
            <th>Customer</th>
            <th>Phone</th>
            <th>Email</th>
            <th>Address</th>
            <th>Orders</th>
            <th>Total Spent</th>
            <th>Last Order</th>
            <th>Rating</th>
            <th>Risk Level</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {visibleCustomers.map((customer) => (
            <Fragment key={customer.id}>
            <tr>
              <td className="management-table__expand-cell">
                <button type="button" onClick={() => setExpandedCustomerId((current) => current === customer.id ? null : customer.id)} aria-label={`Show details for ${customer.name}`}>
                  {expandedCustomerId === customer.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>
              </td>
              <td><input type="checkbox" aria-label={`Select ${customer.name}`} /></td>
              <td>
                <div className="customer-cell"><span className="customer-cell__avatar">{String(customer.name || "C").slice(0, 2).toUpperCase()}</span><strong>{customer.name}</strong></div>
              </td>
              <td>+{customer.normalizedPhone}</td>
              <td>{customer.email || "No email"}</td>
              <td>{[customer.defaultAddress?.line1, customer.defaultAddress?.city, customer.defaultAddress?.district].filter(Boolean).join(", ") || "No address"}</td>
              <td>{customer.completedOrderCount ?? 0}</td>
              <td>
                LKR{" "}
                {((customer.totalSpentMinor ?? 0) / 100).toLocaleString(
                  "en-LK",
                )}
              </td>
              <td>{customer.lastOrderDate || "—"}</td>
              <td><span className="customer-rating">{customer.rating ? `${customer.rating} ★` : "—"}</span></td>
              <td>
                <span
                  className={`management-table__badge management-table__badge--${customer.riskLevel}`}
                >
                  {customer.riskLevel}
                </span>
              </td>
              <td><button type="button" className="customer-action-button" aria-label={`Open actions for ${customer.name}`}>•••</button></td>
            </tr>
            {expandedCustomerId === customer.id && (
              <tr key={`${customer.id}-details`} className="management-table__expanded-row">
                <td colSpan={12}>
                  <div className="customer-expanded-details">
                    <div><strong>{customer.name}</strong><span>Customer ID: {customer.id}</span><span>Joined: {customer.createdAt ? new Date(customer.createdAt).toLocaleDateString("en-LK") : "—"}</span></div>
                    <div><strong>Contact</strong><span>☎ +{customer.normalizedPhone}</span><span>✉ {customer.email || "No email"}</span></div>
                    <div><strong>Delivery Address</strong><span>{[customer.defaultAddress?.line1, customer.defaultAddress?.line2, customer.defaultAddress?.city, customer.defaultAddress?.district, customer.defaultAddress?.postalCode, customer.defaultAddress?.country].filter(Boolean).join(", ") || "No address saved"}</span></div>
                    <div><strong>Recent orders</strong><span>{customer.completedOrderCount ?? 0} completed · {customer.returnedOrderCount ?? 0} returned</span><span>Preferred contact: Phone</span></div>
                  </div>
                </td>
              </tr>
            )}
            </Fragment>
          ))}
          {!isLoading && visibleCustomers.length === 0 && (
            <tr>
              <td colSpan={12}>No matching customers found.</td>
            </tr>
          )}
        </tbody>
      </table>}
    </main>
  );
}

function ReviewsTable({ reviews, isLoading }) {
  return (
    <table className="management-table customer-reviews-table">
      <thead>
        <tr>
          <th>Customer</th>
          <th>Phone</th>
          <th>Email</th>
          <th>Product</th>
          <th>Rating</th>
          <th>Review</th>
          <th>Review images</th>
          <th>Date</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {reviews.map((review, index) => (
          <tr key={`${review.id || review.customerId || review.name}-${index}`}>
            <td><strong>{review.name || "Customer"}</strong></td>
            <td>+{review.normalizedPhone || "—"}</td>
            <td>{review.email || "—"}</td>
            <td>
              <div className="review-product-cell">
                {review.productImageUrl && <img src={review.productImageUrl} alt="" />}
                <span>{review.productName || review.itemName || "Product review"}</span>
              </div>
            </td>
            <td><span className="customer-rating">{"★".repeat(Math.max(0, Math.min(5, Number(review.rating) || 0)))}{"☆".repeat(Math.max(0, 5 - (Number(review.rating) || 0)))}</span></td>
            <td>{review.reviewText || review.comment || "No written review"}</td>
            <td>{(review.images || review.reviewImages || []).length ? `${(review.images || review.reviewImages).length} image(s)` : "—"}</td>
            <td>{review.createdAt ? new Date(review.createdAt).toLocaleDateString("en-LK") : "—"}</td>
            <td><span className={`management-table__badge management-table__badge--${review.status || "pending"}`}>{review.status || "pending"}</span></td>
            <td><button type="button" className="customer-action-button" aria-label="Review actions">•••</button></td>
          </tr>
        ))}
        {!isLoading && reviews.length === 0 && <tr><td colSpan={10}>No reviews found.</td></tr>}
      </tbody>
    </table>
  );
}

export default CustomersPage;
