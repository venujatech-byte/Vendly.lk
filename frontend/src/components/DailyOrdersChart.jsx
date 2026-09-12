import { useMemo, useState } from "react";
import { formatAnalyticsMoney } from "../services/analyticsService";
import "./AnalyticsChart.css";

function formatFullDate(dateString) {
  if (!dateString) return "";
  try {
    const iso = dateString.includes("T") ? dateString : `${dateString}T00:00:00`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString("en-LK", {
      weekday: "long",
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

function formatShortDay(dateString) {
  if (!dateString) return "";
  try {
    const iso = dateString.includes("T") ? dateString : `${dateString}T00:00:00`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString("en-LK", { weekday: "short" });
  } catch {
    return dateString;
  }
}

function formatShortDate(dateString) {
  if (!dateString) return "";
  try {
    const iso = dateString.includes("T") ? dateString : `${dateString}T00:00:00`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "";
    return `${date.getDate()} ${date.toLocaleDateString("en-LK", { month: "short" })}`;
  } catch {
    return "";
  }
}

export default function DailyOrdersChart({ data = [] }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const totalOrders = useMemo(() => {
    return (data || []).reduce((sum, item) => sum + (item.count || 0), 0);
  }, [data]);

  const maxVal = useMemo(() => {
    const rawMax = Math.max(...(data || []).map((d) => d.count || 0), 1);
    if (rawMax <= 5) return 5;
    if (rawMax <= 10) return 10;
    if (rawMax <= 20) return 20;
    return Math.ceil(rawMax / 10) * 10;
  }, [data]);

  const yTicks = useMemo(() => {
    return [0, Math.round(maxVal / 2), maxVal];
  }, [maxVal]);

  const width = 560;
  const height = 210;
  const padLeft = 42;
  const padRight = 16;
  const padTop = 24;
  const padBottom = 40;

  const chartWidth = width - padLeft - padRight;
  const chartHeight = height - padTop - padBottom;

  const count = data.length || 1;
  const colWidth = chartWidth / count;
  const barWidth = Math.min(32, colWidth * 0.55);

  const isToday = (dateString) => {
    if (!dateString) return false;
    const today = new Date().toISOString().split("T")[0];
    return dateString.startsWith(today);
  };

  return (
    <div className="analytics-vector-chart analytics-vector-chart--bar">
      <div className="analytics-chart-meta">
        <div className="analytics-chart-stat">
          <span className="analytics-chart-stat__label">7-Day Total</span>
          <strong className="analytics-chart-stat__value">{totalOrders} <small>orders</small></strong>
        </div>
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div className="analytics-chart-active-pill">
            <span>{formatShortDay(data[hoveredIndex].date)}</span>
            <strong>{data[hoveredIndex].count} {data[hoveredIndex].count === 1 ? "order" : "orders"}</strong>
          </div>
        )}
      </div>

      <div className="analytics-chart-svg-wrap">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="analytics-chart-svg"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="dailyOrdersBarGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#059669" />
            </linearGradient>
            <linearGradient id="dailyOrdersBarGradHover" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#34d399" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
            <filter id="barGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#10b981" floodOpacity="0.35" />
            </filter>
          </defs>

          {/* Grid lines & Y-ticks */}
          {yTicks.map((tick) => {
            const y = padTop + chartHeight - (tick / maxVal) * chartHeight;
            return (
              <g key={tick} className="analytics-chart-grid-line">
                <line
                  x1={padLeft}
                  y1={y}
                  x2={width - padRight}
                  y2={y}
                  strokeDasharray="4 4"
                />
                <text
                  x={padLeft - 10}
                  y={y + 3.5}
                  textAnchor="end"
                  className="analytics-chart-tick-text"
                >
                  {tick}
                </text>
              </g>
            );
          })}

          {/* Bars & Column hover targets */}
          {data.map((item, index) => {
            const xCenter = padLeft + index * colWidth + colWidth / 2;
            const barX = xCenter - barWidth / 2;
            const barHeight = Math.max((item.count / maxVal) * chartHeight, item.count > 0 ? 6 : 2);
            const barY = padTop + chartHeight - barHeight;
            const isHovered = hoveredIndex === index;
            const currentDay = isToday(item.date);

            return (
              <g
                key={item.date || index}
                className={`analytics-bar-group ${isHovered ? "is-hovered" : ""} ${currentDay ? "is-today" : ""}`}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Column background hover highlight */}
                <rect
                  x={padLeft + index * colWidth + 2}
                  y={padTop}
                  width={colWidth - 4}
                  height={chartHeight + 6}
                  rx="8"
                  className="analytics-col-hover-track"
                />

                {/* Subtle base marker */}
                <rect
                  x={barX}
                  y={padTop + chartHeight - 2}
                  width={barWidth}
                  height={2}
                  rx="1"
                  className="analytics-bar-base-tick"
                />

                {/* Active Data Bar */}
                {item.count > 0 && (
                  <rect
                    x={barX}
                    y={barY}
                    width={barWidth}
                    height={barHeight}
                    rx="6"
                    ry="6"
                    fill={isHovered ? "url(#dailyOrdersBarGradHover)" : "url(#dailyOrdersBarGrad)"}
                    filter={isHovered ? "url(#barGlow)" : "none"}
                    className="analytics-bar-element"
                  />
                )}

                {/* Value floating above bar if non-zero */}
                {item.count > 0 && (
                  <text
                    x={xCenter}
                    y={Math.max(barY - 7, padTop + 10)}
                    textAnchor="middle"
                    className={`analytics-bar-top-value ${isHovered ? "is-active" : ""}`}
                  >
                    {item.count}
                  </text>
                )}

                {/* X-Axis Day Label */}
                <text
                  x={xCenter}
                  y={height - padBottom + 18}
                  textAnchor="middle"
                  className={`analytics-x-label ${currentDay ? "is-today" : ""} ${isHovered ? "is-hovered" : ""}`}
                >
                  {formatShortDay(item.date)}
                </text>

                {/* X-Axis Date Sublabel */}
                <text
                  x={xCenter}
                  y={height - padBottom + 31}
                  textAnchor="middle"
                  className="analytics-x-sublabel"
                >
                  {formatShortDate(item.date)}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div
            className="analytics-chart-floating-tooltip"
            style={{
              left: `${((padLeft + hoveredIndex * colWidth + colWidth / 2) / width) * 100}%`,
              top: `${Math.max(10, ((padTop + chartHeight - ((data[hoveredIndex].count || 0) / maxVal) * chartHeight) / height) * 100 - 24)}%`,
            }}
          >
            <span className="tooltip-date">{formatFullDate(data[hoveredIndex].date)}</span>
            <div className="tooltip-value">
              <span className="tooltip-dot" style={{ background: "#10b981" }} />
              <strong>{data[hoveredIndex].count}</strong>
              <small>{data[hoveredIndex].count === 1 ? "order" : "orders"}</small>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
