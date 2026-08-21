import { Fragment, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import {
  getCustomers,
  getFraudCustomers,
  reportCustomer,
  updateCustomer,
} from "../services/customerService";
import { getChatSessions } from "../services/messageService";
import { getReviews, moderateReview } from "../services/reviewService";

import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Clock3,
  Filter,
  Flag,
  Mail,
  MessageSquare,
  Repeat2,
  ShieldAlert,
  UsersRound,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";

import StatCard from "../components/StatCard";
import CustomerMessages from "../components/CustomerMessages";
import ActionMenu from "../components/ActionMenu";
import ConfirmDialog from "../components/ConfirmDialog";

import "./ManagementPage.css";
import "./CustomersPage.css";

function CustomersPage() {
  const [searchParameters] = useSearchParams();
  const routeSearch = (searchParameters.get("search") ?? "")
    .trim()
    .toLowerCase();
  const requestedTab = searchParameters.get("tab");
  const requestedSessionId = searchParameters.get("session") ?? "";
  const { business } = useAuth();
  const [customers, setCustomers] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [fraudCustomers, setFraudCustomers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [chatSummary, setChatSummary] = useState({ count: 0, unread: 0 });
  const [activeCustomerTab, setActiveCustomerTab] = useState("all");
  const [expandedCustomerId, setExpandedCustomerId] = useState(null);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
  const [fraudFilters, setFraudFilters] = useState({ search: "", risk: "all", reason: "all", score: "all" });
  const [filters, setFilters] = useState({ search: "", risk: "all", rating: "all", location: "all" });
  const [customerAction, setCustomerAction] = useState(null);
  const [isCustomerActionWorking, setIsCustomerActionWorking] = useState(false);

  useEffect(() => {
    if (["all", "messages", "reviews", "fraud"].includes(requestedTab)) {
      setActiveCustomerTab(requestedTab);
    }
  }, [requestedTab]);

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

  const reviewRows = reviews;

  const fraudRows = fraudCustomers.filter((customer) => {
    const address = customer.defaultAddress || customer.address || {};
    const text = fraudFilters.search.trim().toLowerCase();
    const risk = String(customer.riskLevel || "low").toLowerCase();
    const score = Number(customer.fraudScore ?? customer.returnedOrderCount ?? 0);
    const reason = customer.returnReason || customer.fraudReason || "Unspecified";
    return (risk !== "low" || (customer.returnedOrderCount ?? 0) > 0)
      && (!text || [customer.name, customer.normalizedPhone, customer.email, address.line1, address.city].some((value) => String(value ?? "").toLowerCase().includes(text)))
      && (fraudFilters.risk === "all" || risk === fraudFilters.risk)
      && (fraudFilters.reason === "all" || reason === fraudFilters.reason)
      && (fraudFilters.score === "all" || (fraudFilters.score === "high" ? score >= 70 : fraudFilters.score === "medium" ? score >= 40 && score < 70 : score < 40));
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
      value: chatSummary.unread.toLocaleString("en-LK"),
      icon: Mail,
      tone: "orange",
    },
    {
      label: "Fraud Reports",
      value: fraudCustomers.length.toLocaleString("en-LK"),
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
      count: chatSummary.unread,
    },
    {
      id: "reviews",
      label: "Reviews",
      icon: Mail,
      count: reviews.length,
    },
    {
      id: "fraud",
      label: "Fraud Reports",
      icon: ShieldAlert,
      count: fraudCustomers.length,
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

  useEffect(() => {
    if (!business?.id) return;
    getChatSessions(business.id)
      .then((sessions) =>
        setChatSummary({
          count: sessions.length,
          unread: sessions.reduce(
            (sum, session) => sum + (session.unreadCount || 0),
            0,
          ),
        }),
      )
      .catch(() => {
        // Customer records should still load if this staff role cannot read chats.
      });
  }, [business?.id]);

  useEffect(() => {
    if (!business?.id) return;
    Promise.all([getReviews(business.id), getFraudCustomers(business.id)])
      .then(([reviewRowsResponse, fraudRowsResponse]) => {
        setReviews(reviewRowsResponse);
        setFraudCustomers(fraudRowsResponse);
      })
      .catch((error) => setErrorMessage(error.message));
  }, [business?.id]);

  async function handleModerateReview(reviewId, status) {
    try {
      const updated = await moderateReview(business.id, reviewId, status);
      setReviews((current) =>
        current.map((review) =>
          review.id === reviewId ? { ...review, ...updated } : review,
        ),
      );
    } catch (error) {
      setErrorMessage(error.message);
    }
  }

  async function handleCustomerAction() {
    if (!business?.id || !customerAction?.customer) return;

    const { type, customer } = customerAction;
    setIsCustomerActionWorking(true);
    setErrorMessage("");

    try {
      if (type === "remove") {
        await updateCustomer(business.id, customer.id, { status: "archived" });
        setCustomers((current) =>
          current.filter((item) => item.id !== customer.id),
        );
        if (expandedCustomerId === customer.id) setExpandedCustomerId(null);
      } else {
        await reportCustomer(business.id, customer.id);
        setCustomers((current) =>
          current.map((item) =>
            item.id === customer.id
              ? { ...item, riskLevel: "high", fraudReportCount: 1 }
              : item,
          ),
        );
        setFraudCustomers(await getFraudCustomers(business.id));
      }
      setCustomerAction(null);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsCustomerActionWorking(false);
    }
  }

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

      {activeCustomerTab === "messages" ? (
        <CustomerMessages
          businessId={business?.id}
          onSummaryChange={setChatSummary}
          initialSessionId={requestedSessionId}
        />
      ) : activeCustomerTab === "fraud" ? (
        <>
          <section className="customers-summary" aria-label="Fraud report summary">
            <div className="stats-grid">
              {[
                { label: "High Risk Customers", value: fraudCustomers.filter((customer) => ["high", "fraud"].includes(customer.riskLevel)).length, icon: ShieldAlert, tone: "red" },
                { label: "Medium Risk Customers", value: fraudCustomers.filter((customer) => customer.riskLevel === "medium").length, icon: ShieldAlert, tone: "orange" },
                { label: "Low Risk Customers", value: fraudCustomers.filter((customer) => customer.riskLevel === "low").length, icon: ShieldAlert, tone: "green" },
                { label: "Total Returns", value: fraudCustomers.reduce((sum, customer) => sum + (customer.returnedOrderCount ?? 0), 0), icon: RotateCcw, tone: "blue" },
              ].map((stat) => <StatCard key={stat.label} label={stat.label} value={String(stat.value)} icon={stat.icon} tone={stat.tone} />)}
            </div>
          </section>
          <FraudFilters filters={fraudFilters} setFilters={setFraudFilters} />
          <FraudTable customers={fraudRows} isLoading={isLoading} />
        </>
      ) : activeCustomerTab === "reviews" ? (
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
          <ReviewsTable
            reviews={reviewRows}
            isLoading={isLoading}
            onModerate={handleModerateReview}
          />
        </>
      ) : <section className="customer-table-card" aria-label="Customers list">
      <div className="customer-table-scroll">
      <table className="management-table all-customers-table">
        <colgroup>
          <col className="customer-column--expand" />
          <col className="customer-column--select" />
          <col className="customer-column--name" />
          <col className="customer-column--phone" />
          <col className="customer-column--email" />
          <col className="customer-column--address" />
          <col className="customer-column--orders" />
          <col className="customer-column--spent" />
          <col className="customer-column--rating" />
          <col className="customer-column--risk" />
          <col className="customer-column--actions" />
        </colgroup>
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
              <td><span className="customer-rating">{customer.rating ? `${customer.rating} ★` : "—"}</span></td>
              <td>
                <span
                  className={`management-table__badge management-table__badge--${customer.riskLevel}`}
                >
                  {customer.riskLevel}
                </span>
              </td>
              <td>
                <ActionMenu
                  label={`Open actions for ${customer.name}`}
                  items={[
                    {
                      label: "Report customer",
                      icon: <Flag size={16} aria-hidden="true" />,
                      onClick: () => setCustomerAction({ type: "report", customer }),
                    },
                    {
                      label: "Remove customer",
                      icon: <Trash2 size={16} aria-hidden="true" />,
                      danger: true,
                      onClick: () => setCustomerAction({ type: "remove", customer }),
                    },
                  ]}
                />
              </td>
            </tr>
            {expandedCustomerId === customer.id && (
              <tr key={`${customer.id}-details`} className="management-table__expanded-row">
                <td colSpan={11}>
                  <div className="customer-expanded-details">
                    <div><strong>{customer.name}</strong><span>Customer ID: {customer.id}</span><span>Joined: {customer.createdAt ? new Date(customer.createdAt).toLocaleDateString("en-LK") : "—"}</span></div>
                    <div><strong>Contact</strong><span>☎ +{customer.normalizedPhone}</span>{customer.normalizedSecondaryPhone && <span>☎ +{customer.normalizedSecondaryPhone}</span>}<span>✉ {customer.email || "No email"}</span></div>
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
              <td colSpan={11}>No matching customers found.</td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
      <CustomerTableFooter count={visibleCustomers.length} label="customers" />
      </section>}

      <ConfirmDialog
        isOpen={Boolean(customerAction)}
        title={customerAction?.type === "report" ? "Report customer" : "Remove customer"}
        message={
          customerAction?.type === "report"
            ? `Report ${customerAction?.customer?.name || "this customer"} as a fraud risk? This warning will be added to the shared fraud registry.`
            : `Remove ${customerAction?.customer?.name || "this customer"} from your customer list? Existing orders will be kept.`
        }
        confirmLabel={customerAction?.type === "report" ? "Report customer" : "Remove customer"}
        workingLabel={customerAction?.type === "report" ? "Reporting..." : "Removing..."}
        isWorking={isCustomerActionWorking}
        onCancel={() => !isCustomerActionWorking && setCustomerAction(null)}
        onConfirm={handleCustomerAction}
      />
    </main>
  );
}

function ReviewsTable({ reviews, isLoading, onModerate }) {
  return (
    <section className="customer-table-card" aria-label="Customer reviews list">
    <div className="customer-table-scroll">
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
        {reviews.map((review) => (
          <tr key={review.id}>
            <td><strong>{review.customerName || "Customer"}</strong></td>
            <td>{review.customerPhone ? `+${review.customerPhone}` : "—"}</td>
            <td>{review.customerEmail || "—"}</td>
            <td>
              <div className="review-product-cell">
                {review.productImageUrl && <img src={review.productImageUrl} alt="" />}
                <span>{review.productName || review.itemName || "Product review"}</span>
              </div>
            </td>
            <td><span className="customer-rating">{"★".repeat(Math.max(0, Math.min(5, Number(review.rating) || 0)))}{"☆".repeat(Math.max(0, 5 - (Number(review.rating) || 0)))}</span></td>
            <td>{review.reviewText || review.comment || "No written review"}</td>
            <td>{review.media?.length ? `${review.media.length} image(s)` : "—"}</td>
            <td>{review.createdAt ? new Date(review.createdAt).toLocaleDateString("en-LK") : "—"}</td>
            <td><span className={`management-table__badge management-table__badge--${review.status || "pending"}`}>{review.status || "pending"}</span></td>
            <td>
              {review.status === "pending" ? (
                <span className="review-moderation-actions">
                  <button type="button" onClick={() => onModerate(review.id, "approved")}>Approve</button>
                  <button type="button" onClick={() => onModerate(review.id, "rejected")}>Reject</button>
                </span>
              ) : (
                <span className="review-moderated-label">Moderated</span>
              )}
            </td>
          </tr>
        ))}
        {!isLoading && reviews.length === 0 && <tr><td colSpan={10}>No reviews found.</td></tr>}
      </tbody>
    </table>
    </div>
    <CustomerTableFooter count={reviews.length} label="reviews" />
    </section>
  );
}

function FraudFilters({ filters, setFilters }) {
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);

  return <section className="customers-filters fraud-filters" aria-label="Fraud report filters">
    <button className="customers-filters__mobile-toggle" type="button" onClick={() => setAreMobileFiltersOpen((isOpen) => !isOpen)} aria-expanded={areMobileFiltersOpen} aria-controls="fraud-filter-fields">
      <span><Filter size={17} /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}</span>
      {areMobileFiltersOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
    </button>
    <div id="fraud-filter-fields" className={`fraud-filters__form ${areMobileFiltersOpen ? "is-open" : ""}`}>
    <label className="customers-filters__search"><input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Search customers by name, phone or email..." /></label>
    <select value={filters.risk} onChange={(event) => setFilters((current) => ({ ...current, risk: event.target.value }))} aria-label="Risk status"><option value="all">All Risk Levels</option><option value="high">High Risk</option><option value="medium">Medium Risk</option><option value="low">Low Risk</option></select>
    <select value={filters.reason} onChange={(event) => setFilters((current) => ({ ...current, reason: event.target.value }))} aria-label="Return reason"><option value="all">All Ratings</option><option value="Unreachable">Unreachable</option><option value="Refused Delivery">Refused Delivery</option><option value="Change of Mind">Change of Mind</option><option value="Address Incomplete">Address Incomplete</option></select>
    <select value={filters.score} onChange={(event) => setFilters((current) => ({ ...current, score: event.target.value }))} aria-label="Fraud score"><option value="all">All Locations</option><option value="high">High score</option><option value="medium">Medium score</option><option value="low">Low score</option></select>
    <button type="button" className="customers-filters__button"><Filter size={15} /> More Filters</button>
    <button type="button" className="customers-filters__reset" onClick={() => setFilters({ search: "", risk: "all", reason: "all", score: "all" })}><RotateCcw size={15} /> Reset</button>
    </div>
  </section>;
}

function FraudTable({ customers, isLoading }) {
  return <section className="customer-table-card" aria-label="Fraud reports list"><div className="customer-table-scroll"><table className="management-table fraud-table"><thead><tr><th>Customer</th><th>Phone</th><th>Email</th><th>Address</th><th>Returned Orders</th><th>Total Orders</th><th>Return Rate</th><th>Fraud Score</th><th>Last Returned</th><th>Reason</th><th>Risk Status</th><th>Actions</th></tr></thead><tbody>
    {customers.map((customer) => {
      const returned = customer.returnedOrderCount ?? 0;
      const total = customer.totalOrderCount ?? customer.completedOrderCount ?? returned;
      const score = customer.fraudScore ?? Math.min(99, returned * 15);
      const risk = customer.riskLevel || "low";
      const address = customer.defaultAddress || customer.address || {};
      return <tr key={customer.id}><td><strong>{customer.name}</strong></td><td>+{customer.normalizedPhone || "—"}</td><td>{customer.email || "—"}</td><td>{[address.line1, address.city].filter(Boolean).join(", ") || "—"}</td><td>{returned}</td><td>{total}</td><td>{total ? `${Math.round((returned / total) * 100)}%` : "0%"}</td><td><span className={`fraud-score fraud-score--${risk}`}>{score}</span></td><td>{customer.lastReturnedOrderDate || "—"}</td><td>{customer.returnReason || customer.fraudReason || "Unspecified"}</td><td><span className={`management-table__badge management-table__badge--${risk}`}>{risk} risk</span></td><td><button type="button" className="customer-action-button" aria-label={`Open ${customer.name} fraud actions`}>•••</button></td></tr>;
    })}
    {!isLoading && customers.length === 0 && <tr><td colSpan={12}>No fraud reports found.</td></tr>}
  </tbody></table></div><CustomerTableFooter count={customers.length} label="reports" /></section>;
}

function CustomerTableFooter({ count, label }) {
  return (
    <footer className="customer-table-footer">
      <span>
        Showing {count === 0 ? 0 : 1} to {count} of {count} {label}
      </span>
      <div className="customer-table-pagination" aria-label={`${label} pagination`}>
        <button type="button" disabled>Previous</button>
        <button className="is-active" type="button" aria-current="page">1</button>
        <button type="button" disabled={count === 0}>2</button>
        <button type="button" disabled={count === 0}>3</button>
        <button type="button" disabled={count === 0}>Next</button>
      </div>
    </footer>
  );
}

export default CustomersPage;
