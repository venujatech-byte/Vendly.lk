// React state remembers whether Products or Categories is selected.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

// Icons used by statistics, tabs, and page action buttons.
import {
  Package,
  CircleCheck,
  TriangleAlert,
  CircleX,
  Download,
  Plus,
  ScanBarcode,
  Tags,
} from "lucide-react";

// Reusable inventory components, temporary data, and stock calculations.
import StatCard from "../components/StatCard";
import InventoryFilters from "../components/InventoryFilters";
import InventoryTable from "../components/InventoryTable";
import CategoryTable from "../components/CategoryTable";
import AddCategoryModal from "../components/AddCategoryModal";
import AddProductModal from "../components/AddProductModal";
import ConfirmDialog from "../components/ConfirmDialog";
import ReviewsModal from "../components/ReviewsModal";
import AdjustStockModal from "../components/AdjustStockModal";
import BarcodeScannerModal from "../components/BarcodeScannerModal";
import { useAuth } from "../context/authContextValue";
import { getCategories, removeCategory } from "../services/categoryService";
import { downloadInventoryCsv, getProducts, removeProduct, updateProduct, updateProductStatus } from "../services/productService";
import { getProductStockStatus } from "../utils/inventory";

import "./InventoryPage.css";
import "./Buttons.css";

function InventoryPage() {
  const [searchParameters, setSearchParameters] = useSearchParams();
  const routeSearch = (searchParameters.get("search") ?? "").trim().toLowerCase();
  const routeStockStatus = searchParameters.get("stockStatus") ?? "";
  const routeSortBy = searchParameters.get("sortBy") ?? "";
  const routeSortDirection = searchParameters.get("sortDirection") === "desc" ? "desc" : "asc";
  const assistantAction = searchParameters.get("assistantAction") ?? "";
  const assistantProductId = searchParameters.get("productId") ?? "";
  const { business, accountError } = useAuth();

  // Products is the default tab when the Inventory page opens.
  const [activeTab, setActiveTab] = useState("products");
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [isInventoryLoading, setIsInventoryLoading] = useState(true);
  const [inventoryError, setInventoryError] = useState(null);
  const [isAddCategoryOpen, setIsAddCategoryOpen] = useState(false);
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [reviewProduct, setReviewProduct] = useState(null);
  const [stockAdjustment, setStockAdjustment] = useState(null);
  const [editingProduct, setEditingProduct] = useState(null);
  const [editingCategory, setEditingCategory] = useState(null);
  const [removalTarget, setRemovalTarget] = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [inventoryFilters, setInventoryFilters] = useState({});
  const [inventoryRefreshKey, setInventoryRefreshKey] = useState(0);
  const [isBarcodeScannerOpen, setIsBarcodeScannerOpen] = useState(false);

  useEffect(() => {
    if (!assistantAction) return;

    if (assistantAction === "add-product") {
      setActiveTab("products");
      setIsAddProductOpen(true);
    }


    if (assistantAction === "open-categories") {
      setActiveTab("categories");
    }

    if (assistantAction === "edit-product" && assistantProductId && products.length > 0) {
      const product = products.find((item) => item.id === assistantProductId);
      if (product) {
        setActiveTab("products");
        setEditingProduct(product);
      }
    }

    if (assistantAction === "edit-product" && products.length === 0 && isInventoryLoading) {
      return;
    }

    const nextParameters = new URLSearchParams(searchParameters);
    nextParameters.delete("assistantAction");
    nextParameters.delete("productId");
    setSearchParameters(nextParameters, { replace: true });
  }, [
    assistantAction,
    assistantProductId,
    isInventoryLoading,
    products,
    searchParameters,
    setSearchParameters,
  ]);

  // Reset local and URL filters, then reload the source data for a clean table.
  function resetInventoryFilters() {
    setInventoryFilters({});
    setSearchParameters({}, { replace: true });
    setInventoryRefreshKey((currentKey) => currentKey + 1);
  }

  useEffect(() => {
    function handleAssistantFilterReset() {
      setInventoryFilters({});
      setSearchParameters({}, { replace: true });
      setInventoryRefreshKey((currentKey) => currentKey + 1);
    }

    window.addEventListener("vendly:reset-filters", handleAssistantFilterReset);
    return () => window.removeEventListener("vendly:reset-filters", handleAssistantFilterReset);
  }, [setSearchParameters]);

  useEffect(() => {
    let requestIsCurrent = true;

    async function loadInventory() {
      if (!business?.id) {
        setProducts([]);
        setCategories([]);
        setIsInventoryLoading(false);
        return;
      }

      setIsInventoryLoading(true);
      setInventoryError(null);

      try {
        const [productRecords, categoryResponse] = await Promise.all([
          getProducts(business.id),
          getCategories(business.id),
        ]);

        if (requestIsCurrent) {
          setProducts(productRecords);
          setCategories(categoryResponse.categories.filter((category) => category.status === "active"));
        }
      } catch (error) {
        console.error("Inventory could not be loaded:", error);

        if (requestIsCurrent) {
          setInventoryError(error);
          setProducts([]);
          setCategories([]);
        }
      } finally {
        if (requestIsCurrent) {
          setIsInventoryLoading(false);
        }
      }
    }

    loadInventory();

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id, inventoryRefreshKey]);

  const inventoryStats = useMemo(
    () => [
      {
        label: "All Items",
        value: products.length,
        icon: Package,
        tone: "blue",
      },
      {
        label: "In Stock",
        value: products.filter(
          (product) => getProductStockStatus(product) === "in-stock",
        ).length,
        icon: CircleCheck,
        tone: "green",
      },
      {
        label: "Low Stock",
        value: products.filter(
          (product) => getProductStockStatus(product) === "low-stock",
        ).length,
        icon: TriangleAlert,
        tone: "orange",
      },
      {
        label: "Out of Stock",
        value: products.filter(
          (product) => getProductStockStatus(product) === "out-of-stock",
        ).length,
        icon: CircleX,
        tone: "red",
      },
    ],
    [products],
  );

  const categoryStats = useMemo(() => {
    const categoryStock = categories.map((category) => ({
      ...category,
      stock: products
        .filter((product) => product.categoryId === category.id)
        .reduce((total, product) => total + product.stock, 0),
    }));
    const topCategory = categoryStock.reduce(
      (currentTop, category) =>
        category.stock > currentTop.stock ? category : currentTop,
      { name: "None", stock: -1 },
    );

    return [
      {
        label: "Total categories",
        value: categories.length,
        icon: Tags,
        tone: "blue",
      },
      {
        label: "Active categories",
        value: categories.filter((category) => category.status === "active")
          .length,
        icon: CircleCheck,
        tone: "green",
      },
      {
        label: "Uncategorized Products",
        value: products.filter((product) => !product.categoryId).length,
        icon: TriangleAlert,
        tone: "orange",
      },
      {
        label: "Top Category",
        value: topCategory.name,
        icon: Tags,
        tone: "blue",
      },
    ];
  }, [categories, products]);

  const visibleProducts = useMemo(() => {
    const searchText = (
      routeSearch || inventoryFilters.searchProduct || ""
    ).trim().toLowerCase();

    const filteredProducts = products.filter((product) => {
      const matchesSearch =
        !searchText ||
        [
          product.name,
          product.brand,
          product.category,
          product.categoryName,
          product.sku,
          product.barcode,
          ...(product.sizes ?? []).flatMap((size) => [size.sku, size.barcode]),
        ].some((value) => String(value ?? "").toLowerCase().includes(searchText));
      const matchesCategory =
        !inventoryFilters.category ||
        product.categoryId === inventoryFilters.category;
      const matchesStock =
        !(routeStockStatus || inventoryFilters.stockStatus) ||
        getProductStockStatus(product) === (routeStockStatus || inventoryFilters.stockStatus);

      return matchesSearch && matchesCategory && matchesStock;
    });

    if (!routeSortBy) return filteredProducts;

    return [...filteredProducts].sort((first, second) => {
      let comparison = 0;
      if (routeSortBy === "name") {
        comparison = String(first.name ?? "").localeCompare(String(second.name ?? ""));
      } else if (routeSortBy === "price") {
        comparison = Number(first.sellingPrice ?? 0) - Number(second.sellingPrice ?? 0);
      } else if (routeSortBy === "stock") {
        comparison = Number(first.availableStock ?? first.stock ?? 0)
          - Number(second.availableStock ?? second.stock ?? 0);
      }
      return routeSortDirection === "desc" ? -comparison : comparison;
    });
  }, [
    inventoryFilters,
    products,
    routeSearch,
    routeSortBy,
    routeSortDirection,
    routeStockStatus,
  ]);

  async function confirmRemoval() {
    if (!removalTarget || !business?.id) return;
    setIsRemoving(true);
    try {
      if (removalTarget.type === "product") {
        await removeProduct(business.id, removalTarget.record.id);
        setProducts((current) => current.filter((product) => product.id !== removalTarget.record.id));
      } else {
        await removeCategory(business.id, removalTarget.record.id);
        setCategories((current) => current.filter((category) => category.id !== removalTarget.record.id));
      }
      setRemovalTarget(null);
    } catch (error) {
      setInventoryError(error);
    } finally {
      setIsRemoving(false);
    }
  }

  function handleExportInventory() {
    if (isExporting) return;
    setIsExporting(true);
    try {
      downloadInventoryCsv(visibleProducts);
    } finally {
      setIsExporting(false);
    }
  }

  const handleBarcodeDetected = useCallback((barcode) => {
    setActiveTab("products");
    setSearchParameters({ search: barcode }, { replace: true });
    setIsBarcodeScannerOpen(false);
  }, [setSearchParameters]);

  function handleExportSelected(selectedIds) {
    const selectedProducts = visibleProducts.filter((product) => selectedIds.includes(product.id));
    downloadInventoryCsv(selectedProducts);
  }

  async function handleBulkStatusChange(selectedIds, status) {
    if (!business?.id) return;
    try {
      const selectedProducts = visibleProducts.filter((product) => selectedIds.includes(product.id));
      const updatedProducts = await Promise.all(
        selectedProducts.map((product) => updateProductStatus(business.id, product.id, status)),
      );
      setProducts((currentProducts) =>
        currentProducts.map((product) =>
          updatedProducts.find((updated) => updated.id === product.id) ?? product,
        ),
      );
    } catch (error) {
      setInventoryError(error);
    }
  }

  async function handleBulkCategoryChange(selectedIds, categoryId) {
    if (!business?.id || !categoryId) return;
    try {
      const selectedProducts = visibleProducts.filter((product) => selectedIds.includes(product.id));
      const updatedProducts = await Promise.all(
        selectedProducts.map((product) => updateProduct(business.id, product.id, { categoryId })),
      );
      setProducts((currentProducts) => currentProducts.map((product) => updatedProducts.find((updated) => updated.id === product.id) ?? product));
    } catch (error) {
      setInventoryError(error);
    }
  }

  return (
    <main className="dashboard">
      <div className="inventory-page__heading">
        <p>Manage products, sizes, stock levels, SKUs and barcodes.</p>

        {activeTab === "products" && (
          <div className="page__actions">
            <button type="button" onClick={() => setIsBarcodeScannerOpen(true)}>
              <ScanBarcode size={18} aria-hidden="true" />
              Scan Barcode
            </button>
            <button type="button" onClick={handleExportInventory} disabled={isExporting}>
              <Download size={18} aria-hidden="true" />
              {isExporting ? "Exporting..." : "Export Inventory"}
            </button>
            <button
              className="page__add-button"
              type="button"
              onClick={() => setIsAddProductOpen(true)}
              disabled={!business?.id}
            >
              <Plus size={18} aria-hidden="true" />
              Add Product
            </button>
          </div>

        )}



        {activeTab === "categories" && (
          <div className="page__actions">
            <button
              className="page__add-button"
              type="button"
              onClick={() => setIsAddCategoryOpen(true)}
              disabled={!business?.id}
            >
              <Plus size={18} aria-hidden="true" />
              Add Category
            </button>
          </div>

        )}







        {/* inventory page buttons starts here*/}




        {/* inventory page buttons ends here*/}

      </div>

      {(accountError || inventoryError) && (
        <p className="inventory-page__notice inventory-page__notice--error" role="alert">
          Inventory data could not be loaded from the Vendly API. Start the
          Flask server and check its Firebase Admin configuration.
        </p>
      )}

      {isInventoryLoading && (
        <p className="inventory-page__notice" role="status">
          Loading inventory...
        </p>
      )}

              <nav
          className="inventory-tabs"
          role="tablist"
          aria-label="Inventory sections"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "products"}
            className={`inventory-tabs__button ${activeTab === "products"
              ? "inventory-tabs__button--active"
              : ""
              }`}
            onClick={() => setActiveTab("products")}
          >
            <Package size={17} aria-hidden="true" />
            Products
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "categories"}
            className={`inventory-tabs__button ${activeTab === "categories"
              ? "inventory-tabs__button--active"
              : ""
              }`}
            onClick={() => setActiveTab("categories")}
          >
            <Tags size={17} aria-hidden="true" />
            Categories
          </button>
        </nav>

      {/* Inventory dashboard starts here */}



      {/* Inventory dashboard ends here */}

      {/* Tabs allow the same Inventory page to switch between two sections. */}



      {/* Product filters and table are rendered only while Products is active. */}
      {activeTab === "products" && (
        <>



          <section aria-label="Inventory dashboard">
            <div className="stats-grid">
              {inventoryStats.map((stat) => (
                <StatCard
                  key={stat.label}
                  label={stat.label}
                  value={stat.value}
                  icon={stat.icon}
                  tone={stat.tone}
                />
              ))}
            </div>
          </section>


          <InventoryFilters
            categories={categories}
            onApply={setInventoryFilters}
            onReset={resetInventoryFilters}
          />
          <InventoryTable
            products={visibleProducts}
            onViewReviews={setReviewProduct}
            onEditProduct={setEditingProduct}
            onRemoveProduct={(product) => setRemovalTarget({ type: "product", record: product })}
            onChangeStatus={handleBulkStatusChange}
            categories={categories}
            onChangeCategory={handleBulkCategoryChange}
            onExportSelected={handleExportSelected}
            onAdjustStock={(product, variantId) =>
              setStockAdjustment({ product, variantId })
            }
          />
        </>
      )}

      {/* Temporary category content shown while Categories is active. */}
      {activeTab === "categories" && (
        <>



          <section aria-label="Inventory dashboard">
            <div className="stats-grid">
              {categoryStats.map((stat) => (
                <StatCard
                  key={stat.label}
                  label={stat.label}
                  value={stat.value}
                  icon={stat.icon}
                  tone={stat.tone}
                />
              ))}
            </div>
          </section>


          <CategoryTable categories={categories} products={products} onEditCategory={setEditingCategory} onRemoveCategory={(category) => setRemovalTarget({ type: "category", record: category })} />
        </>
      )}

      <AddCategoryModal
        isOpen={isAddCategoryOpen}
        businessId={business?.id}
        onClose={() => setIsAddCategoryOpen(false)}
        onCreated={(category) =>
          setCategories((currentCategories) =>
            [...currentCategories, category].sort(
              (first, second) => first.sortOrder - second.sortOrder,
            ),
          )
        }
      />

      <AddCategoryModal
        isOpen={Boolean(editingCategory)}
        businessId={business?.id}
        category={editingCategory}
        onClose={() => setEditingCategory(null)}
        onUpdated={(updated) => {
          setCategories((current) => current.map((category) => category.id === updated.id ? updated : category));
          setEditingCategory(null);
        }}
      />

      <AddProductModal
        isOpen={isAddProductOpen}
        businessId={business?.id}
        categories={categories}
        onClose={() => setIsAddProductOpen(false)}
        onCreated={(product) =>
          setProducts((currentProducts) => [product, ...currentProducts])
        }
      />

      <AddProductModal
        isOpen={Boolean(editingProduct)}
        businessId={business?.id}
        product={editingProduct}
        categories={categories}
        onClose={() => setEditingProduct(null)}
        onUpdated={(updated) => {
          setProducts((current) => current.map((product) => product.id === updated.id ? updated : product));
          setEditingProduct(null);
        }}
      />

      <ConfirmDialog
        isOpen={Boolean(removalTarget)}
        title={removalTarget?.type === "product" ? "Remove product?" : "Remove category?"}
        message={`This will archive ${removalTarget?.record?.name ?? "this item"} and hide it from active lists.`}
        isWorking={isRemoving}
        onCancel={() => setRemovalTarget(null)}
        onConfirm={confirmRemoval}
      />

      <ReviewsModal
        businessId={business?.id}
        product={reviewProduct}
        onClose={() => setReviewProduct(null)}
        onApproved={(productId) =>
          setProducts((current) =>
            current.map((product) =>
              product.id === productId
                ? {
                  ...product,
                  approvedReviews: (product.approvedReviews ?? 0) + 1,
                  approvedReviewCount: (product.approvedReviewCount ?? 0) + 1,
                }
                : product,
            ),
          )
        }
      />

      <AdjustStockModal
        businessId={business?.id}
        product={stockAdjustment?.product ?? null}
        initialVariantId={stockAdjustment?.variantId}
        onClose={() => setStockAdjustment(null)}
        onUpdated={(updatedProduct) =>
          setProducts((currentProducts) =>
            currentProducts.map((product) =>
              product.id === updatedProduct.id ? updatedProduct : product,
            ),
          )
        }
      />

      <BarcodeScannerModal
        isOpen={isBarcodeScannerOpen}
        onClose={() => setIsBarcodeScannerOpen(false)}
        onDetected={handleBarcodeDetected}
      />
    </main>
  );
}

export default InventoryPage;
