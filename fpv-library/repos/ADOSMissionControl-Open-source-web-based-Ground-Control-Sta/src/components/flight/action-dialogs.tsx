"use client";

import { useTranslations } from "next-intl";
import { Modal } from "@/components/ui/modal";
import { PreFlightChecklist } from "@/components/flight/PreFlightChecklist";

interface ChecklistModalProps {
  open: boolean;
  onClose: () => void;
}

/**
 * The pre-flight checklist modal. The action confirmation dialogs (Arm, Disarm,
 * RTH, Takeoff, Land, Abort, Kill) are now driven by ConfirmPolicy data through
 * the shared skill-confirm host, so the action panel no longer wires a fixed
 * set of confirm dialogs here. This component is the panel's remaining modal:
 * the pre-flight checklist the operator opens before flight.
 */
export function ChecklistModal({ open, onClose }: ChecklistModalProps) {
  const t = useTranslations("actionDialogs");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("checklistTitle")}
      className="max-w-md max-h-[80vh] flex flex-col"
    >
      <PreFlightChecklist className="max-h-[60vh] -mx-4 -my-4" />
    </Modal>
  );
}
