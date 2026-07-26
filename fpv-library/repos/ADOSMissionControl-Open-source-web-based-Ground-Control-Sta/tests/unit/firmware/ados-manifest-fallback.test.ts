/**
 * Parity check between the ADOS Agent firmware emitter and the embedded
 * fallback baked into the Next.js proxy route. The emitter (in the agent
 * repo) produces the canonical catalog from src/ados/hal/boards/*.yaml.
 * The Mission Control proxy carries an embedded fallback so the Flash
 * Tool stays usable when the GitHub release is unreachable.
 *
 * The fallback must be a SUBSET of the emitted catalog: every board the
 * fallback advertises must also appear upstream so that, when the
 * release manifest finally lands, no fallback-only stubs are silently
 * shadowed.
 *
 * The fixture at tests/fixtures/ados-agent-manifest.fixture.json carries
 * the snapshot of board ids the emitter currently produces. Update it by
 * hand when the agent repo's HAL board set changes. The fixture's
 * leading "_comment" field documents the procedure.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import fixture from "../../fixtures/ados-agent-manifest.fixture.json";
import { EMBEDDED_FALLBACK } from "@/app/api/ados-manifest/fallback";

describe("ADOS manifest embedded-fallback parity", () => {
  it("the fixture has at least one board id (sanity check)", () => {
    expect(fixture.boardIds.length).toBeGreaterThan(0);
  });

  it("every embedded-fallback board id appears in the upstream emitter snapshot", () => {
    const upstream = new Set<string>(fixture.boardIds);
    const missing = EMBEDDED_FALLBACK.boards
      .map((b) => b.id)
      .filter((id) => !upstream.has(id));
    expect(missing).toEqual([]);
  });

  it("embedded fallback only declares known stacks", () => {
    const allowed = new Set(["ados-drone-agent", "ados-ground-agent"]);
    for (const board of EMBEDDED_FALLBACK.boards) {
      for (const stack of board.stacks) {
        expect(allowed.has(stack)).toBe(true);
      }
    }
  });

  it("embedded fallback boards declare an install for every advertised stack", () => {
    for (const board of EMBEDDED_FALLBACK.boards) {
      for (const stack of board.stacks) {
        expect(board.installs[stack]).toBeDefined();
      }
    }
  });
});
