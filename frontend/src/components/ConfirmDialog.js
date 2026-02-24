import React from "react";

const ConfirmDialog = ({ open, title, message, onConfirm, onCancel, confirmLabel = "Evet", danger = true }) => {
  if (!open) return null;
  return (
    <div className="modal-overlay">
      <div className="confirm-dialog">
        <div className="confirm-dialog-title">{title}</div>
        <div className="confirm-dialog-sub">{message}</div>
        <div className="confirm-dialog-actions">
          <button className="btn-ghost" onClick={onCancel}>İptal</button>
          <button
            className={danger ? "btn-danger" : "btn-primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
