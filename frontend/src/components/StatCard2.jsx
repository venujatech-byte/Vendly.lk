// Styles for the compact statistic cards used on the Orders page.
import "./StatCard2.css";

// This compact card uses props so the same layout can show many statistics.
function StatCard2({ label, value, icon: Icon, tone = "blue", onClick, isActive = false }) {
  return (
    <article className={`stat-card2 stat-card2--${tone} ${isActive ? "stat-card2--active" : ""}`} onClick={onClick} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined} onKeyDown={(event) => { if (onClick && (event.key === "Enter" || event.key === " ")) onClick(); }}>
      {/* Icon supplied by the parent page. */}
      <div className="stat-card2__icon">
        <Icon size={28} aria-hidden="true" />
      </div>

{/* Statistic label and value. */}
<div className="stat-card2__content">
  <span className="stat-card2__label">{label}</span>
  <strong className="stat-card2__value">{value}</strong>
</div>
    </article>
  );
}

export default StatCard2;
