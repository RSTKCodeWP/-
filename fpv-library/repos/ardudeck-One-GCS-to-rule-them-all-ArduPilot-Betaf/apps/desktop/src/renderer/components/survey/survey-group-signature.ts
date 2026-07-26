/**
 * Signature + regeneration helpers for survey groups.
 *
 * A survey group's "signature" is a deterministic hash of the inputs that
 * the generator consumes: polygon, holes, workspace, and config. When the
 * stored `lastGeneratedSignature` mismatches the current inputs, the
 * group is stale and its WPs are out of date.
 *
 * Spec: docs/superpowers/specs/2026-05-28-mission-groups-design.md
 */

import type { SurveyGroup } from '../../../shared/mission-group-types';

/**
 * Build a stable string from a survey group's inputs. Object keys are
 * sorted so a re-serialization with shuffled keys still produces the same
 * hash. Numbers are formatted to 9 decimals (well below the centimetre
 * threshold for lat/lng).
 */
function canonicalize(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return 'null';
    // Use enough precision for sub-cm lat/lng without bloating the hash.
    return Number.isInteger(value) ? String(value) : value.toFixed(9);
  }
  if (typeof value === 'string' || typeof value === 'boolean') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return '[' + value.map(canonicalize).join(',') + ']';
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    return '{' + keys.map((k) => JSON.stringify(k) + ':' + canonicalize(obj[k])).join(',') + '}';
  }
  return 'null';
}

/**
 * djb2 hash over a canonicalized representation. Cheap, deterministic,
 * collisions rare enough for the "did these inputs change" use case.
 */
function djb2(str: string): string {
  let h = 5381;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) + h + str.charCodeAt(i)) | 0;
  }
  return (h >>> 0).toString(36);
}

export function computeSurveyGroupSignature(g: SurveyGroup): string {
  const blob = canonicalize({
    polygon: g.polygon,
    holes: g.holes ?? null,
    workspace: g.workspace ?? null,
    config: g.config,
    generatorId: g.generatorId,
    generatorVersion: g.generatorVersion,
  });
  return djb2(blob);
}

/**
 * A survey group is stale when its current input signature does not match
 * the one stored from the last generation. A null `lastGeneratedSignature`
 * means it has never been generated, which is also "stale" semantically.
 */
export function isSurveyGroupStale(g: SurveyGroup): boolean {
  if (!g.lastGeneratedSignature) return true;
  return computeSurveyGroupSignature(g) !== g.lastGeneratedSignature;
}
