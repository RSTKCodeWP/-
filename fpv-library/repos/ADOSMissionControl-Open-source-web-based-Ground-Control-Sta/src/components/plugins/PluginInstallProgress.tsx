"use client";

/**
 * @module PluginInstallProgress
 * @description Toast-style stepper that tracks a plugin install job
 * through the six-stage state machine. Subscribes to the agent's
 * WebSocket on the LAN path or to a Convex reactive query on the cloud
 * path. Auto-reconnects once on a mid-flight LAN drop. Simulates the
 * full sequence in demo mode.
 * @license GPL-3.0-only
 */

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Check, X, Loader2, AlertCircle, Minus } from "lucide-react";
import { useQuery } from "convex/react";
import { makeFunctionReference } from "convex/server";

import { cn, isDemoMode } from "@/lib/utils";
import { useConvexAvailable } from "@/app/ConvexClientProvider";

import {
  INSTALL_STAGES,
  LAN_SKIPPED_STAGES,
  humanStage,
  isTerminalStage,
  stageIndex,
  useInstallProgressStore,
  type InstallJobError,
  type InstallStage,
  type InstallTransport,
} from "./install-progress-store";

// Hand-rolled reference: the Convex deployment ships this query in a
// parallel wave, before `api.d.ts` regenerates with the new path.
interface JobDoc {
  jobId: string;
  stage: InstallStage;
  updatedAt: number;
  installId?: string;
  error?: InstallJobError;
}
const getJobRef = makeFunctionReference<
  "query",
  { jobId: string },
  JobDoc | null
>("cmdPluginInstallJobs:getJob");

export interface PluginInstallProgressProps {
  jobId: string;
  transport: InstallTransport;
  agentLanUrl?: string;
  pairingKey?: string;
  pluginName?: string;
  pluginVersion?: string;
  deviceLabel?: string;
  onComplete?: (result: { installId: string }) => void;
  onFailed?: (error: InstallJobError) => void;
  onRetry?: () => void;
}

interface ProgressState {
  stage: InstallStage;
  error?: InstallJobError;
  installId?: string;
  connectionWarning?: string;
}

const DEMO_TICK_MS = 600;

export function PluginInstallProgress(props: PluginInstallProgressProps) {
  const {
    jobId,
    transport,
    agentLanUrl,
    pairingKey,
    pluginName,
    pluginVersion,
    deviceLabel,
    onComplete,
    onFailed,
    onRetry,
  } = props;

  const [state, setState] = useState<ProgressState>(() => ({
    stage: transport === "lan" ? "verifying" : "uploading",
  }));
  const [dismissed, setDismissed] = useState(false);

  const onCompleteRef = useRef(onComplete);
  const onFailedRef = useRef(onFailed);
  onCompleteRef.current = onComplete;
  onFailedRef.current = onFailed;

  const upsert = useInstallProgressStore((s) => s.upsert);

  useEffect(() => {
    upsert({
      jobId,
      stage: state.stage,
      transport,
      updatedAt: Date.now(),
      installId: state.installId,
      error: state.error,
      pluginName,
      pluginVersion,
      deviceId: deviceLabel,
    });
  }, [
    jobId,
    transport,
    state.stage,
    state.installId,
    state.error,
    upsert,
    pluginName,
    pluginVersion,
    deviceLabel,
  ]);

  // Terminal-stage callbacks (fire once per terminal transition).
  const lastTerminalRef = useRef<string | null>(null);
  useEffect(() => {
    const key = `${jobId}:${state.stage}`;
    if (lastTerminalRef.current === key) return;
    if (state.stage === "completed" && state.installId) {
      lastTerminalRef.current = key;
      onCompleteRef.current?.({ installId: state.installId });
    } else if (state.stage === "failed" && state.error) {
      lastTerminalRef.current = key;
      onFailedRef.current?.(state.error);
    }
  }, [jobId, state.stage, state.installId, state.error]);

  // --- Demo mode ----------------------------------------------------
  useEffect(() => {
    if (!isDemoMode()) return;
    const seq: InstallStage[] =
      transport === "lan"
        ? ["verifying", "installing", "enabling", "completed"]
        : [...INSTALL_STAGES, "completed"];
    let i = 0;
    setState({ stage: seq[0] });
    const id = window.setInterval(() => {
      i += 1;
      if (i >= seq.length) {
        window.clearInterval(id);
        return;
      }
      const next = seq[i];
      setState({
        stage: next,
        installId: next === "completed" ? `demo-${jobId}` : undefined,
      });
    }, DEMO_TICK_MS);
    return () => window.clearInterval(id);
  }, [jobId, transport]);

  // --- LAN WebSocket subscription -----------------------------------
  //
  // Browsers cannot set custom headers on the WebSocket handshake,
  // so the pairing key cannot ride a request header here. We exchange
  // the pairing key (via the normal ``X-ADOS-Key`` REST middleware)
  // for a one-shot ticket and hand the ticket to
  // ``new WebSocket(url, ["ados-job-ticket", ticket])`` so it rides
  // the subprotocol header instead of the URL. URLs end up in
  // DevTools, HAR exports, and reverse-proxy access logs; the ticket
  // does not.
  useEffect(() => {
    if (isDemoMode()) return;
    if (transport !== "lan" || !agentLanUrl) return;

    let attempt = 0;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let cancelled = false;
    let ticketAbort: AbortController | null = null;

    const open = async (): Promise<void> => {
      if (cancelled) return;
      if (!pairingKey) {
        setState((s) => ({
          ...s,
          error: {
            code: "auth_missing",
            message: "Drone is not paired; cannot open progress channel.",
          },
          stage: "failed",
        }));
        return;
      }

      // 1) Mint a one-shot ticket. The REST middleware authenticates
      //    this call with ``X-ADOS-Key`` exactly like every other
      //    REST route.
      let ticket: string;
      try {
        ticketAbort = new AbortController();
        const resp = await fetch(
          `${agentLanUrl.replace(/\/$/, "")}/api/plugins/jobs/${encodeURIComponent(jobId)}/ticket`,
          {
            method: "POST",
            headers: { "X-ADOS-Key": pairingKey },
            signal: ticketAbort.signal,
          },
        );
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const body = (await resp.json()) as { ticket?: string };
        if (!body.ticket) {
          throw new Error("ticket mint response missing ticket");
        }
        ticket = body.ticket;
      } catch (err) {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setState((cur) => {
          if (isTerminalStage(cur.stage)) return cur;
          if (attempt === 0) {
            attempt = 1;
            reconnectTimer = window.setTimeout(() => {
              void open();
            }, 1000);
            return { ...cur, connectionWarning: "Reconnecting..." };
          }
          return {
            ...cur,
            connectionWarning: "Connection lost. Tap to retry.",
          };
        });
        return;
      }

      // 2) Open the WebSocket. The ticket rides the subprotocol
      //    array per RFC 6455 — the agent echoes back
      //    ``ados-job-ticket`` so the handshake completes.
      let wsUrlStr: string;
      try {
        const u = new URL(
          `/api/plugins/jobs/${encodeURIComponent(jobId)}`,
          agentLanUrl.replace(/^http/, "ws"),
        );
        wsUrlStr = u.toString();
      } catch {
        if (cancelled) return;
        setState((s) => ({
          ...s,
          error: { code: "lan_url_invalid", message: "Bad LAN agent URL." },
          stage: "failed",
        }));
        return;
      }
      ws = new WebSocket(wsUrlStr, ["ados-job-ticket", ticket]);
      ws.onmessage = (ev) => {
        try {
          const frame = JSON.parse(String(ev.data)) as Partial<JobDoc> & {
            stage?: InstallStage;
          };
          if (!frame.stage) return;
          setState((s) => ({
            stage: frame.stage as InstallStage,
            installId: frame.installId ?? s.installId,
            error: frame.error ?? s.error,
            connectionWarning: undefined,
          }));
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setState((cur) => {
          if (isTerminalStage(cur.stage)) return cur;
          if (attempt === 0) {
            attempt = 1;
            reconnectTimer = window.setTimeout(() => {
              void open();
            }, 1000);
            return { ...cur, connectionWarning: "Reconnecting..." };
          }
          return {
            ...cur,
            connectionWarning: "Connection lost. Tap to retry.",
          };
        });
      };
    };

    void open();
    return () => {
      cancelled = true;
      if (ticketAbort) {
        try { ticketAbort.abort(); } catch { /* ignore */ }
      }
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      try { ws?.close(); } catch { /* ignore */ }
    };
  }, [jobId, transport, agentLanUrl, pairingKey]);

  // --- Cloud reactive subscription ----------------------------------
  const convexAvailable = useConvexAvailable();
  const cloudArgs = useMemo(
    () =>
      !isDemoMode() && convexAvailable && transport === "cloud"
        ? ({ jobId } as { jobId: string })
        : ("skip" as const),
    [convexAvailable, transport, jobId],
  );
  // Call the query unconditionally and pass "skip" when the cloud path is
  // inactive (demo mode, no Convex, or the LAN transport). Skipping keeps
  // the hook order stable across renders while doing no network work.
  const cloudJob = useQuery(getJobRef, cloudArgs as never) as
    | JobDoc
    | null
    | undefined;
  useEffect(() => {
    if (!cloudJob) return;
    setState((s) => ({
      stage: cloudJob.stage,
      installId: cloudJob.installId ?? s.installId,
      error: cloudJob.error ?? s.error,
    }));
  }, [cloudJob]);

  // --- Render -------------------------------------------------------
  const terminal = isTerminalStage(state.stage);
  if (dismissed && terminal) return null;
  const currentIndex = stageIndex(state.stage);

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed right-4 top-4 z-[100] w-[360px] rounded-md border border-border-default bg-bg-secondary p-3 shadow-lg"
    >
      <header className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text-primary">
            {pluginName ?? "Plugin install"}
            {pluginVersion ? (
              <span className="ml-1 text-xs text-text-tertiary">
                v{pluginVersion}
              </span>
            ) : null}
          </p>
          {deviceLabel ? (
            <p className="truncate text-xs text-text-tertiary">
              on {deviceLabel}
            </p>
          ) : null}
        </div>
        <span
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide",
            transport === "lan"
              ? "bg-status-success/10 text-status-success"
              : "bg-accent-primary/10 text-accent-primary",
          )}
        >
          {transport === "lan" ? "LAN" : "Cloud"}
        </span>
        {terminal ? (
          <button
            type="button"
            onClick={() => setDismissed(true)}
            aria-label="Dismiss install progress"
            className="text-text-tertiary hover:text-text-primary"
          >
            <X size={14} />
          </button>
        ) : null}
      </header>

      <ol className="flex items-center gap-1.5">
        {INSTALL_STAGES.map((s, i) => {
          const lanSkip = transport === "lan" && LAN_SKIPPED_STAGES.has(s);
          const isFailed = state.stage === "failed";
          const isActive = !terminal && i === currentIndex;
          const isDone = i < currentIndex || (terminal && !isFailed);
          const dotState: DotState = lanSkip
            ? "skipped"
            : isFailed && i >= currentIndex
              ? "failed"
              : isActive
                ? "active"
                : isDone
                  ? "done"
                  : "pending";
          return (
            <li key={s} className="flex flex-1 items-center justify-center" aria-label={s}>
              <StageDot state={dotState} />
            </li>
          );
        })}
      </ol>

      <p className="mt-2 text-xs text-text-secondary">
        {terminal
          ? state.stage === "completed"
            ? "Done"
            : `Failed: ${state.error?.code ?? "unknown"}`
          : `${humanStage(state.stage)}...`}
      </p>
      {state.connectionWarning ? (
        <p className="mt-1 text-xs text-status-warning">{state.connectionWarning}</p>
      ) : null}
      {state.stage === "failed" && state.error ? (
        <Details error={state.error} onRetry={onRetry} />
      ) : null}
    </div>
  );
}

// --- helpers --------------------------------------------------------

type DotState = "pending" | "active" | "done" | "failed" | "skipped";

function StageDot({ state }: { state: DotState }): ReactNode {
  if (state === "skipped")
    return <Minus size={12} className="text-text-tertiary/50" aria-hidden />;
  if (state === "done")
    return <Check size={12} className="text-status-success" aria-hidden />;
  if (state === "active")
    return <Loader2 size={12} className="animate-spin text-accent-primary" aria-hidden />;
  if (state === "failed")
    return <AlertCircle size={12} className="text-status-error" aria-hidden />;
  return <span aria-hidden className="block h-2 w-2 rounded-full bg-text-tertiary/40" />;
}

function Details({
  error,
  onRetry,
}: {
  error: InstallJobError;
  onRetry?: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 border-t border-border-default pt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-accent-primary hover:underline"
      >
        {open ? "Hide details" : "Details"}
      </button>
      {open ? (
        <pre className="mt-1 whitespace-pre-wrap break-words text-[11px] text-status-error">
          {error.message}
        </pre>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 block text-xs text-accent-primary hover:underline"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

