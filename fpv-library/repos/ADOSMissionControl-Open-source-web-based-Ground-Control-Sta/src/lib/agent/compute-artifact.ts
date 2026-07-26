/**
 * @module ComputeArtifact
 * @description Rewrite a compute-node reconstruction artifact URL to reach the
 * node through Mission Control's same-origin artifact proxy.
 *
 * The engine stamps each artifact's `uri`/`result_ref` with a host derived from
 * its own OS hostname (an mDNS `.local` name that the browser cannot resolve,
 * and that drifts between runs). The stored PATH under `/artifacts/` is stable,
 * so we keep the path and route it through `/api/lan-pair/artifact` at the host
 * the operator actually paired with — the Next server resolves `.local`→IPv4
 * server-side and streams the blob back over the same origin (no mixed-content,
 * no `.local` resolution in the browser). Rule 39 local-first.
 *
 * @license GPL-3.0-only
 */

/** Pull the stable `artifacts/<relpath>` segment out of a stored artifact URL,
 * ignoring the engine's (drifting, unresolvable) host. */
export function artifactRelPath(rawUri: string): string | null {
  const fromPath = (p: string): string | null => {
    const i = p.indexOf("artifacts/");
    return i >= 0 ? p.slice(i) : null;
  };
  try {
    const u = new URL(rawUri);
    return fromPath(u.pathname.replace(/^\/+/, ""));
  } catch {
    // Not an absolute URL — treat the input as a bare path.
    return fromPath(rawUri.replace(/^\/+/, ""));
  }
}

/** Rewrite a raw engine artifact URL to the same-origin proxy at the paired
 * host. Returns the raw URL unchanged when no paired host is known (nothing to
 * resolve against) or the URL carries no `artifacts/` path. */
export function proxiedArtifactUrl(
  rawUri: string,
  pairedHost: string | null | undefined,
  apiKey?: string | null,
): string {
  const host = (pairedHost ?? "").trim();
  const rel = artifactRelPath(rawUri);
  if (!host || !rel) return rawUri;
  const params = new URLSearchParams({ host, path: rel });
  if (apiKey) params.set("key", apiKey);
  return `/api/lan-pair/artifact?${params.toString()}`;
}
