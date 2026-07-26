"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { Link2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { PluginInstallDialog } from "@/components/plugins/PluginInstallDialog";
import type {
  InstallManifestSummary,
  InstallSource,
  InstallTargetDrone,
} from "@/components/plugins/install-dialog/types";
import { resolveLanTarget } from "@/components/plugins/transports/resolve-lan-url";
import { agentSummaryToManifest } from "@/components/plugins/transports/agent-summary-to-manifest";
import { PluginAgentClient } from "@/lib/agent/plugin-client";
import { RegistryPluginGrid } from "@/components/dashboard/drone-plugins/RegistryPluginGrid";
import { communityApi } from "@/lib/community-api";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import { useAuthStore } from "@/stores/auth-store";
import { useLocalPluginInstallsStore } from "@/stores/local-plugin-installs-store";
import { useLocalNodesStore } from "@/stores/local-nodes-store";
import { usePairingStore } from "@/stores/pairing-store";
import { cn } from "@/lib/utils";

/** One row in the unified installed list (cloud + local-first merged). */
interface InstalledRow {
  /** Stable list key. */
  key: string;
  /** Convex install id when this came from the cloud (links to detail). */
  cloudId?: string;
  pluginId: string;
  name: string;
  version: string;
  status: string;
  /** Where it landed: a drone wire id, or null for a GCS-level install. */
  deviceId: string | null;
}

export default function PluginsIndexPage() {
  const t = useTranslations("plugins");
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const cloudInstalls = useConvexSkipQuery(communityApi.plugins.listMine, {
    enabled: isAuthenticated,
  });
  const localInstalls = useLocalPluginInstallsStore((s) => s.installs);

  // Install is PER-DRONE (the normal path): the operator picks which drone
  // to install on, sourced from both cloud-paired drones and LAN-paired
  // nodes (Rule 39 local-first), deduped by wire id. A no-drone target is
  // the edge case — only a GCS-only plugin can install with no drone.
  const pairedDrones = usePairingStore((s) => s.pairedDrones);
  const selectedPairedId = usePairingStore((s) => s.selectedPairedId);
  const localNodes = useLocalNodesStore((s) => s.nodes);
  const targets = useMemo<InstallTargetDrone[]>(() => {
    const byDevice = new Map<string, InstallTargetDrone>();
    for (const d of pairedDrones) {
      byDevice.set(d.deviceId, {
        _id: d._id,
        deviceId: d.deviceId,
        name: d.name,
      });
    }
    for (const n of localNodes) {
      if (byDevice.has(n.deviceId)) continue;
      byDevice.set(n.deviceId, {
        _id: n.deviceId,
        deviceId: n.deviceId,
        name: n.name,
      });
    }
    return Array.from(byDevice.values());
  }, [pairedDrones, localNodes]);

  const [chosenDeviceId, setChosenDeviceId] = useState<string | null>(null);
  // Resolve the active target: the operator's pick, else the
  // cloud-selected drone, else the first known target, else none.
  const target = useMemo<InstallTargetDrone | null>(() => {
    if (targets.length === 0) return null;
    return (
      targets.find((t) => t.deviceId === chosenDeviceId) ??
      targets.find((t) => t._id === selectedPairedId) ??
      targets[0]
    );
  }, [targets, chosenDeviceId, selectedPairedId]);

  const [installOpen, setInstallOpen] = useState(false);
  const [urlOpen, setUrlOpen] = useState(false);
  const [urlValue, setUrlValue] = useState("");
  const [urlSubmitting, setUrlSubmitting] = useState(false);
  // Prefill for the install dialog when the source is an operator-supplied URL:
  // the agent parses the archive (the browser cannot fetch an arbitrary URL),
  // and the dialog reviews permissions before consent like a dropped file.
  const [urlPrefill, setUrlPrefill] = useState<{
    manifest: InstallManifestSummary;
    source: InstallSource;
  } | null>(null);
  // URL install needs a direct http call to the agent (the agent fetches the
  // archive). A browser on an https origin (the hosted GCS, cloud mode) can't
  // reach the agent's http endpoint — mixed-content — so the path is only
  // available on the desktop app or a GCS served on the drone's network.
  // Tracked in state (not a render-time const) to avoid a hydration mismatch.
  const [isHttpsOrigin, setIsHttpsOrigin] = useState(false);
  useEffect(() => {
    setIsHttpsOrigin(window.location.protocol === "https:");
  }, []);
  const { toast } = useToast();

  // Merge cloud + local-first installs into one list. Cloud rows win on a
  // collision (they carry status + risk); a local-only install renders with
  // a neutral pill so a signed-out operator still sees what they installed.
  const installs = useMemo<InstalledRow[] | undefined>(() => {
    // Still loading the cloud list (signed in, query pending).
    if (isAuthenticated && cloudInstalls === undefined) return undefined;
    const byKey = new Map<string, InstalledRow>();
    const keyOf = (deviceId: string | null, pluginId: string) =>
      `${deviceId ?? "fleet"}::${pluginId}`;
    for (const i of localInstalls) {
      const key = keyOf(i.deviceId, i.pluginId);
      byKey.set(key, {
        key,
        pluginId: i.pluginId,
        name: i.name,
        version: i.version,
        status: "installed",
        deviceId: i.deviceId,
      });
    }
    for (const c of cloudInstalls ?? []) {
      const deviceId = c.droneId ?? null;
      const key = keyOf(deviceId, c.pluginId);
      byKey.set(key, {
        key,
        cloudId: c._id,
        pluginId: c.pluginId,
        name: c.name,
        version: c.version,
        status: c.status,
        deviceId,
      });
    }
    return Array.from(byKey.values()).sort((a, b) =>
      a.name.localeCompare(b.name),
    );
  }, [isAuthenticated, cloudInstalls, localInstalls]);

  const openInstall = () => {
    setUrlPrefill(null);
    setInstallOpen(true);
  };

  // Install from a pasted URL: the agent (on the LAN-paired drone) fetches +
  // signature-checks the archive and returns the manifest summary, then the
  // standard install dialog reviews permissions before installing (Rule 39).
  const handleUrlInstall = async () => {
    const trimmed = urlValue.trim();
    if (!trimmed) return;
    if (!target) {
      toast(t("urlNeedsDrone"), "warning");
      return;
    }
    const lan = resolveLanTarget(target.deviceId);
    if (!lan) {
      toast(
        isHttpsOrigin ? t("urlHttpsNeedsDesktop") : t("urlNotReachableLan"),
        "warning",
      );
      return;
    }
    setUrlSubmitting(true);
    try {
      const client = new PluginAgentClient(lan.url, lan.apiKey);
      const summary = await client.parseFromUrl(trimmed);
      setUrlPrefill({
        manifest: agentSummaryToManifest(summary),
        source: {
          kind: "registry",
          url: trimmed,
          // Pin the install to the exact bytes the agent fetched + we reviewed
          // (TOCTOU-safe; the install endpoint also requires a pin on this path).
          expectedSha256: summary.archive_sha256 ?? "",
          pluginId: summary.plugin_id,
          version: summary.version,
        },
      });
      setUrlOpen(false);
      setUrlValue("");
      setInstallOpen(true);
    } catch (err) {
      toast(
        err instanceof Error ? err.message : t("urlParseFailed"),
        "warning",
      );
    } finally {
      setUrlSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">
            {t("pageTitle")}
          </h1>
          <p className="max-w-2xl text-xs text-text-tertiary">
            {t("pageBlurb")}
          </p>
        </div>
        <div className="flex items-end gap-2">
          {targets.length > 0 && (
            <div className="w-52">
              <Select
                label={t("installOn")}
                value={target?.deviceId ?? ""}
                onChange={(v) => setChosenDeviceId(v)}
                options={targets.map((t) => ({
                  value: t.deviceId,
                  label: t.name,
                }))}
              />
            </div>
          )}
          <Button
            variant="secondary"
            icon={<Link2 className="h-4 w-4" />}
            onClick={() => setUrlOpen(true)}
            disabled={isHttpsOrigin}
            title={isHttpsOrigin ? t("installFromUrlHttpsHint") : undefined}
          >
            {t("installFromUrl")}
          </Button>
          <Button icon={<Plus className="h-4 w-4" />} onClick={openInstall}>
            {t("installPlugin")}
          </Button>
        </div>
      </header>

      {targets.length === 0 && (
        <p className="rounded-md border border-dashed border-border-default bg-bg-secondary px-3 py-2 text-xs text-text-tertiary">
          {t("noDronesPaired")}
        </p>
      )}

      {installs === undefined ? (
        <p className="py-12 text-center text-sm text-text-tertiary">
          {t("loadingInstalls")}
        </p>
      ) : installs.length === 0 ? (
        <EmptyState onInstall={openInstall} />
      ) : (
        <ul className="divide-y divide-border-default rounded-md border border-border-default bg-bg-secondary">
          {installs.map((install) => (
            <li key={install.key}>
              <InstalledItem install={install} />
            </li>
          ))}
        </ul>
      )}

      {/* Discover + install from the published registry, targeting the
          chosen drone (or null for a GCS-only install when none paired). */}
      <RegistryPluginGrid target={target} />

      <PluginInstallDialog
        open={installOpen}
        onClose={() => {
          setInstallOpen(false);
          setUrlPrefill(null);
        }}
        targetDevice={target}
        initialManifest={urlPrefill?.manifest}
        initialSource={urlPrefill?.source}
      />

      <Modal
        open={urlOpen}
        onClose={() => {
          if (!urlSubmitting) {
            setUrlOpen(false);
            setUrlValue("");
          }
        }}
        title={t("installFromUrl")}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setUrlOpen(false);
                setUrlValue("");
              }}
              disabled={urlSubmitting}
            >
              {t("cancel")}
            </Button>
            <Button
              onClick={handleUrlInstall}
              disabled={urlSubmitting || !urlValue.trim()}
            >
              {urlSubmitting ? t("fetching") : t("install")}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-xs text-text-tertiary">{t("urlModalBlurb")}</p>
          <Input
            label={t("pluginUrlLabel")}
            placeholder="https://example.com/com.example.thermal-1.0.0.adosplug"
            value={urlValue}
            onChange={(e) => setUrlValue(e.target.value)}
            autoFocus
          />
        </div>
      </Modal>
    </div>
  );
}

function InstalledItem({ install }: { install: InstalledRow }) {
  const t = useTranslations("plugins");
  const scopeLabel = install.deviceId ? t("scopeDrone") : t("scopeGcs");
  const body = (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-text-primary">
            {install.name}
          </span>
          <span className="text-xs text-text-tertiary">v{install.version}</span>
        </div>
        <code className="block truncate text-xs text-text-tertiary">
          {install.pluginId}
        </code>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <span className="rounded-md border border-border-default bg-bg-tertiary px-2 py-0.5 text-[10px] uppercase tracking-wide text-text-tertiary">
          {scopeLabel}
        </span>
        <StatusPill status={install.status} />
      </div>
    </div>
  );
  // Cloud rows link to their detail page; a local-only row has no detail
  // route yet, so it renders inert (still visible in the list).
  return install.cloudId ? (
    <Link
      href={`/config/plugins/${install.cloudId}`}
      className="block transition-colors hover:bg-bg-tertiary"
    >
      {body}
    </Link>
  ) : (
    body
  );
}

function EmptyState({ onInstall }: { onInstall: () => void }) {
  const t = useTranslations("plugins");
  return (
    <div className="rounded-md border border-dashed border-border-default p-8 text-center">
      <p className="text-sm text-text-primary">{t("emptyTitle")}</p>
      <p className="mt-1 text-xs text-text-tertiary">{t("emptyBlurb")}</p>
      <Button
        variant="secondary"
        className="mt-4"
        icon={<Plus className="h-4 w-4" />}
        onClick={onInstall}
      >
        {t("installFirst")}
      </Button>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const palette: Record<string, string> = {
    installed: "border-text-secondary/30 bg-bg-tertiary text-text-tertiary",
    enabled: "border-accent-primary/40 bg-accent-primary/10 text-accent-primary",
    running:
      "border-status-success/40 bg-status-success/10 text-status-success",
    disabled: "border-text-secondary/30 bg-bg-tertiary text-text-tertiary",
    crashed: "border-status-error/40 bg-status-error/10 text-status-error",
    removed: "border-text-secondary/30 bg-bg-tertiary text-text-tertiary",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize",
        palette[status] ?? palette.disabled,
      )}
    >
      {status}
    </span>
  );
}
