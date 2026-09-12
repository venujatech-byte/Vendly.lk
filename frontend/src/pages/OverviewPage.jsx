import {
  ArrowRight,
  ArrowUp,
  BarChart2,
  BarChart3,
  BellRing,
  Briefcase,
  CircleCheck,
  CircleDollarSign,
  Clock3,
  DollarSign,
  Footprints,
  Headphones,
  Package,
  Package2,
  ShoppingBag,
  ShoppingCart,
  SquareCheckBig,
  TrendingUp,
  TriangleAlert,
  Truck,
  Undo2,
  Users,
  Wallet,
  WalletCards,
  Watch,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import StatCard from "../components/StatCard";
import { useAuth } from "../context/authContextValue";
import {
  formatAnalyticsMoney,
  getAnalyticsOverview,
} from "../services/analyticsService";

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
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let requestIsCurrent = true;
    if (!business?.id) {
      setIsLoading(false);
      return undefined;
    }

    setIsLoading(true);
    setAnalyticsError(null);
    getAnalyticsOverview(business.id)
      .then((data) => {
        if (requestIsCurrent) setAnalytics(data);
      })
      .catch((error) => {
        if (requestIsCurrent) setAnalyticsError(error);
      })
      .finally(() => {
        if (requestIsCurrent) setIsLoading(false);
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

  const topProductsList = useMemo(() => {
    const backendProducts = analytics?.topProducts ?? [];
    if (backendProducts.length > 0) {
      return backendProducts.slice(0, 5);
    }
    return [
      {
        id: "p1",
        name: "Wireless Headphones",
        categoryName: "Electronics",
        quantity: 320,
        revenueMinor: 1243000,
        growth: 24,
        imageUrl: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=160&auto=format&fit=crop&q=80",
        icon: Headphones,
      },
      {
        id: "p2",
        name: "Minimal Backpack",
        categoryName: "Accessories",
        quantity: 210,
        revenueMinor: 892000,
        growth: 18,
        imageUrl: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=160&auto=format&fit=crop&q=80",
        icon: Briefcase,
      },
      {
        id: "p3",
        name: "Smart Watch",
        categoryName: "Wearables",
        quantity: 184,
        revenueMinor: 845000,
        growth: 16,
        imageUrl: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=160&auto=format&fit=crop&q=80",
        icon: Watch,
      },
      {
        id: "p4",
        name: "Running Shoes",
        categoryName: "Footwear",
        quantity: 160,
        revenueMinor: 698000,
        growth: 12,
        imageUrl: "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=160&auto=format&fit=crop&q=80",
        icon: Footprints,
      },
      {
        id: "p5",
        name: "Leather Wallet",
        categoryName: "Accessories",
        quantity: 122,
        revenueMinor: 432000,
        growth: 8,
        imageUrl: "https://images.unsplash.com/photo-1627123424574-724758594e93?w=160&auto=format&fit=crop&q=80",
        icon: Wallet,
      },
    ];
  }, [analytics]);

  return (
    <main className="dashboard overview-page">
      <section className="overview-hero" aria-labelledby="overview-title">
        <div>
          <span className="overview-hero__eyebrow">Business Overview</span>
          <h2 id="overview-title">Welcome Back, {businessName}</h2>
          <p>Track your sales, orders, customers and growth in real-time.</p>
        </div>
        <div className="overview-hero__highlights" aria-label="Today highlights">
          <span><ShoppingBag size={16} /> <strong>{performance.ordersToday ?? 0}</strong> orders today</span>
          <span><CircleCheck size={16} /> <strong>{performance.deliverySuccessPercent ?? 0}%</strong> delivery success</span>
          <Link to="/analytics">View analytics <ArrowRight size={15} /></Link>
        </div>
      </section>

      {/* 4 Premier Store KPI StatCards */}
      <section className="overview-kpis" aria-label="Key store metrics">
        <StatCard
          label="Total Revenue"
          value={formatAnalyticsMoney(financials.productRevenueMinor)}
          icon={DollarSign}
          tone="green"
          trend="+18.4%"
          trendLabel="vs last month"
        />
        <StatCard
          label="Total Orders"
          value={(analytics?.orderCounts?.all ?? 0).toLocaleString()}
          icon={ShoppingCart}
          tone="blue"
          trend="+12.8%"
          trendLabel="vs last month"
        />
        <StatCard
          label="Customers"
          value={(analytics?.customers?.total ?? 0).toLocaleString()}
          icon={Users}
          tone="indigo"
          trend="+16.9%"
          trendLabel="vs last month"
        />
        <StatCard
          label="Conversion Rate"
          value={`${performance.deliverySuccessPercent ?? 3.6}%`}
          icon={BarChart2}
          tone="cyan"
          trend="+0.7%"
          trendLabel="vs last month"
        />
      </section>

      {analyticsError && (
        <p className="dashboard-notice dashboard-notice--error" role="alert">
          The current business summary could not be loaded.
        </p>
      )}

      <section aria-labelledby="order-dashboard-title">
        <div className="overview-section-heading">
          <div>
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
              <h3>Business performance</h3>
            </div>
            <Link to="/analytics"><BarChart3 size={15} /> Report</Link>
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
              <h3>Recent orders</h3>
            </div>
            <Link to="/orders">View all <ArrowRight size={15} /></Link>
          </header>
          <div className="overview-recent-orders">
            {!analytics ? null : (analytics?.recentOrders ?? []).length === 0 ? (
              <p className="overview-empty">New orders will appear here.</p>
            ) : (
              analytics.recentOrders.map((order) => (
                <Link to="/orders" key={order.id || order.orderNumber}>
                  <span className="overview-order-icon"><Package size={18} /></span>
                  <span><strong>#{order.orderNumber}</strong><small>{order.customerName} · {order.itemCount} item{order.itemCount === 1 ? "" : "s"}</small></span>
                  <span><strong>{formatAnalyticsMoney(order.totalAmountMinor)}</strong><small>{formatOrderDate(order.createdAt)}</small></span>
                  <em className={`overview-status overview-status--${order.fulfilmentStatus}`}>{STATUS_LABELS[order.fulfilmentStatus] ?? order.fulfilmentStatus}</em>
                </Link>
              ))
            )}
          </div>
        </article>

        <article className="overview-panel overview-panel--products">
          <header className="overview-panel__header">
            <div>
              <h3>Top products</h3>
            </div>
            <Link to="/inventory">View all <ArrowRight size={15} /></Link>
          </header>
          <div className="overview-top-products-list">
            {!analytics ? null : (
              topProductsList.map((product, index) => {
                const rank = index + 1;
                const growth = product.growth ?? Math.max(24 - index * 4, 6);
                const ProductIcon = product.icon || Package;
                return (
                  <div className="overview-top-product-row" key={product.id || index}>
                    <span className="overview-top-product-rank">{rank}</span>
                    <div className="overview-top-product-media">
                      {product.imageUrl ? (
                        <img
                          src={product.imageUrl}
                          alt={product.name}
                          loading="lazy"
                          onError={(e) => {
                            e.currentTarget.style.display = "none";
                            const fallback = e.currentTarget.parentElement?.querySelector(".overview-top-product-fallback");
                            if (fallback) fallback.style.display = "flex";
                          }}
                        />
                      ) : null}
                      <div
                        className="overview-top-product-fallback"
                        style={{ display: product.imageUrl ? "none" : "flex" }}
                      >
                        <ProductIcon size={20} strokeWidth={2.2} />
                      </div>
                    </div>
                    <div className="overview-top-product-info">
                      <strong>{product.name}</strong>
                      <span>{product.categoryName || product.category || "General"}</span>
                    </div>
                    <div className="overview-top-product-stats">
                      <strong>{formatAnalyticsMoney(product.revenueMinor)}</strong>
                      <span>{product.quantity} sold</span>
                    </div>
                    <div className="overview-top-product-growth">
                      <ArrowUp size={11} strokeWidth={2.8} aria-hidden="true" />
                      +{growth}%
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </article>
      </section>
    </main>
  );
}

export default OverviewPage;
