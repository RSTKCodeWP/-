/**
 * Module-level toast bridge for non-React plugin handler code.
 *
 * Plugin RPC handlers run outside the React tree — they are plain
 * functions the postMessage bridge dispatches — so they cannot call a
 * React toast hook directly. The plugin host wires the live toast
 * callback once at mount via {@link setPluginNotifier}; until then
 * notifications are dropped so a handler never throws for want of a UI.
 * Mirrors the `setSkillNotifier` singleton in `src/lib/skills/registry.ts`.
 *
 * @module plugins/notifier
 * @license GPL-3.0-only
 */

export type PluginNotifyStatus = "success" | "warning" | "error" | "info";

type Notifier = (message: string, status: PluginNotifyStatus) => void;

let notifier: Notifier | null = null;

/**
 * Wire the live toast callback. Called once from the plugin host at mount.
 * Pass `null` to unwire on teardown.
 */
export function setPluginNotifier(fn: Notifier | null): void {
  notifier = fn;
}

/**
 * Raise a toast from non-React handler code. No-op until a notifier is
 * wired, so a handler can call this unconditionally without guarding.
 */
export function pluginNotify(message: string, status: PluginNotifyStatus): void {
  notifier?.(message, status);
}
