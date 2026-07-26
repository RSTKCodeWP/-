export interface Telemetry {
  lat: number; lon: number; alt_m: number; speed_ms: number;
  battery_pct: number; flight_mode: string; armed: boolean;
  gps_ok: boolean; ekf_ok: boolean;
  roll?: number; pitch?: number; yaw?: number;
}
export interface VideoStatus { ok: boolean; url: string; }
export type ControlWho = "manual" | "assistant";
export interface ChatMessage { role: "user" | "assistant"; reply: string; thinking?: string; }
export interface ProposalView { command: any; say?: string; }
export interface EventEntry { ts: number; kind: string; text: string; }
