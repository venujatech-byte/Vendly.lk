import { ArchiveX, Boxes, ChevronDown, CircleDollarSign, Funnel, PackageSearch, RotateCcw, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import useTablePagination from "../hooks/useTablePagination";
import { formatAnalyticsMoney } from "../services/analyticsService";
import StatCard from "./StatCard";
import TablePagination from "./TablePagination";
import "./OrderFilters.css";
import "./DeadStockReport.css";

function DeadStockReport({ report, isLoading }) {
  const [filters, setFilters] = useState({ search: "", category: "all", state: "all" });
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
  const products = report?.products ?? [];
  const summary = report?.summary ?? {};
  const categories = useMemo(
    () => [...new Set(products.map((product) => product.categoryName))].sort(),
    [products],
  );
  const filteredProducts = useMemo(() => {
    const needle = filters.search.trim().toLowerCase();
    return products.filter((product) => (
      (!needle || [product.name, product.sku, product.categoryName].join(" ").toLowerCase().includes(needle))
      && (filters.category === "all" || product.categoryName === filters.category)
      && (filters.state === "all" || product.state === filters.state)
    ));
  }, [filters, products]);
  const pagination = useTablePagination(filteredProducts);

  function resetFilters() {
    setFilters({ search: "", category: "all", state: "all" });
  }

  return (
    <section className="dead-stock" aria-labelledby="dead-stock-title">
      <header className="dead-stock__intro">
        <div><span>Inventory intelligence</span><h3 id="dead-stock-title">Dead-stock report</h3><p>Products with available stock that have never sold or have not sold for at least {report?.staleAfterDays ?? 60} days.</p></div>
        <ArchiveX aria-hidden="true" />
      </header>

      <div className="dead-stock__stats">
        <StatCard label="Dead products" value={String(summary.productCount ?? 0)} icon={ArchiveX} tone="red" />
        <StatCard label="Stock units" value={String(summary.stockUnits ?? 0)} icon={Boxes} tone="orange" />
        <StatCard label="Cost tied up" value={formatAnalyticsMoney(summary.tiedUpCostMinor)} icon={CircleDollarSign} tone="blue" />
        <StatCard label="Never sold" value={String(summary.neverSoldCount ?? 0)} icon={PackageSearch} tone="purple" />
      </div>

      <section className="filter-panel" aria-label="Dead-stock filters">
        <button
          className="filter-panel__mobile-toggle"
          type="button"
          aria-expanded={areMobileFiltersOpen}
          aria-controls="dead-stock-filter-fields"
          onClick={() => setAreMobileFiltersOpen((value) => !value)}
        >
          <span><Funnel size={17} aria-hidden="true" /> {areMobileFiltersOpen ? "Hide filters" : "Show filters"}</span>
          <ChevronDown className={areMobileFiltersOpen ? "is-open" : ""} size={18} aria-hidden="true" />
        </button>
        <div id="dead-stock-filter-fields" className={`filter-panel__form dead-stock__filter-form ${areMobileFiltersOpen ? "is-open" : ""}`}>
          <div className="filter-panel__field filter-panel__field--search">
            <Search size={15} className="filter-panel__search-icon" aria-hidden="true" />
            <input
              type="search"
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="Search product, SKU or category..."
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
            <select value={filters.category} onChange={(event) => setFilters((current) => ({ ...current, category: event.target.value }))}>
              <option value="all">All categories</option>
              {categories.map((category) => <option key={category}>{category}</option>)}
            </select>
          </div>
          <div className="filter-panel__field filter-panel__field--select">
            <select value={filters.state} onChange={(event) => setFilters((current) => ({ ...current, state: event.target.value }))}>
              <option value="all">All dead stock</option>
              <option value="never-sold">Never sold</option>
              <option value="stale">60-119 days</option>
              <option value="critical">120+ days</option>
            </select>
          </div>
          <div className="filter-panel__actions">
            <button className="filter-panel__apply" type="button" onClick={() => setAreMobileFiltersOpen(false)}>
              <Funnel size={15} aria-hidden="true" />
              <span>Filter</span>
            </button>
            <button
              className="filter-panel__reset"
              type="button"
              onClick={resetFilters}
              aria-label="Reset dead-stock filters"
              title="Reset filters"
            >
              <RotateCcw className="order-filters__resetbt" size={17} aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      <div className="dead-stock__table-shell">
        <table>
          <thead><tr><th>Product</th><th>Category</th><th>Available</th><th>Last sold</th><th>Sold / 90 days</th><th>Stock cost</th><th>Margin</th><th>Recommendation</th></tr></thead>
          <tbody>
            {isLoading ? <tr><td colSpan="8">Loading dead-stock report...</td></tr> : pagination.pageItems.length === 0 ? <tr><td colSpan="8">No products match these dead-stock filters.</td></tr> : pagination.pageItems.map((product) => (
              <tr key={product.id}>
                <td><span className="dead-stock__product">{product.imageUrl ? <img src={product.imageUrl} alt="" /> : <Boxes aria-hidden="true" />}<span><strong>{product.name}</strong><small>{product.sku}</small></span></span></td>
                <td>{product.categoryName}</td><td><strong>{product.availableStock}</strong></td>
                <td><span className={`dead-stock__state is-${product.state}`}>{product.state === "never-sold" ? "Never sold" : `${product.daysSinceLastSale} days ago`}</span></td>
                <td>{product.unitsSoldLast90Days}</td>
                <td><strong>{formatAnalyticsMoney(product.tiedUpCostMinor)}</strong><small>{formatAnalyticsMoney(product.unitCostMinor)} each</small></td>
                <td>{product.grossMarginPercent}%</td><td>{product.recommendation}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && <TablePagination pagination={pagination} label="dead-stock products" />}
      </div>
    </section>
  );
}

export default DeadStockReport;
