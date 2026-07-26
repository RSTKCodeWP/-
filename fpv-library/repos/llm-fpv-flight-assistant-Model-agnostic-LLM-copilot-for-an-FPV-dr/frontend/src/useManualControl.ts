import { useEffect, useRef } from "react";

export interface Setpoint { forward: number; right: number; down: number; yaw_rate: number; }
const YAW_RATE = 60; // deg/s at full deflection

export function keysToSetpoint(keys: Set<string>, maxSpeed: number): Setpoint {
  const boost = keys.has("shift") ? 1 : 0.5;
  const v = maxSpeed * boost;
  let forward = 0, right = 0, down = 0, yaw_rate = 0;
  if (keys.has("w")) forward += v;
  if (keys.has("s")) forward -= v;
  if (keys.has("d")) right += v;
  if (keys.has("a")) right -= v;
  if (keys.has("r")) down -= v;   // up
  if (keys.has("f")) down += v;   // down
  if (keys.has("e")) yaw_rate += YAW_RATE * (boost === 1 ? 1.5 : 1);
  if (keys.has("q")) yaw_rate -= YAW_RATE * (boost === 1 ? 1.5 : 1);
  return { forward, right, down, yaw_rate };
}

export function useManualControl(
  active: boolean, maxSpeed: number,
  send: (f: number, r: number, d: number, yr: number) => void,
) {
  const keys = useRef(new Set<string>());
  useEffect(() => {
    if (!active) return;
    const norm = (k: string) => (k === "Shift" ? "shift" : k.toLowerCase());
    const down = (e: KeyboardEvent) => { keys.current.add(norm(e.key)); };
    const up = (e: KeyboardEvent) => { keys.current.delete(norm(e.key)); };
    const clear = () => { keys.current.clear(); send(0, 0, 0, 0); };
    const onVisibility = () => { if (document.hidden) clear(); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    document.addEventListener("visibilitychange", onVisibility);
    const id = setInterval(() => {
      const sp = keysToSetpoint(keys.current, maxSpeed);
      send(sp.forward, sp.right, sp.down, sp.yaw_rate);
    }, 50); // 20 Hz
    return () => {
      clearInterval(id); send(0, 0, 0, 0);
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", clear);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [active, maxSpeed, send]);
  return keys;
}
