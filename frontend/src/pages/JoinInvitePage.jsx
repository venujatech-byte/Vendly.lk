import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Lock,
  LogOut,
  ShieldCheck,
  Store,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import vendlyLogo from "../assets/vendly-logo.png";
import { auth } from "../firebase/firebase";
import { logoutUser } from "../services/authService";
import { getPublicInvitation } from "../services/memberService";
import "./JoinInvitePage.css";

function JoinInvitePage() {
  const [token, setToken] = useState("");
  const [invitation, setInvitation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentUser, setCurrentUser] = useState(auth.currentUser);
  const navigate = useNavigate();

  useEffect(() => {
    const unsubscribe = auth.onAuthStateChanged((u) => {
      setCurrentUser(u);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (!urlToken) {
      setError("No invitation token provided in URL.");
      setLoading(false);
      return;
    }

    setToken(urlToken);

    getPublicInvitation(urlToken)
      .then((data) => {
        setInvitation(data);
      })
      .catch((err) => {
        setError(
          err.message || "This invitation link is invalid, expired, or has already been claimed.",
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  async function handleLogout() {
    await logoutUser();
  }

  function handleGoToApp() {
    navigate("/");
    window.location.reload();
  }

  if (loading) {
    return (
      <div className="join-page">
        <div className="join-card">
          <div className="join-card__loading">
            <div className="join-card__spinner" />
            <p>Loading invitation...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="join-page">
        <div className="join-card">
          <div className="join-card__header">
            <img src={vendlyLogo} alt="Vendly" className="join-card__logo" />
            <h2>Invitation Error</h2>
          </div>
          <div className="join-card__error-banner">
            <AlertCircle size={20} />
            <p>{error}</p>
          </div>
          <div className="join-card__actions">
            <Link to="/login" className="join-card__btn-primary">
              Go to Sign In
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isEmailMatch =
    currentUser?.email?.toLowerCase() === invitation?.email?.toLowerCase();

  return (
    <div className="join-page">
      <div className="join-card">
        <div className="join-card__header">
          <img src={vendlyLogo} alt="Vendly" className="join-card__logo" />
          <h2>You're Invited to Join</h2>
        </div>

        <div className="join-card__store-box">
          <Store size={26} className="join-card__store-icon" />
          <div className="join-card__store-info">
            <h3>{invitation?.businessName || "Vendly Store"}</h3>
            <p>
              Invited as <strong className="join-card__role-tag">{invitation?.role}</strong>
            </p>
          </div>
        </div>

        <div className="join-card__details">
          <div className="join-card__detail-row">
            <span>Target Email:</span>
            <strong>{invitation?.email}</strong>
          </div>
          <div className="join-card__detail-row">
            <span>Modular Permissions:</span>
            <span>
              {Array.isArray(invitation?.permissions)
                ? invitation.permissions.join(", ")
                : "Standard"}
            </span>
          </div>
        </div>

        {currentUser ? (
          <div className="join-card__auth-status">
            {isEmailMatch ? (
              <div className="join-card__match-box">
                <CheckCircle2 size={20} className="join-card__success-icon" />
                <div>
                  <strong>Signed in as {currentUser.email}</strong>
                  <p>Your account matches this invitation.</p>
                </div>
                <button
                  type="button"
                  className="join-card__btn-primary"
                  onClick={handleGoToApp}
                >
                  Enter Store Dashboard <ArrowRight size={16} />
                </button>
              </div>
            ) : (
              <div className="join-card__mismatch-box">
                <AlertCircle size={20} className="join-card__warning-icon" />
                <div>
                  <strong>Different Account Detected</strong>
                  <p>
                    You are signed in as <em>{currentUser.email}</em>. This invite is for{" "}
                    <em>{invitation?.email}</em>.
                  </p>
                </div>
                <button
                  type="button"
                  className="join-card__btn-secondary"
                  onClick={handleLogout}
                >
                  <LogOut size={16} /> Sign out & switch account
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="join-card__unauth-actions">
            <p className="join-card__prompt">
              To accept this invitation and join the team, create an account or sign in with{" "}
              <strong>{invitation?.email}</strong>:
            </p>
            <div className="join-card__btn-group">
              <Link
                to={`/register?email=${encodeURIComponent(invitation?.email || "")}`}
                className="join-card__btn-primary"
              >
                Register & Join Store
              </Link>
              <Link
                to={`/login?email=${encodeURIComponent(invitation?.email || "")}`}
                className="join-card__btn-secondary"
              >
                Sign In
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default JoinInvitePage;
