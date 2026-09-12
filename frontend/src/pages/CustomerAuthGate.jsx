import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  LogIn,
  Mail,
  ShieldCheck,
  Sparkles,
  User,
  UserPlus,
} from "lucide-react";
import { useAuth } from "../context/authContextValue";
import {
  loginAsGuest,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import StorefrontPage from "./StorefrontPage";
import vendlyLoginLogo from "../assets/logo.png";
import googleLogo from "../assets/g.webp";
import "./CustomerAuthGate.css";

function CustomerAuthGate({ linkType }) {
  const { user, isAuthLoading } = useAuth();
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  if (isAuthLoading) {
    return (
      <main className="customer-auth-gate__loading">
        <div className="customer-auth-gate__loading-box">
          <Loader2 size={36} className="customer-auth-gate__loading-spinner" />
          <p>Loading storefront...</p>
        </div>
      </main>
    );
  }

  if (user) return <StorefrontPage linkType={linkType} />;

  async function run(action) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
    } catch (nextError) {
      setError(nextError.message || "Unable to sign in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    if (mode === "login") {
      return run(() => loginWithEmail(email, password));
    }

    return run(async () => {
      await registerWithEmail(name, email, password);
      await logoutUser();
      setMode("login");
      setSuccess("Verification email sent! Check your inbox, then sign in.");
    });
  }

  function switchMode(newMode) {
    setMode(newMode);
    setError("");
    setSuccess("");
    setShowPassword(false);
  }

  return (
    <main className="customer-auth-gate">
      {/* Background ambient lighting */}
      <div className="customer-auth-gate__ambient customer-auth-gate__ambient--1" aria-hidden="true" />
      <div className="customer-auth-gate__ambient customer-auth-gate__ambient--2" aria-hidden="true" />

      <section className="customer-auth-card" aria-labelledby="customer-auth-title">
        <div className="customer-auth-card__heading">
          <div className="customer-auth-card__logo-wrap">
            <img height="76" src={vendlyLoginLogo} alt="Vendly.lk" className="customer-auth-card__logo" />
            <span className="customer-auth-card__badge">Storefront Customer Portal</span>
          </div>

          <h1 id="customer-auth-title" className="customer-auth-card__title">
            {mode === "login" ? "Welcome to the Store" : "Create Customer Account"}
          </h1>
          <p className="customer-auth-card__subtitle">
            {mode === "login"
              ? "Sign in to access your chat history, saved cart, and order tracking."
              : "Sign up to track your deliveries and resume conversations on any device."}
          </p>
        </div>

        {/* Mode selector */}
        <div className="customer-auth-card__tabs">
          <button
            type="button"
            className={`customer-auth-card__tab ${mode === "login" ? "customer-auth-card__tab--active" : ""}`}
            onClick={() => switchMode("login")}
          >
            <LogIn size={16} aria-hidden="true" />
            <span>Sign In</span>
          </button>
          <button
            type="button"
            className={`customer-auth-card__tab ${mode === "register" ? "customer-auth-card__tab--active" : ""}`}
            onClick={() => switchMode("register")}
          >
            <UserPlus size={16} aria-hidden="true" />
            <span>Create Account</span>
          </button>
        </div>

        <form onSubmit={submit} className="customer-auth-card__form">
          {mode === "register" && (
            <div className="customer-auth-card__field">
              <label htmlFor="customer-name">Full Name</label>
              <div className="customer-auth-card__input-wrap">
                <User size={18} className="customer-auth-card__input-icon" aria-hidden="true" />
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

          <div className="customer-auth-card__field">
            <label htmlFor="customer-email">Email Address</label>
            <div className="customer-auth-card__input-wrap">
              <Mail size={18} className="customer-auth-card__input-icon" aria-hidden="true" />
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

          <div className="customer-auth-card__field">
            <label htmlFor="customer-password">Password</label>
            <div className="customer-auth-card__input-wrap">
              <Lock size={18} className="customer-auth-card__input-icon" aria-hidden="true" />
              <input
                id="customer-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={mode === "register" ? "At least 6 characters" : "Your password"}
                autoComplete={mode === "register" ? "new-password" : "current-password"}
                minLength={6}
                required
              />
              <button
                type="button"
                className="customer-auth-card__toggle-pwd"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="customer-auth-card__alert customer-auth-card__alert--error" role="alert">
              <AlertCircle size={18} className="customer-auth-card__alert-icon" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="customer-auth-card__alert customer-auth-card__alert--success" role="status">
              <CheckCircle2 size={18} className="customer-auth-card__alert-icon" />
              <span>{success}</span>
            </div>
          )}

          <button className="customer-auth-card__primary" disabled={busy} type="submit">
            {busy ? (
              <>
                <Loader2 size={18} className="customer-auth-card__spinner" />
                <span>{mode === "login" ? "Signing in..." : "Creating account..."}</span>
              </>
            ) : (
              <>
                {mode === "login" ? <LogIn size={18} /> : <UserPlus size={18} />}
                <span>{mode === "login" ? "Sign In" : "Create Account"}</span>
              </>
            )}
          </button>
        </form>

        <div className="customer-auth-card__divider">
          <span>or continue with</span>
        </div>

        <div className="customer-auth-card__social-actions">
          <button
            className="customer-auth-card__google"
            disabled={busy}
            type="button"
            onClick={() => run(loginWithGoogle)}
          >
            <img width="20" height="20" src={googleLogo} alt="" aria-hidden="true" />
            <span>Continue with Google</span>
          </button>

          <button
            className="customer-auth-card__guest"
            disabled={busy}
            type="button"
            onClick={() => run(loginAsGuest)}
          >
            <Sparkles size={18} className="customer-auth-card__guest-icon" aria-hidden="true" />
            <span>Continue as Guest (No password required)</span>
          </button>
        </div>

        <p className="customer-auth-card__note">
          Guest accounts automatically store your cart and chat history on this browser. Create an account anytime to sync your orders across devices.
        </p>

        <div className="customer-auth-card__footer">
          <ShieldCheck size={14} aria-hidden="true" />
          <span>Secure customer portal &bull; Vendly.lk</span>
        </div>
      </section>
    </main>
  );
}

export default CustomerAuthGate;
