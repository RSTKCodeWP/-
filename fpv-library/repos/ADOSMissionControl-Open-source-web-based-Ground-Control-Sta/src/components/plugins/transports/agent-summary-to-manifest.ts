/**
 * @module transports/agent-summary-to-manifest
 * @description Map the agent's parse summary (from `POST /api/plugins/
 * parse_from_url`) to the install dialog's manifest shape, so an
 * operator-supplied URL gets the same permission-review surface as a dropped
 * file. The browser cannot fetch + parse an arbitrary URL itself (CORS /
 * mixed-content), so the agent fetches + signature-checks the archive and
 * returns this summary; this mirrors the file-parse trust-signal derivation.
 * @license GPL-3.0-only
 */

import type { PluginAgentParseSummary } from "@/lib/agent/plugin-client";
import type { InstallManifestSummary } from "../install-dialog/types";
import { displayTrustSignals } from "@/lib/plugins/trust-signals";
import { getMergedCapabilityMeta } from "@/lib/plugins/capabilities";

export function agentSummaryToManifest(
  s: PluginAgentParseSummary,
): InstallManifestSummary {
  const trustSignals = displayTrustSignals({
    signerId: s.signer_id ?? undefined,
    license: s.license || undefined,
  });
  return {
    pluginId: s.plugin_id,
    version: s.version,
    name: s.name,
    description: s.description || undefined,
    author: s.author || undefined,
    license: s.license || undefined,
    halves: [...s.halves],
    signerId: s.signer_id ?? undefined,
    trustSignals,
    icon: s.icon ?? undefined,
    archiveSha256: s.archive_sha256,
    // Resolve each permission id through the merged catalog so the review
    // surface shows a plain-language label + category + risk, the same way the
    // file-parse path does — instead of a bare id under "Other".
    permissions: s.permissions.map((p) => {
      const meta = getMergedCapabilityMeta(p.id);
      const unknown =
        (meta as { unknown?: boolean }).unknown === true ? true : undefined;
      return {
        id: p.id,
        required: p.required,
        label: unknown ? undefined : meta.label,
        description: unknown ? undefined : meta.description,
        category: unknown ? undefined : meta.category,
        risk: unknown ? undefined : meta.risk,
        risk_reason: unknown ? undefined : meta.risk_reason,
        unknown,
      };
    }),
  };
}
