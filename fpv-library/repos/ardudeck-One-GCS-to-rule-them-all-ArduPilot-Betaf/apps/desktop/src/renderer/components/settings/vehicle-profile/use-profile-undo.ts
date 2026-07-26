import { useCallback } from 'react';
import type { VehicleProfile } from '../../../stores/settings-store.js';
import { useParameterStore } from '../../../stores/parameter-store.js';
import { useNavigationStore } from '../../../stores/navigation-store.js';
import { getSnapshot } from '../../../lib/vehicle-templates/snapshot.js';
import { buildUndoDiffs } from '../../../lib/vehicle-templates/apply.js';

/**
 * Hook: restore a specific snapshot's `before` values via the compare modal.
 * Returns a function; call with a snapshotId (or omit to use profile.lastSnapshotId).
 */
export function useProfileUndo(
  profile: VehicleProfile,
  updateVehicle: (id: string, updates: Partial<VehicleProfile>) => void,
) {
  return useCallback((snapshotId?: string) => {
    const id = snapshotId ?? profile.lastSnapshotId;
    if (!id) return;
    const snapshot = getSnapshot(profile.id, id);
    if (!snapshot) return;

    const pStore = useParameterStore;
    const current = new Map<string, { value: number; type: number }>();
    for (const [k, v] of pStore.getState().parameters) {
      current.set(k, { value: v.value, type: v.type });
    }
    const diffs = buildUndoDiffs(snapshot, current);
    if (diffs.length === 0) return;

    pStore.setState({
      fileParamDiffs: diffs,
      fileSkippedParams: [],
      fileSkippedCount: 0,
      fileTotalCount: diffs.length,
      fileVehicleType: null,
      showCompareModal: true,
      applyProgress: null,
      fileApplyResult: null,
    });

    // Update profile bookkeeping — clear lastSnapshot since we're rolling back.
    updateVehicle(profile.id, { lastSnapshotId: undefined, lastAppliedAt: undefined });

    try { useNavigationStore.getState().setView('parameters'); } catch { /* ignore */ }
  }, [profile, updateVehicle]);
}
