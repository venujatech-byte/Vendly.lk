import {
  Banknote,
  Boxes,
  PackageCheck,
  TrendingUp,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../context/authContextValue";
import {
  formatAnalyticsMoney,
  getAnalyticsOverview,
} from "../services/analyticsService";
import "./AnalyticsPage.css";


function AnalyticsPage() {
  const { business } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!business?.id) return undefined;

    getAnalyticsOverview(business.id)
      .then((data) => {
        if (requestIsCurrent) setAnalytics(data);
      })
      .catch((requestError) => {
        if (requestIsCurrent) setError(requestError);
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
        <div className="dashboard__intro">
          <h2>Business Analytics</h2>
          <p role="alert">Analytics could not be loaded from the Vendly API.</p>
        </div>
      </main>
    );
  }

  const financials = analytics?.financials ?? {};

  return (
    <main className="dashboard analytics-page">
      <div className="dashboard__intro">
        <h2>Business Analytics</h2>
        <p>Revenue, gross profit, orders and product performance from Firestore.</p>
      </div>

      <section className="analytics-summary" aria-label="Business totals">
        <article><Banknote /><span>Product revenue</span><strong>{formatAnalyticsMoney(financials.productRevenueMinor)}</strong></article>
        <article><PackageCheck /><span>Total orders</span><strong>{analytics?.orderCounts?.all ?? 0}</strong></article>
        <article><Boxes /><span>Stock units</span><strong>{analytics?.inventory?.totalUnits ?? 0}</strong></article>
        <article><TrendingUp /><span>Gross profit</span><strong>{formatAnalyticsMoney(financials.grossProfitMinor)}</strong></article>
      </section>

      <section className="analytics-grid">
        <article className="analytics-panel">
          <h3>Daily orders</h3>
          <p>Orders created during the last seven days</p>
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

        <article className="analytics-panel">
          <h3>Monthly product revenue</h3>
          <p>Delivered product sales, excluding delivery fees</p>
          <div className="analytics-bars">
            {visibleMonths.map((item) => (
              <div key={item.month}>
                <span className="analytics-bars__value">{formatAnalyticsMoney(item.revenueMinor).replace("LKR ", "")}</span>
                <i style={{ height: `${Math.max((item.revenueMinor / maximumMonthlyRevenue) * 100, 4)}%` }} />
                <small>{item.month}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="analytics-panel">
          <h3>Top-selling products</h3>
          <p>Ranked by delivered units</p>
          <div className="analytics-products">
            {(analytics?.topProducts ?? []).length === 0 ? (
              <span>No delivered product sales yet.</span>
            ) : (
              analytics.topProducts.map((product, index) => (
                <div key={product.id}>
                  <b>{index + 1}</b>
                  <span><strong>{product.name}</strong><small>{product.quantity} units</small></span>
                  <em>{formatAnalyticsMoney(product.revenueMinor)}</em>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="analytics-panel">
          <h3>Daily work centre</h3>
          <p>Actions that currently need attention</p>
          <div className="analytics-work">
            <div><span>Needs confirmation</span><strong>{analytics?.workCentre?.needsConfirmation ?? 0}</strong></div>
            <div><span>Ready to pack</span><strong>{analytics?.workCentre?.needsPacking ?? 0}</strong></div>
            <div><span>Low stock</span><strong>{analytics?.workCentre?.lowStockProducts ?? 0}</strong></div>
            <div><span>Out of stock</span><strong>{analytics?.workCentre?.outOfStockProducts ?? 0}</strong></div>
          </div>
        </article>
      </section>

      <p className="analytics-page__footnote">
        Gross profit is product revenue minus recorded product cost. It does not yet subtract salaries, rent, advertising, tax or other business expenses.
      </p>
    </main>
  );
}

export default AnalyticsPage;
