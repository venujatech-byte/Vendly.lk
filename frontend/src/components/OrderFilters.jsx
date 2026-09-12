import { useEffect, useState } from "react";
import {
  ChevronDown,
  Funnel,
  RotateCcw,
  Search,
  X,
} from "lucide-react";
import DateRangePicker from "./DateRangePicker";

import "./OrderFilters.css";

// Initial values are also reused when the user resets the form.
const initialFilters = {
  dateFrom: "",
  dateTo: "",
  search: "",
  courier: "",
  status: "",
  payment: "",
};

function OrderFilters({ couriers = [], onApply, onReset, onStatusChange, appliedFilters, actions }) {
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

  function handleDateRangeChange({ startDate, endDate }) {
    const nextFilters = {
      ...filters,
      dateFrom: startDate,
      dateTo: endDate,
    };
    setFilters(nextFilters);
    onApply?.(nextFilters);
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
        {/* Live search with search icon */}
        <div className="filter-panel__field filter-panel__field--search">
          <Search size={15} className="filter-panel__search-icon" aria-hidden="true" />
          <input
            id="order-search"
            name="search"
            type="search"
            placeholder="Search orders, customers, phone, items..."
            value={filters.search}
            onChange={handleInputChange}
          />
          {filters.search && (
            <button
              type="button"
              className="filter-panel__clear"
              onClick={() => handleInputChange({ target: { name: "search", value: "" } })}
              aria-label="Clear order search"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Date range picker */}
        <div className="filter-panel__field filter-panel__field--date">
          <DateRangePicker
            startDate={filters.dateFrom}
            endDate={filters.dateTo}
            onChange={handleDateRangeChange}
          />
        </div>

        {/* Restrict results to a selected courier. */}
        <div className="filter-panel__field filter-panel__field--select">
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

        {/* Filter orders by how the customer paid. */}
        <div className="filter-panel__field filter-panel__field--select">
          <select id="order-payment" name="payment" value={filters.payment} onChange={handleInputChange}>
            <option value="">All payments</option>
            <option value="cod">COD</option>
            <option value="partially-paid">Half paid</option>
            <option value="paid">Fully paid</option>
          </select>
        </div>

        {/* Apply and reset action buttons */}
        <div className="filter-panel__actions">
          <button className="filter-panel__apply" type="submit" aria-label="Filter" title="Filter">
            <Funnel size={15} aria-hidden="true" />
          </button>

          <button
            className="filter-panel__reset"
            type="button"
            onClick={handleReset}
            aria-label="Reset order filters"
            title="Reset filters"
          >
            <RotateCcw className="order-filters__resetbt" size={17} aria-hidden="true" />
          </button>
        </div>

        {actions && (
          <div className="filter-panel__extra-actions">
            {actions}
          </div>
        )}
      </form>
    </section>
  );
}

export default OrderFilters;
