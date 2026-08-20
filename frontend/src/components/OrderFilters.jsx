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
  orderNumber: "",
  itemName: "",
  customer: "",
  courier: "",
  waybillNumber: "",
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
    if (!fieldValue && ["orderNumber", "itemName", "customer"].includes(fieldName)) onApply?.(nextFilters);
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
          <label htmlFor="date-from">Order date</label>

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

        <div className="order-filters__field">
          <label htmlFor="waybill-number">Waybill number</label>
          <input id="waybill-number" name="waybillNumber" type="search" placeholder="Scan or enter waybill" value={filters.waybillNumber} onChange={handleInputChange} />
          {filters.waybillNumber && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "waybillNumber", value: "" } })} aria-label="Clear waybill number"><X size={15} /></button>}
        </div>

        {/* Search by order number. */}
        <div className="order-filters__field">
          <label htmlFor="order-number">Order number</label>

            <input
              id="order-number"
              name="orderNumber"
              type="search"
            placeholder="e.g. VD-100001"
            value={filters.orderNumber}
              onChange={handleInputChange}
            />
            {filters.orderNumber && <button type="button" className="order-filters__clear" onClick={() => { const event = { target: { name: "orderNumber", value: "" } }; handleInputChange(event); }} aria-label="Clear order number"><X size={15} /></button>}
        </div>

        {/* Search by product/item name. */}
        <div className="order-filters__field">
          <label htmlFor="item-name">Item name</label>

          <input
            id="item-name"
            name="itemName"
            type="search"
            placeholder="Search item"
            value={filters.itemName}
            onChange={handleInputChange}
          />
          {filters.itemName && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "itemName", value: "" } })} aria-label="Clear item name"><X size={15} /></button>}
        </div>

        {/* Search by customer name or phone number. */}
        <div className="order-filters__field">
          <label htmlFor="customer">Customer / Phone</label>

          <input
            id="customer"
            name="customer"
            type="search"
            placeholder="Name or phone"
            value={filters.customer}
            onChange={handleInputChange}
          />
          {filters.customer && <button type="button" className="order-filters__clear" onClick={() => handleInputChange({ target: { name: "customer", value: "" } })} aria-label="Clear customer search"><X size={15} /></button>}
        </div>

        {/* Restrict results to a selected courier. */}
        <div className="order-filters__field">
          <label htmlFor="courier">Courier</label>

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
