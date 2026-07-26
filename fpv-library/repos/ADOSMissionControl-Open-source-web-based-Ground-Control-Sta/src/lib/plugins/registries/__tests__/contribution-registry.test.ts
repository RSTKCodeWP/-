/**
 * @license GPL-3.0-only
 */
import { describe, it, expect } from "vitest";

import { createContributionRegistry } from "../contribution-registry";

interface Item {
  id: string;
  order?: number;
  label?: string;
}

describe("createContributionRegistry", () => {
  it("registers, resolves ordered by order then insertion, and unregisters", () => {
    const useReg = createContributionRegistry<Item>();
    const { register } = useReg.getState();
    register({ id: "a", order: 2 });
    register({ id: "b", order: 1 });
    register({ id: "c" }); // unordered sorts last
    register({ id: "d", order: 1 });

    // order 1 bucket keeps insertion order (b before d), then order 2 (a),
    // then the unordered item (c) last.
    expect(useReg.getState().resolve().map((i) => i.id)).toEqual([
      "b",
      "d",
      "a",
      "c",
    ]);

    useReg.getState().unregister("a");
    expect(useReg.getState().resolve().map((i) => i.id)).toEqual(["b", "d", "c"]);
    expect(useReg.getState().items.has("a")).toBe(false);
  });

  it("applies a filter predicate", () => {
    const useReg = createContributionRegistry<Item>();
    useReg.getState().register({ id: "x", label: "keep" });
    useReg.getState().register({ id: "y", label: "drop" });
    const ids = useReg
      .getState()
      .resolve((i) => i.label === "keep")
      .map((i) => i.id);
    expect(ids).toEqual(["x"]);
  });

  it("re-registering preserves the original insertion slot and replaces the item", () => {
    const useReg = createContributionRegistry<Item>();
    useReg.getState().register({ id: "a" });
    useReg.getState().register({ id: "b" });
    useReg.getState().register({ id: "a", label: "updated" });
    const list = useReg.getState().resolve();
    expect(list.map((i) => i.id)).toEqual(["a", "b"]);
    expect(list.find((i) => i.id === "a")?.label).toBe("updated");
  });

  it("unregistering an unknown id is a no-op", () => {
    const useReg = createContributionRegistry<Item>();
    useReg.getState().register({ id: "a" });
    useReg.getState().unregister("missing");
    expect(useReg.getState().resolve().map((i) => i.id)).toEqual(["a"]);
  });
});
