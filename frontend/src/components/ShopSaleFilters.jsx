import { CalendarDays, ChevronDown, Funnel, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import "./ShopSales.css";
import "./OrderFilters.css";

const empty = { search: "", dateFrom: "", dateTo: "" };

export default function ShopSaleFilters({ onChange }) {
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
  function update(name, value) {
    const next = { ...filters, [name]: value };
    setFilters(next);
    onChange?.(next);
  }
  function reset() { setFilters(empty); onChange?.(empty); setOpen(false); }
  function submit(event) {
    event.preventDefault();
    onChange?.(filters);
    setOpen(false);
  }
  return <section className="shop-sale-filters filter-panel">
    <button className="shop-sale-filters__toggle filter-panel__mobile-toggle" type="button" onClick={() => setOpen(!open)}>
      <span><Funnel size={17} />{open ? "Hide filters" : "Show filters"}</span><ChevronDown className={open ? "is-open" : ""} size={18} />
    </button>
    <form className={`shop-sale-filters__fields filter-panel__form ${open ? "is-open" : ""}`} onSubmit={submit}>
      <label className="filter-panel__field filter-panel__field--search"><input type="search" value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="Search sale number, item or customer..." /></label>
      <label className="shop-sale-filters__dates filter-panel__field filter-panel__field--date filter-panel__date-control"><CalendarDays size={17} /><input type="date" value={filters.dateFrom} onChange={(e) => update("dateFrom", e.target.value)} /><span>to</span><input type="date" value={filters.dateTo} onChange={(e) => update("dateTo", e.target.value)} /></label>
      <button className="filter-panel__apply" type="submit"><Funnel size={18} /><span>Filter</span></button>
      <button className="filter-panel__reset" type="button" onClick={reset} aria-label="Reset shop sale filters" title="Reset filters"><RotateCcw className="order-filters__resetbt" size={21} /></button>
    </form>
  </section>;
}
