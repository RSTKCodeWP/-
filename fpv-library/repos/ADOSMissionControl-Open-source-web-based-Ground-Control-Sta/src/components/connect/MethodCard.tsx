/**
 * @module MethodCard
 * @description One selectable Direct-to-FC connection method in the connect
 * dialog: icon, name, a one-line purpose, and an availability chip for the
 * current surface. Selecting it reveals that method's form below.
 * @license GPL-3.0-only
 */

"use client";

import { useTranslations } from "next-intl";
import { Usb, Globe, Network, Server, Bluetooth, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { AvailabilityChip } from "./AvailabilityChip";
import type { ConnectionMethod, DirectMethodId } from "@/lib/connect/connection-methods";

const ICONS: Record<DirectMethodId, LucideIcon> = {
  serial: Usb,
  websocket: Globe,
  udp: Network,
  tcp: Server,
  bluetooth: Bluetooth,
};

export function MethodCard({
  method,
  selected,
  onSelect,
}: {
  method: ConnectionMethod;
  selected: boolean;
  onSelect: (id: DirectMethodId) => void;
}) {
  const t = useTranslations("connect");
  const Icon = ICONS[method.id];

  return (
    <button
      type="button"
      onClick={() => onSelect(method.id)}
      aria-pressed={selected}
      className={cn(
        "w-full flex items-center gap-2.5 px-2.5 py-2 text-left border transition-colors cursor-pointer",
        selected
          ? "border-accent-primary bg-accent-primary/10"
          : "border-border-default hover:border-border-strong",
      )}
    >
      <Icon
        size={16}
        className={cn(
          "shrink-0",
          selected ? "text-accent-primary" : "text-text-secondary",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-text-primary">
          {t(method.labelKey)}
        </div>
        <div className="text-[10px] text-text-tertiary truncate">
          {t(method.blurbKey)}
        </div>
      </div>
      <AvailabilityChip availability={method.availability} />
    </button>
  );
}
