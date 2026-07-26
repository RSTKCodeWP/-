/**
 * Tests for the cockpit keybindings slice: the default loadout shape, the
 * one-slot-per-Skill / one-slot-per-chord / one-slot-per-button conflict
 * invariants (last-write-wins), loadout CRUD, and the permanence of the
 * default loadout.
 *
 * @license GPL-3.0-only
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

// The persist middleware writes through idb-keyval; mock it so the store can
// hydrate/persist without a real IndexedDB in the test environment.
vi.mock("idb-keyval", () => {
  const store = new Map<string, unknown>();
  return {
    get: vi.fn(async (key: string) => store.get(key)),
    set: vi.fn(async (key: string, value: unknown) => {
      store.set(key, value);
    }),
    del: vi.fn(async (key: string) => {
      store.delete(key);
    }),
    clear: vi.fn(async () => {
      store.clear();
    }),
    keys: vi.fn(async () => Array.from(store.keys())),
    entries: vi.fn(async () => Array.from(store.entries())),
  };
});

import { useSettingsStore } from "@/stores/settings-store";
import {
  cloneDefaultLoadout,
  DEFAULT_LOADOUT_ID,
} from "@/stores/settings/keybindings-slice";

function resetLoadouts(): void {
  useSettingsStore.setState({
    loadouts: { [DEFAULT_LOADOUT_ID]: cloneDefaultLoadout() },
    activeLoadoutId: DEFAULT_LOADOUT_ID,
  });
}

describe("keybindings slice", () => {
  beforeEach(() => resetLoadouts());

  it("ships a default loadout with arm bound to slot 0", () => {
    const loadout = useSettingsStore.getState().loadouts[DEFAULT_LOADOUT_ID];
    const slot0 = loadout.slots.find((s) => s.index === 0);
    expect(slot0?.skillId).toBe("arm");
    expect(slot0?.key).toBe("shift+a");
    // Kill is slotted but deliberately unbound.
    const kill = loadout.slots.find((s) => s.skillId === "kill");
    expect(kill?.key).toBe(null);
  });

  it("a Skill lives in exactly one slot (last-write-wins)", () => {
    const { bindSkillToSlot } = useSettingsStore.getState();
    // "land" starts in slot 2; bind it to slot 5 -> slot 2 must clear.
    bindSkillToSlot(DEFAULT_LOADOUT_ID, 5, "land");
    const slots = useSettingsStore.getState().loadouts[DEFAULT_LOADOUT_ID].slots;
    expect(slots.find((s) => s.index === 5)?.skillId).toBe("land");
    expect(slots.find((s) => s.index === 2)?.skillId).toBe(null);
    // Exactly one slot now holds "land".
    expect(slots.filter((s) => s.skillId === "land")).toHaveLength(1);
  });

  it("a key chord lives in exactly one slot (last-write-wins)", () => {
    const { setSlotKey } = useSettingsStore.getState();
    // "shift+a" starts on slot 0; assign it to slot 9 -> slot 0 must clear.
    setSlotKey(DEFAULT_LOADOUT_ID, 9, "shift+a");
    const slots = useSettingsStore.getState().loadouts[DEFAULT_LOADOUT_ID].slots;
    expect(slots.find((s) => s.index === 9)?.key).toBe("shift+a");
    expect(slots.find((s) => s.index === 0)?.key).toBe(null);
    expect(slots.filter((s) => s.key === "shift+a")).toHaveLength(1);
  });

  it("a gamepad button lives in exactly one slot (last-write-wins)", () => {
    const { setSlotGamepadButton } = useSettingsStore.getState();
    // Button 0 starts on slot 0; assign it to slot 4 -> slot 0 must clear.
    setSlotGamepadButton(DEFAULT_LOADOUT_ID, 4, 0);
    const slots = useSettingsStore.getState().loadouts[DEFAULT_LOADOUT_ID].slots;
    expect(slots.find((s) => s.index === 4)?.gamepadButton).toBe(0);
    expect(slots.find((s) => s.index === 0)?.gamepadButton).toBe(null);
    expect(slots.filter((s) => s.gamepadButton === 0)).toHaveLength(1);
  });

  it("clearing a slot's skill (null) leaves other slots untouched", () => {
    const { bindSkillToSlot } = useSettingsStore.getState();
    bindSkillToSlot(DEFAULT_LOADOUT_ID, 0, null);
    const slots = useSettingsStore.getState().loadouts[DEFAULT_LOADOUT_ID].slots;
    expect(slots.find((s) => s.index === 0)?.skillId).toBe(null);
    // takeoff on slot 1 is unaffected.
    expect(slots.find((s) => s.index === 1)?.skillId).toBe("takeoff");
  });

  it("createLoadout clones the default and switches with setActiveLoadout", () => {
    const id = useSettingsStore.getState().createLoadout("Racer");
    expect(useSettingsStore.getState().loadouts[id]?.name).toBe("Racer");

    useSettingsStore.getState().setActiveLoadout(id);
    expect(useSettingsStore.getState().activeLoadoutId).toBe(id);

    // A non-existent loadout id is rejected.
    useSettingsStore.getState().setActiveLoadout("nope");
    expect(useSettingsStore.getState().activeLoadoutId).toBe(id);
  });

  it("createLoadout copies an explicit source loadout's slots", () => {
    const { setSlotKey, createLoadout } = useSettingsStore.getState();
    setSlotKey(DEFAULT_LOADOUT_ID, 0, "ctrl+a");
    const id = createLoadout("Copy", DEFAULT_LOADOUT_ID);
    const copied = useSettingsStore.getState().loadouts[id];
    expect(copied.slots.find((s) => s.index === 0)?.key).toBe("ctrl+a");
  });

  it("the default loadout is permanent and never deletable", () => {
    useSettingsStore.getState().deleteLoadout(DEFAULT_LOADOUT_ID);
    expect(useSettingsStore.getState().loadouts[DEFAULT_LOADOUT_ID]).toBeDefined();
  });

  it("deleting the active custom loadout falls back to the default", () => {
    const id = useSettingsStore.getState().createLoadout("Temp");
    useSettingsStore.getState().setActiveLoadout(id);
    useSettingsStore.getState().deleteLoadout(id);
    expect(useSettingsStore.getState().loadouts[id]).toBeUndefined();
    expect(useSettingsStore.getState().activeLoadoutId).toBe(DEFAULT_LOADOUT_ID);
  });

  it("renameLoadout updates the name in place", () => {
    const id = useSettingsStore.getState().createLoadout("Old");
    useSettingsStore.getState().renameLoadout(id, "New");
    expect(useSettingsStore.getState().loadouts[id]?.name).toBe("New");
  });

  it("resetLoadoutToDefaults restores the factory default slots", () => {
    useSettingsStore.getState().setSlotKey(DEFAULT_LOADOUT_ID, 0, "ctrl+z");
    useSettingsStore.getState().resetLoadoutToDefaults();
    const slot0 = useSettingsStore
      .getState()
      .loadouts[DEFAULT_LOADOUT_ID].slots.find((s) => s.index === 0);
    expect(slot0?.key).toBe("shift+a");
    expect(useSettingsStore.getState().activeLoadoutId).toBe(DEFAULT_LOADOUT_ID);
  });
});
