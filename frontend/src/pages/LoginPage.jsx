import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Lock,
  LogIn,
  Mail,
  ShieldCheck,
  Sparkles,
  Truck,
  User,
  UserPlus,
} from "lucide-react";

import {
  getAuthErrorMessage,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
  sendPasswordReset,
} from "../services/authService";
import { saveSellerProfile } from "../services/sellerService";
import PasswordRequirements from "../components/PasswordRequirements";
import { passwordMeetsPolicy } from "../utils/passwordValidation";
import { useAuth } from "../context/authContextValue";
import vendlyLoginLogo from "../assets/vendly-logo.png";
import googleLogo from "../assets/g.webp";

import "./LoginPage.css";

function LoginPage() {
  const { user, isAuthLoading, refreshSellerProfile } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const destination = location.state?.from || "/";

  // Redirect if already authenticated
  useEffect(() => {
    if (user && !isAuthLoading) {
      navigate(destination, { replace: true });
    }
  }, [user, isAuthLoading, destination, navigate]);

  // Form mode: 'login' | 'register' | 'forgot'
  const [formMode, setFormMode] = useState("login");
  const [showPassword, setShowPassword] = useState(false);

  const [formData, setFormData] = useState({
    ownerName: "",
    businessName: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isRegisterMode = formMode === "register";
  const isForgotMode = formMode === "forgot";

  function handleInputChange(event) {
    const fieldName = event.target.name;
    const fieldValue = event.target.value;

    setFormData((currentData) => ({
      ...currentData,
      [fieldName]: fieldValue,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      if (isForgotMode) {
        await sendPasswordReset(formData.email);
        setSuccessMessage(
          `Password reset instructions sent to ${formData.email}. Please check your inbox and spam folder.`
        );
        return;
      }

      if (isRegisterMode) {
        if (!passwordMeetsPolicy(formData.password)) {
          setErrorMessage("Choose a password that meets all requirements.");
          return;
        }
        if (formData.password !== formData.confirmPassword) {
          setErrorMessage("Passwords do not match.");
          return;
        }
        const registeredUser = await registerWithEmail(
          formData.ownerName,
          formData.email,
          formData.password,
        );

        await saveSellerProfile(registeredUser, {
          ownerName: formData.ownerName,
          businessName: formData.businessName,
        });

        // Keep unverified accounts out until confirmation link is clicked
        await logoutUser();

        setSuccessMessage(
          `Confirmation email sent to ${formData.email}. Please open the email and click the confirmation link to verify your account before logging in.`
        );
        setFormMode("login");
        return;
      }

      // Login mode
      await loginWithEmail(formData.email, formData.password);
      await refreshSellerProfile();
      navigate(destination, { replace: true });
    } catch (error) {
      if (error.code === "auth/email-not-verified") {
        setErrorMessage(
          "Please verify your email address before logging in. Check your inbox and spam folder for the confirmation link."
        );
      } else {
        setErrorMessage(getAuthErrorMessage(error));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleLogin() {
    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      await loginWithGoogle();
      await refreshSellerProfile();
      navigate(destination, { replace: true });
    } catch (error) {
      setErrorMessage(getAuthErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  function switchMode(newMode) {
    setFormMode(newMode);
    setErrorMessage("");
    setSuccessMessage("");
    setShowPassword(false);
  }

  return (
    <main className="login-page">
      {/* Background ambient lighting effects */}
      <div className="login-page__ambient login-page__ambient--1" aria-hidden="true" />
      <div className="login-page__ambient login-page__ambient--2" aria-hidden="true" />

      {/* Main Side-by-Side Card Container */}
      <div className="login-layout-card">
        {/* Left Column: Brand, Logo & Platform Highlights */}
        <section className="login-brand-panel" aria-label="Vendly merchant platform introduction">
          <div className="login-brand-panel__header">
            <img src={vendlyLoginLogo} alt="Vendly.lk" className="login-brand-panel__logo" />
            <span className="login-brand-panel__badge">
              <Sparkles size={13} aria-hidden="true" />
              <span>Merchant Command Center</span>
            </span>
          </div>

          <div className="login-brand-panel__body">
            <h1 className="login-brand-panel__title">
              Scale your Sri Lankan business with AI & automation
            </h1>
            <p className="login-brand-panel__desc">
              All-in-one e-commerce management: multilingual WhatsApp-style storefront chatbot, automated courier sync, and unified order fulfillment.
            </p>

            <ul className="login-brand-panel__features">
              <li>
                <div className="login-brand-panel__feature-icon">
                  <Bot size={17} />
                </div>
                <div>
                  <strong>AI Sales Chatbot</strong>
                  <span>Auto-close sales in Sinhala, Tamil & English 24/7</span>
                </div>
              </li>
              <li>
                <div className="login-brand-panel__feature-icon">
                  <Truck size={17} />
                </div>
                <div>
                  <strong>Direct Courier Integration</strong>
                  <span>1-click waybill creation with Domex, Pronto & Prompt</span>
                </div>
              </li>
              <li>
                <div className="login-brand-panel__feature-icon">
                  <ShieldCheck size={17} />
                </div>
                <div>
                  <strong>Bank-Grade Security</strong>
                  <span>Encrypted credentials & secure cloud infrastructure</span>
                </div>
              </li>
            </ul>
          </div>

          <div className="login-brand-panel__footer">
            <ShieldCheck size={14} aria-hidden="true" />
            <span>Vendly.lk Secure Merchant Operating System &bull; 2026</span>
          </div>
        </section>

        {/* Right Column: Authentication Form */}
        <section className="login-form-panel" aria-label="Merchant account access">
          <div className="login-form-panel__top">
            <h2 className="login-form-panel__title">
              {isForgotMode
                ? "Reset Your Password"
                : isRegisterMode
                ? "Create Merchant Account"
                : "Welcome Back"}
            </h2>
            <p className="login-form-panel__subtitle">
              {isForgotMode
                ? "Enter your email to receive recovery instructions."
                : isRegisterMode
                ? "Start managing your store and orders today."
                : "Sign in to access your sales and store analytics."}
            </p>
          </div>

          {/* Navigation switcher tabs */}
          {!isForgotMode ? (
            <div className="login-form-panel__tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={formMode === "login"}
                className={`login-form-panel__tab ${formMode === "login" ? "login-form-panel__tab--active" : ""}`}
                onClick={() => switchMode("login")}
              >
                <LogIn size={15} aria-hidden="true" />
                <span>Sign In</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={formMode === "register"}
                className={`login-form-panel__tab ${formMode === "register" ? "login-form-panel__tab--active" : ""}`}
                onClick={() => switchMode("register")}
              >
                <UserPlus size={15} aria-hidden="true" />
                <span>Register</span>
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="login-form-panel__back-btn"
              onClick={() => switchMode("login")}
            >
              <ArrowLeft size={15} aria-hidden="true" />
              <span>Back to Sign In</span>
            </button>
          )}

          {/* In-Card Status Notifications */}
          {errorMessage && (
            <div className="login-form-panel__alert login-form-panel__alert--error" role="alert">
              <AlertCircle size={17} className="login-form-panel__alert-icon" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="login-form-panel__alert login-form-panel__alert--success" role="status">
              <CheckCircle2 size={17} className="login-form-panel__alert-icon" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Form */}
          <form className="login-form-panel__form" onSubmit={handleSubmit}>
            {isRegisterMode && (
              <div className="login-form-panel__row">
                <div className="login-form-panel__field">
                  <label htmlFor="merchant-owner-name">Owner Name</label>
                  <div className="login-form-panel__input-wrap">
                    <User size={16} className="login-form-panel__icon" aria-hidden="true" />
                    <input
                      id="merchant-owner-name"
                      name="ownerName"
                      type="text"
                      value={formData.ownerName}
                      onChange={handleInputChange}
                      placeholder="Full name"
                      autoComplete="name"
                      required
                    />
                  </div>
                </div>

                <div className="login-form-panel__field">
                  <label htmlFor="merchant-business-name">Business Name</label>
                  <div className="login-form-panel__input-wrap">
                    <Building2 size={16} className="login-form-panel__icon" aria-hidden="true" />
                    <input
                      id="merchant-business-name"
                      name="businessName"
                      type="text"
                      value={formData.businessName}
                      onChange={handleInputChange}
                      placeholder="Store name"
                      autoComplete="organization"
                      required
                    />
                  </div>
                </div>
              </div>
            )}

            <div className="login-form-panel__field">
              <label htmlFor="merchant-email">Email Address</label>
              <div className="login-form-panel__input-wrap">
                <Mail size={16} className="login-form-panel__icon" aria-hidden="true" />
                <input
                  id="merchant-email"
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

            {!isForgotMode && (
              <div className="login-form-panel__field">
                <div className="login-form-panel__label-row">
                  <div className="login-form-panel__label-group">
                    <label htmlFor="merchant-password">Password</label>
                    {isRegisterMode && (
                      <PasswordRequirements
                        password={formData.password}
                        confirmPassword={formData.confirmPassword}
                      />
                    )}
                  </div>
                  {formMode === "login" && (
                    <button
                      type="button"
                      className="login-form-panel__forgot-link"
                      onClick={() => switchMode("forgot")}
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="login-form-panel__input-wrap">
                  <Lock size={16} className="login-form-panel__icon" aria-hidden="true" />
                  <input
                    id="merchant-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={formData.password}
                    onChange={handleInputChange}
                    placeholder={isRegisterMode ? "Create strong password" : "Enter password"}
                    autoComplete={isRegisterMode ? "new-password" : "current-password"}
                    minLength={isRegisterMode ? 8 : 6}
                    required
                  />
                  <button
                    type="button"
                    className="login-form-panel__toggle-pwd"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            )}

            {isRegisterMode && (
              <div className="login-form-panel__field">
                <label htmlFor="merchant-confirm-password">Confirm Password</label>
                <div className="login-form-panel__input-wrap">
                  <Lock size={16} className="login-form-panel__icon" aria-hidden="true" />
                  <input
                    id="merchant-confirm-password"
                    name="confirmPassword"
                    type="password"
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                    placeholder="Repeat password"
                    autoComplete="new-password"
                    required
                  />
                </div>
              </div>
            )}

            <button
              className="login-form-panel__submit-btn"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={17} className="login-form-panel__spinner" />
                  <span>Processing...</span>
                </>
              ) : isForgotMode ? (
                <>
                  <KeyRound size={17} />
                  <span>Send Reset Link</span>
                </>
              ) : isRegisterMode ? (
                <>
                  <UserPlus size={17} />
                  <span>Create Merchant Account</span>
                </>
              ) : (
                <>
                  <LogIn size={17} />
                  <span>Sign In to Dashboard</span>
                </>
              )}
            </button>
          </form>

          {!isForgotMode && (
            <>
              <div className="login-form-panel__divider">
                <span>or continue with</span>
              </div>

              <button
                className="login-form-panel__google-btn"
                type="button"
                onClick={handleGoogleLogin}
                disabled={isSubmitting}
              >
                <img width="18" height="18" src={googleLogo} alt="" aria-hidden="true" />
                <span>Continue with Google</span>
              </button>
            </>
          )}
        </section>
      </div>
    </main>
  );
}

export default LoginPage;
