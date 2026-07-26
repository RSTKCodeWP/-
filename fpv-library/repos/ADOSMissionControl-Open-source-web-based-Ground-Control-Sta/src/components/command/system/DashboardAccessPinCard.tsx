"use client";

/**
 * @module command/system/DashboardAccessPinCard
 * @description Per-node control for the DASHBOARD-ACCESS PIN. A paired node's own
 * web dashboard (`http://<node>:8080`) is unlocked from another device on the
 * network by a 4-digit PIN. Mission Control — which holds the node's API key —
 * shows whether a PIN is set and can set or reset it. A reset signs out every
 * browser currently unlocked on that node's dashboard (the session tokens are
 * keyed with a salt the reset rotates).
 *
 * Local-first: the control reaches the node over the LAN via the `/api/lan-pair`
 * proxy with the stored key. It renders only for a locally-paired node (a cloud
 * relay session has no LAN key path), matching the pattern of the sibling
 * regulatory-region panel.
 * @license GPL-3.0-only
 */

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, KeyRound, Lock } from "lucide-react";
import { useAgentConnectionStore } from "@/stores/agent-connection-store";
import { useLocalNodesStore } from "@/stores/local-nodes-store";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";
import {
  clearDashboardPin,
  getDashboardPinStatus,
  setDashboardPin,
  type DashboardPinStatus,
} from "@/lib/agent/local-pair-client";

const PIN_LENGTH = 4;

export function DashboardAccessPinCard() {
  const cloudMode = useAgentConnectionStore((s) => s.cloudMode);
  const activeUrl = useAgentConnectionStore((s) => s.agentUrl);
  const nodes = useLocalNodesStore((s) => s.nodes);
  const { toast } = useToast();

  // The focused agent as a locally-paired node (LAN host + stored key). Absent
  // in cloud mode or for a node paired only through the relay.
  const activeNode = nodes.find((n) => n.hostname === activeUrl) ?? null;
  const available = !cloudMode && !!activeNode;

  const [status, setStatus] = useState<DashboardPinStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmingReset, setConfirmingReset] = useState(false);

  const refresh = useCallback(async () => {
    if (!activeNode) return;
    setLoading(true);
    try {
      setStatus(await getDashboardPinStatus(activeNode.hostname, activeNode.apiKey));
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [activeNode]);

  useEffect(() => {
    if (available) void refresh();
  }, [available, refresh]);

  // Cloud mode / no local key path: the PIN is managed on the device. Hide the
  // card rather than show a control that cannot reach the node.
  if (!available || !activeNode) return null;

  const onSet = async () => {
    if (pin.length !== PIN_LENGTH || busy) return;
    setBusy(true);
    try {
      await setDashboardPin(activeNode.hostname, activeNode.apiKey, pin);
      toast("Dashboard PIN set", "success");
      setPin("");
      await refresh();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to set PIN", "error");
    } finally {
      setBusy(false);
    }
  };

  const onReset = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await clearDashboardPin(activeNode.hostname, activeNode.apiKey);
      toast("Dashboard PIN reset", "success");
      setConfirmingReset(false);
      await refresh();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Failed to reset PIN", "error");
    } finally {
      setBusy(false);
    }
  };

  const reachUrl = activeNode.hostname; // already http://<host>:8080

  return (
    <section className="rounded border border-border-default bg-bg-secondary p-5">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <KeyRound size={16} className="text-accent-primary" />
        <h2 className="text-lg font-medium text-text-primary">Dashboard access</h2>
        <div className="flex-1" />
        {loading ? (
          <span className="text-xs text-text-tertiary">checking…</span>
        ) : status?.locked ? (
          <span className="inline-flex items-center gap-1.5 rounded border border-status-warning/40 bg-status-warning/10 px-2.5 py-1 text-xs font-medium text-status-warning">
            <Lock size={12} /> Locked
          </span>
        ) : status?.pinSet ? (
          <span className="inline-flex items-center gap-1.5 rounded border border-status-success/40 bg-status-success/10 px-2.5 py-1 text-xs font-medium text-status-success">
            PIN set
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded border border-border-default bg-bg-tertiary/40 px-2.5 py-1 text-xs font-medium text-text-secondary">
            No PIN
          </span>
        )}
      </div>

      <p className="mb-4 text-sm text-text-secondary">
        Visitors to this node&apos;s web dashboard enter a 4-digit PIN to unlock it. Reset issues a
        new one and signs out anyone currently connected.
      </p>

      {/* Reach URL */}
      <div className="mb-4 rounded border border-border-default/60 bg-bg-tertiary/40 px-3 py-2">
        <div className="text-[10px] uppercase tracking-wide text-text-tertiary">Web dashboard</div>
        <a
          href={reachUrl}
          target="_blank"
          rel="noreferrer"
          className="mt-0.5 inline-flex items-center gap-1.5 font-mono text-sm text-accent-primary hover:underline"
        >
          {reachUrl}
          <ExternalLink size={12} />
        </a>
      </div>

      {status && !status.pinSet ? (
        // Trust-on-first-use: Mission Control can seed the initial PIN.
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-[160px]">
            <label className="mb-1 block text-xs text-text-secondary">Set a 4-digit PIN</label>
            <input
              type="text"
              inputMode="numeric"
              autoComplete="off"
              maxLength={PIN_LENGTH}
              value={pin}
              placeholder="0000"
              onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, PIN_LENGTH))}
              className="h-9 w-full rounded border border-border-default bg-bg-tertiary px-2 text-center font-mono text-lg tracking-[0.4em] text-text-primary focus:border-accent-primary focus:outline-none"
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void onSet()}
            disabled={pin.length !== PIN_LENGTH || busy}
          >
            {busy ? "Setting…" : "Set PIN"}
          </Button>
        </div>
      ) : status?.pinSet ? (
        // A PIN exists: offer a reset behind an inline confirm (destructive).
        confirmingReset ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-text-secondary">
              Reset the PIN? Connected browsers will be signed out.
            </span>
            <Button variant="danger" size="sm" onClick={() => void onReset()} disabled={busy}>
              {busy ? "Resetting…" : "Confirm reset"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setConfirmingReset(false)}
              disabled={busy}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="danger" size="sm" onClick={() => setConfirmingReset(true)}>
            Reset PIN
          </Button>
        )
      ) : null}
    </section>
  );
}
