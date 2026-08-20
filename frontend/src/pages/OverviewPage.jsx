// Icons used by the order summary cards.
import {
  CircleCheck,
  Clock3,
  Package,
  Truck,
  Undo2,
  SquareCheckBig,
  Package2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import "./OrdersPage.css";
import StatCard from "../components/StatCard";
import { useAuth } from "../context/authContextValue";
import { getAnalyticsOverview } from "../services/analyticsService";


function OverviewPage() {
  const { sellerProfile, business } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";
  const [analytics, setAnalytics] = useState(null);
  const [analyticsError, setAnalyticsError] = useState(null);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!business?.id) return undefined;

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
      {
        label: "Pending",
        value: counts["needs-confirmation"] ?? 0,
        icon: Clock3,
        tone: "orange",
      },
      {
        label: "Confirmed",
        value: counts.confirmed ?? 0,
        icon: SquareCheckBig,
        tone: "green",
      },
      { label: "Packed", value: counts.packed ?? 0, icon: Package2, tone: "blue" },
      { label: "Shipped", value: counts.shipped ?? 0, icon: Truck, tone: "purple" },
      {
        label: "Delivered",
        value: counts.delivered ?? 0,
        icon: CircleCheck,
        tone: "green",
      },
      { label: "Returned", value: counts.returned ?? 0, icon: Undo2, tone: "red" },
    ];
  }, [analytics]);

  return (
    <main className="dashboard">
      {/* Store greeting and short page explanation. */}
      <div className="dashboard__intro">
        <h2>Hi! {businessName}</h2>
        <p>Here is your business summary.</p>
      </div>

      {analyticsError && (
        <p className="orders-page__notice orders-page__notice--error" role="alert">
          The current business summary could not be loaded.
        </p>
      )}

      {/* Overview cards created by mapping over orderStats. */}
      <section aria-labelledby="order-dashboard-title">
        <h2 id="order-dashboard-title">Order Dashboard</h2>

        <div className="stats-grid">
          {orderStats.map((stat) => (
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

      {analytics?.workCentre && (
        <section className="overview-work" aria-labelledby="work-centre-title">
          <h2 id="work-centre-title">Today&apos;s work centre</h2>
          <div className="overview-work__grid">
            <span>{analytics.workCentre.needsConfirmation} orders need confirmation</span>
            <span>{analytics.workCentre.needsPacking} orders are ready to pack</span>
            <span>{analytics.workCentre.lowStockProducts} products are low in stock</span>
            <span>{analytics.workCentre.unreadNotifications} unread notifications</span>
          </div>
        </section>
      )}
    </main>
  );
}

export default OverviewPage;
