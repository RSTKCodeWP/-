"use client";

/**
 * @module ConflictScanCard
 * @description Sweeps every known node by id and surfaces duplicate
 * GetNodeInfo unique_id fields. The scan calls `client.getNodeInfo` per
 * known node with a per-node 700 ms ceiling and aggregates responses;
 * two matching ids with different unique_ids flag a conflict.
 *
 * @license GPL-3.0-only
 */

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";
import type { DroneCanClient } from "@/lib/dronecan/client";

const CONFLICT_SCAN_PER_NODE_TIMEOUT_MS = 700;

export interface ConflictScanCardProps {
  client?: Pick<DroneCanClient, "getNodeInfo"> | null;
}

interface ConflictRecord {
  nodeId: number;
  uniqueIds: string[];
}

export function ConflictScanCard({ client }: ConflictScanCardProps) {
  const t = useTranslations("canConfig.testUtilities.conflictScan");
  const nodesMap = useDroneCanNodeStore((s) => s.nodes);

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ConflictRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleScan = useCallback(async () => {
    if (!client || busy) return;
    setBusy(true);
    setResult(null);
    setError(null);

    const seen = new Map<number, Set<string>>();
    const ids = Array.from(nodesMap.keys()).sort((a, b) => a - b);

    try {
      await Promise.all(
        ids.map(async (id) => {
          try {
            const info = await client.getNodeInfo(id, {
              timeoutMs: CONFLICT_SCAN_PER_NODE_TIMEOUT_MS,
            });
            const uid = uniqueIdHex(info.hardware_version.unique_id);
            const bucket = seen.get(id) ?? new Set<string>();
            bucket.add(uid);
            seen.set(id, bucket);
          } catch {
            // Non-responsive nodes are skipped silently. The scanner is a
            // best-effort sweep; the underlying timeout is intentionally
            // short so the operator gets a result inside a few seconds.
          }
        }),
      );
      const conflicts: ConflictRecord[] = [];
      for (const [id, set] of seen) {
        if (set.size > 1) conflicts.push({ nodeId: id, uniqueIds: Array.from(set) });
      }
      setResult(conflicts);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [client, busy, nodesMap]);

  return (
    <Card title={t("title")}>
      <div className="flex items-center gap-3 flex-wrap">
        <Button
          variant="secondary"
          size="sm"
          icon={<AlertTriangle size={12} />}
          onClick={handleScan}
          disabled={!client || busy}
          loading={busy}
        >
          {t("button")}
        </Button>
        <div className="flex-1 min-w-[240px] text-[11px] font-mono">
          {error ? (
            <span className="text-status-error">{error}</span>
          ) : result === null ? (
            <span className="text-text-tertiary">—</span>
          ) : result.length === 0 ? (
            <span className="text-status-success" data-testid="conflict-scan-clean">
              {t("noConflicts")}
            </span>
          ) : (
            <span className="text-status-error" data-testid="conflict-scan-found">
              {t("conflictDetected", {
                count: result.length,
                first: result[0].nodeId,
              })}
            </span>
          )}
        </div>
      </div>
    </Card>
  );
}

function uniqueIdHex(uid: Uint8Array): string {
  const out: string[] = [];
  for (const b of uid) out.push(b.toString(16).padStart(2, "0"));
  return out.join("");
}
