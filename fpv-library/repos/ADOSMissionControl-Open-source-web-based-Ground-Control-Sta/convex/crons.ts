import { cronJobs } from "convex/server";
import { internal } from "./_generated/api";

const crons = cronJobs();

crons.interval(
  "sync-changelog-from-github",
  { minutes: 15 },
  internal.changelogSync.syncFromGithub
);

// Cron-only (internal): the sweep walks the by_expiresAt index. A public
// no-auth mutation here would let any client trigger the table scan on demand.
crons.interval(
  "clean-expired-pairing",
  { minutes: 15 },
  internal.cmdPairing.cleanExpiredRequests
);

// Retention: terminal cloud-relay command rows and exported log windows are
// append-mostly tables that otherwise grow without bound. Each sweep deletes
// only rows past its retention window via a bounded indexed range, so the
// hourly tick stays cheap and a backlog drains over successive ticks.
crons.interval(
  "prune-terminal-commands",
  { hours: 1 },
  internal.cmdDroneCommands.pruneTerminalCommands
);

crons.interval(
  "prune-old-logd-windows",
  { hours: 6 },
  internal.cmdLogdWindows.pruneOldWindows
);

export default crons;
