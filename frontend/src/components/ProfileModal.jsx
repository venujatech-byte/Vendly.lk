import { KeyRound, Mail, RotateCcw, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";

import {
  changeAccountPassword,
  currentUserHasPasswordProvider,
  requestAccountEmailChange,
  sendCurrentUserPasswordReset,
} from "../services/authService";
import ModalShell from "./ModalShell";

import "./ProfileModal.css";

function readableAuthError(error) {
  const messages = {
    "auth/email-already-in-use": "That email address is already used by another account.",
    "auth/invalid-email": "Enter a valid email address.",
    "auth/invalid-credential": "The current password is incorrect.",
    "auth/wrong-password": "The current password is incorrect.",
    "auth/weak-password": "Use a stronger password with at least 6 characters.",
    "auth/too-many-requests": "Too many attempts. Please wait and try again.",
    "auth/popup-closed-by-user": "Google verification was cancelled.",
    "auth/popup-blocked": "Allow popups and try Google verification again.",
    "auth/requires-recent-login": "For security, sign out and sign in again before trying this change.",
  };

  return messages[error?.code] ?? error?.message ?? "The account could not be updated.";
}

function ProfileModal({ isOpen, onClose, user }) {
  const [newEmail, setNewEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [emailMessage, setEmailMessage] = useState(null);
  const [passwordMessage, setPasswordMessage] = useState(null);
  const [workingAction, setWorkingAction] = useState("");
  const hasPasswordProvider = currentUserHasPasswordProvider();
  const providerNames = (user?.providerData ?? []).map((provider) =>
    provider.providerId === "google.com" ? "Google" :
      provider.providerId === "password" ? "Email and password" : provider.providerId,
  );

  useEffect(() => {
    if (!isOpen) return;
    setNewEmail("");
    setEmailPassword("");
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setEmailMessage(null);
    setPasswordMessage(null);
  }, [isOpen]);

  async function handleEmailChange(event) {
    event.preventDefault();
    const cleanEmail = newEmail.trim().toLowerCase();
    setEmailMessage(null);

    if (!cleanEmail || cleanEmail === user?.email?.toLowerCase()) {
      setEmailMessage({ type: "error", text: "Enter a different email address." });
      return;
    }

    setWorkingAction("email");
    try {
      await requestAccountEmailChange(cleanEmail, emailPassword);
      setEmailMessage({
        type: "success",
        text: `Verification was sent to ${cleanEmail}. Your email changes after you open that link.`,
      });
      setNewEmail("");
      setEmailPassword("");
    } catch (error) {
      setEmailMessage({ type: "error", text: readableAuthError(error) });
    } finally {
      setWorkingAction("");
    }
  }

  async function handlePasswordChange(event) {
    event.preventDefault();
    setPasswordMessage(null);

    if (newPassword.length < 6) {
      setPasswordMessage({ type: "error", text: "The new password needs at least 6 characters." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: "error", text: "The new passwords do not match." });
      return;
    }

    setWorkingAction("password");
    try {
      await changeAccountPassword(currentPassword, newPassword);
      setPasswordMessage({ type: "success", text: "Your password was changed successfully." });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      setPasswordMessage({ type: "error", text: readableAuthError(error) });
    } finally {
      setWorkingAction("");
    }
  }

  async function handlePasswordReset() {
    setPasswordMessage(null);
    setWorkingAction("reset");
    try {
      await sendCurrentUserPasswordReset();
      setPasswordMessage({ type: "success", text: `Password-reset email sent to ${user?.email}.` });
    } catch (error) {
      setPasswordMessage({ type: "error", text: readableAuthError(error) });
    } finally {
      setWorkingAction("");
    }
  }

  return (
    <ModalShell
      isOpen={isOpen}
      onClose={onClose}
      title="My Profile"
      description="Manage your Firebase sign-in details securely."
      size="large"
    >
      <div className="profile-modal">
        <section className="profile-modal__identity">
          <span className="profile-modal__identity-icon"><UserRound size={24} /></span>
          <div>
            <strong>{user?.displayName || "Vendly user"}</strong>
            <span>{user?.email}</span>
            <small>Sign-in method: {providerNames.join(", ") || "Unknown"}</small>
          </div>
          {user?.emailVerified && (
            <span className="profile-modal__verified"><ShieldCheck size={15} /> Verified</span>
          )}
        </section>

        <form className="profile-modal__section" onSubmit={handleEmailChange}>
          <div className="profile-modal__section-title">
            <Mail size={19} />
            <div><h3>Change email</h3><p>A verification link will be sent to the new address.</p></div>
          </div>
          <label>
            New email address
            <input type="email" value={newEmail} onChange={(event) => setNewEmail(event.target.value)} placeholder="new-email@example.com" required />
          </label>
          {hasPasswordProvider && (
            <label>
              Current password
              <input type="password" value={emailPassword} onChange={(event) => setEmailPassword(event.target.value)} autoComplete="current-password" required />
            </label>
          )}
          {!hasPasswordProvider && <p className="profile-modal__hint">Google will open a popup to confirm your identity.</p>}
          {emailMessage && <p className={`profile-modal__message profile-modal__message--${emailMessage.type}`} role="status">{emailMessage.text}</p>}
          <button className="profile-modal__primary" type="submit" disabled={Boolean(workingAction)}>
            {workingAction === "email" ? "Sending verification..." : "Verify new email"}
          </button>
        </form>

        <form className="profile-modal__section" onSubmit={handlePasswordChange}>
          <div className="profile-modal__section-title">
            <KeyRound size={19} />
            <div><h3>Change password</h3><p>Use a password you do not use on another website.</p></div>
          </div>

          {hasPasswordProvider ? (
            <>
              <div className="profile-modal__password-grid">
                <label>Current password<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" required /></label>
                <label>New password<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" minLength={6} required /></label>
                <label>Confirm new password<input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={6} required /></label>
              </div>
              {passwordMessage && <p className={`profile-modal__message profile-modal__message--${passwordMessage.type}`} role="status">{passwordMessage.text}</p>}
              <div className="profile-modal__button-row">
                <button className="profile-modal__secondary" type="button" onClick={handlePasswordReset} disabled={Boolean(workingAction)}><RotateCcw size={16} /> Send reset email</button>
                <button className="profile-modal__primary" type="submit" disabled={Boolean(workingAction)}>{workingAction === "password" ? "Changing..." : "Change password"}</button>
              </div>
            </>
          ) : (
            <p className="profile-modal__provider-note">This account signs in with Google, so it does not have a separate Vendly password. Manage your Google password from your Google Account.</p>
          )}
        </form>
      </div>
    </ModalShell>
  );
}

export default ProfileModal;
