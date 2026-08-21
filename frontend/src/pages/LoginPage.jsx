import { useState } from "react";
import {
  LogIn,
  UserPlus,
} from "lucide-react";

import {
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import { saveSellerProfile } from "../services/sellerService";
import { useAuth } from "../context/authContextValue";
import vendlyLoginLogo from "../assets/logo.png";
import googleLogo from "../assets/g.webp";

import "./LoginPage.css";

// Convert Firebase error codes into understandable messages.
function getAuthErrorMessage(error) {
  switch (error.code) {
    case "auth/email-already-in-use":
      return "An account already exists with this email.";

    case "auth/invalid-email":
      return "Please enter a valid email address.";

    case "auth/invalid-credential":
      return "The email or password is incorrect.";

    case "auth/weak-password":
      return "Please use a stronger password.";

    case "auth/popup-closed-by-user":
      return "Google login was cancelled.";

    case "auth/email-not-verified":
      return "Please verify your email address before logging in.";

    default:
      return "Authentication failed. Please try again.";
  }
}

function LoginPage() {
  const { refreshSellerProfile } = useAuth();

  // The same page handles both login and registration.
  const [formMode, setFormMode] = useState("login");

  const [formData, setFormData] = useState({
    ownerName: "",
    businessName: "",
    email: "",
    password: "",
  });

  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegisterMode = formMode === "register";

  // Update the field that the seller changes.
  function handleInputChange(event) {
    const fieldName = event.target.name;
    const fieldValue = event.target.value;

    setFormData((currentData) => ({
      ...currentData,
      [fieldName]: fieldValue,
    }));
  }

  // Login or register using the submitted form.
  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      if (isRegisterMode) {
        const registeredUser = await registerWithEmail(
          formData.ownerName,
          formData.email,
          formData.password,
        );

        await saveSellerProfile(registeredUser, {
          ownerName: formData.ownerName,
          businessName: formData.businessName,
        });

        // Keep the new account out of the dashboard until email verification.
        await logoutUser();

        setSuccessMessage(
          "Verification email sent. Please check your inbox before logging in.",
        );

        return;
      } else {
        await loginWithEmail(
          formData.email,
          formData.password,
        );
        await refreshSellerProfile();
      }

      // Reload once after login so the dashboard starts with the latest
      // Firebase account, business, and membership state.  This is placed
      // only after a successful login, never during component rendering.
      window.location.replace("/");
    } catch (error) {
      setErrorMessage(getAuthErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  // Login or register using a Google account.
  async function handleGoogleLogin() {
    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      await loginWithGoogle();
      await refreshSellerProfile();

      // Google login uses the same one-time fresh dashboard load.
      window.location.replace("/");
    } catch (error) {
      setErrorMessage(getAuthErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  // Change between Login and Register modes.
  function changeFormMode(newMode) {
    setFormMode(newMode);
    setErrorMessage("");
    setSuccessMessage("");

    setFormData({
      ownerName: "",
      businessName: "",
      email: "",
      password: "",
    });
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <div className="login-card__heading">
        <img height="90" src={vendlyLoginLogo} alt="Vendly.lk" />

          <p>
            {isRegisterMode
              ? "Create your seller account."
              : "Login to manage your business."}
          </p>
        </div>

        {/* Login and registration selector */}
        <div className="login-card__tabs">
          <button
            className={
              formMode === "login"
                ? "login-card__tab login-card__tab--active"
                : "login-card__tab"
            }
            type="button"
            onClick={() => changeFormMode("login")}
          >
            <LogIn size={17} aria-hidden="true" />
            Login
          </button>

          <button
            className={
              formMode === "register"
                ? "login-card__tab login-card__tab--active"
                : "login-card__tab"
            }
            type="button"
            onClick={() => changeFormMode("register")}
          >
            <UserPlus size={17} aria-hidden="true" />
            Register
          </button>
        </div>

        {/* Email and password form */}
        <form
          className="login-card__form"
          onSubmit={handleSubmit}
        >
          {isRegisterMode && (
            <div className="login-card__field">
              <label htmlFor="owner-name">
                Owner name
              </label>

              <input
                id="owner-name"
                name="ownerName"
                type="text"
                value={formData.ownerName}
                onChange={handleInputChange}
                placeholder="Enter your name"
                autoComplete="name"
                required
              />
            </div>
          )}

          {isRegisterMode && (
            <div className="login-card__field">
              <label htmlFor="business-name">
                Business name
              </label>

              <input
                id="business-name"
                name="businessName"
                type="text"
                value={formData.businessName}
                onChange={handleInputChange}
                placeholder="Example: VS Tech Store"
                autoComplete="organization"
                required
              />
            </div>
          )}

          <div className="login-card__field">
            <label htmlFor="seller-email">
              Email address
            </label>

            <input
              id="seller-email"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleInputChange}
              placeholder="seller@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div className="login-card__field">
            <label htmlFor="seller-password">
              Password
            </label>

            <input
              id="seller-password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleInputChange}
              placeholder="Enter your password"
              autoComplete={
                isRegisterMode
                  ? "new-password"
                  : "current-password"
              }
              minLength={6}
              required
            />
          </div>

          {errorMessage && (
            <p className="login-card__error" role="alert">
              {errorMessage}
            </p>
          )}

          {successMessage && (
            <p className="login-card__success" role="status">
              {successMessage}
            </p>
          )}

          <button
            className="login-card__submit"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? "Please wait..."
              : isRegisterMode
                ? "Create account"
                : "Login"}
          </button>
        </form>

        <div className="login-card__divider">
          <span>or</span>
        </div>

{/* Google login button */}
        <button
          className="login-card__google"
          type="button"
          onClick={handleGoogleLogin}
          disabled={isSubmitting}
        >
          <img width="25" src={googleLogo} alt="" aria-hidden="true" />
          Sign in with Google
        </button>


      </section>
    </main>
  );
}

export default LoginPage;
