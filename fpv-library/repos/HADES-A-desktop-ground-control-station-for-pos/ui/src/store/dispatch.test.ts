import { describe, expect, it } from "vitest";

import { nextClearance, primaryVerb, prevClearance } from "./dispatch";

/* The clearance state machine (design doc "core loop"): one-click transitions, REVERSIBLE
 * (life-safety undo). One primary verb per state. NEW → ASSIGNED → EN_ROUTE → FOUND, with
 * SEARCHED_NEGATIVE as the other terminal. */

describe("clearance transitions", () => {
  it("advances along the dispatch chain", () => {
    expect(nextClearance("NEW")).toBe("ASSIGNED");
    expect(nextClearance("ASSIGNED")).toBe("EN_ROUTE");
    expect(nextClearance("EN_ROUTE")).toBe("FOUND");
  });

  it("a terminal state does not auto-advance", () => {
    expect(nextClearance("FOUND")).toBe("FOUND");
    expect(nextClearance("SEARCHED_NEGATIVE")).toBe("SEARCHED_NEGATIVE");
  });

  it("is REVERSIBLE — every forward step can be undone (life-safety undo)", () => {
    expect(prevClearance("ASSIGNED")).toBe("NEW");
    expect(prevClearance("EN_ROUTE")).toBe("ASSIGNED");
    expect(prevClearance("FOUND")).toBe("EN_ROUTE");
  });

  it("undo from NEW stays at NEW (nothing before it)", () => {
    expect(prevClearance("NEW")).toBe("NEW");
  });
});

describe("primaryVerb", () => {
  it("gives ONE primary action verb per state (canonical command panel)", () => {
    expect(primaryVerb("NEW")).toMatch(/dispatch/i);
    expect(primaryVerb("ASSIGNED")).toMatch(/en.?route|moving|underway/i);
    expect(primaryVerb("EN_ROUTE")).toMatch(/found|mark/i);
    expect(primaryVerb("FOUND")).toMatch(/reopen|clear/i);
  });
});
