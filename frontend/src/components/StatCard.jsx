import { ArrowDown, ArrowUp } from "lucide-react";
import "./StatCard.css";

// Modern dashboard statistic card inspired by clean e-commerce UI
function StatCard({
  label,
  value,
  icon: Icon,
  tone = "blue",
  trend,
  trendDirection,
  trendLabel = "vs last month",
  note,
  onClick,
  isActive = false,
  className = "",
}) {
  const CardElement = onClick ? "button" : "article";
  const isDown =
    trendDirection === "down" ||
    (typeof trend === "string" && trend.trim().startsWith("-"));

  return (
    <CardElement
      className={`stat-card stat-card--${tone} ${onClick ? "stat-card--interactive" : ""} ${
        isActive ? "stat-card--active" : ""
      } ${trend || note ? "stat-card--has-footer" : ""} ${className}`}
      type={onClick ? "button" : undefined}
      onClick={onClick}
      aria-pressed={onClick ? isActive : undefined}
    >
      <div className="stat-card__top">
        {/* Soft pastel squircle icon badge */}
        <div className="stat-card__icon" aria-hidden="true">
          {Icon && <Icon size={22} strokeWidth={2.4} />}
        </div>

        {/* Statistic label and value */}
        <div className="stat-card__content">
          <span className="stat-card__label">{label}</span>
          <strong className="stat-card__value">{value}</strong>
        </div>
      </div>

      {/* Optional bottom trend / note line */}
      {(trend || note) && (
        <div className="stat-card__footer">
          {trend ? (
            <div className={`stat-card__trend stat-card__trend--${isDown ? "down" : "up"}`}>
              <span className="stat-card__trend-badge">
                {isDown ? (
                  <ArrowDown size={13} strokeWidth={2.6} aria-hidden="true" />
                ) : (
                  <ArrowUp size={13} strokeWidth={2.6} aria-hidden="true" />
                )}
                {trend}
              </span>
              {trendLabel && (
                <span className="stat-card__trend-label">{trendLabel}</span>
              )}
            </div>
          ) : (
            <span className="stat-card__note">{note}</span>
          )}
        </div>
      )}
    </CardElement>
  );
}

export default StatCard;
