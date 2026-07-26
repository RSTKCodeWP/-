"use client";

/**
 * @module CellularSection
 * @description 4G modem status card with Configure button. Shows state,
 * signal bars, operator/carrier, APN, IP, interface, and a data-cap usage
 * bar when a cap is set. The configure modal lives in the parent.
 * @license GPL-3.0-only
 */

import { Button } from "@/components/ui/button";
import { DataUsageBar } from "@/components/hardware/DataUsageBar";
import { HintChip } from "@/components/hardware/HintChip";
import type { ModemStatus } from "@/lib/api/ground-station/types";
import { StatRow } from "./StatRow";

const EMPTY = "…";

interface Props {
  modem: ModemStatus | null;
  onConfigure: () => void;
}

export function CellularSection({ modem, onConfigure }: Props) {
  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-medium text-text-primary">4G Modem</h2>
        <Button
          variant="secondary"
          size="sm"
          onClick={onConfigure}
          disabled={!modem?.available}
        >
          Configure
        </Button>
      </div>

      {!modem?.available ? (
        <div className="text-sm text-text-secondary">No modem detected.</div>
      ) : (
        <div className="flex flex-col gap-3">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
            <StatRow label="State" value={modem.state ?? EMPTY} />
            <StatRow
              label="Signal"
              value={
                modem.signal_bars != null
                  ? modem.signal_bars + " / 5"
                  : modem.signal_dbm != null
                    ? modem.signal_dbm + " dBm"
                    : EMPTY
              }
            />
            <StatRow label="Operator" value={modem.operator ?? modem.carrier ?? EMPTY} />
            <StatRow label="APN" value={modem.apn ?? EMPTY} />
            <StatRow label="Interface" value={modem.iface ?? EMPTY} />
            <StatRow label="IP" value={modem.ip ?? EMPTY} />
          </dl>

          {modem.data_cap && modem.data_cap.cap_mb > 0 ? (
            <div className="mt-1">
              <div className="mb-1 flex items-center gap-2">
                <span className="text-xs uppercase tracking-wide text-text-secondary">
                  Data usage
                </span>
                <HintChip>Caps apply to 4G only. WiFi and Ethernet are uncapped.</HintChip>
              </div>
              <DataUsageBar
                usedMb={modem.data_cap.used_mb}
                capMb={modem.data_cap.cap_mb}
                state={modem.data_cap.state}
              />
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
