import { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import "./ModalShell.css";

function ModalShell({ isOpen, title, description, onClose, children, size = "medium" }) {
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
          <div>
            <h2 id="modal-shell-title">{title}</h2>
            {description && <p>{description}</p>}
          </div>

          <button type="button" onClick={onClose} aria-label={`Close ${title}`}>
            <X size={21} aria-hidden="true" />
          </button>
        </header>

        <div className="modal-shell__content">{children}</div>
      </section>
    </div>,
    document.body,
  );
}

export default ModalShell;
