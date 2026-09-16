import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Lock,
  LogIn,
  Mail,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Store,
  Truck,
  User,
  UserPlus,
} from "lucide-react";
import { useAuth } from "../context/authContextValue";
import {
  getAuthErrorMessage,
  loginAsGuest,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
  sendPasswordReset,
} from "../services/authService";
import { getPublicProduct, getPublicStore } from "../services/publicService";
import StorefrontPage from "./StorefrontPage";
import PasswordRequirements from "../components/PasswordRequirements";
import EmailVerificationPromptModal from "../components/EmailVerificationPromptModal";
import PasswordStrengthMeter from "../components/PasswordStrengthMeter";
import { passwordMeetsPolicy } from "../utils/passwordValidation";
import vendlyLoginLogo from "../assets/vendly-logo.png";
import googleLogo from "../assets/g.webp";
import "./CustomerAuthGate.css";

function CustomerAuthGate({ linkType }) {
  const { user, isAuthLoading } = useAuth();
  const { storeCode, productCode } = useParams();

  // Store/business context
  const [storeName, setStoreName] = useState("");

  // 'login' | 'register' | 'forgot'
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [verificationModal, setVerificationModal] = useState({
    isOpen: false,
    email: "",
    mode: "registered", // 'registered' | 'unverified_login'
  });

  const isRegister = mode === "register";
  const isForgot = mode === "forgot";

  const isPasswordValid = Boolean(password && passwordMeetsPolicy(password));
  const isConfirmMatch = Boolean(
    confirmPassword &&
    confirmPassword === password &&
    isPasswordValid
  );
  const isConfirmMismatch = Boolean(
    confirmPassword &&
    confirmPassword !== password
  );

  // Fetch store name if route parameter is available
  useEffect(() => {
    let active = true;
    if (storeCode) {
      getPublicStore(storeCode)
        .then((data) => {
          if (active && data?.store?.name) {
            setStoreName(data.store.name);
          }
        })
        .catch(() => {});
    } else if (productCode) {
      getPublicProduct(productCode)
        .then((data) => {
          if (active && data?.store?.name) {
            setStoreName(data.store.name);
          }
        })
        .catch(() => {});
    }
    return () => {
      active = false;
    };
  }, [storeCode, productCode]);

  if (isAuthLoading) {
    return (
      <main className="customer-auth-gate__loading">
        <div className="customer-auth-gate__loading-box">
          <Loader2 size={36} className="customer-auth-gate__loading-spinner" />
          <p>Connecting to store...</p>
        </div>
      </main>
    );
  }

  // Once authenticated and verified, render storefront directly
  const isCustomerVerified = Boolean(
    user &&
    (user.isAnonymous || user.emailVerified || !user.providerData?.some((p) => p.providerId === "password"))
  );
  if (user && isCustomerVerified) {
    return <StorefrontPage linkType={linkType} />;
  }

  async function run(action) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
    } catch (nextError) {
      if (nextError.code === "auth/email-not-verified") {
        setError(
          "Please verify your account via email before logging in. Check your inbox and spam folder."
        );
        setVerificationModal({
          isOpen: true,
          email,
          mode: "unverified_login",
        });
      } else {
        setError(getAuthErrorMessage(nextError));
      }
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();

    if (mode === "forgot") {
      return run(async () => {
        await sendPasswordReset(email);
        setSuccess(
          `Password reset link sent to ${email}. Check your inbox and spam folder.`
        );
      });
    }

    if (mode === "login") {
      return run(() => loginWithEmail(email, password));
    }

    return run(async () => {
      if (!passwordMeetsPolicy(password)) {
        throw new Error("Choose a password that meets all requirements.");
      }
      if (password !== confirmPassword) {
        throw new Error("Passwords do not match.");
      }
      const currentEmail = email;
      await registerWithEmail(name, currentEmail, password);
      await logoutUser();
      setMode("login");
      setPassword("");
      setConfirmPassword("");
      setSuccess(
        `Confirmation email sent to ${currentEmail}. Please verify your account via email before signing in.`
      );
      setVerificationModal({
        isOpen: true,
        email: currentEmail,
        mode: "registered",
      });
    });
  }

  function switchMode(newMode) {
    setMode(newMode);
    setError("");
    setSuccess("");
    setShowPassword(false);
    setConfirmPassword("");
  }

  return (
    <main className="customer-auth-gate">
      {/* Background ambient lighting */}
      <div className="customer-auth-gate__ambient customer-auth-gate__ambient--1" aria-hidden="true" />
      <div className="customer-auth-gate__ambient customer-auth-gate__ambient--2" aria-hidden="true" />

      {/* Main Side-by-Side Split Container */}
      <div className="customer-auth-layout-card">
        {/* Left Column: Store Branding & Customer Benefits */}
        <section className="customer-brand-panel" aria-label="Store information and customer perks">
          <div className="customer-brand-panel__header">
            <img src={vendlyLoginLogo} alt="Vendly.lk" className="customer-brand-panel__logo" />
            <span className="customer-brand-panel__badge">
              <Store size={13} aria-hidden="true" />
              <span>{storeName ? `${storeName} • Customer Portal` : "Storefront Customer Portal"}</span>
            </span>
          </div>

          <div className="customer-brand-panel__body">
            <h1 className="customer-brand-panel__title">
              {storeName ? `Welcome to ${storeName}` : "Welcome to the Store"}
            </h1>
            <p className="customer-brand-panel__desc">
              Sign in or continue as guest to start chatting with our shopping assistant, save your cart, and track deliveries.
            </p>

            <ul className="customer-brand-panel__features">
              <li>
                <div className="customer-brand-panel__feature-icon">
                  <Sparkles size={16} />
                </div>
                <div>
                  <strong>Instant Guest Access</strong>
                  <span>Browse and order right away without creating a password</span>
                </div>
              </li>
              <li>
                <div className="customer-brand-panel__feature-icon">
                  <MessageSquare size={16} />
                </div>
                <div>
                  <strong>Live AI Chatbot Sync</strong>
                  <span>Resume questions, deals, and recommendations anytime</span>
                </div>
              </li>
              <li>
                <div className="customer-brand-panel__feature-icon">
                  <Truck size={16} />
                </div>
                <div>
                  <strong>Live Courier Tracking</strong>
                  <span>Track package status from dispatch to your doorstep</span>
                </div>
              </li>
            </ul>
          </div>

          <div className="customer-brand-panel__footer">
            <ShieldCheck size={14} aria-hidden="true" />
            <span>Secure Customer Portal &bull; Powered by Vendly.lk</span>
          </div>
        </section>

        {/* Right Column: Customer Authentication Form */}
        <section className="customer-form-panel" aria-label="Customer sign in options">
          <div className="customer-form-panel__top">
            <h2 className="customer-form-panel__title">
              {isForgot
                ? "Reset Your Password"
                : isRegister
                ? "Create Customer Account"
                : "Sign In to Store"}
            </h2>
            <p className="customer-form-panel__subtitle">
              {isForgot
                ? "Enter your email to receive recovery instructions."
                : isRegister
                ? "Sign up to track orders across devices."
                : "Access your order history and saved items."}
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          {!isForgot ? (
            <div className="customer-form-panel__tabs" role="tablist">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "login"}
                className={`customer-form-panel__tab ${mode === "login" ? "customer-form-panel__tab--active" : ""}`}
                onClick={() => switchMode("login")}
              >
                <LogIn size={15} aria-hidden="true" />
                <span>Sign In</span>
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "register"}
                className={`customer-form-panel__tab ${mode === "register" ? "customer-form-panel__tab--active" : ""}`}
                onClick={() => switchMode("register")}
              >
                <UserPlus size={15} aria-hidden="true" />
                <span>Create Account</span>
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="customer-form-panel__back-btn"
              onClick={() => switchMode("login")}
            >
              <ArrowLeft size={15} aria-hidden="true" />
              <span>Back to Sign In</span>
            </button>
          )}

          {/* Status Alerts */}
          {error && (
            <div className="customer-form-panel__alert customer-form-panel__alert--error" role="alert">
              <AlertCircle size={17} className="customer-form-panel__alert-icon" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="customer-form-panel__alert customer-form-panel__alert--success" role="status">
              <CheckCircle2 size={17} className="customer-form-panel__alert-icon" />
              <span>{success}</span>
            </div>
          )}

          {/* Email / Password Form */}
          <form onSubmit={submit} className="customer-form-panel__form">
            {isRegister && (
              <div className="customer-form-panel__field">
                <label htmlFor="customer-name">Full Name</label>
                <div className="customer-form-panel__input-wrap">
                  <User size={16} className="customer-form-panel__icon" aria-hidden="true" />
                  <input
                    id="customer-name"
                    type="text"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Your full name"
                    autoComplete="name"
                    required
                  />
                </div>
              </div>
            )}

            <div className="customer-form-panel__field">
              <label htmlFor="customer-email">Email Address</label>
              <div className="customer-form-panel__input-wrap">
                <Mail size={16} className="customer-form-panel__icon" aria-hidden="true" />
                <input
                  id="customer-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="customer@example.com"
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            {!isForgot && (
              <div className="customer-form-panel__field">
                <div className="customer-form-panel__label-row">
                  <div className="customer-form-panel__label-group">
                    <label htmlFor="customer-password">Password</label>
                    {isRegister && (
                      <PasswordRequirements
                        password={password}
                        confirmPassword={confirmPassword}
                      />
                    )}
                  </div>
                  {mode === "login" && (
                    <button
                      type="button"
                      className="customer-form-panel__forgot-link"
                      onClick={() => switchMode("forgot")}
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="customer-form-panel__input-wrap">
                  <Lock size={16} className="customer-form-panel__icon" aria-hidden="true" />
                  <input
                    id="customer-password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder={isRegister ? "Create strong password" : "Enter your password"}
                    autoComplete={isRegister ? "new-password" : "current-password"}
                    minLength={isRegister ? 8 : 6}
                    className={isRegister && isPasswordValid ? "customer-form-panel__input--valid" : ""}
                    required
                  />
                  {isRegister && isPasswordValid && (
                    <span
                      className="customer-form-panel__valid-check"
                      title="Password meets all security requirements"
                      aria-label="Password valid"
                    >
                      <CheckCircle2 size={16} />
                    </span>
                  )}
                  <button
                    type="button"
                    className="customer-form-panel__toggle-pwd"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {isRegister && (
                  <PasswordStrengthMeter password={password} />
                )}
              </div>
            )}

            {isRegister && (
              <div className="customer-form-panel__field">
                <label htmlFor="customer-confirm-password">Confirm Password</label>
                <div className="customer-form-panel__input-wrap">
                  <Lock size={16} className="customer-form-panel__icon" aria-hidden="true" />
                  <input
                    id="customer-confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="Repeat your password"
                    autoComplete="new-password"
                    className={
                      isConfirmMatch
                        ? "customer-form-panel__input--valid-alone"
                        : isConfirmMismatch
                        ? "customer-form-panel__input--invalid"
                        : ""
                    }
                    required
                  />
                  {isConfirmMatch && (
                    <span
                      className="customer-form-panel__valid-check customer-form-panel__valid-check--alone"
                      title="Passwords match"
                      aria-label="Passwords match"
                    >
                      <CheckCircle2 size={16} />
                    </span>
                  )}
                </div>
                {isConfirmMatch && (
                  <div className="customer-form-panel__field-hint customer-form-panel__field-hint--valid">
                    <CheckCircle2 size={12} />
                    <span>Passwords match</span>
                  </div>
                )}
                {isConfirmMismatch && (
                  <div className="customer-form-panel__field-hint customer-form-panel__field-hint--invalid">
                    <span>Passwords do not match</span>
                  </div>
                )}
              </div>
            )}

            <button className="customer-form-panel__submit-btn" disabled={busy} type="submit">
              {busy ? (
                <>
                  <Loader2 size={17} className="customer-form-panel__spinner" />
                  <span>Processing...</span>
                </>
              ) : isForgot ? (
                <>
                  <KeyRound size={17} />
                  <span>Send Reset Link</span>
                </>
              ) : isRegister ? (
                <>
                  <UserPlus size={17} />
                  <span>Create Account</span>
                </>
              ) : (
                <>
                  <LogIn size={17} />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>

          {/* Social & Guest Fast-Track Actions */}
          {!isForgot && (
            <>
              <div className="customer-form-panel__divider">
                <span>or quick access</span>
              </div>

              <div className="customer-form-panel__actions">
                <button
                  className="customer-form-panel__google-btn"
                  disabled={busy}
                  type="button"
                  onClick={() => run(loginWithGoogle)}
                >
                  <img width="18" height="18" src={googleLogo} alt="" aria-hidden="true" />
                  <span>Continue with Google</span>
                </button>

                <button
                  className="customer-form-panel__guest-btn"
                  disabled={busy}
                  type="button"
                  onClick={() => run(loginAsGuest)}
                >
                  <Sparkles size={16} className="customer-form-panel__guest-icon" aria-hidden="true" />
                  <span>Continue as Guest (No password required)</span>
                </button>
              </div>

              <small className="customer-form-panel__note">
                Guest sessions store your cart and chat on this browser. Create an account anytime to sync.
              </small>
            </>
          )}
        </section>
      </div>

      <EmailVerificationPromptModal
        isOpen={verificationModal.isOpen}
        email={verificationModal.email}
        mode={verificationModal.mode}
        onClose={() => setVerificationModal((prev) => ({ ...prev, isOpen: false }))}
        onPrimaryAction={() => {
          setVerificationModal((prev) => ({ ...prev, isOpen: false }));
          setMode("login");
        }}
      />
    </main>
  );
}

export default CustomerAuthGate;
