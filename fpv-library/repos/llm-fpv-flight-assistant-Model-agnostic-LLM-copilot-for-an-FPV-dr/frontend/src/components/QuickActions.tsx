import { Button } from "./ui/Button";
export function QuickActions({ quick }: { quick: (verb: string, args?: object) => void }) {
  return (<div style={{ display: "flex", gap: 8 }}>
    <Button onClick={() => quick("arm_takeoff", { alt: 10 })}>Takeoff</Button>
    <Button onClick={() => quick("orbit", { radius: 20, alt: 15 })}>Orbit</Button>
    <Button onClick={() => quick("loiter", {})}>Loiter</Button>
    <Button onClick={() => quick("return_to_launch", {})}>RTL</Button>
    <Button variant="danger" onClick={() => quick("land", {})}>Land</Button>
  </div>);
}
