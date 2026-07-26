"use client";

/**
 * @module EthernetSection
 * @description Ethernet status card. Read-only stat dl + a Configure button
 * that opens the EthernetConfigModal at the parent level.
 * @license GPL-3.0-only
 */

import { Button } from "@/components/ui/button";
import type { EthernetStatus, EthernetConfig } from "@/lib/api/ground-station/types";
import { StatRow } from "./StatRow";

const EMPTY = "…";

interface Props {
  ethernet: EthernetStatus | undefined;
  ethernetConfig: EthernetConfig | null;
  onConfigure: () => void;
}

export function EthernetSection({ ethernet, ethernetConfig, onConfigure }: Props) {
  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-medium text-text-primary">Ethernet</h2>
        <Button
          variant="secondary"
          size="sm"
          onClick={onConfigure}
          disabled={!ethernet?.available}
        >
          Configure
        </Button>
      </div>
      {!ethernet?.available ? (
        <div className="text-sm text-text-secondary">Ethernet not available on this hardware.</div>
      ) : (
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
          <StatRow
            label="Link"
            value={ethernet.link ? "Up" : "Down"}
            valueClass={ethernet.link ? "text-status-success" : "text-text-tertiary"}
          />
          <StatRow
            label="Speed"
            value={ethernet.speed_mbps != null ? ethernet.speed_mbps + " Mbps" : EMPTY}
          />
          <StatRow label="IP" value={ethernet.ip ?? EMPTY} />
          <StatRow label="Gateway" value={ethernet.gateway ?? EMPTY} />
          <StatRow label="Mode" value={ethernetConfig?.mode ?? EMPTY} />
        </dl>
      )}
    </section>
  );
}
