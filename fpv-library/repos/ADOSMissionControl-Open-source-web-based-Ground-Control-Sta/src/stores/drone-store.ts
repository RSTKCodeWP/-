import { create } from "zustand";
import type { ConnectionState, FlightMode, ArmState } from "@/lib/types";
import type { FirmwareType } from "@/lib/protocol/types";

interface DroneStoreState {
  selectedId: string | null;
  connectionState: ConnectionState;
  flightMode: FlightMode;
  previousMode: FlightMode;
  armState: ArmState;
  lastHeartbeat: number;
  firmwareVersion: string;
  frameType: string;
  systemStatus: number;
  firmwareType: FirmwareType | null;

  selectDrone: (id: string | null) => void;
  setConnectionState: (state: ConnectionState) => void;
  setFlightMode: (mode: FlightMode) => void;
  setArmState: (state: ArmState) => void;
  heartbeat: () => void;
  setFirmwareInfo: (version: string, frame: string) => void;
  setSystemStatus: (status: number) => void;
  setFirmwareType: (type: FirmwareType | null) => void;
}

export const useDroneStore = create<DroneStoreState>((set) => ({
  selectedId: null,
  connectionState: "disconnected",
  flightMode: "STABILIZE",
  previousMode: "STABILIZE",
  armState: "disarmed",
  lastHeartbeat: 0,
  firmwareVersion: "",
  frameType: "",
  systemStatus: 0,
  firmwareType: null,

  selectDrone: (id) => set({ selectedId: id }),
  setConnectionState: (connectionState) => set({ connectionState }),
  setFlightMode: (flightMode) => set((s) => ({ previousMode: s.flightMode, flightMode })),
  setArmState: (armState) => set({ armState }),
  heartbeat: () => set({ lastHeartbeat: Date.now() }),
  setFirmwareInfo: (firmwareVersion, frameType) => set({ firmwareVersion, frameType }),
  setSystemStatus: (systemStatus) => set({ systemStatus }),
  setFirmwareType: (firmwareType) => set({ firmwareType }),
}));
