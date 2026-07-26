/**
 * Path-validation helpers for the AP_Periph firmware-index proxy.
 *
 * Lives outside the Next.js route file so it can be imported by tests
 * and any other call site without violating the App Router rule that
 * route files only export HTTP-method handlers and route options.
 *
 * @license GPL-3.0-only
 */

const SEGMENT_RE = /^[A-Za-z0-9._-]+$/;

/**
 * Reject any input that contains characters outside the upstream's
 * directory-name vocabulary, any traversal segment, or any absolute
 * path. Returns the normalized path (without leading slash, with
 * trailing slash preserved if the caller asked for a directory) or
 * null if invalid. An empty string is allowed and maps to the root
 * index.
 */
export function sanitizePath(input: string): string | null {
  if (input === "") return "";

  const trailing = input.endsWith("/");
  const stripped = trailing ? input.slice(0, -1) : input;
  if (stripped.length === 0) return "";

  if (stripped.startsWith("/") || stripped.includes("://")) return null;

  const segments = stripped.split("/");
  if (segments.length > 3) return null;

  for (const segment of segments) {
    if (!SEGMENT_RE.test(segment)) return null;
    if (segment === "." || segment === "..") return null;
  }

  return trailing ? `${segments.join("/")}/` : segments.join("/");
}
