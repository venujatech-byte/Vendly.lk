import { useMemo, useState } from "react";
import { formatAnalyticsMoney } from "../services/analyticsService";
import "./AnalyticsChart.css";

function formatMonthLabel(monthString) {
  if (!monthString) return "";
  try {
    const iso = monthString.length === 7 ? `${monthString}-01T00:00:00` : monthString;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return monthString;
    return date.toLocaleDateString("en-LK", { month: "short" });
  } catch {
    return monthString;
  }
}

function formatFullMonth(monthString) {
  if (!monthString) return "";
  try {
    const iso = monthString.length === 7 ? `${monthString}-01T00:00:00` : monthString;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return monthString;
    return date.toLocaleDateString("en-LK", { month: "long", year: "numeric" });
  } catch {
    return monthString;
  }
}

function formatCompactLkr(minorUnits) {
  const value = minorUnits / 100;
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(0)}k`;
  }
  return String(Math.round(value));
}

// Generate smooth cubic bezier SVG path
function getSmoothSplinePath(points) {
  if (!points || points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

  let d = `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[Math.max(i - 1, 0)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(i + 2, points.length - 1)];

    const cp1x = p1.x + (p2.x - p0.x) / 5.5;
    const cp1y = p1.y + (p2.y - p0.y) / 5.5;
    const cp2x = p2.x - (p3.x - p1.x) / 5.5;
    const cp2y = p2.y - (p3.y - p1.y) / 5.5;

    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

export default function MonthlyRevenueChart({ data = [] }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const totalRevenueMinor = useMemo(() => {
    return (data || []).reduce((sum, item) => sum + (item.revenueMinor || 0), 0);
  }, [data]);

  const maxVal = useMemo(() => {
    const rawMax = Math.max(...(data || []).map((d) => d.revenueMinor || 0), 10000000);
    // Round up to a pleasant tick step (e.g. 50k, 100k, 500k)
    const step = rawMax > 50_000_000 ? 20_000_000 : rawMax > 20_000_000 ? 10_000_000 : rawMax > 5_000_000 ? 5_000_000 : 2_000_000;
    return Math.ceil(rawMax / step) * step;
  }, [data]);

  const yTicks = useMemo(() => {
    return [0, Math.round(maxVal / 2), maxVal];
  }, [maxVal]);

  const width = 560;
  const height = 210;
  const padLeft = 48;
  const padRight = 24;
  const padTop = 24;
  const padBottom = 40;

  const chartWidth = width - padLeft - padRight;
  const chartHeight = height - padTop - padBottom;

  const count = data.length || 1;
  const stepX = count > 1 ? chartWidth / (count - 1) : chartWidth;

  const points = useMemo(() => {
    return (data || []).map((item, index) => {
      const x = padLeft + index * stepX;
      const y = padTop + chartHeight - Math.min((item.revenueMinor || 0) / maxVal, 1) * chartHeight;
      return { x, y, item, index };
    });
  }, [data, maxVal, stepX, chartHeight, padLeft, padTop]);

  const linePath = useMemo(() => getSmoothSplinePath(points), [points]);

  const areaPath = useMemo(() => {
    if (points.length === 0) return "";
    const bottomY = padTop + chartHeight;
    const firstX = points[0].x;
    const lastX = points[points.length - 1].x;
    return `${linePath} L ${lastX.toFixed(1)} ${bottomY} L ${firstX.toFixed(1)} ${bottomY} Z`;
  }, [linePath, points, padTop, chartHeight]);

  return (
    <div className="analytics-vector-chart analytics-vector-chart--area">
      <div className="analytics-chart-meta">
        <div className="analytics-chart-stat">
          <span className="analytics-chart-stat__label">6-Month Revenue</span>
          <strong className="analytics-chart-stat__value">{formatAnalyticsMoney(totalRevenueMinor)}</strong>
        </div>
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div className="analytics-chart-active-pill is-revenue">
            <span>{formatMonthLabel(data[hoveredIndex].month)}</span>
            <strong>{formatAnalyticsMoney(data[hoveredIndex].revenueMinor)}</strong>
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
            <linearGradient id="monthlyRevenueAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.38" />
              <stop offset="45%" stopColor="#2563eb" stopOpacity="0.14" />
              <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="monthlyRevenueLineGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#60a5fa" />
              <stop offset="50%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#2563eb" />
            </linearGradient>
            <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#2563eb" floodOpacity="0.35" />
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
                  {formatCompactLkr(tick)}
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          {areaPath && (
            <path
              d={areaPath}
              fill="url(#monthlyRevenueAreaGrad)"
              className="analytics-chart-area-path"
            />
          )}

          {/* Spline Line */}
          {linePath && (
            <path
              d={linePath}
              fill="none"
              stroke="url(#monthlyRevenueLineGrad)"
              strokeWidth="3.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#lineGlow)"
              className="analytics-chart-spline-line"
            />
          )}

          {/* Hover Crosshair Guide */}
          {hoveredIndex !== null && points[hoveredIndex] && (
            <g className="analytics-chart-crosshair">
              <line
                x1={points[hoveredIndex].x}
                y1={padTop}
                x2={points[hoveredIndex].x}
                y2={padTop + chartHeight}
                stroke="#3b82f6"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity="0.75"
              />
            </g>
          )}

          {/* Data Points & Interactive Hitboxes */}
          {points.map((pt) => {
            const isHovered = hoveredIndex === pt.index;
            const isLatest = pt.index === points.length - 1;

            return (
              <g
                key={pt.item.month || pt.index}
                className={`analytics-point-group ${isHovered ? "is-hovered" : ""}`}
                onMouseEnter={() => setHoveredIndex(pt.index)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Transparent Column Hitbox for easy hover */}
                <rect
                  x={pt.x - stepX / 2}
                  y={padTop}
                  width={stepX}
                  height={chartHeight + padBottom}
                  fill="transparent"
                />

                {/* Node Outer Ring on Hover */}
                {isHovered && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="10"
                    fill="rgba(59, 130, 246, 0.2)"
                    className="analytics-point-pulse"
                  />
                )}

                {/* Node Core */}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isHovered ? "6" : isLatest ? "5" : "4"}
                  fill="#ffffff"
                  stroke={isHovered ? "#1d4ed8" : "#2563eb"}
                  strokeWidth={isHovered ? "3" : "2.5"}
                  className="analytics-point-circle"
                />

                {/* X-Axis Month Label */}
                <text
                  x={pt.x}
                  y={height - padBottom + 22}
                  textAnchor="middle"
                  className={`analytics-x-label ${isHovered ? "is-hovered" : ""} ${isLatest ? "is-latest" : ""}`}
                >
                  {formatMonthLabel(pt.item.month)}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Floating Tooltip */}
        {hoveredIndex !== null && points[hoveredIndex] && (
          <div
            className="analytics-chart-floating-tooltip"
            style={{
              left: `${(points[hoveredIndex].x / width) * 100}%`,
              top: `${Math.max(8, (points[hoveredIndex].y / height) * 100 - 26)}%`,
            }}
          >
            <span className="tooltip-date">{formatFullMonth(points[hoveredIndex].item.month)}</span>
            <div className="tooltip-value">
              <span className="tooltip-dot" style={{ background: "#3b82f6" }} />
              <strong>{formatAnalyticsMoney(points[hoveredIndex].item.revenueMinor)}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
