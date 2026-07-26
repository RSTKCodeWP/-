/**
 * Wires the live toast callback into the plugin notifier seam.
 *
 * Plugin RPC handlers run outside the React tree (the postMessage bridge
 * dispatches them as plain functions), so `notification.publish` /
 * `ctx.notifications.publish` routes through the `setPluginNotifier` singleton
 * (`src/lib/plugins/notifier.ts`) rather than a React toast hook. This host
 * connects that singleton to the live `useToast` callback at mount, so a
 * plugin's `notification.channel` reaches the operator's toast system. Without
 * it, `pluginNotify` is a no-op (notifications are dropped, never thrown).
 *
 * Mounts once, shell-wide, alongside the other plugin host bridges (mirrors
 * `PluginConfirmHost`). Renders nothing.
 *
 * @module plugins/PluginNotifierHost
 * @license GPL-3.0-only
 */

"use client";

import { useEffect } from "react";

import { useToast } from "@/components/ui/toast";
import { setPluginNotifier } from "@/lib/plugins/notifier";

export function PluginNotifierHost() {
  const { toast } = useToast();

  useEffect(() => {
    setPluginNotifier((message, status) => toast(message, status));
    return () => setPluginNotifier(null);
  }, [toast]);

  return null;
}
