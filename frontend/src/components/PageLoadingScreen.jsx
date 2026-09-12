import vendlyLogo from "../assets/react.png";
import "./PageLoadingScreen.css";

export default function PageLoadingScreen({ message = "Loading..." }) {
  return (
    <div className="page-loading-screen" aria-label={message} aria-live="polite">
      <div className="app-loading__content">
        <div className="app-loading__logo">
          <span>
            <img className="sidebar__logo-image" src={vendlyLogo} alt="Vendly.lk" />
          </span>
        </div>

        <h1>Vendly.lk</h1>
        <p>{message}</p>

        <div className="app-loading__progress">
          <span />
        </div>

        <div className="app-loading__dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
      </div>
    </div>
  );
}
