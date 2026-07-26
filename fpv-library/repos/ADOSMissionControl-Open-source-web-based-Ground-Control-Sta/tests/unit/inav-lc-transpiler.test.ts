/**
 * iNav JS-like -> Logic Conditions transpiler tests. Verifies the generated
 * LC slots (operation + operand type/value) against the firmware enums.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect } from "vitest";
import { compileToLogicConditions } from "@/lib/inav/lc-transpiler";

// firmware codes
const OP = { EQUAL: 1, GT: 2, LT: 3, AND: 7, OR: 8, NOT: 12, ADD: 14, MUL: 16, GVAR_SET: 18 };
const T = { VALUE: 0, RC: 1, LC: 4, GVAR: 5 };

function used(source: string) {
  const { conditions, error } = compileToLogicConditions(source);
  expect(error).toBeUndefined();
  return conditions.filter((c) => c.enabled);
}

describe("compileToLogicConditions", () => {
  it("compiles a conditional gvar assignment", () => {
    const c = used("gvar[0] = rc[6] > 1600");
    expect(c).toHaveLength(2);
    // LC0: rc[6] GREATER_THAN 1600
    expect(c[0]).toMatchObject({ operation: OP.GT, operandAType: T.RC, operandAValue: 6, operandBType: T.VALUE, operandBValue: 1600 });
    // LC1: GVAR_SET(gvar 0, LC0 result)
    expect(c[1]).toMatchObject({ operation: OP.GVAR_SET, operandAType: T.VALUE, operandAValue: 0, operandBType: T.LC, operandBValue: 0 });
  });

  it("honours arithmetic precedence (* before +)", () => {
    const c = used("gvar[1] = gvar[0] * 10 + 5");
    expect(c).toHaveLength(3);
    expect(c[0]).toMatchObject({ operation: OP.MUL, operandAType: T.GVAR, operandAValue: 0, operandBType: T.VALUE, operandBValue: 10 });
    expect(c[1]).toMatchObject({ operation: OP.ADD, operandAType: T.LC, operandAValue: 0, operandBType: T.VALUE, operandBValue: 5 });
    expect(c[2]).toMatchObject({ operation: OP.GVAR_SET, operandAValue: 1, operandBType: T.LC, operandBValue: 1 });
  });

  it("compiles a bare boolean expression (no assignment)", () => {
    const c = used("rc[5] > 1500 && gvar[2] < 20");
    expect(c).toHaveLength(3);
    expect(c[0]).toMatchObject({ operation: OP.GT, operandAType: T.RC, operandAValue: 5 });
    expect(c[1]).toMatchObject({ operation: OP.LT, operandAType: T.GVAR, operandAValue: 2, operandBValue: 20 });
    expect(c[2]).toMatchObject({ operation: OP.AND, operandAType: T.LC, operandAValue: 0, operandBType: T.LC, operandBValue: 1 });
  });

  it("composes >= as NOT(<)", () => {
    const c = used("gvar[0] = rc[5] >= 1500");
    expect(c).toHaveLength(3);
    expect(c[0]).toMatchObject({ operation: OP.LT, operandAType: T.RC, operandAValue: 5, operandBValue: 1500 });
    expect(c[1]).toMatchObject({ operation: OP.NOT, operandAType: T.LC, operandAValue: 0 });
    expect(c[2]).toMatchObject({ operation: OP.GVAR_SET, operandAValue: 0, operandBType: T.LC, operandBValue: 1 });
  });

  it("handles unary not and parentheses", () => {
    const c = used("gvar[0] = !(gvar[1] == 3)");
    expect(c[0]).toMatchObject({ operation: OP.EQUAL, operandAType: T.GVAR, operandAValue: 1, operandBValue: 3 });
    expect(c[1]).toMatchObject({ operation: OP.NOT, operandAType: T.LC, operandAValue: 0 });
    expect(c[2].operation).toBe(OP.GVAR_SET);
  });

  it("ignores blank lines and // comments", () => {
    const c = used("// set an aux flag\ngvar[0] = rc[6] > 1600\n\n");
    expect(c).toHaveLength(2);
  });

  it("pads to 64 slots so it maps cleanly onto the LC table", () => {
    const { conditions } = compileToLogicConditions("gvar[0] = rc[6] > 1600");
    expect(conditions).toHaveLength(64);
    expect(conditions[2].enabled).toBe(false);
  });

  it("reports a parse error without throwing", () => {
    const r = compileToLogicConditions("gvar[0] = rc[");
    expect(r.error).toBeTruthy();
    expect(r.conditions).toHaveLength(0);
  });

  it("errors when the program exceeds 64 logic conditions", () => {
    // deep nesting: 70 chained additions needs > 64 LCs
    let expr = "1";
    for (let i = 0; i < 70; i++) expr += " + 1";
    const r = compileToLogicConditions(`gvar[0] = ${expr}`);
    expect(r.error).toMatch(/64 logic conditions/);
  });
});
