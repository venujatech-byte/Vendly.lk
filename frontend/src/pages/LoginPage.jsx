import { useState } from "react";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  LogIn,
  Mail,
  ShieldCheck,
  User,
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
      return "Please use a stronger password (at least 6 characters).";

    case "auth/popup-closed-by-user":
      return "Google login was cancelled.";

    case "auth/email-not-verified":
      return "Please verify your email address before logging in.";

    default:
      return error?.message || "Authentication failed. Please try again.";
  }
}

function LoginPage() {
  const { refreshSellerProfile } = useAuth();

  // The same page handles both login and registration.
  const [formMode, setFormMode] = useState("login");
  const [showPassword, setShowPassword] = useState(false);

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
      // Firebase account, business, and membership state.
      setTimeout(() => {
        window.location.replace("/");
      }, 1000);

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

      setTimeout(() => {
        window.location.replace("/");
      }, 1000);
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
    setShowPassword(false);

    setFormData({
      ownerName: "",
      businessName: "",
      email: "",
      password: "",
    });
  }

  return (
    <main className="login-page">
      {/* Background ambient lighting */}
      <div className="login-page__ambient login-page__ambient--1" aria-hidden="true" />
      <div className="login-page__ambient login-page__ambient--2" aria-hidden="true" />

      <section className="login-card">
        <div className="login-card__heading">
          <div className="login-card__logo-wrap">
            <img height="82" src={vendlyLoginLogo} alt="Vendly.lk" className="login-card__logo" />
            <span className="login-card__badge">Merchant Portal</span>
          </div>

          <h1 className="login-card__title">
            {isRegisterMode ? "Create Seller Account" : "Welcome Back"}
          </h1>
          <p className="login-card__subtitle">
            {isRegisterMode
              ? "Start managing your store, orders & AI chatbot today."
              : "Sign in to access your store dashboard and sales."}
          </p>
        </div>

        {/* Login and registration selector */}
        <div className="login-card__tabs">
          <button
            className={`login-card__tab ${formMode === "login" ? "login-card__tab--active" : ""}`}
            type="button"
            onClick={() => changeFormMode("login")}
          >
            <LogIn size={16} aria-hidden="true" />
            <span>Login</span>
          </button>

          <button
            className={`login-card__tab ${formMode === "register" ? "login-card__tab--active" : ""}`}
            type="button"
            onClick={() => changeFormMode("register")}
          >
            <UserPlus size={16} aria-hidden="true" />
            <span>Register</span>
          </button>
        </div>

        {/* Email and password form */}
        <form className="login-card__form" onSubmit={handleSubmit}>
          {isRegisterMode && (
            <div className="login-card__field">
              <label htmlFor="owner-name">Owner Name</label>
              <div className="login-card__input-wrap">
                <User size={18} className="login-card__input-icon" aria-hidden="true" />
                <input
                  id="owner-name"
                  name="ownerName"
                  type="text"
                  value={formData.ownerName}
                  onChange={handleInputChange}
                  placeholder="Your full name"
                  autoComplete="name"
                  required
                />
              </div>
            </div>
          )}

          {isRegisterMode && (
            <div className="login-card__field">
              <label htmlFor="business-name">Business Name</label>
              <div className="login-card__input-wrap">
                <Building2 size={18} className="login-card__input-icon" aria-hidden="true" />
                <input
                  id="business-name"
                  name="businessName"
                  type="text"
                  value={formData.businessName}
                  onChange={handleInputChange}
                  placeholder="e.g. City Boutique LK"
                  autoComplete="organization"
                  required
                />
              </div>
            </div>
          )}

          <div className="login-card__field">
            <label htmlFor="seller-email">Email Address</label>
            <div className="login-card__input-wrap">
              <Mail size={18} className="login-card__input-icon" aria-hidden="true" />
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
          </div>

          <div className="login-card__field">
            <label htmlFor="seller-password">Password</label>
            <div className="login-card__input-wrap">
              <Lock size={18} className="login-card__input-icon" aria-hidden="true" />
              <input
                id="seller-password"
                name="password"
                type={showPassword ? "text" : "password"}
                value={formData.password}
                onChange={handleInputChange}
                placeholder={isRegisterMode ? "Min. 6 characters" : "Enter your password"}
                autoComplete={isRegisterMode ? "new-password" : "current-password"}
                minLength={6}
                required
              />
              <button
                type="button"
                className="login-card__toggle-pwd"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>

          {errorMessage && (
            <div className="login-card__alert login-card__alert--error" role="alert">
              <AlertCircle size={18} className="login-card__alert-icon" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="login-card__alert login-card__alert--success" role="status">
              <CheckCircle2 size={18} className="login-card__alert-icon" />
              <span>{successMessage}</span>
            </div>
          )}

          <button className="login-card__submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 size={18} className="login-card__spinner" />
                <span>{isRegisterMode ? "Creating account..." : "Signing in..."}</span>
              </>
            ) : (
              <>
                {isRegisterMode ? <UserPlus size={18} /> : <LogIn size={18} />}
                <span>{isRegisterMode ? "Create Seller Account" : "Sign In to Dashboard"}</span>
              </>
            )}
          </button>
        </form>

        <div className="login-card__divider">
          <span>or continue with</span>
        </div>

        {/* Google login button */}
        <button
          className="login-card__google"
          type="button"
          onClick={handleGoogleLogin}
          disabled={isSubmitting}
        >
          <img width="20" height="20" src={googleLogo} alt="" aria-hidden="true" />
          <span>Continue with Google</span>
        </button>

        <div className="login-card__footer">
          <ShieldCheck size={14} aria-hidden="true" />
          <span>Encrypted merchant authentication &bull; Vendly.lk</span>
        </div>
      </section>
    </main>
  );
}

export default LoginPage;
