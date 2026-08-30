import {
  CalendarRange,
  CircleGauge,
  Goal,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";

import { formatAnalyticsMoney } from "../services/analyticsService";
import StatCard from "./StatCard";
import "./SalesForecast.css";
import "./SalesForecastTarget.css";

function monthLabel(value) {
  if (!value) return "";
  const [year, month] = value.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-LK", {
    month: "short",
    year: "2-digit",
  });
}

function SalesForecast({ report, isLoading, onSaveTarget, canManageTarget = false }) {
  const summary = report?.summary ?? {};
  const history = report?.history ?? [];
  const maximumRevenue = Math.max(...history.map((item) => item.revenueMinor), 1);
  const trendIsNegative = (summary.trendPercent ?? 0) < 0;
  const TrendIcon = trendIsNegative ? TrendingDown : TrendingUp;
  const [isEditingTarget, setIsEditingTarget] = useState(false);
  const [targetValue, setTargetValue] = useState("");
  const [targetError, setTargetError] = useState("");
  const [isSavingTarget, setIsSavingTarget] = useState(false);

  useEffect(() => {
    setTargetValue(summary.monthlyTargetMinor ? String(summary.monthlyTargetMinor / 100) : "");
  }, [summary.monthlyTargetMinor]);

  async function saveTarget(event) {
    event.preventDefault();
    const amount = Number(targetValue);
    if (!Number.isFinite(amount) || amount < 0) {
      setTargetError("Enter a valid target amount.");
      return;
    }
    setIsSavingTarget(true);
    setTargetError("");
    try {
      await onSaveTarget(Math.round(amount * 100));
      setIsEditingTarget(false);
    } catch (error) {
      setTargetError(error.message || "The target could not be saved.");
    } finally {
      setIsSavingTarget(false);
    }
  }

  return (
    <section className="sales-forecast" aria-labelledby="sales-forecast-title">
      <header className="sales-forecast__intro">
        <div>
          <span>Planning insight</span>
          <h3 id="sales-forecast-title">Sales forecast</h3>
          <p>Use recognized sales history to plan next month without treating an estimate as guaranteed revenue.</p>
        </div>
        <CircleGauge aria-hidden="true" />
      </header>

      <div className="sales-forecast__stats">
        <StatCard label="Next-month estimate" value={formatAnalyticsMoney(summary.nextMonthForecastMinor)} icon={CalendarRange} tone="blue" />
        <StatCard label="Monthly target" value={formatAnalyticsMoney(summary.activeTargetMinor)} icon={Goal} tone="purple" />
        <StatCard label="Current revenue" value={formatAnalyticsMoney(summary.currentMonthRevenueMinor)} icon={TrendingUp} tone="green" />
        <StatCard label="Current run rate" value={formatAnalyticsMoney(summary.currentMonthRunRateMinor)} icon={CircleGauge} tone="orange" />
      </div>

      {isLoading ? (
        <div className="sales-forecast__empty">Loading sales forecast...</div>
      ) : (
        <div className="sales-forecast__grid">
          <article className="sales-forecast__chart">
            <header>
              <div><span>Seven-month view</span><h4>Recognized revenue history</h4></div>
              <span className={`sales-forecast__trend ${trendIsNegative ? "is-negative" : ""}`}><TrendIcon size={14} />{summary.trendPercent ?? 0}%</span>
            </header>
            <div className="sales-forecast__bars">
              {history.map((item) => (
                <div className="sales-forecast__month" key={item.month}>
                  <span>{formatAnalyticsMoney(item.revenueMinor).replace("LKR ", "")}</span>
                  <i className={item.isCurrentMonth ? "is-current" : ""} style={{ height: `${Math.max((item.revenueMinor / maximumRevenue) * 100, item.revenueMinor ? 5 : 0)}%` }} />
                  <small>{monthLabel(item.month)}</small>
                </div>
              ))}
            </div>
          </article>

          <aside className="sales-forecast__explanation">
            <div className="sales-forecast__confidence"><CircleGauge size={18} /><span><small>Forecast confidence</small><strong className={`is-${summary.confidence ?? "low"}`}>{summary.confidence ?? "Low"}</strong></span></div>
            <dl>
              <div><dt>Target progress</dt><dd>{summary.targetProgressPercent ?? 0}%</dd></div>
              <div><dt>Amount remaining</dt><dd>{formatAnalyticsMoney(summary.targetGapMinor)}</dd></div>
              <div><dt>History used</dt><dd>{summary.historyMonthsUsed ?? 0} completed months</dd></div>
              <div><dt>Suggested target</dt><dd>{formatAnalyticsMoney(summary.suggestedTargetMinor)}</dd></div>
              <div><dt>Current month</dt><dd>Projected from elapsed days</dd></div>
            </dl>
            {canManageTarget && isEditingTarget ? (
              <form className="sales-forecast__target-form" onSubmit={saveTarget}>
                <label htmlFor="monthly-revenue-target">Monthly revenue target (LKR)</label>
                <div><input id="monthly-revenue-target" type="number" min="0" step="1" value={targetValue} onChange={(event) => setTargetValue(event.target.value)} placeholder="e.g. 500000" autoFocus /><button type="submit" disabled={isSavingTarget}>{isSavingTarget ? "Saving..." : "Save"}</button><button type="button" onClick={() => setIsEditingTarget(false)}>Cancel</button></div>
                {targetError && <small role="alert">{targetError}</small>}
              </form>
            ) : canManageTarget ? (
              <button className="sales-forecast__target-button" type="button" onClick={() => setIsEditingTarget(true)}>
                <Goal size={14} /> {summary.targetSource === "seller" ? "Change monthly target" : "Set your monthly target"}
              </button>
            ) : null}
            <p>{report?.method}</p>
            <small className="sales-forecast__notice">Planning estimate only. Promotions, stock availability, seasonality and unusual sales can change the actual result.</small>
          </aside>
        </div>
      )}
    </section>
  );
}

export default SalesForecast;
