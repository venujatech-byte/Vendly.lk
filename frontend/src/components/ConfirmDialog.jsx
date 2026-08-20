import ModalShell from "./ModalShell";

import "./ConfirmDialog.css";

function ConfirmDialog({ isOpen, title, message, confirmLabel = "Remove", isWorking = false, onCancel, onConfirm }) {
  return (
    <ModalShell isOpen={isOpen} title={title} description="Please confirm this action." onClose={onCancel}>
      <div className="confirm-dialog">
        <p>{message}</p>
        <footer className="confirm-dialog__actions">
          <button type="button" onClick={onCancel} disabled={isWorking}>Cancel</button>
          <button className="confirm-dialog__danger" type="button" onClick={onConfirm} disabled={isWorking}>
            {isWorking ? "Removing..." : confirmLabel}
          </button>
        </footer>
      </div>
    </ModalShell>
  );
}

export default ConfirmDialog;
