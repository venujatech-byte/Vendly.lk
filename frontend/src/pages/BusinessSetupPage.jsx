import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import { createBusiness } from "../services/businessService";

import "./LoginPage.css";

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
        "Business details could not be saved. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-card__heading">
          <h1>Set up your business</h1>
          <p>This information will appear on your Vendly dashboard.</p>
        </div>

        <form className="login-card__form" onSubmit={handleSubmit}>
          <div className="login-card__field">
            <label htmlFor="setup-owner-name">Owner name</label>
            <input
              id="setup-owner-name"
              type="text"
              value={ownerName}
              onChange={(event) => setOwnerName(event.target.value)}
              placeholder="Enter your name"
              autoComplete="name"
              required
            />
          </div>

          <div className="login-card__field">
            <label htmlFor="setup-business-name">Business name</label>
            <input
              id="setup-business-name"
              type="text"
              value={businessName}
              onChange={(event) => setBusinessName(event.target.value)}
              placeholder="Example: VS Tech Store"
              autoComplete="organization"
              required
            />
          </div>

          {errorMessage && (
            <p className="login-card__error" role="alert">
              {errorMessage}
            </p>
          )}

          <button
            className="login-card__submit"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Saving..." : "Continue to dashboard"}
          </button>
        </form>
      </section>
    </main>
  );
}

export default BusinessSetupPage;
