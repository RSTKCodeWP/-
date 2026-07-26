/**
 * Mission file migration.
 *
 * Legacy mission files (v1) have a flat `items: MissionItem[]` array and no
 * `groups` field. v2 introduces persistent groups; every WP belongs to one.
 *
 * Migration creates a single auto-named "Manual" group, assigns every WP to
 * it, and stamps `version: 2` on the result. Idempotent: a v2 file passes
 * through unchanged.
 *
 * Spec: docs/superpowers/specs/2026-05-28-mission-groups-design.md
 */

import type { MissionItem } from './mission-types';
import {
  MISSION_FILE_VERSION,
  type StoredMission,
  type SaveMissionPayload,
} from './mission-library-types';
import {
  createManualGroup,
  type Group,
  type ManualGroup,
} from './mission-group-types';

/**
 * Migrate a raw stored-mission blob (as read from disk) to the v2 shape.
 * Returns null if the blob is unrecognizable.
 */
export function migrateStoredMission(raw: unknown): StoredMission | null {
  if (!isRecord(raw)) return null;
  if (!Array.isArray(raw.items)) return null;

  // Identify v2 by the presence of a groups array. We don't trust the
  // `version` field alone since a hand-edited file might lie about it.
  if (Array.isArray(raw.groups) && raw.groups.length > 0) {
    // Already v2-shaped. Backfill version if missing, ensure every item has
    // a groupId (a hand-edited file might have added a WP without one).
    // `visible` replaced the old `includeInUpload` flag; map it forward and
    // default to shown so a pre-rename file doesn't load with hidden groups.
    const groups = (raw.groups as Array<Group & { includeInUpload?: boolean }>).map((g) => {
      if (typeof g.visible === 'boolean') return g;
      const { includeInUpload, ...rest } = g;
      return { ...rest, visible: includeInUpload ?? true } as Group;
    });
    const fallbackGroupId = pickFallbackGroupId(groups);
    const items = (raw.items as MissionItem[]).map((it) =>
      it.groupId ? it : { ...it, groupId: fallbackGroupId },
    );
    return {
      ...(raw as unknown as StoredMission),
      version: MISSION_FILE_VERSION,
      groups,
      items,
    };
  }

  // v1: wrap every item in a single Manual group.
  const { group, items } = wrapInDefaultGroup(raw.items as MissionItem[]);
  return {
    ...(raw as unknown as StoredMission),
    version: MISSION_FILE_VERSION,
    groups: [group],
    items,
  };
}

/**
 * Migrate a SaveMissionPayload from a legacy caller that did not supply
 * groups. Produces a v2 payload with a single Manual group and every item
 * assigned to it.
 */
export function migrateSavePayload(payload: SaveMissionPayload): SaveMissionPayload & {
  groups: Group[];
} {
  if (payload.groups && payload.groups.length > 0) {
    const fallbackGroupId = pickFallbackGroupId(payload.groups);
    const items = payload.items.map((it) =>
      it.groupId ? it : { ...it, groupId: fallbackGroupId },
    );
    return { ...payload, groups: payload.groups, items };
  }
  const { group, items } = wrapInDefaultGroup(payload.items);
  return { ...payload, groups: [group], items };
}

/**
 * Build a single Manual group and assign every supplied item to it.
 * Items that already carry a groupId are left untouched (defensive: a v1
 * file might still have stragglers from an aborted migration).
 */
function wrapInDefaultGroup(items: MissionItem[]): {
  group: ManualGroup;
  items: MissionItem[];
} {
  const group = createManualGroup({ name: 'Manual', order: 0 });
  const stamped = items.map((it) => (it.groupId ? it : { ...it, groupId: group.id }));
  return { group, items: stamped };
}

function pickFallbackGroupId(groups: Group[]): string {
  // Prefer the first Manual group; otherwise the first group.
  const firstManual = groups.find((g) => g.kind === 'manual');
  return (firstManual ?? groups[0]!).id;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}
