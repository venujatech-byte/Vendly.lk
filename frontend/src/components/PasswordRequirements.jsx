import { useEffect, useState } from "react";
import { Check, Circle, X } from "lucide-react";
import { PASSWORD_RULES } from "../utils/passwordValidation";
import "./PasswordRequirements.css";

function PasswordRequirements({ password = "", confirmPassword = "" }) {
  const [isOpen, setIsOpen] = useState(false);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <div
      className="password-requirements-wrapper"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <button
        type="button"
        className="password-requirements-trigger"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsOpen((prev) => !prev);
        }}
        onFocus={() => setIsOpen(true)}
        aria-label="Password requirements information"
        aria-expanded={isOpen}
      >
        <span>?</span>
      </button>

      {/* Backdrop for mobile touch dismiss */}
      {isOpen && (
        <div
          className="password-requirements-backdrop"
          onClick={(e) => {
            e.stopPropagation();
            setIsOpen(false);
          }}
          aria-hidden="true"
        />
      )}

      <div
        className={`password-requirements-popover ${isOpen ? "is-visible" : ""}`}
        role="dialog"
        aria-label="Password requirements"
        aria-live="polite"
      >
        <div className="password-requirements-popover__header">
          <span className="password-requirements__title">Password must include</span>
          <button
            type="button"
            className="password-requirements-close"
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(false);
            }}
            aria-label="Close password requirements"
          >
            <X size={14} />
          </button>
        </div>

        <div className="password-requirements__list">
          {PASSWORD_RULES.map((rule) => {
            const valid = rule.test(password);
            return (
              <span className={valid ? "is-valid" : ""} key={rule.key}>
                {valid ? <Check size={13} /> : <Circle size={9} />}
                {rule.label}
              </span>
            );
          })}
        </div>

        {confirmPassword && (
          <span className={`password-requirements__match ${confirmPassword === password ? "is-valid" : ""}`}>
            {confirmPassword === password ? <Check size={13} /> : <Circle size={9} />}
            Passwords match
          </span>
        )}
      </div>
    </div>
  );
}

export default PasswordRequirements;
