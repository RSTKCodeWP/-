"use client";

/**
 * @module NodePingCard
 * @description GetNodeInfo round-trip timer with a five-entry rolling
 * history. Renders a node-id input and a [Ping] button; on success shows
 * RTT in ms; on timeout shows the 1000 ms hint message.
 *
 * @license GPL-3.0-only
 */

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { TimeoutError, type DroneCanClient } from "@/lib/dronecan/client";

const PING_HISTORY_CAP = 5;
const PING_TIMEOUT_MS = 1000;

export interface NodePingCardProps {
  client?: Pick<DroneCanClient, "getNodeInfo"> | null;
}

export function NodePingCard({ client }: NodePingCardProps) {
  const t = useTranslations("canConfig.testUtilities.ping");

  const [nodeIdRaw, setNodeIdRaw] = useState("");
  const [history, setHistory] = useState<number[]>([]);
  const [lastResultMs, setLastResultMs] = useState<number | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const nodeId = useMemo(() => {
    const n = Number.parseInt(nodeIdRaw, 10);
    if (Number.isFinite(n) && n >= 1 && n <= 127) return n;
    return null;
  }, [nodeIdRaw]);

  const handlePing = useCallback(async () => {
    if (nodeId == null || !client || busy) return;
    setBusy(true);
    setLastError(null);
    const start =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    try {
      await client.getNodeInfo(nodeId, { timeoutMs: PING_TIMEOUT_MS });
      const end =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const rtt = Math.max(0, Math.round(end - start));
      setLastResultMs(rtt);
      setHistory((prev) => {
        const next = [...prev, rtt];
        if (next.length > PING_HISTORY_CAP) next.shift();
        return next;
      });
    } catch (err) {
      setLastResultMs(null);
      if (err instanceof TimeoutError) {
        setLastError(t("timeout", { ms: PING_TIMEOUT_MS }));
      } else {
        setLastError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setBusy(false);
    }
  }, [client, nodeId, busy, t]);

  return (
    <Card title={t("title")}>
      <div className="flex items-end gap-3 flex-wrap">
        <div className="w-32">
          <Input
            label={t("nodeId")}
            type="number"
            min={1}
            max={127}
            value={nodeIdRaw}
            onChange={(e) => setNodeIdRaw(e.target.value)}
          />
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<Activity size={12} />}
          onClick={handlePing}
          disabled={nodeId == null || !client || busy}
          loading={busy}
        >
          {t("button")}
        </Button>
        <div className="flex-1 min-w-[200px] text-[11px] font-mono">
          {lastError ? (
            <span className="text-status-error" data-testid="ping-error">
              ✖ {lastError}
            </span>
          ) : lastResultMs != null ? (
            <span className="text-status-success" data-testid="ping-result">
              → {lastResultMs} ms RTT
              {history.length > 0 && (
                <span className="text-text-tertiary ml-2">
                  {t("history", { values: history.join(", ") })}
                </span>
              )}
            </span>
          ) : (
            <span className="text-text-tertiary">—</span>
          )}
        </div>
      </div>
    </Card>
  );
}
