/**
 * Marketing label derived from the app version - single source of truth is the
 * package.json version, so the "Beta" label never has to be maintained by hand.
 *
 * While we're on 0.x we're in beta, and the semver doubles as the beta number:
 *   0.<minor>.<patch>  ->  "Beta <minor>[.<patch>]"   (patch dropped when 0)
 * At 1.0.0 we've graduated, so show the plain version (trailing .0 patch trimmed).
 */
export function betaLabel(version: string): string {
  const core = version.split('-')[0] ?? version; // strip any -prerelease suffix
  const parts = core.split('.');
  const major = Number(parts[0]);
  const minor = Number(parts[1] ?? '0');
  const patch = Number(parts[2] ?? '0');
  if (!Number.isFinite(major) || !Number.isFinite(minor) || !Number.isFinite(patch)) {
    return version; // unparseable - show as-is
  }
  if (major === 0) {
    return patch > 0 ? `Beta ${minor}.${patch}` : `Beta ${minor}`;
  }
  return patch > 0 ? `${major}.${minor}.${patch}` : `${major}.${minor}`;
}
