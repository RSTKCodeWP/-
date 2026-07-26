export type PanelId =
  | 'logPanel'
  | 'video'
  | 'calibration'
  | 'shortcuts'
  | 'inspector'
  | 'console'
  | 'motorTest'
  | 'rcCal'
  | 'failsafe'
  | 'powerCal'
  | 'escCal'
  | 'frameSelect'
  | 'pid'
  | 'autoTune'
  | 'flightModes'
  | 'setupWizard'
  | 'paramDiff'
  | 'flightReport'
  | 'logViewer'
  | 'fft'
  | 'compass3d'
  | 'advCmd'
  | 'overlapCalc'
  | 'corridor'
  | 'poi'
  | 'annotation'
  | 'remote'
  | 'role'
  | 'airspace'
  | 'offlineMap'
  | 'mission3d'
  | 'gimbal'
  | 'dashboard'
  | 'aiPlanner'
  | 'script'
  | 'ortho'
  | 'aiAnnotation'
  | 'scheduler'
  | 'posSource'
  | 'ntrip'
  | 'fleet'
  | 'terrainProfile';

class PanelRegistry {
  _open = $state(new Set<PanelId>());

  isOpen(id: PanelId): boolean {
    return this._open.has(id);
  }

  open(id: PanelId) {
    const next = new Set(this._open);
    next.add(id);
    this._open = next;
  }

  close(id: PanelId) {
    const next = new Set(this._open);
    next.delete(id);
    this._open = next;
  }

  toggle(id: PanelId) {
    this.isOpen(id) ? this.close(id) : this.open(id);
  }
}

export const panels = new PanelRegistry();

export const PANEL_LOADERS: Record<PanelId, () => Promise<{ default: unknown }>> = {
  logPanel: () => import('../components/tools/LogPanel.svelte'),
  video: () => import('../components/vehicle/VideoOverlay.svelte'),
  calibration: () => import('../components/setup/CalibrationPanel.svelte'),
  shortcuts: () => Promise.resolve({ default: null }),
  inspector: () => import('../components/tools/InspectorPanel.svelte'),
  console: () => import('../components/tools/ConsolePanel.svelte'),
  motorTest: () => import('../components/setup/MotorTestPanel.svelte'),
  rcCal: () => import('../components/setup/RcCalibPanel.svelte'),
  failsafe: () => import('../components/params/FailsafeConfigPanel.svelte'),
  powerCal: () => import('../components/params/PowerCalPanel.svelte'),
  escCal: () => import('../components/setup/EscCalPanel.svelte'),
  frameSelect: () => import('../components/setup/FrameSelectPanel.svelte'),
  pid: () => import('../components/params/PidPanel.svelte'),
  autoTune: () => import('../components/params/AutoTunePanel.svelte'),
  flightModes: () => import('../components/params/FlightModePanel.svelte'),
  setupWizard: () => import('../components/setup/SetupWizard.svelte'),
  paramDiff: () => import('../components/params/ParamDiffPanel.svelte'),
  flightReport: () => import('../components/tools/FlightReportPanel.svelte'),
  logViewer: () => import('../components/tools/LogViewerPanel.svelte'),
  fft: () => import('../components/tools/FFTPanel.svelte'),
  compass3d: () => import('../components/map/Compass3DPanel.svelte'),
  advCmd: () => import('../components/tools/AdvancedCmdPanel.svelte'),
  overlapCalc: () => import('../components/planning/OverlapCalcPanel.svelte'),
  corridor: () => import('../components/mission/CorridorPanel.svelte'),
  poi: () => import('../components/mission/PoiPanel.svelte'),
  annotation: () => import('../components/planning/AnnotationPanel.svelte'),
  remote: () => import('../components/tools/RemotePanel.svelte'),
  role: () => import('../components/shared/RolePanel.svelte'),
  airspace: () => import('../components/map/AirspacePanel.svelte'),
  offlineMap: () => import('../components/map/OfflineMapPanel.svelte'),
  mission3d: () => import('../components/map/Mission3DPanel.svelte'),
  gimbal: () => import('../components/vehicle/GimbalPanel.svelte'),
  dashboard: () => import('../components/planning/CustomDashboard.svelte'),
  aiPlanner: () => import('../components/planning/AiPlannerPanel.svelte'),
  script: () => import('../components/planning/ScriptPanel.svelte'),
  ortho: () => import('../components/map/OrthoOverlayPanel.svelte'),
  aiAnnotation: () => import('../components/planning/AiAnnotationPanel.svelte'),
  scheduler: () => import('../components/planning/SchedulerPanel.svelte'),
  posSource: () => import('../components/setup/PositionSourcePanel.svelte'),
  ntrip: () => import('../components/setup/NtripPanel.svelte'),
  fleet: () => import('../components/vehicle/FleetDashboard.svelte'),
  terrainProfile: () => import('../components/mission/TerrainProfilePanel.svelte'),
};
