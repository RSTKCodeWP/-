"use client";

/**
 * @module ForgeJobs
 * @description Jobs sub-view of the Atlas Forge workbench: the compute node's
 * reconstruction / offload job list with state badges, progress, and a cancel
 * affordance for in-flight jobs. Reads the live list from `use-compute-jobs`.
 * @license GPL-3.0-only
 */

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Layers, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  ComputeAgentClient,
  ComputeJob,
} from "@/lib/agent/compute-client";
import { qualityForSteps } from "@/lib/atlas/reconstruction-quality";

/** atlas i18n key for a job state, or null for an unknown state (rendered raw). */
function jobStateKey(state: string): string | null {
  switch (state) {
    case "queued":
      return "jobQueued";
    case "running":
      return "jobRunning";
    case "completed":
      return "jobCompleted";
    case "failed":
      return "jobFailed";
    case "cancelled":
      return "jobCancelled";
    default:
      return null;
  }
}

function jobStateClass(state: string): string {
  switch (state) {
    case "running":
      return "bg-accent-primary/15 text-accent-primary";
    case "completed":
      return "bg-status-success/15 text-status-success";
    case "failed":
      return "bg-status-error/15 text-status-error";
    default:
      return "bg-bg-tertiary text-text-tertiary";
  }
}

function ago(ms: number): string {
  if (ms <= 0) return "—";
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${Math.round(s / 3600)}h`;
}

function JobRow({
  job,
  onCancel,
}: {
  job: ComputeJob;
  onCancel: ((id: string) => void) | null;
}) {
  const t = useTranslations("atlas");
  const stateKey = jobStateKey(job.state);
  const stateLabel = stateKey ? t(stateKey) : job.state;
  const cancellable = job.state === "queued" || job.state === "running";

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded bg-bg-tertiary">
      <Layers size={12} className="text-text-tertiary flex-shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-text-secondary truncate">
            {job.kind}
          </span>
          {job.kind === "reconstruct" && job.steps !== null && (
            <span
              className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-bg-tertiary text-text-tertiary flex-shrink-0"
              title={`${job.steps.toLocaleString()} steps`}
            >
              {t(qualityForSteps(job.steps).labelKey)}
            </span>
          )}
          <span
            className="text-[10px] font-mono text-text-tertiary truncate"
            title={job.id}
          >
            {job.id}
          </span>
        </div>
        {job.state === "running" && (
          <div className="h-1 mt-1 bg-bg-tertiary rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-accent-primary transition-all"
              style={{ width: `${Math.min(job.progress * 100, 100)}%` }}
            />
          </div>
        )}
        {job.error && (
          <p className="text-[10px] text-status-error truncate" title={job.error}>
            {job.error}
          </p>
        )}
      </div>
      <span className="text-[10px] font-mono text-text-tertiary flex-shrink-0 tabular-nums">
        {ago(job.updatedMs || job.createdMs)}
      </span>
      <span
        className={cn(
          "text-[10px] font-medium px-1.5 py-0.5 rounded flex-shrink-0",
          jobStateClass(job.state),
        )}
      >
        {stateLabel}
      </span>
      {cancellable && onCancel && (
        <button
          type="button"
          onClick={() => onCancel(job.id)}
          title={t("forgeCancel")}
          aria-label={t("forgeCancel")}
          className="text-text-tertiary hover:text-status-error transition-colors flex-shrink-0"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}

export function ForgeJobs({
  jobs,
  client,
}: {
  jobs: ComputeJob[];
  client: ComputeAgentClient | null;
}) {
  const t = useTranslations("atlas");
  // Track ids we have asked to cancel so the button hides immediately (the
  // next poll reflects the engine's terminal state).
  const [cancelling, setCancelling] = useState<Set<string>>(new Set());

  const onCancel = client
    ? (id: string) => {
        setCancelling((prev) => new Set(prev).add(id));
        void client.cancelJob(id);
      }
    : null;

  if (jobs.length === 0) {
    return (
      <div className="text-[11px] text-text-tertiary text-center py-8">
        {t("forgeNoJobs")}
      </div>
    );
  }

  return (
    <div className="space-y-1.5 p-1">
      {jobs.map((job) => (
        <JobRow
          key={job.id}
          job={job}
          onCancel={cancelling.has(job.id) ? null : onCancel}
        />
      ))}
    </div>
  );
}
