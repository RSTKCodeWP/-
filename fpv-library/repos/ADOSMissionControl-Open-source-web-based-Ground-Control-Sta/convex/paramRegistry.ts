/**
 * First-party parameter-metadata registry.
 *
 * Stores version-matched firmware metadata snapshots (gzipped + base64) and
 * serves the best match for a connected FC's version. Public read (generic
 * technical reference data); admin (internal) write, seeded by the maintainer
 * generator. The GCS overlays this on top of its bundled offline floor.
 */

import { query, internalMutation } from "./_generated/server";
import { v } from "convex/values";

function parseVer(s: string): { major: number; minor: number } | null {
  const m = String(s).match(/(\d+)\.(\d+)/);
  return m ? { major: Number(m[1]), minor: Number(m[2]) } : null;
}
const rank = (v: { major: number; minor: number }) => v.major * 10000 + v.minor;

/**
 * Best snapshot for a firmware + (optional) version: the highest snapshot
 * whose version is ≤ the requested version; else the lowest available
 * versioned snapshot; else the "latest" row. Returns null when none exist.
 */
export const getSnapshot = query({
  args: { firmware: v.string(), version: v.optional(v.string()) },
  handler: async (ctx, { firmware, version }) => {
    const rows = await ctx.db
      .query("param_registry")
      .withIndex("by_firmware", (q) => q.eq("firmware", firmware))
      .collect();
    if (rows.length === 0) return null;

    let chosen = null as (typeof rows)[number] | null;
    const want = version ? parseVer(version) : null;
    if (want) {
      const versioned = rows
        .map((r) => ({ r, v: parseVer(r.version) }))
        .filter((x): x is { r: (typeof rows)[number]; v: { major: number; minor: number } } => x.v !== null);
      if (versioned.length) {
        const le = versioned
          .filter((x) => rank(x.v) <= rank(want))
          .sort((a, b) => rank(b.v) - rank(a.v));
        chosen = le.length
          ? le[0].r
          : versioned.sort((a, b) => rank(a.v) - rank(b.v))[0].r;
      }
    }
    if (!chosen) chosen = rows.find((r) => r.version === "latest") ?? rows[0];

    return { version: chosen.version, paramCount: chosen.param_count, gzB64: chosen.gz_b64 };
  },
});

/** Upsert a snapshot (maintainer-seeded). Internal — never client-callable. */
export const upsertSnapshot = internalMutation({
  args: {
    firmware: v.string(),
    version: v.string(),
    paramCount: v.number(),
    gzB64: v.string(),
  },
  handler: async (ctx, { firmware, version, paramCount, gzB64 }) => {
    const existing = await ctx.db
      .query("param_registry")
      .withIndex("by_firmware_version", (q) => q.eq("firmware", firmware).eq("version", version))
      .unique();
    const doc = { firmware, version, param_count: paramCount, gz_b64: gzB64, updated_at: Date.now() };
    if (existing) await ctx.db.patch(existing._id, doc);
    else await ctx.db.insert("param_registry", doc);
    return { firmware, version, paramCount };
  },
});
