"use client";

/**
 * @module ManualFrameInjectCard
 * @description Single-frame inject onto the active CAN transport. After
 * send, watches the decoded bus log for 100 ms for a frame with matching
 * CAN ID + payload and reports the round-trip latency.
 *
 * @license GPL-3.0-only
 */

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDroneCanBusStore } from "@/stores/dronecan/bus-store";
import type {
  CanFrame,
  CanTransport,
} from "@/lib/protocol/transport/can-transport";

const ECHO_WINDOW_MS = 100;

export interface ManualFrameInjectCardProps {
  transport?: Pick<CanTransport, "send"> | null;
}

export function ManualFrameInjectCard({
  transport,
}: ManualFrameInjectCardProps) {
  const t = useTranslations("canConfig.testUtilities.inject");

  const [canIdHex, setCanIdHex] = useState("");
  const [dlcRaw, setDlcRaw] = useState("8");
  const [dataHex, setDataHex] = useState("");
  const [echo, setEcho] = useState<"idle" | "seen" | "missed">("idle");
  const [echoLatencyMs, setEchoLatencyMs] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = useMemo(() => {
    const id = Number.parseInt(canIdHex.replace(/^0x/i, ""), 16);
    const dlc = Number.parseInt(dlcRaw, 10);
    const clean = dataHex.replace(/[^0-9a-fA-F]/g, "");
    if (!Number.isFinite(id) || id < 0) return null;
    if (!Number.isFinite(dlc) || dlc < 0 || dlc > 8) return null;
    if (clean.length !== dlc * 2) return null;
    const bytes = new Uint8Array(dlc);
    for (let i = 0; i < dlc; i++) {
      bytes[i] = Number.parseInt(clean.substring(i * 2, i * 2 + 2), 16);
    }
    return { id, dlc, bytes };
  }, [canIdHex, dlcRaw, dataHex]);

  const handleSend = useCallback(async () => {
    if (!parsed || !transport || busy) return;
    setBusy(true);
    setEcho("idle");
    setEchoLatencyMs(null);
    setError(null);

    const sentAt =
      typeof performance !== "undefined" ? performance.now() : Date.now();
    let echoSeen = false;

    // Read the O(1) ring length directly. toArray() would allocate a full copy
    // of the (potentially large) CAN ring just to read its count. The later
    // echo-detection loop legitimately needs toArray() to scan contents.
    const startCount = useDroneCanBusStore.getState().frames.length;

    try {
      const frame: CanFrame = {
        id: parsed.id,
        extended: true,
        dlc: parsed.dlc,
        data: parsed.bytes,
      };
      await transport.send(frame);

      await new Promise<void>((resolve) => {
        const check = () => {
          const ring = useDroneCanBusStore.getState().frames.toArray();
          for (let i = startCount; i < ring.length; i++) {
            const f = ring[i];
            if (
              f.canId === parsed.id &&
              payloadMatches(f.payload, parsed.bytes)
            ) {
              echoSeen = true;
              const seenAt =
                typeof performance !== "undefined"
                  ? performance.now()
                  : Date.now();
              setEchoLatencyMs(Math.max(0, +(seenAt - sentAt).toFixed(1)));
              break;
            }
          }
          if (echoSeen) {
            resolve();
            return;
          }
          const elapsed =
            typeof performance !== "undefined"
              ? performance.now() - sentAt
              : Date.now() - sentAt;
          if (elapsed >= ECHO_WINDOW_MS) {
            resolve();
            return;
          }
          setTimeout(check, 10);
        };
        check();
      });

      setEcho(echoSeen ? "seen" : "missed");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setEcho("idle");
    } finally {
      setBusy(false);
    }
  }, [parsed, transport, busy]);

  return (
    <Card title={t("title")}>
      <div className="flex items-end gap-2 flex-wrap">
        <div className="w-36">
          <Input
            label={t("canId")}
            placeholder="0x18000000"
            value={canIdHex}
            onChange={(e) => setCanIdHex(e.target.value)}
          />
        </div>
        <div className="w-16">
          <Input
            label={t("dlc")}
            type="number"
            min={0}
            max={8}
            value={dlcRaw}
            onChange={(e) => setDlcRaw(e.target.value)}
          />
        </div>
        <div className="flex-1 min-w-[180px]">
          <Input
            label={t("data")}
            placeholder="0011223344556677"
            value={dataHex}
            onChange={(e) => setDataHex(e.target.value)}
          />
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<Send size={12} />}
          onClick={handleSend}
          disabled={!parsed || !transport || busy}
          loading={busy}
        >
          {t("button")}
        </Button>
      </div>
      <div className="mt-2 text-[11px] font-mono">
        {error ? (
          <span className="text-status-error">{error}</span>
        ) : echo === "seen" ? (
          <span className="text-status-success" data-testid="inject-echo-seen">
            {t("echoSeen", { ms: echoLatencyMs ?? 0 })}
          </span>
        ) : echo === "missed" ? (
          <span className="text-status-warning" data-testid="inject-echo-missed">
            {t("echoMissed")}
          </span>
        ) : (
          <span className="text-text-tertiary">—</span>
        )}
      </div>
    </Card>
  );
}

function payloadMatches(a: Uint8Array, b: Uint8Array): boolean {
  if (a.byteLength !== b.byteLength) return false;
  for (let i = 0; i < a.byteLength; i++) if (a[i] !== b[i]) return false;
  return true;
}
