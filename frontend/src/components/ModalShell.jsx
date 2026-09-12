import { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import "./ModalShell.css";

function ModalShell({
  isOpen,
  title,
  description,
  onClose,
  children,
  size = "medium",
  icon: Icon = null,
  iconTone = "primary",
}) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function closeWithEscape(event) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", closeWithEscape);
    document.body.classList.add("modal-is-open");

    return () => {
      document.removeEventListener("keydown", closeWithEscape);
      document.body.classList.remove("modal-is-open");
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return createPortal(
    <div className="modal-shell__backdrop" role="presentation">
      <section
        className={`modal-shell modal-shell--${size}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-shell-title"
      >
        <header className="modal-shell__header">
          <div className="modal-shell__header-main">
            {Icon && (
              <div className={`modal-shell__icon modal-shell__icon--${iconTone}`} aria-hidden="true">
                <Icon size={22} strokeWidth={2.2} />
              </div>
            )}
            <div className="modal-shell__title-group">
              <h2 id="modal-shell-title">{title}</h2>
              {description && <p>{description}</p>}
            </div>
          </div>

          <button className="modal-shell__close-btn" type="button" onClick={onClose} aria-label={`Close ${title}`}>
            <X size={20} aria-hidden="true" />
          </button>
        </header>

        <div className="modal-shell__content">{children}</div>
      </section>
    </div>,
    document.body,
  );
}

export default ModalShell;
