import { AlertTriangle, Banknote, ChevronDown, CircleDollarSign, Filter, RotateCcw, Search, WalletCards, X } from "lucide-react";
import { useMemo, useState } from "react";

import useTablePagination from "../hooks/useTablePagination";
import { formatAnalyticsMoney, saveCodSettlement } from "../services/analyticsService";
import StatCard from "./StatCard";
import TablePagination from "./TablePagination";
import "./OrderFilters.css";
import "./CodReconciliation.css";


const EMPTY_FORM = {
  amountCollected: "", courierCharge: "", receivedSettlement: "",
  settlementDate: "", settlementReference: "", note: "", isDisputed: false,
};

function toMajor(minor) {
  return minor === undefined || minor === null ? "" : String(minor / 100);
}

function toMinor(value) {
  return Math.round(Math.max(Number(value) || 0, 0) * 100);
}

function CodReconciliation({ businessId, reconciliation, isLoading, error, onChange }) {
  const [filters, setFilters] = useState({ search: "", status: "all", courier: "all" });
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const couriers = useMemo(() => [...new Set((reconciliation?.entries ?? []).map((item) => item.courierName))].sort(), [reconciliation]);
  const entries = useMemo(() => {
    const needle = filters.search.trim().toLowerCase();
    return (reconciliation?.entries ?? []).filter((entry) => (
      (!needle || [entry.orderNumber, entry.customerName, entry.courierName, entry.settlementReference].join(" ").toLowerCase().includes(needle))
      && (filters.status === "all" || entry.status === filters.status)
      && (filters.courier === "all" || entry.courierName === filters.courier)
    ));
  }, [filters, reconciliation]);
  const pagination = useTablePagination(entries);
  const summary = reconciliation?.summary ?? {};

  function openSettlement(entry) {
    setEditing(entry);
    setSaveError("");
    setForm({
      amountCollected: toMajor(entry.amountCollectedMinor || entry.expectedCollectionMinor),
      courierCharge: toMajor(entry.courierChargeMinor),
      receivedSettlement: toMajor(entry.receivedSettlementMinor),
      settlementDate: entry.settlementDate || "",
      settlementReference: entry.settlementReference || "",
      note: entry.note || "",
      isDisputed: entry.isDisputed,
    });
  }

  async function save(event) {
    event.preventDefault();
    setIsSaving(true);
    setSaveError("");
    try {
      const next = await saveCodSettlement(businessId, editing.orderId, {
        amountCollectedMinor: toMinor(form.amountCollected),
        courierChargeMinor: toMinor(form.courierCharge),
        receivedSettlementMinor: toMinor(form.receivedSettlement),
        settlementDate: form.settlementDate,
        settlementReference: form.settlementReference,
        note: form.note,
        isDisputed: form.isDisputed,
      });
      onChange(next);
      setEditing(null);
    } catch (requestError) {
      setSaveError(requestError.message || "The settlement could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  if (error) return <section className="cod-reconciliation cod-reconciliation--message" role="alert">COD reconciliation could not be loaded.</section>;

  return (
    <section className="cod-reconciliation" aria-labelledby="cod-title">
      <header className="cod-reconciliation__intro">
        <div><span>Courier collections</span><h3 id="cod-title">COD reconciliation</h3><p>Compare delivered COD balances with courier charges and settlements received.</p></div>
        <WalletCards aria-hidden="true" />
      </header>

      <div className="cod-reconciliation__stats">
        <StatCard label="Expected settlement" value={formatAnalyticsMoney(summary.expectedSettlementMinor)} icon={CircleDollarSign} tone="blue" />
        <StatCard label="Received" value={formatAnalyticsMoney(summary.receivedSettlementMinor)} icon={Banknote} tone="green" />
        <StatCard label="Variance" value={formatAnalyticsMoney(summary.varianceMinor)} icon={WalletCards} tone="purple" />
        <StatCard label="Overdue" value={String(summary.overdueCount ?? 0)} icon={AlertTriangle} tone="red" />
      </div>

      <section className="cod-reconciliation__filters filter-panel" aria-label="COD reconciliation filters">
        <button
          className="filter-panel__mobile-toggle"
          type="button"
          aria-expanded={areMobileFiltersOpen}
          aria-controls="cod-reconciliation-filter-fields"
          onClick={() => setAreMobileFiltersOpen((value) => !value)}
        >
          <span><Filter size={17} /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}</span>
          <ChevronDown className={areMobileFiltersOpen ? "is-open" : ""} size={18} />
        </button>
        <div id="cod-reconciliation-filter-fields" className={`filter-panel__form cod-reconciliation__filter-form ${areMobileFiltersOpen ? "is-open" : ""}`}>
          <label className="filter-panel__field filter-panel__field--search"><span className="cod-reconciliation__field-label">Search</span><span className="filter-panel__icon-field"><Search size={16} /><input value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="Order, customer, courier or reference..." /></span></label>
          <label className="filter-panel__field"><span className="cod-reconciliation__field-label">Status</span><select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}><option value="all">All statuses</option>{["unreconciled", "pending", "partial", "reconciled", "disputed"].map((status) => <option key={status} value={status}>{status.replaceAll("-", " ")}</option>)}</select></label>
          <label className="filter-panel__field"><span className="cod-reconciliation__field-label">Courier</span><select value={filters.courier} onChange={(event) => setFilters((current) => ({ ...current, courier: event.target.value }))}><option value="all">All couriers</option>{couriers.map((courier) => <option key={courier}>{courier}</option>)}</select></label>
          <button className="filter-panel__apply" type="button"><Filter size={15} /> Filter</button>
          <button className="filter-panel__reset filter-panel__reset--text" type="button" onClick={() => setFilters({ search: "", status: "all", courier: "all" })}><RotateCcw size={15} /> Reset</button>
        </div>
      </section>

      <div className="cod-reconciliation__table-shell">
        <table><thead><tr><th>Order</th><th>Customer</th><th>Courier</th><th>COD due</th><th>Courier fee</th><th>Expected</th><th>Received</th><th>Variance</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>{isLoading ? <tr><td colSpan="10">Loading reconciliation...</td></tr> : pagination.pageItems.length === 0 ? <tr><td colSpan="10">No delivered COD orders match these filters.</td></tr> : pagination.pageItems.map((entry) => (
            <tr key={entry.orderId} className={entry.isOverdue ? "is-overdue" : ""}>
              <td data-label="Order"><strong>{entry.orderNumber}</strong><small>{entry.deliveredAt ? new Date(entry.deliveredAt).toLocaleDateString("en-LK") : "Delivered"}</small></td>
              <td data-label="Customer">{entry.customerName}</td><td data-label="Courier">{entry.courierName}</td>
              <td data-label="COD due">{formatAnalyticsMoney(entry.expectedCollectionMinor)}</td><td data-label="Courier fee">{formatAnalyticsMoney(entry.courierChargeMinor)}</td>
              <td data-label="Expected">{formatAnalyticsMoney(entry.expectedSettlementMinor)}</td><td data-label="Received">{formatAnalyticsMoney(entry.receivedSettlementMinor)}</td>
              <td data-label="Variance" className={entry.varianceMinor < 0 ? "is-negative" : ""}>{formatAnalyticsMoney(entry.varianceMinor)}</td>
              <td data-label="Status"><span className={`cod-reconciliation__status is-${entry.status}`}>{entry.isOverdue ? "overdue" : entry.status}</span></td>
              <td data-label="Action"><button className="cod-reconciliation__record" type="button" onClick={() => openSettlement(entry)}>Record</button></td>
            </tr>))}</tbody></table>
        {!isLoading && <TablePagination pagination={pagination} label="COD orders" />}
      </div>

      {editing && <div className="cod-reconciliation__overlay" role="presentation"><form className="cod-reconciliation__dialog" onSubmit={save}><header><div><span>Courier settlement</span><h3>{editing.orderNumber}</h3></div><button type="button" onClick={() => setEditing(null)} aria-label="Close"><X /></button></header>
        <div className="cod-reconciliation__form-grid">
          <label>Amount collected (LKR)<input type="number" min="0" step="0.01" value={form.amountCollected} onChange={(event) => setForm((current) => ({ ...current, amountCollected: event.target.value }))} /></label>
          <label>Courier charges (LKR)<input type="number" min="0" step="0.01" value={form.courierCharge} onChange={(event) => setForm((current) => ({ ...current, courierCharge: event.target.value }))} /></label>
          <label>Settlement received (LKR)<input type="number" min="0" step="0.01" value={form.receivedSettlement} onChange={(event) => setForm((current) => ({ ...current, receivedSettlement: event.target.value }))} /></label>
          <label>Settlement date<input type="date" value={form.settlementDate} onChange={(event) => setForm((current) => ({ ...current, settlementDate: event.target.value }))} /></label>
          <label className="is-wide">Reference<input value={form.settlementReference} onChange={(event) => setForm((current) => ({ ...current, settlementReference: event.target.value }))} placeholder="Courier statement or bank reference" /></label>
          <label className="is-wide">Private note<textarea value={form.note} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))} /></label>
          <label className="is-check is-wide"><input type="checkbox" checked={form.isDisputed} onChange={(event) => setForm((current) => ({ ...current, isDisputed: event.target.checked }))} /> Mark this settlement as disputed</label>
        </div>{saveError && <p role="alert">{saveError}</p>}<footer><button type="button" onClick={() => setEditing(null)}>Cancel</button><button type="submit" disabled={isSaving}>{isSaving ? "Saving..." : "Save settlement"}</button></footer>
      </form></div>}
    </section>
  );
}

export default CodReconciliation;
