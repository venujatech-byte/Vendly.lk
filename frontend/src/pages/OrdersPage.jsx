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
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

// Reusable components that build the Orders page.
import StatCard2 from "../components/StatCard2";
import OrderFilters from "../components/OrderFilters";
import OrderTable from "../components/OrderTable";
import { useAuth } from "../context/authContextValue";
import {
  getOrders,
  removeOrder,
  updateOrder,
  updateOrderStatus,
} from "../services/orderService";
import AddOrderModal from "../components/AddOrderModal";
import EditOrderModal from "../components/EditOrderModal";
import ConfirmDialog from "../components/ConfirmDialog";
import { getCouriers } from "../services/courierService";
import {
  downloadOrderExport,
  generateOrderWaybill,
  reportCourierIssue,
  reportFraudOrder,
} from "../services/operationService";

import "./OrdersPage.css";

function OrdersPage() {
  const [searchParameters, setSearchParameters] = useSearchParams();
  const routeSearch = searchParameters.get("search") ?? "";
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
  const [isRemoving, setIsRemoving] = useState(false);

  // Reset field, status-card, and URL filters so the complete table is shown again.
  function resetOrderFilters() {
    setFilters({});
    setStatusFilter("");
    setSearchParameters({}, { replace: true });
  }

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
          search: filters.orderNumber || filters.waybillNumber || filters.itemName || filters.customer,
          dateFrom: filters.dateFrom,
          dateTo: filters.dateTo,
          courierId: filters.courier,
          ...(routeSearch ? { search: routeSearch } : {}),
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
  }, [business?.id, filters, routeSearch]);

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
    const waybill = window.prompt("Scan or enter the waybill number:", "");
    if (!waybill?.trim()) return;
    setFilters((current) => ({
      ...current,
      waybillNumber: waybill.trim(),
      orderNumber: "",
      itemName: "",
      customer: "",
    }));
  }

  return (
    <main className="dashboard orders-page">
      {/* Page title, description, and order export action. */}
      <div className="dashboard__intro">
 <div className="orders-page__heading">
  <h2>Sales Orders</h2>

 <div className="orders-page__heading-actions">
   <button className="orders-page__export-button" type="button" onClick={handleScanWaybill}>
     <ScanLine size={19} aria-hidden="true" />
     <span>Scan Waybill</span>
   </button>
   <button
     className="orders-page__share-button"
     type="button"
     onClick={handleCopyChatbotLink}
     disabled={!business?.shortCode}
     title="Copy the seller-specific catalogue and chatbot link"
   >
     {linkWasCopied ? (
       <Check size={19} aria-hidden="true" />
     ) : (
       <Link2 size={19} aria-hidden="true" />
     )}
     <span>{linkWasCopied ? "Link Copied" : "Chatbot Link"}</span>
   </button>

   <button
     className="orders-page__export-button"
     type="button"
     onClick={handleExport}
     disabled={isExporting || !business?.id}
   >
    <Download size={19} strokeWidth={1.8} />
    <span>{isExporting ? "Exporting..." : "Export Orders"}</span>
   </button>

   <button
     className="orders-page__add-button"
     type="button"
     onClick={() => setIsAddOrderOpen(true)}
     disabled={!business?.id}
   >
     <Plus size={19} aria-hidden="true" />
     Add Order
   </button>
 </div>
</div>
         <p>View and manage all customer orders.</p>
      </div>
      {(accountError || ordersError) && (
        <p className="orders-page__notice orders-page__notice--error" role="alert">
          Orders could not be loaded from the Vendly API.
        </p>
      )}
      {isLoading && (
        <p className="orders-page__notice" role="status">Loading orders...</p>
      )}
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
      />

      {/* Main expandable orders table. */}
      <OrderTable
        orders={visibleOrders}
        onStatusChange={handleStatusChange}
        onGenerateWaybill={handleGenerateWaybill}
        onFraudReport={handleFraudReport}
        onCourierIssue={handleCourierIssue}
        onEditOrder={setEditingOrder}
        onRemoveOrder={setRemovalTarget}
        onBulkStatusChange={handleBulkStatusChange}
        onExportSelected={handleExportSelected}
        onWaybillSave={handleWaybillSave}
      />

      <AddOrderModal
        isOpen={isAddOrderOpen}
        businessId={business?.id}
        business={business}
        onClose={() => setIsAddOrderOpen(false)}
        onCreated={(order) => setOrders((current) => [order, ...current])}
      />

      <EditOrderModal isOpen={Boolean(editingOrder)} businessId={business?.id} order={editingOrder} onClose={() => setEditingOrder(null)} onUpdated={(updated) => { setOrders((current) => current.map((order) => order.id === updated.id ? updated : order)); setEditingOrder(null); }} />
      <ConfirmDialog isOpen={Boolean(removalTarget)} title="Remove order?" message={`This cancels ${removalTarget?.orderNumber ?? "this order"} and releases its reserved stock.`} isWorking={isRemoving} onCancel={() => setRemovalTarget(null)} onConfirm={confirmOrderRemoval} />
    </main>
  );
}

export default OrdersPage;
