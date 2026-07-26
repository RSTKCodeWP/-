import { Button } from "./ui/Button";
export function AbortButton({ onAbort }: { onAbort: () => void }) {
  return <Button variant="danger" onClick={onAbort} title="Abort: cancel command, exit manual, hold">⏹ ABORT</Button>;
}
