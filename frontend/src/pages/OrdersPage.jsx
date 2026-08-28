// Icons used by the order statistics and export button.
import {
  CircleCheck,
  Clock3,
  Package,
  Truck,
  Undo2,
  SquareCheckBig,
  Package2,
  Download,
  Plus,
  Link2,
  Check,
  ScanLine,
  Store,
  GlobeCheck,
  ShieldCheck,
  Banknote,
  ShoppingBasket,
  Trophy,
  ReceiptText,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

// Reusable components that build the Orders page.
import StatCard2 from "../components/StatCard2";
import StatCard from "../components/StatCard";
import OrderFilters from "../components/OrderFilters";
import OrderTable from "../components/OrderTable";
import RecordPaymentModal from "../components/RecordPaymentModal";
import { useAuth } from "../context/authContextValue";
import {
  getOrders,
  removeOrder,
  updateOrder,
  updateOrderStatus,
  recordOrderPayment,
} from "../services/orderService";
import AddOrderModal from "../components/AddOrderModal";
import EditOrderModal from "../components/EditOrderModal";
import ConfirmDialog from "../components/ConfirmDialog";
import AddShopSaleModal from "../components/AddShopSaleModal";
import ShopSaleFilters from "../components/ShopSaleFilters";
import ShopSalesTable from "../components/ShopSalesTable";
import WarrantyClaimModal from "../components/WarrantyClaimModal";
import WarrantyClaimsTable from "../components/WarrantyClaimsTable";
import BarcodeScannerModal from "../components/BarcodeScannerModal";
import { getCouriers } from "../services/courierService";
import {
  downloadOrderExport,
  generateOrderWaybill,
  reportCourierIssue,
  reportFraudOrder,
} from "../services/operationService";
import {
  createWarrantyClaim,
  getShopSales,
  getWarrantyClaims,
  removeShopSale,
} from "../services/shopSaleService";
import { downloadReceiptPdf } from "../services/receiptService";

import "./OrdersPage.css";
import "./Buttons.css";
import "./InventoryPage.css";

function OrdersPage() {
  const [activeTab, setActiveTab] = useState("onlineOrders");
  const [searchParameters, setSearchParameters] = useSearchParams();
  const routeSearch = searchParameters.get("search") ?? "";
  const routeStatus = searchParameters.get("status") ?? "";
  const routeDateFrom = searchParameters.get("dateFrom") ?? "";
  const routeDateTo = searchParameters.get("dateTo") ?? "";
  const routeCourier = searchParameters.get("courier") ?? "";
  const assistantAction = searchParameters.get("assistantAction") ?? "";
  const { business, accountError } = useAuth();
  const [orders, setOrders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [ordersError, setOrdersError] = useState(null);
  const [filters, setFilters] = useState({});
  const [isAddOrderOpen, setIsAddOrderOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [couriers, setCouriers] = useState([]);
  const [linkWasCopied, setLinkWasCopied] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [editingOrder, setEditingOrder] = useState(null);
  const [removalTarget, setRemovalTarget] = useState(null);
  const [paymentTarget, setPaymentTarget] = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [shopSales, setShopSales] = useState([]);
  const [shopFilters, setShopFilters] = useState({});
  const [isAddShopSaleOpen, setIsAddShopSaleOpen] = useState(false);
  const [shopRemovalTarget, setShopRemovalTarget] = useState(null);
  const [warrantyClaims, setWarrantyClaims] = useState([]);
  const [warrantySource, setWarrantySource] = useState(null);
  const [isWaybillScannerOpen, setIsWaybillScannerOpen] = useState(false);

  // URL filters are created by the Business Assistant. Keep them separate
  // from the form state so a new assistant request replaces old form filters.
  const assistantOrderFilters = useMemo(() => {
    if (!routeSearch && !routeDateFrom && !routeDateTo && !routeStatus && !routeCourier) return null;
    return {
      search: routeSearch,
      dateFrom: routeDateFrom,
      dateTo: routeDateTo,
      status: routeStatus,
      courier: routeCourier,
    };
  }, [routeSearch, routeDateFrom, routeDateTo, routeStatus, routeCourier]);

  const assistantShopSaleFilters = useMemo(() => {
    if (!routeDateFrom && !routeDateTo) return null;
    return { dateFrom: routeDateFrom, dateTo: routeDateTo };
  }, [routeDateFrom, routeDateTo]);

  // The business assistant reuses the same validated forms as the page buttons.
  useEffect(() => {
    if (!assistantAction) return;

    if (assistantAction === "add-order") {
      setActiveTab("onlineOrders");
      setIsAddOrderOpen(true);
    } else if (assistantAction === "open-online-orders") {
      setActiveTab("onlineOrders");
    } else if (assistantAction === "add-shop-sale") {
      setActiveTab("shopOrders");
      setIsAddShopSaleOpen(true);
    } else if (assistantAction === "open-shop-sales") {
      setActiveTab("shopOrders");
    } else if (assistantAction === "open-warranty-claims") {
      setActiveTab("warrantyClaims");
    } else if (assistantAction === "scan-waybill") {
      setActiveTab("onlineOrders");
      window.setTimeout(handleScanWaybill, 50);
    }

    const nextParameters = new URLSearchParams(searchParameters);
    nextParameters.delete("assistantAction");
    setSearchParameters(nextParameters, { replace: true });
  }, [assistantAction, searchParameters, setSearchParameters]);

  useEffect(() => {
    const validStatuses = new Set([
      "pending",
      "confirmed",
      "packed",
      "shipped",
      "delivered",
      "returned",
      "cancelled",
    ]);
    setStatusFilter(validStatuses.has(routeStatus) ? routeStatus : "");
  }, [routeStatus]);

  useEffect(() => {
    // A new route-based filter starts from a clean local form state. The
    // route values above then become the only active filter values.
    if (assistantOrderFilters) setFilters({});
    if (assistantShopSaleFilters) setShopFilters({});
  }, [assistantOrderFilters, assistantShopSaleFilters]);

  // Reset field, status-card, and URL filters so the complete table is shown again.
  function resetOrderFilters() {
    setFilters({});
    setStatusFilter("");
    setSearchParameters({}, { replace: true });
  }

  useEffect(() => {
    function handleAssistantFilterReset() {
      setFilters({});
      setStatusFilter("");
      setShopFilters({});
      setSearchParameters({}, { replace: true });
    }

    window.addEventListener("vendly:reset-filters", handleAssistantFilterReset);
    return () => window.removeEventListener("vendly:reset-filters", handleAssistantFilterReset);
  }, [setSearchParameters]);

  useEffect(() => {
    let requestIsCurrent = true;

    async function loadOrders() {
      if (!business?.id) {
        setOrders([]);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setOrdersError(null);

      try {
        const orderRecords = await getOrders(business.id, {
          search: filters.search,
          dateFrom: filters.dateFrom,
          dateTo: filters.dateTo,
          courierId: filters.courier,
          ...(routeSearch ? { search: routeSearch } : {}),
          ...(routeDateFrom ? { dateFrom: routeDateFrom } : {}),
          ...(routeDateTo ? { dateTo: routeDateTo } : {}),
          ...(routeCourier ? { courierId: routeCourier } : {}),
        });

        if (requestIsCurrent) {
          setOrders(orderRecords);
        }
      } catch (error) {
        console.error("Orders could not be loaded:", error);

        if (requestIsCurrent) {
          setOrdersError(error);
          setOrders([]);
        }
      } finally {
        if (requestIsCurrent) setIsLoading(false);
      }
    }

    loadOrders();
    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id, filters, routeSearch, routeDateFrom, routeDateTo, routeCourier]);

  useEffect(() => {
    if (!business?.id) return;
    getShopSales(business.id, {
      ...shopFilters,
      ...(routeDateFrom ? { dateFrom: routeDateFrom } : {}),
      ...(routeDateTo ? { dateTo: routeDateTo } : {}),
    }).then(setShopSales).catch(setOrdersError);
  }, [business?.id, shopFilters, routeDateFrom, routeDateTo]);

  useEffect(() => {
    if (!business?.id) return;
    getWarrantyClaims(business.id).then(setWarrantyClaims).catch(setOrdersError);
  }, [business?.id]);

  const visibleOrders = useMemo(() => {
    if (!statusFilter) return orders;
    return orders.filter((order) => order.status === statusFilter);
  }, [orders, statusFilter]);

  useEffect(() => {
    if (!business?.id) return;

    getCouriers(business.id)
      .then(setCouriers)
      .catch((error) => console.error("Courier filters could not be loaded:", error));
  }, [business?.id]);

  const orderStats2 = useMemo(
    () => [
      { label: "All", value: orders.length, icon: Package, tone: "blue" },
      {
        label: "Pending",
        value: orders.filter((order) => order.status === "pending").length,
        icon: Clock3,
        tone: "orange",
      },
      {
        label: "Confirmed",
        value: orders.filter((order) => order.status === "confirmed").length,
        icon: SquareCheckBig,
        tone: "green",
      },
      {
        label: "Packed",
        value: orders.filter((order) => order.status === "packed").length,
        icon: Package2,
        tone: "blue",
      },
      {
        label: "Shipped",
        value: orders.filter((order) => order.status === "shipped").length,
        icon: Truck,
        tone: "purple",
      },
      {
        label: "Delivered",
        value: orders.filter((order) => order.status === "delivered").length,
        icon: CircleCheck,
        tone: "green",
      },
      {
        label: "Returned",
        value: orders.filter((order) => order.status === "returned").length,
        icon: Undo2,
        tone: "red",
      },
    ],
    [orders],
  );

  const shopStats = useMemo(() => {
    const activeSales = shopSales.filter((sale) => sale.status !== "voided");
    // Supplier claims do not cost the seller. Shop claims and repairs do.
    const shopWarrantyDeductions = warrantyClaims
      .filter((claim) => claim.sourceType === "shop-sale" && claim.status !== "cancelled")
      .reduce((sum, claim) => sum + (claim.revenueImpactMinor ?? 0), 0);
    const itemCounts = new Map();
    activeSales.forEach((sale) => sale.items.forEach((item) => itemCounts.set(item.name, (itemCounts.get(item.name) ?? 0) + item.quantity)));
    const topItem = [...itemCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";
    return [
      { label: "Total sales", value: activeSales.length, icon: ReceiptText, tone: "blue" },
      { label: "Sold items", value: activeSales.reduce((sum, sale) => sum + sale.itemCount, 0), icon: ShoppingBasket, tone: "green" },
      { label: "Revenue", value: `LKR ${((activeSales.reduce((sum, sale) => sum + sale.totalAmountMinor, 0) - shopWarrantyDeductions) / 100).toLocaleString("en-LK")}`, icon: Banknote, tone: "orange" },
      { label: "Top item", value: topItem, icon: Trophy, tone: "purple" },
    ];
  }, [shopSales, warrantyClaims]);

  function openOnlineWarranty(order) { setWarrantySource({ ...order, sourceType: "online-order" }); }
  function openShopWarranty(sale) { setWarrantySource({ ...sale, sourceType: "shop-sale" }); }

  async function confirmShopSaleRemoval() {
    if (!shopRemovalTarget || !business?.id) return;
    setIsRemoving(true);
    try {
      await removeShopSale(business.id, shopRemovalTarget.id);
      setShopSales((current) => current.filter((sale) => sale.id !== shopRemovalTarget.id));
      setShopRemovalTarget(null);
    } catch (error) { setOrdersError(error); } finally { setIsRemoving(false); }
  }

  function printShopReceipt(sale) {
    downloadReceiptPdf(business, { ...sale, orderNumber: sale.saleNumber, deliveryFeeMinor: 0, taxTotalMinor: 0, deliveryAddress: {}, paymentMethod: "paid" });
  }

  async function handleStatusChange(orderId, status) {
    if (!business?.id) return;

    try {
      const updatedOrder = await updateOrderStatus(
        business.id,
        orderId,
        status,
      );
      setOrders((current) =>
        current.map((order) => (order.id === orderId ? updatedOrder : order)),
      );
    } catch (error) {
      setOrdersError(error);
    }
  }

  async function handleBulkStatusChange(selectedIds, status) {
    if (!business?.id) return;
    try {
      const updatedOrders = await Promise.all(
        selectedIds.map((orderId) => updateOrderStatus(business.id, orderId, status)),
      );
      setOrders((currentOrders) =>
        currentOrders.map((order) =>
          updatedOrders.find((updated) => updated.id === order.id) ?? order,
        ),
      );
    } catch (error) {
      setOrdersError(error);
    }
  }

  function handleExportSelected(selectedIds) {
    const selectedOrders = visibleOrders.filter((order) => selectedIds.includes(order.id));
    const columns = ["Order number", "Customer", "Phone", "Items", "Subtotal", "Delivery fee", "Total", "Courier", "Status", "Date"];
    const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const rows = selectedOrders.map((order) => [
      order.orderNumber,
      order.customerName,
      order.phoneNumber,
      order.itemCount,
      order.subtotal,
      order.deliveryFee,
      order.total,
      order.courier,
      order.status,
      `${order.date} ${order.time}`,
    ]);
    const csv = [columns, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `vendly-selected-orders-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  // Export only the currently loaded physical-shop sales, including active filters.
  function handleExportShopSales() {
    const activeSales = shopSales.filter((sale) => sale.status !== "voided");
    const columns = ["Sale number", "Customer", "Items", "Subtotal", "Discount", "Total", "Date"];
    const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const rows = activeSales.map((sale) => [
      sale.saleNumber,
      sale.customerName || "Walk-in customer",
      (sale.items ?? []).map((item) => `${item.productName || item.name} x ${item.quantity}`).join("; "),
      sale.subtotal,
      sale.discount,
      sale.total,
      `${sale.date} ${sale.time}`,
    ]);
    const csv = [columns, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `vendly-shop-sales-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function confirmOrderRemoval() {
    if (!removalTarget || !business?.id) return;
    setIsRemoving(true);
    try {
      const removed = await removeOrder(business.id, removalTarget.id);
      setOrders((current) => current.filter((order) => order.id !== removed.id));
      setRemovalTarget(null);
    } catch (error) { setOrdersError(error); }
    finally { setIsRemoving(false); }
  }

  async function handleGenerateWaybill(orderId) {
    const updatedOrder = await generateOrderWaybill(business.id, orderId);
    setOrders((current) =>
      current.map((order) => (order.id === orderId ? updatedOrder : order)),
    );
    return updatedOrder;
  }

  async function handleWaybillSave(orderId, waybillNumber) {
    const updatedOrder = await updateOrder(business.id, orderId, { waybillNumber });
    setOrders((current) =>
      current.map((order) => (order.id === orderId ? updatedOrder : order)),
    );
    return updatedOrder;
  }

  async function handleFraudReport(orderId, note) {
    await reportFraudOrder(business.id, orderId, "fake-details", note);
    setOrders((current) =>
      current.map((order) =>
        order.id === orderId
          ? { ...order, fraudReport: { status: "active", reason: "fake-details" } }
          : order,
      ),
    );
  }

  async function handleCourierIssue(orderId, note) {
    await reportCourierIssue(business.id, orderId, "branch-problem", note);
  }

  async function handleExport() {
    if (!business?.id || isExporting) return;

    setIsExporting(true);
    setOrdersError(null);

    try {
      await downloadOrderExport(business.id);
    } catch (error) {
      setOrdersError(error);
    } finally {
      setIsExporting(false);
    }
  }

  async function handleCopyChatbotLink() {
    if (!business?.shortCode) return;

    const chatbotLink = `${window.location.origin}/s/${business.shortCode}`;

    try {
      await navigator.clipboard.writeText(chatbotLink);
      setLinkWasCopied(true);
      window.setTimeout(() => setLinkWasCopied(false), 2200);
    } catch {
      window.prompt("Copy your Vendly chatbot link:", chatbotLink);
    }
  }

  function handleScanWaybill() {
    setActiveTab("onlineOrders");
    setIsWaybillScannerOpen(true);
  }

  const handleWaybillDetected = useCallback((waybillNumber) => {
    const value = waybillNumber.trim();
    if (!value) return;

    // A waybill scan is an exact search intent. Remove any previous local or
    // status filters so they cannot hide the matching order.
    setFilters({});
    setStatusFilter("");
    setSearchParameters({ search: value }, { replace: true });
    setIsWaybillScannerOpen(false);
  }, [setSearchParameters]);

  return (
    <main className="dashboard orders-page">
      {/* Page title, description, and order export action. */}
      <div className="dashboard__intro">
        <div className="inventory-page__heading">
          <p>View and manage all customer orders.</p>

          {activeTab === "onlineOrders" && <div className="page__actions">
              <button type="button" onClick={handleScanWaybill}>
                <ScanLine size={19} aria-hidden="true" />
                <span>Scan Waybill</span>
              </button>
              <button type="button" onClick={handleCopyChatbotLink} disabled={!business?.shortCode} title="Copy the seller-specific catalogue and chatbot link">
                {linkWasCopied ? <Check size={19} aria-hidden="true" /> : <Link2 size={19} aria-hidden="true" />}
                <span>{linkWasCopied ? "Link Copied" : "Chatbot Link"}</span>
              </button>
              <button type="button" onClick={handleExport} disabled={isExporting || !business?.id}>
                <Download size={19} strokeWidth={1.8} />
                <span>{isExporting ? "Exporting..." : "Export Orders"}</span>
              </button>
              <button className="page__add-button" type="button" onClick={() => setIsAddOrderOpen(true)} disabled={!business?.id}>
                <Plus size={19} aria-hidden="true" />
                Add Order
              </button>
            </div>}

          {activeTab === "shopOrders" && <div className="page__actions">
              <button type="button" onClick={handleExportShopSales} disabled={!shopSales.length}>
                <Download size={19} strokeWidth={1.8} aria-hidden="true" />
                <span>Export Sales</span>
              </button>
              <button className="page__add-button" type="button" onClick={() => setIsAddShopSaleOpen(true)} disabled={!business?.id}>
                <Plus size={19} aria-hidden="true" />
                Add Shop Sale
              </button>
            </div>}
        </div>

      </div>
      {(accountError || ordersError) && (
        <p className="orders-page__notice orders-page__notice--error" role="alert">
          Orders could not be loaded from the Vendly API.
        </p>
      )}
      {isLoading && (
        <p className="orders-page__notice" role="status">Loading orders...</p>
      )}



      <nav
        className="inventory-tabs"
        role="tablist"
        aria-label="Inventory sections"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "onlineOrders"}
          className={`inventory-tabs__button ${activeTab === "onlineOrders" ? "inventory-tabs__button--active" : ""}`}
          onClick={() => setActiveTab("onlineOrders")}
        >
          <GlobeCheck size={17} aria-hidden="true" />
          Online Orders
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "shopOrders"}
          className={`inventory-tabs__button ${activeTab === "shopOrders"
            ? "inventory-tabs__button--active"
            : ""
            }`}
          onClick={() => setActiveTab("shopOrders")}
        >
          <Store size={17} aria-hidden="true" />
          Shop Sales
        </button>


                <button
          type="button"
          role="tab"
          aria-selected={activeTab === "warrantyClaims"}
          className={`inventory-tabs__button ${activeTab === "warrantyClaims"
            ? "inventory-tabs__button--active"
            : ""
            }`}
          onClick={() => setActiveTab("warrantyClaims")}
        >
          <ShieldCheck size={17} aria-hidden="true" />
          Warranty claims
        </button>
      </nav>




      {activeTab === "onlineOrders" && (
        <>

          {/* Order status summary cards. */}
          <section aria-labelledby="order-dashboard-title">

            <div className="order-stats-grid">
              {orderStats2.map((stat) => (
                <StatCard2
                  key={stat.label}
                  label={stat.label}
                  value={stat.value}
                  icon={stat.icon}
                  tone={stat.tone}
                  isActive={(statusFilter === "" && stat.label === "All") || statusFilter === stat.label.toLowerCase()}
                  onClick={() => setStatusFilter(stat.label === "All" ? "" : stat.label.toLowerCase())}
                />
              ))}
            </div>
          </section>


          {/* Filters narrow the orders shown in the table below. */}
          <OrderFilters
            couriers={couriers}
            onApply={setFilters}
            onReset={resetOrderFilters}
            onStatusChange={setStatusFilter}
            appliedFilters={assistantOrderFilters}
          />

          {/* Main expandable orders table. */}
          <OrderTable
            orders={visibleOrders}
            onStatusChange={handleStatusChange}
            onGenerateWaybill={handleGenerateWaybill}
            onFraudReport={handleFraudReport}
            onRecordPayment={setPaymentTarget}
            onCourierIssue={handleCourierIssue}
            onEditOrder={setEditingOrder}
            onRemoveOrder={setRemovalTarget}
            onBulkStatusChange={handleBulkStatusChange}
            onExportSelected={handleExportSelected}
            onWaybillSave={handleWaybillSave}
            onWarrantyClaim={openOnlineWarranty}
          />

        </>
      )}





      {paymentTarget && (
        <RecordPaymentModal
          order={paymentTarget}
          onClose={() => setPaymentTarget(null)}
          onSubmit={async (payment) => {
            const updated = await recordOrderPayment(
              businessId,
              paymentTarget.id,
              payment,
            );
            // Replaced in place: the row's colour and the balance the courier
            // collects both come from this order, so a stale copy would show
            // the seller a payment they have just recorded as still missing.
            setOrders((current) =>
              current.map((order) =>
                order.id === updated.id ? updated : order,
              ),
            );
          }}
        />
      )}

      {activeTab === "shopOrders" && (
        <>
          <section aria-label="Shop sales summary">
            <div className="stats-grid shop-sales-stats">
              {shopStats.map((stat) => (
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
          <ShopSaleFilters onChange={setShopFilters} appliedFilters={assistantShopSaleFilters} />
          <ShopSalesTable sales={shopSales.filter((sale) => sale.status !== "voided")} onPrint={printShopReceipt} onWarranty={openShopWarranty} onRemove={setShopRemovalTarget}/>
        </>
      )}

      {activeTab === "warrantyClaims" && (
        <>
          <div className="shop-sales-heading"><div><h2>Warranty claims</h2><p>Claims from online orders and physical shop sales appear together.</p></div></div>
          <WarrantyClaimsTable claims={warrantyClaims}/>
        </>
      )}







      <AddOrderModal
        isOpen={isAddOrderOpen}
        businessId={business?.id}
        business={business}
        onClose={() => setIsAddOrderOpen(false)}
        onCreated={(order) => setOrders((current) => [order, ...current])}
      />
      <AddShopSaleModal isOpen={isAddShopSaleOpen} businessId={business?.id} onClose={() => setIsAddShopSaleOpen(false)} onCreated={(sale) => setShopSales((current) => [sale, ...current])}/>
      <WarrantyClaimModal source={warrantySource} businessId={business?.id} onClose={() => setWarrantySource(null)} onCreate={async (businessId, payload) => { const claim = await createWarrantyClaim(businessId, payload); setWarrantyClaims((current) => [claim, ...current]); }}/>

      <EditOrderModal isOpen={Boolean(editingOrder)} businessId={business?.id} order={editingOrder} onClose={() => setEditingOrder(null)} onUpdated={(updated) => { setOrders((current) => current.map((order) => order.id === updated.id ? updated : order)); setEditingOrder(null); }} />
      <ConfirmDialog isOpen={Boolean(removalTarget)} title="Remove order?" message={`This cancels ${removalTarget?.orderNumber ?? "this order"} and releases its reserved stock.`} isWorking={isRemoving} onCancel={() => setRemovalTarget(null)} onConfirm={confirmOrderRemoval} />
      <ConfirmDialog isOpen={Boolean(shopRemovalTarget)} title="Delete shop sale?" message={`Deleting ${shopRemovalTarget?.saleNumber ?? "this sale"} restores every sold item to inventory. This action is recorded in stock history.`} isWorking={isRemoving} onCancel={() => setShopRemovalTarget(null)} onConfirm={confirmShopSaleRemoval} />
      <BarcodeScannerModal
        isOpen={isWaybillScannerOpen}
        onClose={() => setIsWaybillScannerOpen(false)}
        onDetected={handleWaybillDetected}
        title="Scan waybill"
        description="Place the waybill barcode or QR code inside the camera frame."
        manualLabel="Or enter the waybill number"
        inputPlaceholder="Scan or enter a waybill number"
        submitLabel="Use waybill"
      />
    </main>
  );
}

export default OrdersPage;
