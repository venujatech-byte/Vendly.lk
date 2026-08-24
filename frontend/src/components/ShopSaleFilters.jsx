import { CalendarDays, ChevronDown, Funnel, RotateCcw, Search } from "lucide-react";
import { useState } from "react";
import "./ShopSales.css";

const empty = { search: "", dateFrom: "", dateTo: "" };

export default function ShopSaleFilters({ onChange }) {
  const [filters, setFilters] = useState(empty);
  const [open, setOpen] = useState(false);
  function update(name, value) {
    const next = { ...filters, [name]: value };
    setFilters(next);
    onChange?.(next);
  }
  function reset() { setFilters(empty); onChange?.(empty); setOpen(false); }
  return <section className="shop-sale-filters">
    <button className="shop-sale-filters__toggle" type="button" onClick={() => setOpen(!open)}>
      <span><Funnel size={17} />{open ? "Hide filters" : "Show filters"}</span><ChevronDown size={18} />
    </button>
    <div className={`shop-sale-filters__fields ${open ? "is-open" : ""}`}>
      <label><Search size={17} /><input type="search" value={filters.search} onChange={(e) => update("search", e.target.value)} placeholder="Search sale number, item or customer..." /></label>
      <label className="shop-sale-filters__dates"><CalendarDays size={17} /><input type="date" value={filters.dateFrom} onChange={(e) => update("dateFrom", e.target.value)} /><span>to</span><input type="date" value={filters.dateTo} onChange={(e) => update("dateTo", e.target.value)} /></label>
      <button type="button" onClick={reset}><RotateCcw size={17} /> Reset</button>
    </div>
  </section>;
}
