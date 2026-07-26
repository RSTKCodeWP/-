/**
 * @module use-planner-io
 * @description Save/load/export handlers and autosave effects for the mission planner.
 * @license GPL-3.0-only
 */

import { useCallback, useEffect, useRef } from "react";
import { usePlanLibraryStore } from "@/stores/plan-library-store";
import { useDroneManager } from "@/stores/drone-manager";
import { usePlannerStore } from "@/stores/planner-store";
import { useSettingsStore } from "@/stores/settings-store";
import { capturePlanExtras } from "@/lib/plan-workspace";
import {
  autoSave,
  cancelAutoSave,
  getAutoSave,
  exportWaypointsFormat,
  exportQGCPlan,
  exportMissionKML,
  exportMissionCSV,
  exportMissionKMZ,
  downloadMissionFile,
} from "@/lib/mission-io";
import type { Waypoint } from "@/lib/types";

interface IODeps {
  waypoints: Waypoint[];
  missionName: string;
  selectedDroneId: string;
  activePlanId: string | null;
  isDirty: boolean;
  libAutoSaveTimer: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;
  setWaypoints: (wps: Waypoint[]) => void;
  setMissionName: (name: string) => void;
  setSelectedDroneId: (id: string) => void;
  setSelectedWaypoint: (id: string | null) => void;
  setExpandedWaypoint: (id: string | null) => void;
  setShowDownloadConfirm: (show: boolean) => void;
  clearMission: () => void;
  downloadMission: () => Promise<Waypoint[]>;
  toast: (message: string, status?: "success" | "warning" | "error" | "info") => void;
}

export function usePlannerIO(deps: IODeps) {
  const {
    waypoints, missionName, selectedDroneId, activePlanId, isDirty,
    libAutoSaveTimer, setWaypoints, setMissionName, setSelectedDroneId,
    setSelectedWaypoint, setExpandedWaypoint, setShowDownloadConfirm,
    clearMission, downloadMission, toast,
  } = deps;

  // ── Autosave recovery ─────────────────────────────────────
  const autoSaveChecked = useRef(false);
  useEffect(() => {
    if (autoSaveChecked.current) return;
    autoSaveChecked.current = true;
    (async () => {
      const saved = await getAutoSave();
      if (saved && saved.waypoints.length > 0) {
        toast("Unsaved mission found — restoring", "info");
        setWaypoints(saved.waypoints);
        if (saved.metadata.name) setMissionName(saved.metadata.name);
        if (saved.metadata.droneId) setSelectedDroneId(saved.metadata.droneId);
      }
    })();
  }, [setWaypoints, toast, setMissionName, setSelectedDroneId]);

  // Auto-save to IndexedDB on waypoint changes
  useEffect(() => {
    if (waypoints.length > 0) {
      autoSave(waypoints, {
        name: missionName,
        droneId: selectedDroneId || undefined,
      });
    }
    return () => cancelAutoSave();
  }, [waypoints, missionName, selectedDroneId]);

  // Auto-save to library plan (debounced 3s)
  useEffect(() => {
    const libStore = usePlanLibraryStore.getState();
    if (!libStore.activePlanId || waypoints.length === 0) return;
    if (libAutoSaveTimer.current) clearTimeout(libAutoSaveTimer.current);
    libAutoSaveTimer.current = setTimeout(() => {
      const current = usePlanLibraryStore.getState();
      if (!current.activePlanId || !current.isDirty) return;
      current.savePlan(current.activePlanId, waypoints, {
        droneId: selectedDroneId || undefined,
      }, capturePlanExtras());
    }, 3000);
    return () => { if (libAutoSaveTimer.current) clearTimeout(libAutoSaveTimer.current); };
  }, [waypoints, selectedDroneId, libAutoSaveTimer]);

  // Auto-sync plan name to library
  useEffect(() => {
    const libStore = usePlanLibraryStore.getState();
    if (!libStore.activePlanId || !missionName) return;
    libStore.updatePlanName(libStore.activePlanId, missionName);
  }, [missionName]);

  // Dirty detection
  useEffect(() => {
    const libStore = usePlanLibraryStore.getState();
    if (!libStore.activePlanId) return;
    const waypointsDirty = JSON.stringify(waypoints) !== libStore.savedSnapshot;
    const plan = libStore.plans.find((p) => p.id === libStore.activePlanId);
    const nameDirty = plan ? plan.name !== missionName : false;
    libStore.setDirty(waypointsDirty || nameDirty);
  }, [waypoints, missionName]);

  // ── Save/Load handlers ────────────────────────────────────
  const handleSave = useCallback(() => {
    const libStore = usePlanLibraryStore.getState();
    if (libStore.activePlanId) {
      if (missionName) libStore.updatePlanName(libStore.activePlanId, missionName);
      libStore.savePlan(libStore.activePlanId, waypoints, {
        droneId: selectedDroneId || undefined,
        totalDistance: undefined, estimatedTime: undefined,
      }, capturePlanExtras());
    } else {
      libStore.createPlan(missionName || "Untitled Plan", waypoints, {
        droneId: selectedDroneId || undefined,
      }, capturePlanExtras());
    }
    if (libAutoSaveTimer.current) clearTimeout(libAutoSaveTimer.current);
    useSettingsStore.getState().incrementSaveCount();
    toast("Plan saved", "success");
  }, [waypoints, missionName, selectedDroneId, toast, libAutoSaveTimer]);

  const handleSaveAs = useCallback(() => {
    const libStore = usePlanLibraryStore.getState();
    libStore.createPlan(missionName || "Untitled Plan", waypoints, {
      droneId: selectedDroneId || undefined,
    }, capturePlanExtras());
    useSettingsStore.getState().incrementSaveCount();
    toast("Plan saved as new copy", "success");
  }, [waypoints, missionName, selectedDroneId, toast]);

  const handleExportWaypoints = useCallback(() => {
    exportWaypointsFormat(waypoints, missionName || "mission");
    toast("Exported (.waypoints)", "success");
  }, [waypoints, missionName, toast]);

  const handleExportPlan = useCallback(() => {
    exportQGCPlan(waypoints, missionName || "mission", undefined, capturePlanExtras());
    toast("Exported (.plan)", "success");
  }, [waypoints, missionName, toast]);

  const handleExportKML = useCallback(() => {
    exportMissionKML(waypoints, missionName || "mission");
    toast("Exported (.kml)", "success");
  }, [waypoints, missionName, toast]);

  const handleExportCSV = useCallback(() => {
    exportMissionCSV(waypoints, missionName || "mission");
    toast("Exported (.csv)", "success");
  }, [waypoints, missionName, toast]);

  const handleExportKMZ = useCallback(async () => {
    await exportMissionKMZ(waypoints, missionName || "mission");
    toast("Exported (.kmz)", "success");
  }, [waypoints, missionName, toast]);

  const handleExportNative = useCallback(async () => {
    // Native .altmission format — captures the whole plan (path + fence + rally),
    // unlike the interchange formats which drop fields on round-trip.
    await downloadMissionFile(waypoints, {
      name: missionName || "mission",
      droneId: selectedDroneId || undefined,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }, capturePlanExtras());
    toast("Exported (.altmission)", "success");
  }, [waypoints, missionName, selectedDroneId, toast]);

  const handlePlanLoaded = useCallback(
    (plan: { name: string; droneId?: string }) => {
      setMissionName(plan.name);
      setSelectedDroneId(plan.droneId || "");
    },
    [setMissionName, setSelectedDroneId]
  );

  const handlePlanRenamed = useCallback((name: string) => { setMissionName(name); }, [setMissionName]);

  const handleNewPlan = useCallback(() => {
    const libStore = usePlanLibraryStore.getState();
    libStore.createPlan();
    clearMission();
    setMissionName("Untitled Plan");
    setSelectedDroneId("");
    setSelectedWaypoint(null);
    setExpandedWaypoint(null);
    toast("New plan created", "info");
  }, [clearMission, setSelectedWaypoint, setExpandedWaypoint, toast, setMissionName, setSelectedDroneId]);

  const handleFocusSearch = useCallback(() => {
    document.dispatchEvent(new CustomEvent("plan-library:focus-search"));
  }, []);

  // ── Download from drone ───────────────────────────────────
  const executeDownloadFromDrone = useCallback(async () => {
    const downloaded = await downloadMission();
    if (downloaded.length === 0) { toast("No mission found on drone", "info"); return; }
    const time = new Date().toLocaleTimeString("en-US", { hour12: false });
    const name = `Drone Mission (${time})`;
    const libStore = usePlanLibraryStore.getState();
    libStore.createPlan(name, downloaded);
    setMissionName(name);
    setSelectedDroneId(selectedDroneId);
    usePlannerStore.getState().requestFit();
    toast(`Loaded ${downloaded.length} waypoints from drone`, "success");
  }, [downloadMission, selectedDroneId, toast, setMissionName, setSelectedDroneId]);

  const handleDownloadFromDrone = useCallback(() => {
    const droneManager = useDroneManager.getState();
    const hasDrone = droneManager.selectedDroneId !== null || droneManager.drones.size > 0;
    if (!hasDrone) { toast("Connect a drone first", "info"); return; }
    if (isDirty && activePlanId) { setShowDownloadConfirm(true); return; }
    executeDownloadFromDrone();
  }, [isDirty, activePlanId, executeDownloadFromDrone, toast, setShowDownloadConfirm]);

  const handleSaveAndDownload = useCallback(() => {
    handleSave();
    setShowDownloadConfirm(false);
    executeDownloadFromDrone();
  }, [handleSave, executeDownloadFromDrone, setShowDownloadConfirm]);

  const handleDiscardAndDownload = useCallback(() => {
    setShowDownloadConfirm(false);
    executeDownloadFromDrone();
  }, [executeDownloadFromDrone, setShowDownloadConfirm]);

  const handleCancelDownload = useCallback(() => { setShowDownloadConfirm(false); }, [setShowDownloadConfirm]);

  return {
    handleSave, handleSaveAs,
    handleExportWaypoints, handleExportPlan, handleExportKML, handleExportCSV,
    handleExportKMZ, handleExportNative,
    handlePlanLoaded, handlePlanRenamed, handleNewPlan, handleFocusSearch,
    handleDownloadFromDrone, handleSaveAndDownload, handleDiscardAndDownload, handleCancelDownload,
  };
}
