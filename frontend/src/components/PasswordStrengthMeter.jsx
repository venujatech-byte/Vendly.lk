import { CheckCircle2, ShieldAlert, ShieldCheck } from "lucide-react";
import { getPasswordScore, getPasswordStrength, PASSWORD_RULES } from "../utils/passwordValidation";
import "./PasswordStrengthMeter.css";

function PasswordStrengthMeter({ password = "" }) {
  if (!password) return null;

  const strength = getPasswordStrength(password);
  const score = getPasswordScore(password);
  const total = PASSWORD_RULES.length;

  return (
    <div className={`password-meter password-meter--${strength.status}`} aria-live="polite">
      <div className="password-meter__bar-track">
        <div
          className={`password-meter__bar-segment ${score >= 1 ? "is-filled" : ""}`}
        />
        <div
          className={`password-meter__bar-segment ${score >= 3 ? "is-filled" : ""}`}
        />
        <div
          className={`password-meter__bar-segment ${score >= 4 ? "is-filled" : ""}`}
        />
        <div
          className={`password-meter__bar-segment ${strength.isComplete ? "is-filled is-complete" : ""}`}
        />
      </div>

      <div className="password-meter__status-row">
        <span className="password-meter__label">
          {strength.isComplete ? (
            <>
              <CheckCircle2 size={13} className="password-meter__icon" />
              <strong>All password requirements satisfied</strong>
            </>
          ) : score >= 3 ? (
            <>
              <ShieldCheck size={13} className="password-meter__icon" />
              <span>Good password ({score}/{total} rules met)</span>
            </>
          ) : (
            <>
              <ShieldAlert size={13} className="password-meter__icon" />
              <span>Weak password ({score}/{total} rules met)</span>
            </>
          )}
        </span>

        {strength.isComplete && (
          <span className="password-meter__badge">Verified</span>
        )}
      </div>
    </div>
  );
}

export default PasswordStrengthMeter;
