/**
 * Module-level operator-confirmation bridge for non-React plugin handler code.
 *
 * Safety-critical plugin RPCs (command.send, mission.write) must not fire
 * without an explicit operator decision. The handlers run outside the React
 * tree — they are plain functions the postMessage bridge dispatches — so they
 * cannot open a React dialog directly. {@link PluginConfirmHost} wires the live
 * confirm callback once at mount via {@link setPluginConfirmHandler}; until
 * then {@link requestPluginConfirm} resolves `false` so an un-hosted handler
 * DENIES rather than silently proceeding. Mirrors the `setPluginNotifier`
 * singleton in `src/lib/plugins/notifier.ts`.
 *
 * The safe default (deny) is the whole point: a high-consequence command can
 * never reach the vehicle unless a confirm host is mounted and the operator
 * approves.
 *
 * @module plugins/confirm
 * @license GPL-3.0-only
 */

export interface PluginConfirmRequest {
  pluginId: string;
  title: string;
  body: string;
  /** Drives the dialog variant. `critical` renders the danger styling. */
  severity?: "warning" | "critical";
}

type ConfirmHandler = (req: PluginConfirmRequest) => Promise<boolean>;

let handler: ConfirmHandler | null = null;

/**
 * Wire the live confirm callback. Called once from the confirm host at mount.
 * Pass `null` to unwire on teardown.
 */
export function setPluginConfirmHandler(fn: ConfirmHandler | null): void {
  handler = fn;
}

/**
 * Ask the operator to approve a plugin action. Resolves `true` only when a
 * host is wired AND the operator approves. With no host wired this resolves
 * `false` — the safe default that blocks the action.
 */
export function requestPluginConfirm(
  req: PluginConfirmRequest,
): Promise<boolean> {
  if (!handler) return Promise.resolve(false);
  return handler(req);
}
