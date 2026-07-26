"use client";

/**
 * @module ForgeOutputs
 * @description Outputs sub-view of the Atlas Forge workbench: pick a finished
 * job and preview its reconstructed artifact in the selectable World Model
 * viewer (Rerun / Splat / Cloud). Fetches the job's outputs on demand from the
 * compute node; renders a calm empty state when a job has no artifact yet.
 * @license GPL-3.0-only
 */

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Boxes } from "lucide-react";
import type {
  ComputeAgentClient,
  ComputeJob,
  ComputeOutput,
} from "@/lib/agent/compute-client";
import { Select, type SelectOption } from "@/components/ui/select";
import {
  pickArtifactForViewer,
  viewerForKind,
  type AtlasViewer,
} from "@/components/atlas/viewer-types";
import { WorldModelViewport } from "@/components/atlas/WorldModelViewport";
import { ViewerSwitcher } from "@/components/atlas/ViewerSwitcher";

export function ForgeOutputs({
  jobs,
  client,
}: {
  jobs: ComputeJob[];
  client: ComputeAgentClient | null;
}) {
  const t = useTranslations("atlas");
  // Only finished jobs produce artifacts to preview, newest first (the engine
  // returns them oldest-first, so an unsorted default would show a stale job).
  const finished = useMemo(
    () =>
      jobs
        .filter((j) => j.state === "completed")
        .sort((a, b) => (b.createdMs ?? 0) - (a.createdMs ?? 0)),
    [jobs],
  );
  const [selectedJobId, setSelectedJobId] = useState<string>("");
  // Outputs are keyed to the job they belong to so a switch never shows the
  // previous job's artifact while the new fetch is in flight.
  const [outputState, setOutputState] = useState<{
    jobId: string;
    outputs: ComputeOutput[];
  }>({ jobId: "", outputs: [] });
  // A manual viewer choice, keyed to the job it was made for. When the job
  // changes the override drops and the viewer follows the artifact's kind.
  const [override, setOverride] = useState<{
    jobId: string;
    viewer: AtlasViewer;
  } | null>(null);

  // Default the selection to the latest finished job when none is chosen.
  const effectiveJobId =
    finished.find((j) => j.id === selectedJobId)?.id ?? finished[0]?.id ?? "";

  useEffect(() => {
    if (!client || !effectiveJobId) return;
    let cancelled = false;
    void client.getOutputs(effectiveJobId).then((res) => {
      if (!cancelled) setOutputState({ jobId: effectiveJobId, outputs: res ?? [] });
    });
    return () => {
      cancelled = true;
    };
  }, [client, effectiveJobId]);

  const outputs =
    outputState.jobId === effectiveJobId ? outputState.outputs : [];
  const primary = outputs[0] ?? null;
  // Manual override (for this job) wins; otherwise default from the primary
  // artifact's kind.
  const viewer =
    override && override.jobId === effectiveJobId
      ? override.viewer
      : viewerForKind(primary?.kind ?? "");
  // Each viewer consumes the artifact matching ITS kind (World→`.rrd`,
  // Splat→splat `.ply`, Cloud/LOD/Geo→point-cloud `.ply`). A job can emit both
  // a splat and a point-cloud `.ply`, so "first non-rerun" would feed a plain
  // point cloud to the splat renderer (→ black) or the splat to Rerun.
  const artifact = pickArtifactForViewer(outputs, viewer) ?? primary;

  if (finished.length === 0) {
    return (
      <div className="text-[11px] text-text-tertiary text-center py-8">
        {t("forgeNoOutputs")}
      </div>
    );
  }

  const jobOptions: SelectOption[] = finished.map((j) => ({
    value: j.id,
    label: `${j.kind} · ${j.id}`,
  }));

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 p-2 border-b border-border-default">
        <Select
          options={jobOptions}
          value={effectiveJobId}
          onChange={setSelectedJobId}
          placeholder={t("forgeSelectJob")}
          className="w-56"
        />
        <ViewerSwitcher
          viewer={viewer}
          onSelect={(v) => setOverride({ jobId: effectiveJobId, viewer: v })}
          ariaLabel={t("forgeOutputs")}
        />
      </div>

      <div className="flex-1 relative min-h-[320px]">
        {artifact ? (
          <WorldModelViewport
            viewer={viewer}
            artifactUrl={artifact.uri}
            backend={artifact.backend}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="text-center">
              <Boxes className="w-5 h-5 text-text-tertiary mx-auto mb-2" />
              <p className="text-[11px] text-text-tertiary max-w-xs">
                {t("forgeNoOutputs")}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
