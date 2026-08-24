import {
  ArrowRight,
  BarChart3,
  BellRing,
  Boxes,
  CircleCheck,
  CircleDollarSign,
  Clock3,
  Package,
  Package2,
  ShoppingBag,
  SquareCheckBig,
  TrendingUp,
  TriangleAlert,
  Truck,
  Undo2,
  Users,
  WalletCards,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import StatCard from "../components/StatCard";
import { useAuth } from "../context/authContextValue";
import {
  formatAnalyticsMoney,
  getAnalyticsOverview,
} from "../services/analyticsService";
import "./OrdersPage.css";
import "./OverviewPage.css";


const STATUS_LABELS = {
  "needs-confirmation": "Needs confirmation",
  confirmed: "Confirmed",
  packed: "Packed",
  shipped: "Shipped",
  delivered: "Delivered",
  returned: "Returned",
  cancelled: "Cancelled",
};


function formatOrderDate(value) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString("en-LK", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}


function OverviewPage() {
  const { sellerProfile, business } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";
  const [analytics, setAnalytics] = useState(null);
  const [analyticsError, setAnalyticsError] = useState(null);

  useEffect(() => {
    let requestIsCurrent = true;
    if (!business?.id) return undefined;

    setAnalyticsError(null);
    getAnalyticsOverview(business.id)
      .then((data) => {
        if (requestIsCurrent) setAnalytics(data);
      })
      .catch((error) => {
        if (requestIsCurrent) setAnalyticsError(error);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [business?.id]);

  const orderStats = useMemo(() => {
    const counts = analytics?.orderCounts ?? {};
    return [
      { label: "All", value: counts.all ?? 0, icon: Package, tone: "blue" },
      { label: "Pending", value: counts["needs-confirmation"] ?? 0, icon: Clock3, tone: "orange" },
      { label: "Confirmed", value: counts.confirmed ?? 0, icon: SquareCheckBig, tone: "green" },
      { label: "Packed", value: counts.packed ?? 0, icon: Package2, tone: "blue" },
      { label: "Shipped", value: counts.shipped ?? 0, icon: Truck, tone: "purple" },
      { label: "Delivered", value: counts.delivered ?? 0, icon: CircleCheck, tone: "green" },
      { label: "Returned", value: counts.returned ?? 0, icon: Undo2, tone: "red" },
    ];
  }, [analytics]);

  const workItems = [
    {
      label: "Orders need confirmation",
      description: "Review new customer orders",
      value: analytics?.workCentre?.needsConfirmation ?? 0,
      icon: Clock3,
      tone: "orange",
      to: "/orders",
    },
    {
      label: "Orders ready to pack",
      description: "Prepare confirmed orders",
      value: analytics?.workCentre?.needsPacking ?? 0,
      icon: Package2,
      tone: "blue",
      to: "/orders",
    },
    {
      label: "Products need restocking",
      description: "Low and out-of-stock items",
      value: (analytics?.workCentre?.lowStockProducts ?? 0) + (analytics?.workCentre?.outOfStockProducts ?? 0),
      icon: TriangleAlert,
      tone: "red",
      to: "/inventory",
    },
    {
      label: "Unread notifications",
      description: "Updates requiring attention",
      value: analytics?.workCentre?.unreadNotifications ?? 0,
      icon: BellRing,
      tone: "purple",
      to: "/",
    },
  ];

  const financials = analytics?.financials ?? {};
  const performance = analytics?.performance ?? {};
  const inventory = analytics?.inventory ?? {};
  const topProductMaximum = Math.max(
    ...(analytics?.topProducts ?? []).map((item) => item.quantity),
    1,
  );

  return (
    <main className="dashboard overview-page">
      <section className="overview-hero" aria-labelledby="overview-title">
        <div>
          <span className="overview-hero__eyebrow">Business overview</span>
          <h2 id="overview-title">Welcome back, {businessName}</h2>
          <p>Here is what needs your attention and how your business is performing.</p>
        </div>
        <div className="overview-hero__highlights" aria-label="Today highlights">
          <span><ShoppingBag size={16} /> <strong>{performance.ordersToday ?? 0}</strong> orders today</span>
          <span><CircleCheck size={16} /> <strong>{performance.deliverySuccessPercent ?? 0}%</strong> delivery success</span>
          <Link to="/analytics">View analytics <ArrowRight size={15} /></Link>
        </div>
      </section>

      {analyticsError && (
        <p className="orders-page__notice orders-page__notice--error" role="alert">
          The current business summary could not be loaded.
        </p>
      )}

      <section aria-labelledby="order-dashboard-title">
        <div className="overview-section-heading">
          <div>
            <span>Live operations</span>
            <h2 id="order-dashboard-title">Order dashboard</h2>
          </div>
          <Link to="/orders">Manage orders <ArrowRight size={15} /></Link>
        </div>
        <div className="stats-grid overview-order-stats">
          {orderStats.map((stat) => (
            <StatCard key={stat.label} {...stat} />
          ))}
        </div>
      </section>

      <section className="overview-layout" aria-label="Business actions and performance">
        <article className="overview-panel overview-panel--work">
          <header className="overview-panel__header">
            <div>
              <span>Priorities</span>
              <h3>Today&apos;s work centre</h3>
            </div>
            <span className="overview-panel__badge">Live</span>
          </header>
          <div className="overview-work-list">
            {workItems.map(({ label, description, value, icon: Icon, tone, to }) => (
              <Link className={`overview-work-item overview-work-item--${tone}`} to={to} key={label}>
                <span className="overview-work-item__icon"><Icon size={19} /></span>
                <span className="overview-work-item__copy"><strong>{label}</strong><small>{description}</small></span>
                <b>{value}</b>
                <ArrowRight size={16} />
              </Link>
            ))}
          </div>
        </article>

        <article className="overview-panel overview-panel--performance">
          <header className="overview-panel__header">
            <div>
              <span>Financial snapshot</span>
              <h3>Business performance</h3>
            </div>
            <Link to="/analytics"><BarChart3 size={16} /> Report</Link>
          </header>
          <div className="overview-metrics">
            <div><CircleDollarSign /><span>Product revenue</span><strong>{formatAnalyticsMoney(financials.productRevenueMinor)}</strong></div>
            <div><TrendingUp /><span>Gross profit</span><strong>{formatAnalyticsMoney(financials.grossProfitMinor)}</strong><small>{performance.grossMarginPercent ?? 0}% margin</small></div>
            <div><WalletCards /><span>Average order</span><strong>{formatAnalyticsMoney(financials.averageOrderValueMinor)}</strong></div>
            <div><Users /><span>Customers</span><strong>{analytics?.customers?.total ?? 0}</strong></div>
          </div>
        </article>
      </section>

      <section className="overview-layout overview-layout--lower" aria-label="Recent orders and inventory insights">
        <article className="overview-panel overview-panel--orders">
          <header className="overview-panel__header">
            <div>
              <span>Latest activity</span>
              <h3>Recent orders</h3>
            </div>
            <Link to="/orders">View all <ArrowRight size={15} /></Link>
          </header>
          <div className="overview-recent-orders">
            {(analytics?.recentOrders ?? []).length === 0 ? (
              <p className="overview-empty">New orders will appear here.</p>
            ) : analytics.recentOrders.map((order) => (
              <Link to="/orders" key={order.id || order.orderNumber}>
                <span className="overview-order-icon"><Package size={18} /></span>
                <span><strong>#{order.orderNumber}</strong><small>{order.customerName} · {order.itemCount} item{order.itemCount === 1 ? "" : "s"}</small></span>
                <span><strong>{formatAnalyticsMoney(order.totalAmountMinor)}</strong><small>{formatOrderDate(order.createdAt)}</small></span>
                <em className={`overview-status overview-status--${order.fulfilmentStatus}`}>{STATUS_LABELS[order.fulfilmentStatus] ?? order.fulfilmentStatus}</em>
              </Link>
            ))}
          </div>
        </article>

        <article className="overview-panel overview-panel--products">
          <header className="overview-panel__header">
            <div>
              <span>Sales leaders</span>
              <h3>Top products</h3>
            </div>
            <Link to="/inventory">Inventory <ArrowRight size={15} /></Link>
          </header>
          <div className="overview-products">
            {(analytics?.topProducts ?? []).length === 0 ? (
              <p className="overview-empty">Delivered sales will reveal your top products.</p>
            ) : analytics.topProducts.map((product, index) => (
              <div key={product.id}>
                <b>{index + 1}</b>
                <span><strong>{product.name}</strong><small>{product.quantity} sold · {formatAnalyticsMoney(product.revenueMinor)}</small><i><u style={{ width: `${(product.quantity / topProductMaximum) * 100}%` }} /></i></span>
              </div>
            ))}
          </div>
          <div className="overview-inventory-health">
            <Boxes size={19} />
            <span><strong>{inventory.totalUnits ?? 0} units available</strong><small>{inventory.productCount ?? 0} active products</small></span>
            <b>{inventory.lowStockCount ?? 0} low stock</b>
          </div>
        </article>
      </section>
    </main>
  );
}


export default OverviewPage;
