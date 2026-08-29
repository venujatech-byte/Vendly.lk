import ModalShell from "./ModalShell";

import "./ConfirmDialog.css";

function ConfirmDialog({ isOpen, title, message, confirmLabel = "Remove", workingLabel = "Removing...", isWorking = false, tone = "danger", onCancel, onConfirm }) {
  return (
    <ModalShell isOpen={isOpen} title={title} description="Please confirm this action." onClose={onCancel}>
      <div className="confirm-dialog">
        <p>{message}</p>
        <footer className="confirm-dialog__actions">
          <button type="button" onClick={onCancel} disabled={isWorking}>Cancel</button>
          <button className={`confirm-dialog__confirm confirm-dialog__confirm--${tone}`} type="button" onClick={onConfirm} disabled={isWorking}>
            {isWorking ? workingLabel : confirmLabel}
          </button>
        </footer>
      </div>
    </ModalShell>
  );
}

export default ConfirmDialog;
