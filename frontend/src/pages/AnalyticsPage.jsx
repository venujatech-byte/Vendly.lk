import {
  Banknote,
  Boxes,
  CircleCheck,
  Clock3,
  LayoutDashboard,
  PackageCheck,
  ReceiptText,
  RotateCcw,
  ShoppingBag,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import AnalyticsLedger from "../components/AnalyticsLedger";
import { useAuth } from "../context/authContextValue";
import {
  formatAnalyticsMoney,
  getAnalyticsLedger,
  getAnalyticsOverview,
} from "../services/analyticsService";
import "./AnalyticsPage.css";


function percentage(value, total) {
  return total ? Math.round((value / total) * 100) : 0;
}


function AnalyticsPage() {
  const { business } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [error, setError] = useState(null);
  const [ledgerError, setLedgerError] = useState(null);
  const [activeView, setActiveView] = useState("overview");

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

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id]);

  const maximumDailyOrders = useMemo(
    () => Math.max(...(analytics?.dailyOrders ?? []).map((item) => item.count), 1),
    [analytics],
  );
  const visibleMonths = analytics?.monthlyRevenue?.slice(-6) ?? [];
  const maximumMonthlyRevenue = Math.max(
    ...visibleMonths.map((item) => item.revenueMinor),
    1,
  );

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
  const topProductMaximum = Math.max(
    ...(analytics?.topProducts ?? []).map((item) => item.quantity),
    1,
  );
  const inventoryAttention = (inventory.lowStockCount ?? 0) + (inventory.outOfStockCount ?? 0);
  const healthyProducts = Math.max((inventory.productCount ?? 0) - inventoryAttention, 0);

  const summaryCards = [
    { label: "Product revenue", value: formatAnalyticsMoney(financials.productRevenueMinor), note: "Delivered product sales", icon: Banknote, tone: "blue" },
    { label: "Gross profit", value: formatAnalyticsMoney(financials.grossProfitMinor), note: `${performance.grossMarginPercent ?? 0}% gross margin`, icon: TrendingUp, tone: "green" },
    { label: "Total orders", value: totalOrders, note: `${performance.ordersToday ?? 0} received today`, icon: PackageCheck, tone: "purple" },
    { label: "Average order", value: formatAnalyticsMoney(financials.averageOrderValueMinor), note: `${analytics?.customers?.total ?? 0} customers`, icon: ShoppingBag, tone: "orange" },
  ];

  return (
    <main className="dashboard analytics-page">
      <section className="analytics-hero" aria-labelledby="analytics-title">
        <div>
          <span>Business intelligence</span>
          <h2 id="analytics-title">Analytics &amp; insights</h2>
          <p>Understand sales, profitability, fulfilment and inventory from one place.</p>
        </div>
        <div className="analytics-hero__signals">
          <span><ShoppingBag size={16} /><b>{performance.currentWeekOrders ?? 0}</b> orders this week</span>
          <span className={(performance.weeklyOrderChangePercent ?? 0) < 0 ? "is-negative" : ""}>
            <TrendingUp size={16} /><b>{performance.weeklyOrderChangePercent ?? 0}%</b> vs previous week
          </span>
          <span><CircleCheck size={16} /><b>{performance.deliverySuccessPercent ?? 0}%</b> delivery success</span>
        </div>
      </section>

      <nav className="analytics-view-tabs" aria-label="Analytics views">
        <button type="button" className={activeView === "overview" ? "is-active" : ""} onClick={() => setActiveView("overview")}><LayoutDashboard size={16} /> Overview</button>
        <button type="button" className={activeView === "ledger" ? "is-active" : ""} onClick={() => setActiveView("ledger")}><ReceiptText size={16} /> Transaction ledger</button>
      </nav>

      {activeView === "ledger" ? (
        <AnalyticsLedger ledger={ledger} isLoading={!ledger && !ledgerError} error={ledgerError} />
      ) : (
        <>

      <section className="analytics-summary" aria-label="Business totals">
        {summaryCards.map(({ label, value, note, icon: Icon, tone }) => (
          <article className={`analytics-summary__card analytics-summary__card--${tone}`} key={label}>
            <Icon aria-hidden="true" />
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>

      <section className="analytics-grid analytics-grid--charts" aria-label="Sales charts">
        <article className="analytics-panel analytics-panel--chart">
          <header><div><span>Last 7 days</span><h3>Daily orders</h3><p>Orders received each day</p></div><ShoppingBag size={20} /></header>
          <div className="analytics-bars analytics-bars--daily">
            {(analytics?.dailyOrders ?? []).map((item) => (
              <div key={item.date}>
                <span className="analytics-bars__value">{item.count}</span>
                <i style={{ height: `${Math.max((item.count / maximumDailyOrders) * 100, 4)}%` }} />
                <small>{new Date(`${item.date}T00:00:00`).toLocaleDateString("en-LK", { weekday: "short" })}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="analytics-panel analytics-panel--chart">
          <header><div><span>Last 6 months</span><h3>Monthly product revenue</h3><p>Delivered sales, excluding delivery fees</p></div><Banknote size={20} /></header>
          <div className="analytics-bars">
            {visibleMonths.map((item) => (
              <div key={item.month}>
                <span className="analytics-bars__value">{formatAnalyticsMoney(item.revenueMinor).replace("LKR ", "")}</span>
                <i style={{ height: `${Math.max((item.revenueMinor / maximumMonthlyRevenue) * 100, 4)}%` }} />
                <small>{new Date(`${item.month}-01T00:00:00`).toLocaleDateString("en-LK", { month: "short" })}</small>
              </div>
            ))}
          </div>
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
          <header><div><span>Product performance</span><h3>Top-selling products</h3><p>Ranked by delivered units and product revenue</p></div><Boxes size={20} /></header>
          <div className="analytics-products">
            {(analytics?.topProducts ?? []).length === 0 ? (
              <p className="analytics-empty">Delivered product sales will appear here.</p>
            ) : analytics.topProducts.map((product, index) => (
              <div key={product.id}>
                <b>{index + 1}</b>
                <span><strong>{product.name}</strong><small>{product.quantity} units sold</small><i><u style={{ width: `${(product.quantity / topProductMaximum) * 100}%` }} /></i></span>
                <em>{formatAnalyticsMoney(product.revenueMinor)}</em>
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
        Gross profit is product revenue minus recorded product cost. It does not subtract salaries, rent, advertising, tax or other operating expenses.
      </p>
        </>
      )}
    </main>
  );
}


export default AnalyticsPage;
