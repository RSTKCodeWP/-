/**
 * Drag payloads for the Skill Bar editor's native HTML5 drag-and-drop. Two drag
 * sources share one custom dataTransfer type: a drawer skill (bind into the
 * dropped slot) and a bound slot (swap with the dropped slot, or clear when
 * dropped off the bar). The payload is JSON so the drop handler can branch.
 *
 * @module fly/skill-drag
 * @license GPL-3.0-only
 */

/** Custom dataTransfer type so the editor only reacts to its own drags. */
export const SKILL_DRAG_TYPE = "application/x-ados-skill";

export type SkillDragPayload =
  | { kind: "skill"; skillId: string }
  | { kind: "slot"; index: number };

/** Serialize a drag payload for dataTransfer.setData. */
export function packSkillDrag(payload: SkillDragPayload): string {
  return JSON.stringify(payload);
}

/** Parse a drag payload, or null when the data is absent/malformed. */
export function unpackSkillDrag(raw: string): SkillDragPayload | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as SkillDragPayload;
    if (parsed.kind === "skill" && typeof parsed.skillId === "string") {
      return parsed;
    }
    if (parsed.kind === "slot" && typeof parsed.index === "number") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}
