import { useEffect } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, Mail, X } from "lucide-react";
import "./EmailVerificationPromptModal.css";

function EmailVerificationPromptModal({
  isOpen,
  email = "",
  mode = "registered", // 'registered' | 'unverified_login'
  onClose,
  onPrimaryAction,
}) {
  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const isUnverifiedLogin = mode === "unverified_login";

  const modalContent = (
    <div
      className="email-prompt-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="email-prompt-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="email-prompt-title"
      >
        <button
          type="button"
          className="email-prompt-modal__close"
          onClick={onClose}
          aria-label="Close verification modal"
        >
          <X size={18} />
        </button>

        <div className="email-prompt-modal__icon-wrap">
          <div className="email-prompt-modal__icon-circle">
            <Mail size={32} className="email-prompt-modal__mail-icon" />
          </div>
          <span className="email-prompt-modal__icon-badge">
            {isUnverifiedLogin ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
          </span>
        </div>

        <h2 id="email-prompt-title" className="email-prompt-modal__title">
          Verify Your Account via Email
        </h2>

        <p className="email-prompt-modal__message">
          {isUnverifiedLogin ? (
            <>
              Please verify your account via email before logging in. We sent a verification link to{" "}
              <strong>{email || "your email address"}</strong>.
            </>
          ) : (
            <>
              Account created successfully! Please verify your account via email to activate it. We sent a confirmation link to{" "}
              <strong>{email || "your email address"}</strong>.
            </>
          )}
        </p>

        {/* Highlight Spam folder note */}
        <div className="email-prompt-modal__spam-box" role="note">
          <div className="email-prompt-modal__spam-header">
            <AlertTriangle size={16} className="email-prompt-modal__spam-icon" />
            <strong>If you don&apos;t see your email:</strong>
          </div>
          <p>
            Please check in your <strong>spam folder</strong> or junk mail. Email providers occasionally route automated verification messages there.
          </p>
        </div>

        <div className="email-prompt-modal__instructions">
          <span>Click the link in your email to verify your account, then sign in.</span>
        </div>

        <div className="email-prompt-modal__actions">
          <button
            type="button"
            className="email-prompt-modal__btn email-prompt-modal__btn--primary"
            onClick={() => {
              if (onPrimaryAction) {
                onPrimaryAction();
              } else {
                onClose();
              }
            }}
          >
            <span>{isUnverifiedLogin ? "I Understand, Go to Sign In" : "Got It, Continue to Sign In"}</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document !== "undefined" && document.body) {
    return createPortal(modalContent, document.body);
  }

  return modalContent;
}

export default EmailVerificationPromptModal;
