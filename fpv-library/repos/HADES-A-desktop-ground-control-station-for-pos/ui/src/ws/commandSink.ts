/* A tiny command sink so UI actions (the ContactDetailPanel's promote→fuse button) can reach
 * the active data source without prop-drilling. The real-service hook registers a handler that
 * sends the WS promote command (Task 5.10 / M6); the mock registers a handler that records the
 * request to the mission log (the mock has no Python fuser to re-run). Exactly one handler is
 * active at a time (whichever source the app selected). */

export type PromoteHandler = (trackId: number) => void;

class CommandSink {
  private handler: PromoteHandler | null = null;

  setHandler(h: PromoteHandler | null): void {
    this.handler = h;
  }

  promote(trackId: number): void {
    this.handler?.(trackId);
  }
}

export const commandSink = new CommandSink();
