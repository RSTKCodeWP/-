import { useEffect, useState } from "react";

import { formatUtcClock } from "./format";

/* A 1Hz UTC clock string for the status strip. Thin timing glue over the pure
 * formatUtcClock (which is unit-tested); this hook just ticks it. */
export function useClock(): string {
  const [clock, setClock] = useState(() => formatUtcClock(new Date()));
  useEffect(() => {
    const id = setInterval(() => setClock(formatUtcClock(new Date())), 1000);
    return () => clearInterval(id);
  }, []);
  return clock;
}
