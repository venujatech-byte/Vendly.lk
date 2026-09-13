import {
  Banknote,
  ArchiveX,
  Boxes,
  CircleCheck,
  Clock3,
  LayoutDashboard,
  PackageCheck,
  ReceiptText,
  RotateCcw,
  ShoppingBag,
  Store,
  TrendingUp,
  TriangleAlert,
  UsersRound,
  WalletCards,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import AnalyticsLedger from "../components/AnalyticsLedger";
import CodReconciliation from "../components/CodReconciliation";
import CustomerProfitability from "../components/CustomerProfitability";
import DailyOrdersChart from "../components/DailyOrdersChart";
import DeadStockReport from "../components/DeadStockReport";
import MonthlyRevenueChart from "../components/MonthlyRevenueChart";
import SalesChannelPerformance from "../components/SalesChannelPerformance";
import SalesForecast from "../components/SalesForecast";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/authContextValue";
import {
  formatAnalyticsMoney,
  getAnalyticsLedger,
  getAnalyticsOverview,
  getCodReconciliation,
  saveMonthlyRevenueTarget,
} from "../services/analyticsService";
import "./AnalyticsPage.css";


function percentage(value, total) {
  return total ? Math.round((value / total) * 100) : 0;
}


function formatWeekday(dateString) {
  if (!dateString) return "";
  try {
    const iso = dateString.includes("T") ? dateString : `${dateString}T00:00:00`;
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? dateString : date.toLocaleDateString("en-LK", { weekday: "short" });
  } catch {
    return dateString;
  }
}


function formatMonth(monthString) {
  if (!monthString) return "";
  try {
    const iso = monthString.length === 7 ? `${monthString}-01T00:00:00` : monthString;
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? monthString : date.toLocaleDateString("en-LK", { month: "short" });
  } catch {
    return monthString;
  }
}


function AnalyticsPage() {
  const { business, membership } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [reconciliation, setReconciliation] = useState(null);
  const [error, setError] = useState(null);
  const [ledgerError, setLedgerError] = useState(null);
  const [reconciliationError, setReconciliationError] = useState(null);
  const [activeView, setActiveView] = useState("overview");

  async function handleSaveMonthlyTarget(monthlyTargetMinor) {
    await saveMonthlyRevenueTarget(business.id, monthlyTargetMinor);
    const refreshedAnalytics = await getAnalyticsOverview(business.id);
    setAnalytics(refreshedAnalytics);
  }

  async function handleRefreshLedger() {
    if (!business?.id) return;
    try {
      const data = await getAnalyticsLedger(business.id);
      setLedger(data);
    } catch (requestError) {
      setLedgerError(requestError);
    }
  }

  useEffect(() => {
    let requestIsCurrent = true;
    if (!business?.id) return undefined;

    setError(null);
    getAnalyticsOverview(business.id)
      .then((data) => {
        if (requestIsCurrent) setAnalytics(data);
      })
      .catch((requestError) => {
        if (requestIsCurrent) setError(requestError);
      });
    setLedgerError(null);
    getAnalyticsLedger(business.id)
      .then((data) => {
        if (requestIsCurrent) setLedger(data);
      })
      .catch((requestError) => {
        if (requestIsCurrent) setLedgerError(requestError);
      });
    setReconciliationError(null);
    getCodReconciliation(business.id)
      .then((data) => {
        if (requestIsCurrent) setReconciliation(data);
      })
      .catch((requestError) => {
        if (requestIsCurrent) setReconciliationError(requestError);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id]);

  const visibleMonths = analytics?.monthlyRevenue?.slice(-6) ?? [];

  if (error) {
    return (
      <main className="dashboard analytics-page">
        <div className="analytics-hero">
          <div><span>Insights</span><h2>Business analytics</h2><p role="alert">Analytics could not be loaded from the Vendly API.</p></div>
        </div>
      </main>
    );
  }

  const financials = analytics?.financials ?? {};
  const performance = analytics?.performance ?? {};
  const inventory = analytics?.inventory ?? {};
  const counts = analytics?.orderCounts ?? {};
  const totalOrders = counts.all ?? 0;
  const confirmedToPacked = (counts.confirmed ?? 0) + (counts.packed ?? 0);
  const shipped = counts.shipped ?? 0;
  const delivered = counts.delivered ?? 0;
  const deliveryEnd = percentage(delivered, totalOrders);
  const shippedEnd = percentage(delivered + shipped, totalOrders);
  const progressEnd = percentage(delivered + shipped + confirmedToPacked, totalOrders);
  const productProfitMaximum = Math.max(
    ...(analytics?.productProfitability ?? []).map((item) => Math.max(item.grossProfitMinor, 0)),
    1,
  );
  const inventoryAttention = (inventory.lowStockCount ?? 0) + (inventory.outOfStockCount ?? 0);
  const healthyProducts = Math.max((inventory.productCount ?? 0) - inventoryAttention, 0);

  const summaryCards = [
    {
      label: "Total Revenue",
      value: formatAnalyticsMoney(financials.productRevenueMinor),
      icon: Banknote,
      tone: "green",
      trend: "+18.4%",
      trendLabel: "vs last month",
    },
    {
      label: "Gross profit",
      value: formatAnalyticsMoney(financials.grossProfitMinor),
      icon: TrendingUp,
      tone: "blue",
      trend: `${performance.grossMarginPercent ?? 0}% margin`,
      trendLabel: "overall",
    },
    {
      label: "Total orders",
      value: String(totalOrders),
      icon: PackageCheck,
      tone: "purple",
      trend: `+${performance.ordersToday ?? 0}`,
      trendLabel: "received today",
    },
    {
      label: "Average order",
      value: formatAnalyticsMoney(financials.averageOrderValueMinor),
      icon: ShoppingBag,
      tone: "orange",
      note: `${analytics?.customers?.total ?? 0} active customers`,
    },
  ];

  return (
    <main className="dashboard analytics-page">
      <nav className="analytics-view-tabs" aria-label="Analytics views">
        <button type="button" className={activeView === "overview" ? "is-active" : ""} onClick={() => setActiveView("overview")}><LayoutDashboard size={16} /><span>Overview</span></button>
        <button type="button" className={activeView === "ledger" ? "is-active" : ""} onClick={() => setActiveView("ledger")}><ReceiptText size={16} /><span>Transaction ledger</span></button>
        <button type="button" className={activeView === "cod" ? "is-active" : ""} onClick={() => setActiveView("cod")}><WalletCards size={16} /><span>COD reconciliation</span></button>
        <button type="button" className={activeView === "dead-stock" ? "is-active" : ""} onClick={() => setActiveView("dead-stock")}><ArchiveX size={16} /><span>Dead stock</span></button>
        <button type="button" className={activeView === "customers" ? "is-active" : ""} onClick={() => setActiveView("customers")}><UsersRound size={16} /><span>Customer profit</span></button>
        <button type="button" className={activeView === "channels" ? "is-active" : ""} onClick={() => setActiveView("channels")}><Store size={16} /><span>Sales channels</span></button>
        <button type="button" className={activeView === "forecast" ? "is-active" : ""} onClick={() => setActiveView("forecast")}><TrendingUp size={16} /><span>Forecast</span></button>
      </nav>

      {activeView === "ledger" ? (
        <AnalyticsLedger businessId={business?.id} ledger={ledger} isLoading={!ledger && !ledgerError} error={ledgerError} onRefresh={handleRefreshLedger} />
      ) : activeView === "cod" ? (
        <CodReconciliation businessId={business?.id} reconciliation={reconciliation} isLoading={!reconciliation && !reconciliationError} error={reconciliationError} onChange={setReconciliation} />
      ) : activeView === "dead-stock" ? (
        <DeadStockReport report={analytics?.deadStock} isLoading={!analytics} />
      ) : activeView === "customers" ? (
        <CustomerProfitability report={analytics?.customerProfitability} isLoading={!analytics} />
      ) : activeView === "channels" ? (
        <SalesChannelPerformance report={analytics?.salesChannels} isLoading={!analytics} />
      ) : activeView === "forecast" ? (
        <SalesForecast
          report={analytics?.salesForecast}
          isLoading={!analytics}
          onSaveTarget={handleSaveMonthlyTarget}
          canManageTarget={["owner", "admin"].includes(membership?.role)}
        />
      ) : (
        <>
          <section className="analytics-summary" aria-label="Business totals">
            {summaryCards.map((card) => (
              <StatCard key={card.label} {...card} />
            ))}
          </section>

          {!analytics ? null : (
            <>
              <section className="analytics-grid analytics-grid--charts" aria-label="Sales charts">
                <article className="analytics-panel analytics-panel--chart">
                  <header><div><span>Last 7 days</span><h3>Daily orders</h3><p>Orders received each day</p></div><ShoppingBag size={20} /></header>
                  <DailyOrdersChart data={analytics?.dailyOrders ?? []} />
                </article>

                <article className="analytics-panel analytics-panel--chart">
                  <header><div><span>Last 6 months</span><h3>Monthly product revenue</h3><p>Delivered sales, excluding delivery fees</p></div><Banknote size={20} /></header>
                  <MonthlyRevenueChart data={visibleMonths} />
                </article>
              </section>

          <section className="analytics-grid" aria-label="Financial and order insights">
            <article className="analytics-panel analytics-panel--financial">
              <header><div><span>Profitability</span><h3>Financial health</h3><p>How delivered product revenue becomes gross profit</p></div><TrendingUp size={20} /></header>
              <div className="analytics-financial-flow">
                <div><span>Product revenue</span><strong>{formatAnalyticsMoney(financials.productRevenueMinor)}</strong></div>
                <div><span>Cost of goods</span><strong>− {formatAnalyticsMoney(financials.costOfGoodsMinor)}</strong></div>
                <div className="is-total"><span>Gross profit</span><strong>{formatAnalyticsMoney(financials.grossProfitMinor)}</strong></div>
              </div>
              <div className="analytics-margin">
                <span><b>Gross margin</b><strong>{performance.grossMarginPercent ?? 0}%</strong></span>
                <i><u style={{ width: `${Math.min(Math.max(performance.grossMarginPercent ?? 0, 0), 100)}%` }} /></i>
              </div>
            </article>

            <article className="analytics-panel analytics-panel--status">
              <header><div><span>Fulfilment</span><h3>Order status</h3><p>Current distribution across {totalOrders} orders</p></div><PackageCheck size={20} /></header>
              <div className="analytics-status-layout">
                <div
                  className="analytics-donut"
                  style={{ "--delivery-end": `${deliveryEnd}%`, "--shipped-end": `${shippedEnd}%`, "--progress-end": `${progressEnd}%` }}
                >
                  <span><strong>{totalOrders}</strong><small>orders</small></span>
                </div>
                <div className="analytics-status-legend">
                  <span className="is-delivered"><i />Delivered <b>{delivered}</b></span>
                  <span className="is-shipped"><i />Shipped <b>{shipped}</b></span>
                  <span className="is-progress"><i />Confirmed / packed <b>{confirmedToPacked}</b></span>
                  <span className="is-other"><i />Other <b>{Math.max(totalOrders - delivered - shipped - confirmedToPacked, 0)}</b></span>
                </div>
              </div>
              <div className="analytics-rate-row"><span><CircleCheck /> Delivery success <b>{performance.deliverySuccessPercent ?? 0}%</b></span><span><RotateCcw /> Return rate <b>{performance.returnRatePercent ?? 0}%</b></span></div>
            </article>
          </section>


      <section className="analytics-grid analytics-grid--bottom" aria-label="Product and inventory insights">
        <article className="analytics-panel analytics-panel--products">
          <header><div><span>Product performance</span><h3>Product profitability</h3><p>Delivered revenue after discounts, recorded cost and warranty impact</p></div><TrendingUp size={20} /></header>
          <div className="analytics-products">
            {(analytics?.productProfitability ?? []).length === 0 ? (
              <p className="analytics-empty">Delivered product profitability will appear here.</p>
            ) : analytics.productProfitability.map((product, index) => (
              <div key={product.id}>
                <b>{index + 1}</b>
                <span>
                  <strong>{product.name}</strong>
                  <small>{product.quantity} units · revenue {formatAnalyticsMoney(product.revenueMinor)} · cost {formatAnalyticsMoney(product.costOfGoodsMinor)}</small>
                  <i><u style={{ width: `${(Math.max(product.grossProfitMinor, 0) / productProfitMaximum) * 100}%` }} /></i>
                </span>
                <em className={product.grossProfitMinor < 0 ? "is-negative" : ""}>
                  {formatAnalyticsMoney(product.grossProfitMinor)}
                  <small>{product.grossMarginPercent}% margin</small>
                </em>
              </div>
            ))}
          </div>
        </article>

        <article className="analytics-panel analytics-panel--inventory">
          <header><div><span>Stock control</span><h3>Inventory health</h3><p>Products available and requiring attention</p></div><Boxes size={20} /></header>
          <div className="analytics-inventory-score">
            <div><strong>{inventory.productCount ?? 0}</strong><span>products</span></div>
            <div><strong>{inventory.totalUnits ?? 0}</strong><span>stock units</span></div>
          </div>
          <div className="analytics-inventory-list">
            <span><CircleCheck /><b>Healthy stock</b><strong>{healthyProducts}</strong></span>
            <span><TriangleAlert /><b>Low stock</b><strong>{inventory.lowStockCount ?? 0}</strong></span>
            <span><Boxes /><b>Out of stock</b><strong>{inventory.outOfStockCount ?? 0}</strong></span>
          </div>
          <div className="analytics-work-note"><Clock3 size={17} /><span><strong>{analytics?.workCentre?.needsConfirmation ?? 0} orders need confirmation</strong><small>{analytics?.workCentre?.needsPacking ?? 0} more are ready to pack</small></span></div>
        </article>
      </section>

      <p className="analytics-page__footnote">
        Product profitability uses delivered revenue after discounts, recorded product cost and product-linked warranty deductions. It does not subtract salaries, rent, advertising, tax or other operating expenses.
      </p>
            </>
          )}
        </>
      )}
    </main>
  );
}


export default AnalyticsPage;
