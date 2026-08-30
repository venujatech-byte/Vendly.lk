import {
  BadgeDollarSign,
  CircleDollarSign,
  Globe2,
  PackageCheck,
  Store,
  Trophy,
} from "lucide-react";

import { formatAnalyticsMoney } from "../services/analyticsService";
import StatCard from "./StatCard";
import "./SalesChannelPerformance.css";

function monthLabel(value) {
  if (!value) return "";
  const [year, month] = value.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-LK", { month: "short" });
}

function SalesChannelPerformance({ report, isLoading }) {
  const summary = report?.summary ?? {};
  const channels = report?.channels ?? [];
  const online = channels.find((channel) => channel.id === "online");
  const shop = channels.find((channel) => channel.id === "shop");
  const months = online?.monthlyRevenue ?? shop?.monthlyRevenue ?? [];
  const maximumMonthlyRevenue = Math.max(
    ...channels.flatMap((channel) => (channel.monthlyRevenue ?? []).map((item) => item.revenueMinor)),
    1,
  );
  const totalRevenue = summary.productRevenueMinor ?? 0;

  return (
    <section className="sales-channel-report" aria-labelledby="sales-channel-title">
      <header className="sales-channel-report__intro">
        <div>
          <span>Channel intelligence</span>
          <h3 id="sales-channel-title">Online vs physical-shop sales</h3>
          <p>Compare recognized revenue and product profit using delivered online orders and completed counter sales.</p>
        </div>
        <Store aria-hidden="true" />
      </header>

      <div className="sales-channel-report__stats">
        <StatCard label="Recognized sales" value={String(summary.saleCount ?? 0)} icon={PackageCheck} tone="blue" />
        <StatCard label="Units sold" value={String(summary.unitsSold ?? 0)} icon={Store} tone="orange" />
        <StatCard label="Combined revenue" value={formatAnalyticsMoney(summary.productRevenueMinor)} icon={CircleDollarSign} tone="purple" />
        <StatCard label="Gross profit" value={formatAnalyticsMoney(summary.grossProfitMinor)} icon={BadgeDollarSign} tone="green" />
      </div>

      {isLoading ? (
        <div className="sales-channel-report__empty">Loading sales-channel performance...</div>
      ) : (
        <>
          <section className="sales-channel-report__channels" aria-label="Sales channel comparison">
            {channels.map((channel) => {
              const Icon = channel.id === "online" ? Globe2 : Store;
              const share = totalRevenue ? Math.round((channel.productRevenueMinor / totalRevenue) * 100) : 0;
              return (
                <article className={`sales-channel-card sales-channel-card--${channel.id}`} key={channel.id}>
                  <header>
                    <span><Icon size={19} aria-hidden="true" /></span>
                    <div><small>Sales channel</small><h4>{channel.label}</h4></div>
                    {summary.strongestChannel === channel.label && totalRevenue > 0 ? <b><Trophy size={13} /> Strongest</b> : null}
                  </header>
                  <strong className="sales-channel-card__revenue">{formatAnalyticsMoney(channel.productRevenueMinor)}</strong>
                  <span className="sales-channel-card__share">{share}% of recognized revenue</span>
                  <div className="sales-channel-card__bar"><i style={{ width: `${share}%` }} /></div>
                  <dl>
                    <div><dt>Sales</dt><dd>{channel.saleCount}</dd></div>
                    <div><dt>Units</dt><dd>{channel.unitsSold}</dd></div>
                    <div><dt>Average sale</dt><dd>{formatAnalyticsMoney(channel.averageSaleValueMinor)}</dd></div>
                    <div><dt>Discounts</dt><dd>{formatAnalyticsMoney(channel.discountTotalMinor)}</dd></div>
                    <div><dt>Product cost</dt><dd>{formatAnalyticsMoney(channel.costOfGoodsMinor)}</dd></div>
                    <div><dt>Gross profit</dt><dd>{formatAnalyticsMoney(channel.grossProfitMinor)}</dd></div>
                  </dl>
                  <footer><span>Gross margin</span><strong>{channel.grossMarginPercent}%</strong></footer>
                </article>
              );
            })}
          </section>

          <section className="sales-channel-report__trend" aria-labelledby="sales-channel-trend-title">
            <header>
              <div><span>Last six months</span><h4 id="sales-channel-trend-title">Revenue by channel</h4></div>
              <div className="sales-channel-report__legend"><span className="is-online">Online orders</span><span className="is-shop">Physical shop</span></div>
            </header>
            <div className="sales-channel-report__bars">
              {months.map((month, index) => {
                const onlineValue = online?.monthlyRevenue?.[index]?.revenueMinor ?? 0;
                const shopValue = shop?.monthlyRevenue?.[index]?.revenueMinor ?? 0;
                return (
                  <div className="sales-channel-report__month" key={month.month}>
                    <div className="sales-channel-report__bar-pair" title={`${monthLabel(month.month)}: online ${formatAnalyticsMoney(onlineValue)}, shop ${formatAnalyticsMoney(shopValue)}`}>
                      <i className="is-online" style={{ height: `${Math.max((onlineValue / maximumMonthlyRevenue) * 100, onlineValue ? 5 : 0)}%` }} />
                      <i className="is-shop" style={{ height: `${Math.max((shopValue / maximumMonthlyRevenue) * 100, shopValue ? 5 : 0)}%` }} />
                    </div>
                    <span>{monthLabel(month.month)}</span>
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}
    </section>
  );
}

export default SalesChannelPerformance;
