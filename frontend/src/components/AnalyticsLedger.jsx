import {
  BanknoteArrowDown,
  BanknoteArrowUp,
  ChevronDown,
  Filter,
  ReceiptText,
  RotateCcw,
  Search,
  WalletCards,
} from "lucide-react";
import { useMemo, useState } from "react";

import useTablePagination from "../hooks/useTablePagination";
import { formatAnalyticsMoney } from "../services/analyticsService";
import StatCard from "./StatCard";
import TablePagination from "./TablePagination";
import "./OrderFilters.css";
import "./AnalyticsLedger.css";


const TRANSACTION_TYPES = [
  ["all", "All transactions"],
  ["online-order", "Online orders"],
  ["shop-sale", "Shop sales"],
  ["returned", "Order returns"],
  ["cancelled", "Order cancellations"],
  ["voided-sale", "Voided shop sales"],
  ["warranty-adjustment", "Warranty adjustments"],
];


function dateKey(value) {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value).slice(0, 10) : parsed.toISOString().slice(0, 10);
}


function displayDate(value) {
  if (!value) return { date: "Date unavailable", time: "" };
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return { date: String(value), time: "" };
  return {
    date: parsed.toLocaleDateString("en-LK", { year: "numeric", month: "short", day: "numeric" }),
    time: parsed.toLocaleTimeString("en-LK", { hour: "2-digit", minute: "2-digit" }),
  };
}


function AnalyticsLedger({ ledger, isLoading, error }) {
  const [filters, setFilters] = useState({ search: "", type: "all", dateFrom: "", dateTo: "" });
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);

  const filteredEntries = useMemo(() => {
    const needle = filters.search.trim().toLowerCase();
    return (ledger?.entries ?? []).filter((entry) => {
      const entryDate = dateKey(entry.createdAt);
      const searchable = [entry.reference, entry.customerName, entry.description, entry.label, entry.paymentMethod, entry.status]
        .join(" ")
        .toLowerCase();
      return (!needle || searchable.includes(needle))
        && (filters.type === "all" || entry.transactionType === filters.type)
        && (!filters.dateFrom || entryDate >= filters.dateFrom)
        && (!filters.dateTo || entryDate <= filters.dateTo);
    });
  }, [filters, ledger?.entries]);

  const filteredSummary = useMemo(() => {
    const creditMinor = filteredEntries.reduce(
      (total, entry) => total + (entry.direction === "credit" ? entry.amountMinor : 0),
      0,
    );
    const debitMinor = filteredEntries.reduce(
      (total, entry) => total + (entry.direction === "debit" ? entry.amountMinor : 0),
      0,
    );
    return { creditMinor, debitMinor, netMinor: creditMinor - debitMinor };
  }, [filteredEntries]);

  const pagination = useTablePagination(filteredEntries);

  function resetFilters() {
    setFilters({ search: "", type: "all", dateFrom: "", dateTo: "" });
  }

  if (error) {
    return <section className="analytics-ledger analytics-ledger--message" role="alert">The transaction ledger could not be loaded.</section>;
  }

  return (
    <section className="analytics-ledger" aria-labelledby="ledger-title">
      <header className="analytics-ledger__intro">
        <div>
          <span>Sales and adjustments</span>
          <h3 id="ledger-title">Transaction ledger</h3>
          <p>Trace every online order, shop sale, reversal and warranty deduction in one place.</p>
        </div>
        <ReceiptText aria-hidden="true" />
      </header>

      <div className="analytics-ledger__stats" aria-label="Filtered ledger totals">
        <StatCard label="Transactions" value={String(filteredEntries.length)} icon={ReceiptText} tone="blue" />
        <StatCard label="Money in" value={formatAnalyticsMoney(filteredSummary.creditMinor)} icon={BanknoteArrowUp} tone="green" />
        <StatCard label="Money out" value={formatAnalyticsMoney(filteredSummary.debitMinor)} icon={BanknoteArrowDown} tone="red" />
        <StatCard label="Net movement" value={formatAnalyticsMoney(filteredSummary.netMinor)} icon={WalletCards} tone="purple" />
      </div>

      <section className="analytics-ledger__filters filter-panel" aria-label="Ledger filters">
        <button
          className="filter-panel__mobile-toggle"
          type="button"
          aria-expanded={areMobileFiltersOpen}
          aria-controls="ledger-filter-fields"
          onClick={() => setAreMobileFiltersOpen((isOpen) => !isOpen)}
        >
          <span><Filter size={17} /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}</span>
          <ChevronDown className={areMobileFiltersOpen ? "is-open" : ""} size={18} />
        </button>
        <div id="ledger-filter-fields" className={`analytics-ledger__filter-form filter-panel__form ${areMobileFiltersOpen ? "is-open" : ""}`}>
          <label className="filter-panel__field filter-panel__field--search">
            <span className="analytics-ledger__field-label">Search</span>
            <span className="filter-panel__icon-field"><Search size={16} /><input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Reference, customer, item or payment..." /></span>
          </label>
          <label className="filter-panel__field">
            <span className="analytics-ledger__field-label">Transaction type</span>
            <select value={filters.type} onChange={(event) => setFilters((current) => ({ ...current, type: event.target.value }))}>
              {TRANSACTION_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="filter-panel__field">
            <span className="analytics-ledger__field-label">From</span>
            <input type="date" value={filters.dateFrom} onChange={(event) => setFilters((current) => ({ ...current, dateFrom: event.target.value }))} />
          </label>
          <label className="filter-panel__field">
            <span className="analytics-ledger__field-label">To</span>
            <input type="date" value={filters.dateTo} onChange={(event) => setFilters((current) => ({ ...current, dateTo: event.target.value }))} />
          </label>
          <button className="filter-panel__apply" type="button"><Filter size={15} /> Filter</button>
          <button className="filter-panel__reset filter-panel__reset--text" type="button" onClick={resetFilters}><RotateCcw size={15} /> Reset</button>
        </div>
      </section>

      <div className="analytics-ledger__table-shell">
        <table className="analytics-ledger__table">
          <thead><tr><th>Date</th><th>Reference</th><th>Type</th><th>Customer &amp; details</th><th>Payment</th><th>Money in</th><th>Money out</th><th>Balance</th></tr></thead>
          <tbody>
            {isLoading ? (
              <tr><td className="analytics-ledger__empty" colSpan="8">Loading transactions...</td></tr>
            ) : pagination.pageItems.length === 0 ? (
              <tr><td className="analytics-ledger__empty" colSpan="8">No transactions match these filters.</td></tr>
            ) : pagination.pageItems.map((entry) => {
              const displayed = displayDate(entry.createdAt);
              return (
                <tr key={entry.id} className={`analytics-ledger__row analytics-ledger__row--${entry.direction}`}>
                  <td data-label="Date"><strong>{displayed.date}</strong><small>{displayed.time}</small></td>
                  <td data-label="Reference"><strong>{entry.reference}</strong><small>{entry.status?.replaceAll("-", " ")}</small></td>
                  <td data-label="Type"><span className={`analytics-ledger__type analytics-ledger__type--${entry.direction}`}>{entry.label}</span></td>
                  <td data-label="Details"><strong>{entry.customerName}</strong><small>{entry.description}</small></td>
                  <td data-label="Payment"><strong>{entry.paymentMethod?.replaceAll("-", " ")}</strong><small>{entry.paymentStatus?.replaceAll("-", " ")}</small></td>
                  <td data-label="Money in" className="analytics-ledger__money analytics-ledger__money--credit">{entry.direction === "credit" ? formatAnalyticsMoney(entry.amountMinor) : "—"}</td>
                  <td data-label="Money out" className="analytics-ledger__money analytics-ledger__money--debit">{entry.direction === "debit" ? formatAnalyticsMoney(entry.amountMinor) : "—"}</td>
                  <td data-label="Balance" className="analytics-ledger__balance">{formatAnalyticsMoney(entry.balanceMinor)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!isLoading && <TablePagination pagination={pagination} label="transactions" />}
      </div>

      <p className="analytics-ledger__note">This is a sales activity ledger derived from Vendly records. It is not a bank statement or a double-entry accounting report.</p>
    </section>
  );
}


export default AnalyticsLedger;
