// React state stores the current filter values entered by the user.
import { useState } from "react";
import {
  ChevronDown,
  Funnel,
  RotateCcw,
  X,
} from "lucide-react";

import "./InventoryFilters.css";

// Empty values used when the form first loads or is reset.
const initialFilters = {
  searchProduct: "",
  category: "",
  stockStatus: "",
};

function InventoryFilters({ categories = [], onApply, onReset }) {
  // All inventory filter fields are stored together in one state object.
  const [filters, setFilters] = useState(initialFilters);
  const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);

  // Update the field whose name matches the changed input or select element.
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
    if (fieldName === "searchProduct" && !fieldValue) onApply?.(nextFilters);
  }

  // Prevent a page reload and send the selected values to InventoryPage.
  function handleSubmit(event) {
    event.preventDefault();
    onApply?.(filters);
    setAreMobileFiltersOpen(false);
  }

  // Restore every filter to its original empty value.
  function handleReset() {
    setFilters(initialFilters);
    onReset?.();
    setAreMobileFiltersOpen(false);
  }

  return (
    <section className="inventory-filters" aria-label="inventory filters">
      <button
        className="inventory-filters__mobile-toggle"
        type="button"
        onClick={() => setAreMobileFiltersOpen((isOpen) => !isOpen)}
        aria-expanded={areMobileFiltersOpen}
        aria-controls="inventory-filter-fields"
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

      {/* Controlled form: every value comes from the filters state object. */}
      <form
        id="inventory-filter-fields"
        className={`inventory-filters__form ${areMobileFiltersOpen ? "is-open" : ""}`}
        onSubmit={handleSubmit}
      >
    


        {/* Product name, SKU, or barcode search. */}
        <div className="inventory-filters__field">

          <input
            id="searchProduct"
            name="searchProduct"
            type="search"
            aria-label="Search product by name or SKU"
            placeholder="Search product name, SKU, or barcode"
            value={filters.searchProduct}
            onChange={handleInputChange}
          />
          {filters.searchProduct && <button type="button" className="inventory-filters__clear" onClick={() => handleInputChange({ target: { name: "searchProduct", value: "" } })} aria-label="Clear product search"><X size={15} /></button>}
        </div>


        {/* Category selector. */}
        <div className="inventory-filters__field">

          <select
            id="category"
            name="category"
            value={filters.category}
            onChange={handleInputChange}
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </select>
        </div>



        {/* Stock-status selector. */}
        <div className="inventory-filters__field">

          <select
            id="stockStatus"
            name="stockStatus"
            value={filters.stockStatus}
            onChange={handleInputChange}
          >
            <option value="">All statuses</option>
            <option value="in-stock">In Stock</option>
            <option value="low-stock">Low Stock</option>
            <option value="out-of-stock">Out of Stock</option>
          </select>
        </div>

        {/* Submit and reset controls. */}
        <button className="inventory-filters__apply" type="submit">
          <Funnel size={18} aria-hidden="true" />
          <span>Filter</span>
        </button>

        <button
          className="inventory-filters__reset"
          type="button"
          onClick={handleReset}
          aria-label="Reset inventory filters"
          title="Reset filters"
        >
          <RotateCcw className="inventory-filters__resetbt" size={21} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}

export default InventoryFilters;
