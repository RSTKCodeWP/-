"use client";

/**
 * @module components/fc/security/signing/SigningUnsupportedNotice
 * @description Rendered when the agent reports the FC cannot do MAVLink
 * signing. Either the firmware does not support it or the FC is offline.
 */

import { ShieldOff } from "lucide-react";
import { describeReason } from "./describe-reason";

export interface SigningUnsupportedNoticeProps {
  firmware: string;
  reason: string;
}

export function SigningUnsupportedNotice({ firmware, reason }: SigningUnsupportedNoticeProps) {
  const reasonText = describeReason(reason);
  return (
    <div className="border border-border-default bg-bg-secondary p-4 space-y-2">
      <div className="flex items-center gap-2 text-text-secondary">
        <ShieldOff size={16} aria-hidden="true" />
        <span className="font-medium">Signing not available on this drone</span>
      </div>
      <p className="text-sm text-text-tertiary">
        Firmware: {firmware}. {reasonText}
      </p>
      <p className="text-xs text-text-tertiary">
        Commands sent to this drone are not cryptographically authenticated at the MAVLink layer.
      </p>
    </div>
  );
}
