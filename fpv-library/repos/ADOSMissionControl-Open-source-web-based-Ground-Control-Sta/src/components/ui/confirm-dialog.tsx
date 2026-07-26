"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Modal } from "./modal";
import { Button } from "./button";

interface ConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "primary" | "danger";
  confirmDisabled?: boolean;
  /**
   * Optional typed-phrase gate. When provided, the confirm button stays
   * disabled until the user types this exact phrase into the prompt input.
   * Used for destructive actions like factory reset where a plain click
   * would be too easy to fire by accident.
   */
  typedPhrase?: string;
}

export function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title,
  message,
  confirmLabel,
  cancelLabel,
  variant = "primary",
  confirmDisabled = false,
  typedPhrase,
}: ConfirmDialogProps) {
  const t = useTranslations("common");
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  const phraseGate = typedPhrase ? typed !== typedPhrase : false;
  const finalDisabled = confirmDisabled || phraseGate;

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      className="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel ?? t("cancel")}
          </Button>
          <Button
            variant={variant === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={finalDisabled}
          >
            {confirmLabel ?? t("save")}
          </Button>
        </>
      }
    >
      <p className="text-sm text-text-secondary">{message}</p>
      {typedPhrase ? (
        <div className="mt-3 flex flex-col gap-1">
          <label htmlFor="confirm-typed-phrase" className="text-xs text-text-secondary">
            Type <span className="font-mono text-text-primary">{typedPhrase}</span> to confirm
          </label>
          <input
            id="confirm-typed-phrase"
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoFocus
            spellCheck={false}
            autoComplete="off"
            className="w-full h-9 px-2 bg-bg-tertiary border border-border-default text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-primary transition-colors"
          />
        </div>
      ) : null}
    </Modal>
  );
}
