import {
  AlertTriangle,
  Banknote,
  CheckSquare,
  ChevronDown,
  CircleDollarSign,
  DollarSign,
  Funnel,
  Layers,
  RotateCcw,
  Search,
  Trash2,
  WalletCards,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import useTablePagination from "../hooks/useTablePagination";
import {
  formatAnalyticsMoney,
  saveBulkCodSettlements,
  saveCodSettlement,
} from "../services/analyticsService";
import StatCard from "./StatCard";
import TablePagination from "./TablePagination";
import CustomSelect from "./CustomSelect";
import "./OrderFilters.css";
import "./OrderTable.css";
import "./CodReconciliation.css";


const EMPTY_FORM = {
  amountCollected: "",
  courierCharge: "",
  receivedSettlement: "",
  settlementDate: "",
  settlementReference: "",
  note: "",
  isDisputed: false,
};

function toMajor(minor) {
  return minor === undefined || minor === null ? "" : String(minor / 100);
}

function toMinor(value) {
  return Math.round(Math.max(Number(value) || 0, 0) * 100);
}

function getTodayIso() {
  return new Date().toISOString().split("T")[0];
}

function CodReconciliation({ businessId, reconciliation, isLoading, error, onChange }) {
  const [filters, setFilters] = useState({ search: "", status: "all", courier: "all" });
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
  const [selectedOrderIds, setSelectedOrderIds] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Bulk Modal State
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [bulkSharedForm, setBulkSharedForm] = useState({
    settlementDate: getTodayIso(),
    settlementReference: "",
    note: "",
    isDisputed: false,
    flatCourierFee: "",
  });
  const [bulkItems, setBulkItems] = useState([]);
  const [bulkSaveError, setBulkSaveError] = useState("");
  const [isBulkSaving, setIsBulkSaving] = useState(false);

  const couriers = useMemo(
    () => [...new Set((reconciliation?.entries ?? []).map((item) => item.courierName))].sort(),
    [reconciliation],
  );

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

  // Escape key listener for modals and body scroll lock
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        if (editing) setEditing(null);
        if (isBulkModalOpen) setIsBulkModalOpen(false);
      }
    }
    if (editing || isBulkModalOpen) {
      document.body.classList.add("modal-is-open");
    } else {
      document.body.classList.remove("modal-is-open");
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("modal-is-open");
    };
  }, [editing, isBulkModalOpen]);

  // Selection handlers
  const visibleEntries = pagination.pageItems;
  const visibleOrderIds = visibleEntries.map((item) => item.orderId);
  const allVisibleSelected =
    visibleOrderIds.length > 0 && visibleOrderIds.every((id) => selectedOrderIds.includes(id));

  function toggleSelectOrder(orderId) {
    setSelectedOrderIds((current) =>
      current.includes(orderId) ? current.filter((id) => id !== orderId) : [...current, orderId],
    );
  }

  function toggleSelectAllVisible() {
    if (allVisibleSelected) {
      setSelectedOrderIds((current) => current.filter((id) => !visibleOrderIds.includes(id)));
    } else {
      setSelectedOrderIds((current) => [...new Set([...current, ...visibleOrderIds])]);
    }
  }

  function selectAllFiltered() {
    setSelectedOrderIds(entries.map((item) => item.orderId));
  }

  function deselectAll() {
    setSelectedOrderIds([]);
  }

  // Single order settlement
  function openSettlement(entry) {
    setEditing(entry);
    setSaveError("");
    setForm({
      amountCollected: toMajor(entry.amountCollectedMinor || entry.expectedCollectionMinor),
      courierCharge: toMajor(entry.courierChargeMinor),
      receivedSettlement: toMajor(entry.receivedSettlementMinor || Math.max((entry.amountCollectedMinor || entry.expectedCollectionMinor) - entry.courierChargeMinor, 0)),
      settlementDate: entry.settlementDate || getTodayIso(),
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

  // Bulk settlement initialization
  function openBulkSettlement() {
    const selectedEntries = (reconciliation?.entries ?? []).filter((entry) =>
      selectedOrderIds.includes(entry.orderId),
    );
    if (!selectedEntries.length) return;

    setBulkSharedForm({
      settlementDate: getTodayIso(),
      settlementReference: "",
      note: "",
      isDisputed: false,
      flatCourierFee: "",
    });
    setBulkItems(
      selectedEntries.map((entry) => {
        const collectedMinor = entry.amountCollectedMinor || entry.expectedCollectionMinor;
        const courierFeeMinor = entry.courierChargeMinor || 0;
        const receivedMinor = entry.receivedSettlementMinor || Math.max(collectedMinor - courierFeeMinor, 0);
        return {
          orderId: entry.orderId,
          orderNumber: entry.orderNumber,
          customerName: entry.customerName,
          courierName: entry.courierName,
          expectedCollectionMinor: entry.expectedCollectionMinor,
          amountCollected: toMajor(collectedMinor),
          courierCharge: toMajor(courierFeeMinor),
          receivedSettlement: toMajor(receivedMinor),
        };
      }),
    );
    setBulkSaveError("");
    setIsBulkModalOpen(true);
  }

  function handleBulkItemChange(orderId, field, value) {
    setBulkItems((items) =>
      items.map((item) => {
        if (item.orderId !== orderId) return item;
        const updated = { ...item, [field]: value };
        // If updating collected or courier charge in full-settlement mindset, auto compute received
        if (field === "amountCollected" || field === "courierCharge") {
          const col = Number(field === "amountCollected" ? value : item.amountCollected) || 0;
          const fee = Number(field === "courierCharge" ? value : item.courierCharge) || 0;
          updated.receivedSettlement = String(Math.max(col - fee, 0));
        }
        return updated;
      }),
    );
  }

  function handleApplyFlatCourierFee(feeValue) {
    setBulkSharedForm((current) => ({ ...current, flatCourierFee: feeValue }));
    if (feeValue === "") return;
    const feeNum = Number(feeValue) || 0;
    setBulkItems((items) =>
      items.map((item) => {
        const col = Number(item.amountCollected) || 0;
        return {
          ...item,
          courierCharge: feeValue,
          receivedSettlement: String(Math.max(col - feeNum, 0)),
        };
      }),
    );
  }

  function handleMarkAllFullSettlement() {
    setBulkItems((items) =>
      items.map((item) => {
        const col = Number(item.amountCollected || toMajor(item.expectedCollectionMinor)) || 0;
        const fee = Number(item.courierCharge) || 0;
        return {
          ...item,
          receivedSettlement: String(Math.max(col - fee, 0)),
        };
      }),
    );
  }

  function removeBulkItem(orderId) {
    setBulkItems((items) => items.filter((item) => item.orderId !== orderId));
    setSelectedOrderIds((ids) => ids.filter((id) => id !== orderId));
  }

  async function saveBulk(event) {
    event.preventDefault();
    if (!bulkItems.length) {
      setBulkSaveError("No orders selected to record.");
      return;
    }
    setIsBulkSaving(true);
    setBulkSaveError("");
    try {
      const payload = {
        settlements: bulkItems.map((item) => ({
          orderId: item.orderId,
          amountCollectedMinor: toMinor(item.amountCollected),
          courierChargeMinor: toMinor(item.courierCharge),
          receivedSettlementMinor: toMinor(item.receivedSettlement),
          settlementDate: bulkSharedForm.settlementDate,
          settlementReference: bulkSharedForm.settlementReference,
          note: bulkSharedForm.note,
          isDisputed: bulkSharedForm.isDisputed,
        })),
      };
      const next = await saveBulkCodSettlements(businessId, payload);
      onChange(next);
      setIsBulkModalOpen(false);
      setSelectedOrderIds([]);
    } catch (requestError) {
      setBulkSaveError(requestError.message || "Bulk settlements could not be recorded.");
    } finally {
      setIsBulkSaving(false);
    }
  }

  // Selected totals for bulk bar
  const selectedEntries = useMemo(() => {
    return (reconciliation?.entries ?? []).filter((e) => selectedOrderIds.includes(e.orderId));
  }, [reconciliation, selectedOrderIds]);

  const selectedTotalCodMinor = useMemo(() => {
    return selectedEntries.reduce((sum, e) => sum + (e.expectedCollectionMinor || 0), 0);
  }, [selectedEntries]);

  const selectedTotalExpectedMinor = useMemo(() => {
    return selectedEntries.reduce((sum, e) => sum + (e.expectedSettlementMinor || 0), 0);
  }, [selectedEntries]);

  // Bulk modal live totals
  const bulkTotalCollectedMinor = useMemo(() => {
    return bulkItems.reduce((sum, item) => sum + toMinor(item.amountCollected), 0);
  }, [bulkItems]);

  const bulkTotalCourierChargesMinor = useMemo(() => {
    return bulkItems.reduce((sum, item) => sum + toMinor(item.courierCharge), 0);
  }, [bulkItems]);

  const bulkTotalReceivedMinor = useMemo(() => {
    return bulkItems.reduce((sum, item) => sum + toMinor(item.receivedSettlement), 0);
  }, [bulkItems]);

  const bulkTotalExpectedMinor = Math.max(bulkTotalCollectedMinor - bulkTotalCourierChargesMinor, 0);
  const bulkVarianceMinor = bulkTotalReceivedMinor - bulkTotalExpectedMinor;

  if (error) {
    return (
      <section className="cod-reconciliation cod-reconciliation--message" role="alert">
        COD reconciliation could not be loaded.
      </section>
    );
  }

  return (
    <section className="cod-reconciliation" aria-labelledby="cod-title">
      <div className="cod-reconciliation__stats stats-grid">
        <StatCard
          label="Expected settlement"
          value={formatAnalyticsMoney(summary.expectedSettlementMinor)}
          icon={CircleDollarSign}
          tone="blue"
        />
        <StatCard
          label="Received"
          value={formatAnalyticsMoney(summary.receivedSettlementMinor)}
          icon={Banknote}
          tone="green"
        />
        <StatCard
          label="Variance"
          value={formatAnalyticsMoney(summary.varianceMinor)}
          icon={WalletCards}
          tone="purple"
        />
        <StatCard
          label="Overdue"
          value={String(summary.overdueCount ?? 0)}
          icon={AlertTriangle}
          tone="red"
        />
      </div>

      <section className="orders-table-section cod-reconciliation__table-card">
        <div className="orders-table__filters-wrapper">
          <section className="cod-reconciliation__filters filter-panel" aria-label="COD reconciliation filters">
            <button
              className="filter-panel__mobile-toggle"
              type="button"
              aria-expanded={areMobileFiltersOpen}
              aria-controls="cod-reconciliation-filter-fields"
              onClick={() => setAreMobileFiltersOpen((value) => !value)}
            >
              <span>
                <Funnel size={17} aria-hidden="true" /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}
              </span>
              <ChevronDown className={areMobileFiltersOpen ? "is-open" : ""} size={18} aria-hidden="true" />
            </button>
            <div
              id="cod-reconciliation-filter-fields"
              className={`filter-panel__form cod-reconciliation__filter-form ${
                areMobileFiltersOpen ? "is-open" : ""
              }`}
            >
              <div className="filter-panel__field filter-panel__field--search">
                <Search size={15} className="filter-panel__search-icon" aria-hidden="true" />
                <input
                  type="search"
                  value={filters.search}
                  onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
                  placeholder="Search order, customer, courier or reference..."
                />
                {filters.search && (
                  <button
                    type="button"
                    className="filter-panel__clear"
                    onClick={() => setFilters((current) => ({ ...current, search: "" }))}
                    aria-label="Clear search"
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
              <div className="filter-panel__field filter-panel__field--select">
                <CustomSelect
                  value={filters.status}
                  onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}
                >
                  <option value="all">All statuses</option>
                  {["unreconciled", "pending", "partial", "reconciled", "disputed"].map((status) => (
                    <option key={status} value={status}>
                      {status.replaceAll("-", " ")}
                    </option>
                  ))}
                </CustomSelect>
              </div>
              <div className="filter-panel__field filter-panel__field--select">
                <CustomSelect
                  value={filters.courier}
                  onChange={(event) => setFilters((current) => ({ ...current, courier: event.target.value }))}
                >
                  <option value="all">All couriers</option>
                  {couriers.map((courier) => (
                    <option key={courier}>{courier}</option>
                  ))}
                </CustomSelect>
              </div>
              <div className="filter-panel__actions">
                <button
                  className="filter-panel__apply"
                  type="button"
                  onClick={() => setAreMobileFiltersOpen(false)}
                  aria-label="Filter"
                  title="Filter"
                >
                  <Funnel size={15} aria-hidden="true" />
                </button>
                <button
                  className="filter-panel__reset"
                  type="button"
                  onClick={() => setFilters({ search: "", status: "all", courier: "all" })}
                  aria-label="Reset reconciliation filters"
                  title="Reset filters"
                >
                  <RotateCcw className="order-filters__resetbt" size={17} aria-hidden="true" />
                </button>
              </div>
            </div>
          </section>
        </div>

        {selectedOrderIds.length > 0 && (
          <div className="inventory-table__bulk-actions cod-bulk-bar" role="toolbar" aria-label="Bulk reconciliation actions">
            <div className="inventory-table__bulk-summary">
              <span className="inventory-table__bulk-badge">
                <CheckSquare size={13} aria-hidden="true" />
                {selectedOrderIds.length}
              </span>
              <span className="inventory-table__bulk-count-label">
                {selectedOrderIds.length === 1 ? "order selected" : "orders selected"}
              </span>
              <div className="cod-bulk-bar__pills">
                <span className="cod-bulk-bar__pill" title="Total COD Due for selected orders">
                  COD: <strong>{formatAnalyticsMoney(selectedTotalCodMinor)}</strong>
                </span>
                <span className="cod-bulk-bar__pill" title="Total Expected Settlement for selected orders">
                  Expected: <strong>{formatAnalyticsMoney(selectedTotalExpectedMinor)}</strong>
                </span>
              </div>
              <button
                type="button"
                className="inventory-table__bulk-clear-btn"
                onClick={deselectAll}
                title="Clear selection"
              >
                <X size={13} aria-hidden="true" />
                <span>Deselect</span>
              </button>
            </div>

            <div className="inventory-table__bulk-controls">
              {entries.length > visibleEntries.length && selectedOrderIds.length < entries.length && (
                <button
                  type="button"
                  className="cod-bulk-select-all-btn"
                  onClick={selectAllFiltered}
                >
                  Select all {entries.length} filtered
                </button>
              )}
              <button
                type="button"
                className="cod-bulk-record-btn"
                onClick={openBulkSettlement}
                title="Record settlements for selected orders"
              >
                <Banknote size={15} aria-hidden="true" />
                <span>Record Settlements ({selectedOrderIds.length})</span>
              </button>
            </div>
          </div>
        )}

        <div className="orders-table__scroll cod-reconciliation__table-shell">
          <table>
            <thead>
              <tr>
                <th className="cod-reconciliation__checkbox-th">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleSelectAllVisible}
                    aria-label="Select all visible orders"
                    title={allVisibleSelected ? "Deselect all visible" : "Select all visible"}
                  />
                </th>
                <th>Order</th>
                <th>Customer</th>
                <th>Courier</th>
                <th>COD due</th>
                <th>Courier fee</th>
                <th>Expected</th>
                <th>Received</th>
                <th>Variance</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan="11">Loading reconciliation...</td>
                </tr>
              ) : pagination.pageItems.length === 0 ? (
                <tr>
                  <td colSpan="11">No delivered COD orders match these filters.</td>
                </tr>
              ) : (
                pagination.pageItems.map((entry) => {
                  const isSelected = selectedOrderIds.includes(entry.orderId);
                  return (
                    <tr
                      key={entry.orderId}
                      className={`${entry.isOverdue ? "is-overdue" : ""} ${
                        isSelected ? "is-selected-row" : ""
                      }`}
                    >
                      <td className="cod-reconciliation__checkbox-td">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectOrder(entry.orderId)}
                          aria-label={`Select order ${entry.orderNumber}`}
                        />
                      </td>
                      <td data-label="Order">
                        <strong>{entry.orderNumber}</strong>
                        <small>
                          {entry.deliveredAt
                            ? new Date(entry.deliveredAt).toLocaleDateString("en-LK")
                            : "Delivered"}
                        </small>
                      </td>
                      <td data-label="Customer">{entry.customerName}</td>
                      <td data-label="Courier">{entry.courierName}</td>
                      <td data-label="COD due">{formatAnalyticsMoney(entry.expectedCollectionMinor)}</td>
                      <td data-label="Courier fee">{formatAnalyticsMoney(entry.courierChargeMinor)}</td>
                      <td data-label="Expected">{formatAnalyticsMoney(entry.expectedSettlementMinor)}</td>
                      <td data-label="Received">{formatAnalyticsMoney(entry.receivedSettlementMinor)}</td>
                      <td
                        data-label="Variance"
                        className={entry.varianceMinor < 0 ? "is-negative" : ""}
                      >
                        {formatAnalyticsMoney(entry.varianceMinor)}
                      </td>
                      <td data-label="Status">
                        <span className={`cod-reconciliation__status is-${entry.status}`}>
                          {entry.isOverdue ? "overdue" : entry.status}
                        </span>
                      </td>
                      <td data-label="Action">
                        <button
                          className="cod-reconciliation__record"
                          type="button"
                          onClick={() => openSettlement(entry)}
                        >
                          Record
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {!isLoading && <TablePagination pagination={pagination} label="COD orders" />}
        </div>
      </section>

      {/* Single Order Settlement Modal */}
      {editing && createPortal(
        <div
          className="cod-reconciliation__overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setEditing(null);
          }}
        >
          <form className="cod-reconciliation__dialog" onSubmit={save}>
            <header>
              <div>
                <span>Courier settlement</span>
                <h3>{editing.orderNumber}</h3>
              </div>
              <button type="button" onClick={() => setEditing(null)} aria-label="Close">
                <X />
              </button>
            </header>
            <div className="cod-reconciliation__form-grid">
              <label>
                Amount collected (LKR)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.amountCollected}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, amountCollected: event.target.value }))
                  }
                />
              </label>
              <label>
                Courier charges (LKR)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.courierCharge}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, courierCharge: event.target.value }))
                  }
                />
              </label>
              <label>
                Settlement received (LKR)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.receivedSettlement}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, receivedSettlement: event.target.value }))
                  }
                />
              </label>
              <label>
                Settlement date
                <input
                  type="date"
                  value={form.settlementDate}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, settlementDate: event.target.value }))
                  }
                />
              </label>
              <label className="is-wide">
                Reference
                <input
                  value={form.settlementReference}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, settlementReference: event.target.value }))
                  }
                  placeholder="Courier statement or bank reference"
                />
              </label>
              <label className="is-wide">
                Private note
                <textarea
                  value={form.note}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, note: event.target.value }))
                  }
                />
              </label>
              <label className="is-check is-wide">
                <input
                  type="checkbox"
                  checked={form.isDisputed}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, isDisputed: event.target.checked }))
                  }
                />{" "}
                Mark this settlement as disputed
              </label>
            </div>
            {saveError && <p className="cod-dialog-error" role="alert">{saveError}</p>}
            <footer>
              <button type="button" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button type="submit" disabled={isSaving}>
                {isSaving ? "Saving..." : "Save settlement"}
              </button>
            </footer>
          </form>
        </div>,
        document.body,
      )}

      {/* Bulk Settlement Modal */}
      {isBulkModalOpen && createPortal(
        <div
          className="cod-reconciliation__overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsBulkModalOpen(false);
          }}
        >
          <form className="cod-reconciliation__dialog cod-reconciliation__dialog--bulk" onSubmit={saveBulk}>
            <header>
              <div>
                <span className="cod-bulk-modal-badge">
                  <Layers size={13} /> Bulk Settlement Recording
                </span>
                <h3>Record Settlement for {bulkItems.length} Orders</h3>
              </div>
              <button type="button" onClick={() => setIsBulkModalOpen(false)} aria-label="Close">
                <X />
              </button>
            </header>

            <div className="cod-bulk-modal__content">
              {/* Summary stat cards */}
              <div className="cod-bulk-stats-grid">
                <div className="cod-bulk-stat">
                  <span className="cod-bulk-stat__label">Total COD Due</span>
                  <strong className="cod-bulk-stat__val">{formatAnalyticsMoney(bulkTotalCollectedMinor)}</strong>
                </div>
                <div className="cod-bulk-stat">
                  <span className="cod-bulk-stat__label">Total Courier Fees</span>
                  <strong className="cod-bulk-stat__val">{formatAnalyticsMoney(bulkTotalCourierChargesMinor)}</strong>
                </div>
                <div className="cod-bulk-stat">
                  <span className="cod-bulk-stat__label">Expected Settlement</span>
                  <strong className="cod-bulk-stat__val">{formatAnalyticsMoney(bulkTotalExpectedMinor)}</strong>
                </div>
                <div className="cod-bulk-stat">
                  <span className="cod-bulk-stat__label">Total Received</span>
                  <strong className="cod-bulk-stat__val cod-bulk-stat__val--green">
                    {formatAnalyticsMoney(bulkTotalReceivedMinor)}
                  </strong>
                </div>
                <div className="cod-bulk-stat">
                  <span className="cod-bulk-stat__label">Net Variance</span>
                  <strong
                    className={`cod-bulk-stat__val ${
                      bulkVarianceMinor < 0 ? "cod-bulk-stat__val--neg" : ""
                    }`}
                  >
                    {formatAnalyticsMoney(bulkVarianceMinor)}
                  </strong>
                </div>
              </div>

              {/* Shared Batch Inputs */}
              <div className="cod-bulk-shared-grid">
                <label>
                  Settlement Date
                  <input
                    type="date"
                    required
                    value={bulkSharedForm.settlementDate}
                    onChange={(event) =>
                      setBulkSharedForm((cur) => ({ ...cur, settlementDate: event.target.value }))
                    }
                  />
                </label>

                <label>
                  Settlement Reference / Bank Slip #
                  <input
                    placeholder="e.g. KOOMBIYO-PAY-202609, Slip #891"
                    value={bulkSharedForm.settlementReference}
                    onChange={(event) =>
                      setBulkSharedForm((cur) => ({
                        ...cur,
                        settlementReference: event.target.value,
                      }))
                    }
                  />
                </label>

                <label>
                  Apply Flat Courier Fee to all (LKR)
                  <div className="cod-bulk-input-with-btn">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="e.g. 350.00"
                      value={bulkSharedForm.flatCourierFee}
                      onChange={(event) => handleApplyFlatCourierFee(event.target.value)}
                    />
                  </div>
                </label>

                <div className="cod-bulk-preset-actions">
                  <button
                    type="button"
                    className="cod-bulk-preset-btn"
                    onClick={handleMarkAllFullSettlement}
                    title="Auto-calculate Received = COD Due - Courier Fee for all orders"
                  >
                    <DollarSign size={14} /> Mark all Full Settlement (0 Variance)
                  </button>
                </div>

                <label className="is-wide">
                  Batch Note
                  <input
                    placeholder="Optional shared note for this payout statement..."
                    value={bulkSharedForm.note}
                    onChange={(event) =>
                      setBulkSharedForm((cur) => ({ ...cur, note: event.target.value }))
                    }
                  />
                </label>

                <label className="is-check is-wide">
                  <input
                    type="checkbox"
                    checked={bulkSharedForm.isDisputed}
                    onChange={(event) =>
                      setBulkSharedForm((cur) => ({ ...cur, isDisputed: event.target.checked }))
                    }
                  />{" "}
                  Mark these settlements as disputed
                </label>
              </div>

              {/* Selected items table */}
              <div className="cod-bulk-items-wrapper">
                <div className="cod-bulk-items-header">
                  <h4>Selected Orders Breakdown ({bulkItems.length})</h4>
                  <small>You can tweak individual courier fees or received amounts below</small>
                </div>
                <div className="cod-bulk-table-scroll">
                  <table className="cod-bulk-table">
                    <thead>
                      <tr>
                        <th>Order</th>
                        <th>Customer</th>
                        <th>Courier</th>
                        <th>COD Due (LKR)</th>
                        <th>Courier Fee (LKR)</th>
                        <th>Received (LKR)</th>
                        <th>Variance</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {bulkItems.map((item) => {
                        const colMinor = toMinor(item.amountCollected);
                        const feeMinor = toMinor(item.courierCharge);
                        const recMinor = toMinor(item.receivedSettlement);
                        const expMinor = Math.max(colMinor - feeMinor, 0);
                        const varMinor = recMinor - expMinor;
                        return (
                          <tr key={item.orderId}>
                            <td>
                              <strong>{item.orderNumber}</strong>
                            </td>
                            <td>{item.customerName}</td>
                            <td>{item.courierName}</td>
                            <td>
                              <input
                                type="number"
                                className="cod-bulk-cell-input"
                                min="0"
                                step="0.01"
                                value={item.amountCollected}
                                onChange={(e) =>
                                  handleBulkItemChange(item.orderId, "amountCollected", e.target.value)
                                }
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                className="cod-bulk-cell-input"
                                min="0"
                                step="0.01"
                                value={item.courierCharge}
                                onChange={(e) =>
                                  handleBulkItemChange(item.orderId, "courierCharge", e.target.value)
                                }
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                className="cod-bulk-cell-input"
                                min="0"
                                step="0.01"
                                value={item.receivedSettlement}
                                onChange={(e) =>
                                  handleBulkItemChange(item.orderId, "receivedSettlement", e.target.value)
                                }
                              />
                            </td>
                            <td className={varMinor < 0 ? "is-negative" : ""}>
                              {formatAnalyticsMoney(varMinor)}
                            </td>
                            <td>
                              <button
                                type="button"
                                className="cod-bulk-item-del-btn"
                                onClick={() => removeBulkItem(item.orderId)}
                                title="Remove from this batch"
                              >
                                <Trash2 size={13} />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {bulkSaveError && <p className="cod-dialog-error" role="alert">{bulkSaveError}</p>}

            <footer>
              <button type="button" onClick={() => setIsBulkModalOpen(false)}>
                Cancel
              </button>
              <button type="submit" disabled={isBulkSaving || bulkItems.length === 0}>
                {isBulkSaving
                  ? "Recording..."
                  : `Record ${bulkItems.length} Settlements`}
              </button>
            </footer>
          </form>
        </div>,
        document.body,
      )}
    </section>
  );
}

export default CodReconciliation;

