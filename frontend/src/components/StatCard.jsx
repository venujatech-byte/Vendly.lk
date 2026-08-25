// Styles for the larger dashboard statistic cards.
import "./StatCard.css";

// A reusable card receives its text, number, icon, and colour tone as props.
function StatCard({ label, value, icon: Icon, tone = "blue", onClick, isActive = false }) {
  const CardElement = onClick ? "button" : "article";

  return (
    <CardElement
      className={`stat-card stat-card--${tone} ${onClick ? "stat-card--interactive" : ""} ${isActive ? "stat-card--active" : ""}`}
      type={onClick ? "button" : undefined}
      onClick={onClick}
      aria-pressed={onClick ? isActive : undefined}
    >
      {/* Render the icon component supplied through the icon prop. */}
      <div className="stat-card__icon">
        <Icon size={40} aria-hidden="true" />
      </div>

      {/* Display the statistic label and value. */}
      <div className="stat-card__content">
        <span className="stat-card__label">{label}</span>
        <strong className="stat-card__value">{value}</strong>
      </div>
    </CardElement>
  );
}

export default StatCard;
