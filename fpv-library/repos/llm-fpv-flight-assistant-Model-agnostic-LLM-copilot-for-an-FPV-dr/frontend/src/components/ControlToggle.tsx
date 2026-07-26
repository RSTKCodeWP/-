import type { ControlWho } from "../types";
import { Button } from "./ui/Button";
export function ControlToggle({ control, onTake, onRelease }:
  { control: ControlWho; onTake: () => void; onRelease: () => void }) {
  const manual = control === "manual";
  return (<div style={{ display: "flex", gap: 8, alignItems: "center" }}>
    <span style={{ font: "700 12px Inter, sans-serif", color: manual ? "#f5b945" : "#3ddc97" }}>
      {manual ? "MANUAL (YOU)" : "ASSISTANT"}</span>
    <Button variant={manual ? "default" : "accent"} onClick={manual ? onRelease : onTake}>
      {manual ? "RELEASE" : "TAKE CONTROL"}</Button>
  </div>);
}
