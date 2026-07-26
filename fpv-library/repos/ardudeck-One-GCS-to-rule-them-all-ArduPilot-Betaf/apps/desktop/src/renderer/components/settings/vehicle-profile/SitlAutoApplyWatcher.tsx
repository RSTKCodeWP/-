import { useEffect, useRef } from 'react';
import { useSettingsStore } from '../../../stores/settings-store.js';
import { useConnectionStore } from '../../../stores/connection-store.js';
import { useParameterStore } from '../../../stores/parameter-store.js';
import { useTelemetryStore } from '../../../stores/telemetry-store.js';
import { useSitlStore } from '../../../stores/sitl-store.js';
import { prepareApply, finalizeApply } from '../../../lib/vehicle-templates/apply.js';
import { recordSitlApply, getSitlMemory } from '../../../lib/vehicle-templates/sitl-stickiness.js';

/**
 * Auto-apply watcher. Mount once at app root. When SITL is running + connected
 * + params are loaded, if the active profile has `autoApplyOnSitl=true`, push
 * its diffs into the compare modal. Guard: only fires once per (SITL instance,
 * profile) combination per session.
 */
export function SitlAutoApplyWatcher() {
  const vehicles = useSettingsStore(s => s.vehicles);
  const activeVehicleId = useSettingsStore(s => s.activeVehicleId);
  const updateVehicle = useSettingsStore(s => s.updateVehicle);
  const connectionState = useConnectionStore(s => s.connectionState);
  const paramSize = useParameterStore(s => s.parameters.size);
  const armed = useTelemetryStore(s => s.flight.armed);
  const sitlProfileName = useSitlStore(s => s.currentProfileName);
  const sitlRunning = useSitlStore(s => s.isRunning);

  // Session memory: which (instance, profile) combos we've already auto-applied.
  const firedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!connectionState.isConnected || !connectionState.isSitl) return;
    if (paramSize === 0) return;
    if (armed) return;
    if (!sitlRunning) return;

    const profile = vehicles.find(v => v.id === activeVehicleId);
    if (!profile || !profile.autoApplyOnSitl) return;

    const instanceKey = sitlProfileName ?? connectionState.transport ?? 'sitl';
    const fireKey = `${instanceKey}::${profile.id}`;
    if (firedRef.current.has(fireKey)) return;

    // If our sticky memory says we already applied this profile to this SITL,
    // skip — don't loop on every reconnect.
    const memory = getSitlMemory(instanceKey);
    if (memory?.activeProfileId === profile.id && memory.lastAppliedAt) {
      const ageMs = Date.now() - new Date(memory.lastAppliedAt).getTime();
      if (ageMs < 5 * 60_000) {
        firedRef.current.add(fireKey);
        return;
      }
    }

    firedRef.current.add(fireKey);

    const paramStore = useParameterStore.getState();
    const params = new Map<string, { value: number; type: number }>();
    for (const [k, v] of paramStore.parameters) params.set(k, { value: v.value, type: v.type });

    const gate = prepareApply({
      profile,
      mode: 'sitl',
      connectionState,
      connectionLabel: instanceKey,
      armed,
      currentParams: params,
      isRebootRequired: paramStore.isRebootRequired,
    });
    if (!gate.ok) return;

    // Push diffs through the compare modal so the user still reviews.
    useParameterStore.setState({
      fileParamDiffs: gate.fileDiffs,
      fileSkippedParams: [],
      fileSkippedCount: 0,
      fileTotalCount: gate.fileDiffs.length,
      fileVehicleType: null,
      showCompareModal: true,
      applyProgress: null,
      fileApplyResult: null,
    });
    // Compare modal is global — it'll render over whichever view is active.

    // Finalize after the modal closes. We have to tolerate both the
    // "clean apply" path (applyProgress gets the count for one tick) and
    // the "reboot required / skipped" path (fileApplyResult is populated).
    let cleanCount: number | null = null;
    const unsub = useParameterStore.subscribe((state, prev) => {
      if (prev.isApplyingFileParams && !state.isApplyingFileParams && state.applyProgress) {
        cleanCount = state.applyProgress.applied;
      }
      if (prev.showCompareModal && !state.showCompareModal) {
        unsub();
        const finalResult = useParameterStore.getState().fileApplyResult;
        const applied =
          finalResult?.applied ??
          cleanCount ??
          gate.fileDiffs.filter(d => {
            const cur = useParameterStore.getState().parameters.get(d.paramId);
            return cur && Math.abs(cur.value - d.fileValue) < 1e-4;
          }).length;
        if (applied > 0) {
          finalizeApply({ snapshot: gate.pendingSnapshot, updateVehicle });
          recordSitlApply({
            instanceKey,
            profileId: profile.id,
            snapshotId: gate.pendingSnapshot.id,
          });
        }
      }
    });
  }, [
    connectionState, paramSize, armed, sitlRunning, sitlProfileName,
    vehicles, activeVehicleId, updateVehicle,
  ]);

  // Reset fire memory when SITL stops (so next restart triggers again).
  useEffect(() => {
    if (!sitlRunning) firedRef.current.clear();
  }, [sitlRunning]);

  return null;
}
