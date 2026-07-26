import { describe, expect, it } from "vitest";

import { circleStrokeColorExpr, pinColorExpr, pinRadiusExpr } from "./layers";

/* Paint expressions for the bespoke map layers (DESIGN-SYSTEM §5.1). Built as MapLibre
 * data-driven expressions keyed off the GeoJSON `status` / `selected` properties so the pin
 * and its ring share one encoding, and the selected pin reads larger. Pure + testable. */

describe("pinColorExpr", () => {
  it("is a match expression over the status property covering all statuses", () => {
    const expr = pinColorExpr() as unknown[];
    expect(expr[0]).toBe("match");
    expect(expr[1]).toEqual(["get", "status"]);
    const flat = JSON.stringify(expr);
    for (const hex of ["warning", "caution", "info", "stale", "nominal"]) {
      // each status name must appear as a match key
      expect(flat).toContain(hex);
    }
  });

  it("maps warning (survivor world-urgency) to the hazard-orange hex", () => {
    const flat = JSON.stringify(pinColorExpr());
    expect(flat.toLowerCase()).toContain("#e8531f");
  });
});

describe("pinRadiusExpr", () => {
  it("draws the selected pin larger than an unselected one", () => {
    const expr = pinRadiusExpr() as unknown[];
    expect(expr[0]).toBe("case");
    // ['case', ['get','selected'], <selectedR>, <defaultR>]
    const selectedR = expr[2] as number;
    const defaultR = expr[3] as number;
    expect(selectedR).toBeGreaterThan(defaultR);
  });
});

describe("circleStrokeColorExpr", () => {
  it("tints the uncertainty ring by the same status as its pin", () => {
    const expr = circleStrokeColorExpr() as unknown[];
    expect(expr[0]).toBe("match");
    expect(expr[1]).toEqual(["get", "status"]);
  });
});
