import { ChevronDown, Funnel, RotateCcw, Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import DateRangePicker from "./DateRangePicker";
import "./ShopSales.css";
import "./OrderFilters.css";

const empty = { search: "", dateFrom: "", dateTo: "" };

export default function ShopSaleFilters({ onChange, appliedFilters, actions }) {
  const [filters, setFilters] = useState(empty);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function resetAssistantFilters() {
      setFilters(empty);
      setOpen(false);
    }

    window.addEventListener("vendly:reset-filters", resetAssistantFilters);
    return () => window.removeEventListener("vendly:reset-filters", resetAssistantFilters);
  }, []);

  // Keep the date/search fields in sync when the Business Assistant opens a
  // filtered shop-sales view.
  useEffect(() => {
    if (!appliedFilters) return;
    setFilters({ ...empty, ...appliedFilters });
  }, [appliedFilters]);

  function update(name, value) {
    const next = { ...filters, [name]: value };
    setFilters(next);
    onChange?.(next);
  }

  function handleDateRangeChange({ startDate, endDate }) {
    const next = { ...filters, dateFrom: startDate, dateTo: endDate };
    setFilters(next);
    onChange?.(next);
  }

  function reset() {
    setFilters(empty);
    onChange?.(empty);
    setOpen(false);
  }

  function submit(event) {
    event.preventDefault();
    onChange?.(filters);
    setOpen(false);
  }

  return (
    <section className="shop-sale-filters filter-panel" aria-label="Shop sales filters">
      <button className="shop-sale-filters__toggle filter-panel__mobile-toggle" type="button" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span><Funnel size={17} aria-hidden="true" />{open ? "Hide filters" : "Show filters"}</span>
        <ChevronDown className={open ? "is-open" : ""} size={18} aria-hidden="true" />
      </button>
      <form className={`shop-sale-filters__fields filter-panel__form ${open ? "is-open" : ""}`} onSubmit={submit}>
        <div className="filter-panel__field filter-panel__field--search">
          <Search size={15} className="filter-panel__search-icon" aria-hidden="true" />
          <input type="search" value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="Search sale number, item or customer..." />
          {filters.search && (
            <button type="button" className="filter-panel__clear" onClick={() => update("search", "")} aria-label="Clear search">
              <X size={14} />
            </button>
          )}
        </div>
        <div className="shop-sale-filters__dates filter-panel__field filter-panel__field--date">
          <DateRangePicker
            startDate={filters.dateFrom}
            endDate={filters.dateTo}
            onChange={handleDateRangeChange}
          />
        </div>
        <div className="filter-panel__actions">
          <button className="filter-panel__apply" type="submit" aria-label="Filter" title="Filter">
            <Funnel size={15} aria-hidden="true" />
          </button>
          <button className="filter-panel__reset" type="button" onClick={reset} aria-label="Reset shop sale filters" title="Reset filters">
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
