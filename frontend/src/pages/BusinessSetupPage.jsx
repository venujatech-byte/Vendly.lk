import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowRight,
  Building2,
  Loader2,
  LogOut,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";

import { useAuth } from "../context/authContextValue";
import { createBusiness } from "../services/businessService";
import { logoutUser } from "../services/authService";
import vendlyLogo from "../assets/vendly-logo.png";

import "./BusinessSetupPage.css";

function BusinessSetupPage() {
  const navigate = useNavigate();
  const {
    user,
    refreshSellerProfile,
  } = useAuth();

  const [ownerName, setOwnerName] = useState(
    user?.displayName ?? "",
  );
  const [businessName, setBusinessName] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleLogout() {
    try {
      await logoutUser();
      navigate("/login", { replace: true });
    } catch (error) {
      console.error("Sign out failed:", error);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      await createBusiness({
        ownerName,
        businessName,
      });

      await refreshSellerProfile();
      navigate("/", { replace: true });
    } catch (error) {
      console.error(error);
      setErrorMessage(
        error.message || "Business details could not be saved. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="business-setup-page">
      {/* Ambient background glow orbs */}
      <div className="business-setup__ambient business-setup__ambient--1" aria-hidden="true" />
      <div className="business-setup__ambient business-setup__ambient--2" aria-hidden="true" />

      <section className="business-setup-card" aria-label="Business Setup">
        <header className="business-setup-card__header">
          <img src={vendlyLogo} alt="Vendly.lk" className="business-setup-card__logo" />
          <span className="business-setup-card__badge">
            <Sparkles size={13} aria-hidden="true" />
            <span>Merchant Onboarding</span>
          </span>
          <h1 className="business-setup-card__title">Set up your business</h1>
          <p className="business-setup-card__subtitle">
            Enter your merchant store details to activate your Vendly dashboard and start selling.
          </p>
        </header>

        {user?.email && (
          <div className="business-setup-card__user-strip">
            <div className="business-setup-card__user-info">
              <User size={15} aria-hidden="true" />
              <span>
                Signed in as <span className="business-setup-card__user-email">{user.email}</span>
              </span>
            </div>
            <button
              type="button"
              className="business-setup-card__signout-btn"
              onClick={handleLogout}
              title="Sign out and switch account"
            >
              <LogOut size={13} aria-hidden="true" />
              <span>Sign out</span>
            </button>
          </div>
        )}

        <form className="business-setup-card__form" onSubmit={handleSubmit}>
          <div className="business-setup-card__field">
            <label htmlFor="setup-owner-name">Owner name</label>
            <div className="business-setup-card__input-wrap">
              <User size={17} className="business-setup-card__icon" aria-hidden="true" />
              <input
                id="setup-owner-name"
                type="text"
                value={ownerName}
                onChange={(event) => setOwnerName(event.target.value)}
                placeholder="e.g. Kasun Perera"
                autoComplete="name"
                required
              />
            </div>
          </div>

          <div className="business-setup-card__field">
            <label htmlFor="setup-business-name">Business name</label>
            <div className="business-setup-card__input-wrap">
              <Building2 size={17} className="business-setup-card__icon" aria-hidden="true" />
              <input
                id="setup-business-name"
                type="text"
                value={businessName}
                onChange={(event) => setBusinessName(event.target.value)}
                placeholder="e.g. VS Tech Store"
                autoComplete="organization"
                required
              />
            </div>
            <span className="business-setup-card__hint">
              This name will appear on your customer storefront and courier waybills.
            </span>
          </div>

          {errorMessage && (
            <div className="business-setup-card__alert" role="alert">
              <AlertCircle size={16} aria-hidden="true" />
              <span>{errorMessage}</span>
            </div>
          )}

          <button
            className="business-setup-card__submit"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={17} className="business-setup-card__spinner" aria-hidden="true" />
                <span>Saving details...</span>
              </>
            ) : (
              <>
                <span>Continue to dashboard</span>
                <ArrowRight size={17} aria-hidden="true" />
              </>
            )}
          </button>
        </form>

        <footer className="business-setup-card__footer">
          <ShieldCheck size={14} aria-hidden="true" />
          <span>Vendly.lk Secure Merchant Onboarding &bull; 2026</span>
        </footer>
      </section>
    </main>
  );
}

export default BusinessSetupPage;

