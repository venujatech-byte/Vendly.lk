import {
  BadgeDollarSign,
  ChevronDown,
  CircleDollarSign,
  Filter,
  RotateCcw,
  Search,
  TriangleAlert,
  UsersRound,
} from "lucide-react";
import { useMemo, useState } from "react";

import useTablePagination from "../hooks/useTablePagination";
import { formatAnalyticsMoney } from "../services/analyticsService";
import StatCard from "./StatCard";
import TablePagination from "./TablePagination";
import "./OrderFilters.css";
import "./CustomerProfitability.css";

const EMPTY_FILTERS = {
  search: "",
  profitability: "all",
  returnRisk: "all",
};

function formatDate(value) {
  if (!value) return "No orders";
  return new Date(value).toLocaleDateString("en-LK", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatPhone(value) {
  if (!value) return "No phone";
  return value.startsWith("94") ? `+${value}` : value;
}

function CustomerProfitability({ report, isLoading }) {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
  const customers = report?.customers ?? [];
  const summary = report?.summary ?? {};

  const filteredCustomers = useMemo(() => {
    const needle = filters.search.trim().toLowerCase();
    return customers.filter((customer) => (
      (!needle || [customer.name, customer.phoneNumber, customer.email]
        .join(" ").toLowerCase().includes(needle))
      && (filters.profitability === "all"
        || customer.profitabilityState === filters.profitability)
      && (filters.returnRisk === "all"
        || (filters.returnRisk === "high" && customer.isHighReturn)
        || (filters.returnRisk === "healthy" && !customer.isHighReturn))
    ));
  }, [customers, filters]);
  const pagination = useTablePagination(filteredCustomers);

  return (
    <section className="customer-profitability" aria-labelledby="customer-profitability-title">
      <header className="customer-profitability__intro">
        <div>
          <span>Customer intelligence</span>
          <h3 id="customer-profitability-title">Customer profitability</h3>
          <p>Compare delivered product revenue, discounts, product cost, gross profit and return behaviour for every customer.</p>
        </div>
        <UsersRound aria-hidden="true" />
      </header>

      <div className="customer-profitability__stats">
        <StatCard label="Customers" value={String(summary.customerCount ?? 0)} icon={UsersRound} tone="blue" />
        <StatCard label="Customer revenue" value={formatAnalyticsMoney(summary.productRevenueMinor)} icon={CircleDollarSign} tone="purple" />
        <StatCard label="Gross profit" value={formatAnalyticsMoney(summary.grossProfitMinor)} icon={BadgeDollarSign} tone="green" />
        <StatCard label="High return" value={String(summary.highReturnCustomerCount ?? 0)} icon={TriangleAlert} tone="orange" />
      </div>

      <section className="filter-panel" aria-label="Customer profitability filters">
        <button
          className="filter-panel__mobile-toggle"
          type="button"
          aria-expanded={areMobileFiltersOpen}
          aria-controls="customer-profitability-filter-fields"
          onClick={() => setAreMobileFiltersOpen((value) => !value)}
        >
          <span><Filter size={17} /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}</span>
          <ChevronDown className={areMobileFiltersOpen ? "is-open" : ""} size={18} />
        </button>
        <div id="customer-profitability-filter-fields" className={`filter-panel__form customer-profitability__filter-form ${areMobileFiltersOpen ? "is-open" : ""}`}>
          <label className="filter-panel__field filter-panel__field--search">
            <span className="customer-profitability__field-label">Search</span>
            <span className="filter-panel__icon-field"><Search size={16} /><input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Customer, phone or email..." /></span>
          </label>
          <label className="filter-panel__field">
            <span className="customer-profitability__field-label">Profitability</span>
            <select value={filters.profitability} onChange={(event) => setFilters((current) => ({ ...current, profitability: event.target.value }))}>
              <option value="all">All customers</option>
              <option value="profitable">Profitable</option>
              <option value="low-margin">Low margin</option>
              <option value="loss">Loss making</option>
              <option value="no-sales">No delivered sales</option>
            </select>
          </label>
          <label className="filter-panel__field">
            <span className="customer-profitability__field-label">Return risk</span>
            <select value={filters.returnRisk} onChange={(event) => setFilters((current) => ({ ...current, returnRisk: event.target.value }))}>
              <option value="all">All return levels</option>
              <option value="healthy">Below 30%</option>
              <option value="high">30% or higher</option>
            </select>
          </label>
          <button className="filter-panel__apply" type="button"><Filter size={15} /> Filter</button>
          <button className="filter-panel__reset filter-panel__reset--text" type="button" onClick={() => setFilters(EMPTY_FILTERS)}><RotateCcw size={15} /> Reset</button>
        </div>
      </section>

      <div className="customer-profitability__table-shell">
        <table>
          <thead><tr><th>Customer</th><th>Orders</th><th>Revenue</th><th>Discounts</th><th>Product cost</th><th>Gross profit</th><th>Margin</th><th>Returns</th><th>Last order</th></tr></thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan="9">Loading customer profitability...</td></tr>
            ) : pagination.pageItems.length === 0 ? (
              <tr><td colSpan="9">No customers match these filters.</td></tr>
            ) : pagination.pageItems.map((customer) => (
              <tr key={customer.id}>
                <td><span className="customer-profitability__customer"><i>{customer.name.slice(0, 2).toUpperCase()}</i><span><strong>{customer.name}</strong><small>{formatPhone(customer.phoneNumber)}{customer.email ? ` · ${customer.email}` : ""}</small></span></span></td>
                <td><strong>{customer.orderCount}</strong><small>{customer.deliveredOrderCount} delivered</small></td>
                <td><strong>{formatAnalyticsMoney(customer.productRevenueMinor)}</strong><small>{formatAnalyticsMoney(customer.averageOrderValueMinor)} average</small></td>
                <td>{formatAnalyticsMoney(customer.discountTotalMinor)}</td>
                <td>{formatAnalyticsMoney(customer.costOfGoodsMinor)}</td>
                <td><strong className={customer.grossProfitMinor < 0 ? "is-loss" : "is-profit"}>{formatAnalyticsMoney(customer.grossProfitMinor)}</strong></td>
                <td><span className={`customer-profitability__state is-${customer.profitabilityState}`}>{customer.profitabilityState === "no-sales" ? "No sales" : `${customer.grossMarginPercent}%`}</span></td>
                <td><strong>{customer.returnedOrderCount}</strong><small className={customer.isHighReturn ? "is-risk" : ""}>{customer.returnRatePercent}% rate</small></td>
                <td>{formatDate(customer.lastOrderAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && <TablePagination pagination={pagination} label="customers" />}
      </div>
    </section>
  );
}

export default CustomerProfitability;
