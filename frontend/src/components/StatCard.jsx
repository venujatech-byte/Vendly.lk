// Styles for the larger dashboard statistic cards.
import "./StatCard.css";

// A reusable card receives its text, number, icon, and colour tone as props.
function StatCard({ label, value, icon: Icon, tone = "blue" }) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      {/* Render the icon component supplied through the icon prop. */}
      <div className="stat-card__icon">
        <Icon size={40} aria-hidden="true" />
      </div>

      {/* Display the statistic label and value. */}
      <div className="stat-card__content">
        <span className="stat-card__label">{label}</span>
        <strong className="stat-card__value">{value}</strong>
      </div>
    </article>
  );
}

export default StatCard;
