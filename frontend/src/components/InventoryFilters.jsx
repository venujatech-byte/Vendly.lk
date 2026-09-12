import { useEffect, useState } from "react";
import {
  ChevronDown,
  Funnel,
  RotateCcw,
  Search,
  X,
} from "lucide-react";

import CustomSelect from "./CustomSelect";
import "./OrderFilters.css";

// Empty values used when the form first loads or is reset.
const initialFilters = {
  searchProduct: "",
  category: "",
  stockStatus: "",
};

function InventoryFilters({ categories = [], onApply, onReset, appliedFilters, actions }) {
  // All inventory filter fields are stored together in one state object.
  const [filters, setFilters] = useState(initialFilters);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);

  useEffect(() => {
    function resetAssistantFilters() {
      setFilters(initialFilters);
      setAreMobileFiltersOpen(false);
    }

    window.addEventListener("vendly:reset-filters", resetAssistantFilters);
    return () => {
      window.removeEventListener("vendly:reset-filters", resetAssistantFilters);
    };
  }, []);

  // Update local inputs when active filters change from the outside.
  useEffect(() => {
    if (appliedFilters) {
      setFilters({
        searchProduct: appliedFilters.searchProduct || "",
        category: appliedFilters.category || "",
        stockStatus: appliedFilters.stockStatus || "",
      });
    }
  }, [appliedFilters]);

  // Keep filter state updated on change.
  function handleInputChange(event) {
    const { name, value } = event.target;
    setFilters((currentFilters) => ({
      ...currentFilters,
      [name]: value,
    }));
  }

  // Clear single search input immediately.
  function clearSearch() {
    const updatedFilters = { ...filters, searchProduct: "" };
    setFilters(updatedFilters);
    if (onApply) onApply(updatedFilters);
  }

  // Trigger search filter submission.
  function handleSubmit(event) {
    event.preventDefault();
    if (onApply) onApply(filters);
    setAreMobileFiltersOpen(false);
  }

  // Reset all filters back to empty defaults.
  function handleReset() {
    setFilters(initialFilters);
    if (onReset) onReset();
    setAreMobileFiltersOpen(false);
  }

  // Count filters currently in use.
  const activeFilterCount = [
    filters.searchProduct,
    filters.category,
    filters.stockStatus,
  ].filter(Boolean).length;

  return (
    <section className="inventory-filters filter-panel" aria-label="Inventory filters">
      {/* Mobile-only toggle button. */}
      <div className="inventory-filters__mobile-bar">
        <button
          className="inventory-filters__mobile-toggle filter-panel__mobile-toggle"
          type="button"
          onClick={() => setAreMobileFiltersOpen((wasOpen) => !wasOpen)}
          aria-expanded={areMobileFiltersOpen}
          aria-controls="inventory-filter-fields"
        >
          <Funnel size={14} aria-hidden="true" />
          <span>Filters</span>
          {activeFilterCount > 0 && (
            <span className="filter-panel__count">{activeFilterCount}</span>
          )}
          <ChevronDown
            size={14}
            className={`filter-panel__chevron ${areMobileFiltersOpen ? "is-open" : ""}`}
            aria-hidden="true"
          />
        </button>
      </div>

      {/* Main filter form wrapper. */}
      <form
        id="inventory-filter-fields"
        className={`inventory-filters__form filter-panel__form ${areMobileFiltersOpen ? "is-open" : ""}`}
        onSubmit={handleSubmit}
      >
        {/* Search input with icons. */}
        <div className="inventory-filters__field filter-panel__field filter-panel__field--search">
          <Search size={15} className="filter-panel__search-icon" aria-hidden="true" />
          <input
            id="searchProduct"
            name="searchProduct"
            type="search"
            placeholder="Search by name, SKU, or barcode..."
            value={filters.searchProduct}
            onChange={handleInputChange}
            aria-label="Search by name, SKU, or barcode"
          />
          {filters.searchProduct && (
            <button
              className="inventory-filters__clear filter-panel__clear"
              type="button"
              onClick={clearSearch}
              aria-label="Clear search input"
              title="Clear search"
            >
              <X size={13} aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Category selector. */}
        <div className="inventory-filters__field filter-panel__field filter-panel__field--select">
          <CustomSelect
            id="category"
            name="category"
            value={filters.category}
            onChange={handleInputChange}
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </CustomSelect>
        </div>

        {/* Stock-status selector. */}
        <div className="inventory-filters__field filter-panel__field filter-panel__field--select">
          <CustomSelect
            id="stockStatus"
            name="stockStatus"
            value={filters.stockStatus}
            onChange={handleInputChange}
          >
            <option value="">All statuses</option>
            <option value="in-stock">In Stock</option>
            <option value="low-stock">Low Stock</option>
            <option value="out-of-stock">Out of Stock</option>
          </CustomSelect>
        </div>

        {/* Submit and reset controls wrapped in filter-panel__actions. */}
        <div className="filter-panel__actions">
          <button
            className="inventory-filters__apply filter-panel__apply"
            type="submit"
            aria-label="Filter"
            title="Filter"
          >
            <Funnel size={15} aria-hidden="true" />
          </button>

          <button
            className="inventory-filters__reset filter-panel__reset"
            type="button"
            onClick={handleReset}
            aria-label="Reset inventory filters"
            title="Reset filters"
          >
            <RotateCcw className="inventory-filters__resetbt" size={17} aria-hidden="true" />
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

export default InventoryFilters;
