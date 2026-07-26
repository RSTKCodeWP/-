/**
 * @module plugins/FleetNotificationChannelHost
 * @description Shell-wide host for the `notification.channel` fleet slot. A
 * notification-channel plugin's iframe is headless: it runs in the background
 * for the whole session and publishes operator notifications via
 * `ctx.notifications.publish` (which routes through the plugin notifier seam to
 * the toast system — wired by `PluginNotifierHost`). So unlike the other fleet
 * slots (which mount at a visible surface), this one mounts once, shell-wide,
 * off-screen, and stays alive across navigation.
 *
 * The iframe is rendered into a 0×0, visually-hidden, non-interactive box: it
 * is a sandboxed sink/source, not a visible panel. It is inert until a plugin
 * contributes a `notification.channel` (the fleet producer yields nothing
 * otherwise), so a GCS with no such plugin pays no DOM cost.
 *
 * @license GPL-3.0-only
 */

"use client";

import { FleetPluginSlot } from "@/components/plugins/FleetPluginSlot";

export function FleetNotificationChannelHost() {
  return (
    <div
      aria-hidden
      data-fleet-slot="notification.channel"
      className="sr-only pointer-events-none"
    >
      <FleetPluginSlot
        name="notification.channel"
        iframeClassName="h-0 w-0 border-0"
      />
    </div>
  );
}
