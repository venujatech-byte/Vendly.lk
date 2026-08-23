// React state stores the filter form; icons improve the form controls visually.
import { useState } from "react";
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
};

function OrderFilters({ couriers = [], onApply, onReset }) {
  // One state object keeps all order-filter values together.
  const [filters, setFilters] = useState(initialFilters);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);

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
    <section className="order-filters" aria-label="Order filters">
      <button
        className="order-filters__mobile-toggle"
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
        className={`order-filters__form ${areMobileFiltersOpen ? "is-open" : ""}`}
        onSubmit={handleSubmit}
      >
        {/* Start and end date range. */}
        <div className="order-filters__field order-filters__date-field">


          <div className="order-filters__date-control">
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
        <div className="order-filters__field">
          <input id="order-search" name="search" type="search" placeholder="Search orders, customers, phone, items or waybill..." value={filters.search} onChange={handleInputChange} />
          {filters.search && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "search", value: "" } })} aria-label="Clear order search"><X size={15} /></button>}
        </div>

        {/* Restrict results to a selected courier. */}
        <div className="order-filters__field">


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

        {/* Apply or reset the completed filter form. */}
        <button className="order-filters__apply" type="submit">
          <Funnel size={18} aria-hidden="true" />
          <span>Filter</span>
        </button>

        <button
          className="order-filters__reset"
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
