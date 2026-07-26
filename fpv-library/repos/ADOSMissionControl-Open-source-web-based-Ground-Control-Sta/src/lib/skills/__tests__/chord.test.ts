import { describe, expect, it } from "vitest";

import { canonicalChord, isReservedChord } from "@/lib/skills/chord";

describe("chord digits — the stream-switcher hotkeys", () => {
  it("canonicalizes a bare digit row key to '1'..'9'", () => {
    for (let d = 1; d <= 9; d++) {
      const e = new KeyboardEvent("keydown", { code: `Digit${d}`, key: String(d) });
      expect(canonicalChord(e)).toBe(String(d));
    }
  });

  it("canonicalizes numpad digits the same way", () => {
    const e = new KeyboardEvent("keydown", { code: "Numpad5", key: "5" });
    expect(canonicalChord(e)).toBe("5");
  });

  it("reserves bare digits 1..9 so no skill can bind them", () => {
    for (let d = 1; d <= 9; d++) {
      expect(isReservedChord(String(d))).toBe(true);
    }
  });

  it("leaves modified digits and 0 bindable (only bare 1..9 are the switcher)", () => {
    expect(isReservedChord("ctrl+1")).toBe(false);
    expect(isReservedChord("shift+2")).toBe(false);
    expect(isReservedChord("0")).toBe(false);
  });
});

describe("chord backtick + p — the cockpit stream-cycle + PiP hotkeys", () => {
  it("canonicalizes a bare Backquote to '`' and KeyP to 'p'", () => {
    expect(
      canonicalChord({ code: "Backquote", key: "`" } as KeyboardEvent),
    ).toBe("`");
    expect(canonicalChord({ code: "KeyP", key: "p" } as KeyboardEvent)).toBe(
      "p",
    );
  });

  it("reserves bare backtick and bare p so no skill can bind them", () => {
    expect(isReservedChord("`")).toBe(true);
    expect(isReservedChord("p")).toBe(true);
  });

  it("leaves modified backtick / p bindable (only the bare keys are owned)", () => {
    expect(isReservedChord("shift+p")).toBe(false);
    expect(isReservedChord("ctrl+p")).toBe(false);
    expect(isReservedChord("ctrl+`")).toBe(false);
  });
});
