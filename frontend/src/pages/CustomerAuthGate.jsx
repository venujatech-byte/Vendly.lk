import { useState } from "react";
import { Globe2, Eye, EyeOff, UserRound } from "lucide-react";
import { useAuth } from "../context/authContextValue";
import {
  loginAsGuest,
  loginWithEmail,
  loginWithGoogle,
  logoutUser,
  registerWithEmail,
} from "../services/authService";
import StorefrontPage from "./StorefrontPage";
import "./CustomerAuthGate.css";

function CustomerAuthGate({ linkType }) {
  const { user, isAuthLoading } = useAuth();
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (isAuthLoading) {
    return <main className="customer-auth-gate__loading">Loading storefront...</main>;
  }

  if (user) return <StorefrontPage linkType={linkType} />;

  async function run(action) {
    setBusy(true);
    setError("");
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
    return run(() => mode === "login"
      ? loginWithEmail(email, password)
      : registerWithEmail(name, email, password).then(async () => {
        await logoutUser();
        setMode("login");
        setError("Verification email sent. Verify your email, then sign in.");
      }));
  }

  return (
    <main className="customer-auth-gate">
      <section className="customer-auth-card" aria-labelledby="customer-auth-title">
        <div className="customer-auth-card__brand">Vendly<span>.lk</span></div>
        <p className="customer-auth-card__eyebrow">Customer storefront</p>
        <h1 id="customer-auth-title">Sign in to continue</h1>
        <p className="customer-auth-card__hint">Sign in to save your chats, orders, and delivery updates.</p>

        <form onSubmit={submit} className="customer-auth-form">
          {mode === "register" && (
            <label>Full name<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
          )}
          <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password
            <span className="customer-auth-password">
              <input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} minLength={6} required />
              <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label="Show password">{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
            </span>
          </label>
          {error && <p className="customer-auth-error" role="alert">{error}</p>}
          <button className="customer-auth-primary" disabled={busy}>{busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>

        <div className="customer-auth-divider"><span>or</span></div>
        <button className="customer-auth-secondary" disabled={busy} onClick={() => run(loginWithGoogle)}><Globe2 size={18} /> Continue with Google</button>
        <button className="customer-auth-guest" disabled={busy} onClick={() => run(loginAsGuest)}><UserRound size={18} /> Continue as guest</button>
        <button className="customer-auth-switch" onClick={() => { setMode((value) => value === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "New customer? Create an account" : "Already have an account? Sign in"}
        </button>
        <p className="customer-auth-note">Guest accounts keep your current chat and order history on this device.</p>
      </section>
    </main>
  );
}

export default CustomerAuthGate;
