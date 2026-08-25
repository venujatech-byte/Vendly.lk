// React state stores the filter form; icons improve the form controls visually.
import { useEffect, useState } from "react";
import {
  CalendarDays,
  ChevronDown,
  Funnel,
  RotateCcw,
  X,
} from "lucide-react";

import "./OrderFilters.css";

// Initial values are also reused when the user resets the form.
const initialFilters = {
  dateFrom: "",
  dateTo: "",
  search: "",
  courier: "",
  status: "",
};

function OrderFilters({ couriers = [], onApply, onReset, onStatusChange, appliedFilters }) {
  // One state object keeps all order-filter values together.
  const [filters, setFilters] = useState(initialFilters);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);

  useEffect(() => {
    function resetAssistantFilters() {
      setFilters(initialFilters);
      setAreMobileFiltersOpen(false);
    }

    window.addEventListener("vendly:reset-filters", resetAssistantFilters);
    return () => window.removeEventListener("vendly:reset-filters", resetAssistantFilters);
  }, []);

  // Assistant links contain the exact filter values in the URL. Mirror those
  // values in the form so the table and the visible controls always agree.
  useEffect(() => {
    if (!appliedFilters) return;

    setFilters({
      ...initialFilters,
      ...appliedFilters,
    });
  }, [appliedFilters]);

  // Use the input name to update only the field that changed.
  function handleInputChange(event) {
    const fieldName = event.target.name;
    const fieldValue = event.target.value;

    const nextFilters = {
      ...filters,
      [fieldName]: fieldValue,
    };
    setFilters((currentFilters) => ({
      ...currentFilters,
      [fieldName]: fieldValue,
    }));
    if (fieldName === "status") onStatusChange?.(fieldValue);
    // Search is live: the parent reloads matching orders on every keystroke.
    onApply?.(nextFilters);
  }

  // Stop the browser refresh and prepare filters for future API/database use.
  function handleSubmit(event) {
    event.preventDefault();

    onApply?.(filters);
    setAreMobileFiltersOpen(false);
  }

  // Clear all filters at once.
  function handleReset() {
    setFilters(initialFilters);
    onReset?.();
    setAreMobileFiltersOpen(false);
  }

  return (
    <section className="order-filters filter-panel" aria-label="Order filters">
      <button
        className="order-filters__mobile-toggle filter-panel__mobile-toggle"
        type="button"
        onClick={() => setAreMobileFiltersOpen((isOpen) => !isOpen)}
        aria-expanded={areMobileFiltersOpen}
        aria-controls="order-filter-fields"
      >
        <span>
          <Funnel size={17} aria-hidden="true" />
          {areMobileFiltersOpen ? "Hide filters" : "Show filters"}
        </span>
        <ChevronDown
          className={areMobileFiltersOpen ? "is-open" : ""}
          size={18}
          aria-hidden="true"
        />
      </button>

      {/* All fields below are controlled by the filters state object. */}
      <form
        id="order-filter-fields"
        className={`order-filters__form filter-panel__form ${areMobileFiltersOpen ? "is-open" : ""}`}
        onSubmit={handleSubmit}
      >
        {/* Start and end date range. */}
        <div className="order-filters__field order-filters__date-field filter-panel__field filter-panel__field--date">


          <div className="order-filters__date-control filter-panel__date-control">
            <CalendarDays size={17} aria-hidden="true" />

            <input
              id="date-from"
              name="dateFrom"
              type="date"
              value={filters.dateFrom}
              onChange={handleInputChange}
            />

            <span>to</span>

            <input
              id="date-to"
              name="dateTo"
              type="date"
              value={filters.dateTo}
              onChange={handleInputChange}
            />
          </div>
        </div>

        {/* One live search covers order number, waybill, item, customer and phone. */}
        <div className="order-filters__field filter-panel__field filter-panel__field--search">
          <input id="order-search" name="search" type="search" placeholder="Search orders, customers, phone, items or waybill..." value={filters.search} onChange={handleInputChange} />
          {filters.search && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "search", value: "" } })} aria-label="Clear order search"><X size={15} /></button>}
        </div>

        {/* Restrict results to a selected courier. */}
        <div className="order-filters__field filter-panel__field">


          <select
            id="courier"
            name="courier"
            value={filters.courier}
            onChange={handleInputChange}
          >
            <option value="">All couriers</option>
            {couriers.map((courier) => (
              <option key={courier.id} value={courier.id}>{courier.name}</option>
            ))}
          </select>
        </div>

        {/* Status remains a normal dropdown as well as being available from the
            summary cards, which is useful for assistant-applied filters. */}
        <div className="order-filters__field filter-panel__field">
          <select
            id="order-status"
            name="status"
            value={filters.status}
            onChange={handleInputChange}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="confirmed">Confirmed</option>
            <option value="packed">Packed</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="returned">Returned</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        {/* Apply or reset the completed filter form. */}
        <button className="order-filters__apply filter-panel__apply" type="submit">
          <Funnel size={18} aria-hidden="true" />
          <span>Filter</span>
        </button>

        <button
          className="order-filters__reset filter-panel__reset"
          type="button"
          onClick={handleReset}
          aria-label="Reset order filters"
          title="Reset filters"
        >
          <RotateCcw className="order-filters__resetbt" size={21} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}

export default OrderFilters;
