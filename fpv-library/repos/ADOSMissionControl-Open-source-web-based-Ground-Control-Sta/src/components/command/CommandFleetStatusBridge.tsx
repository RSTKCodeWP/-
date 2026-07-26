"use client";

/**
 * @module CommandFleetStatusBridge
 * @description Loads display-safe cloud status for every cloud-paired
 * Command agent. Co-owns the `cloudStatuses` map with the LAN-only
 * `CommandFleetLocalBridge`: each bridge tracks its own set of
 * deviceIds and uses `upsertCloudStatuses` / `removeCloudStatuses` to
 * avoid stomping the other.
 * @license GPL-3.0-only
 */

import { useEffect, useRef } from "react";
import { cmdDroneStatusApi } from "@/lib/community-api-drones";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import { useCommandFleetStore, type CommandCloudStatus } from "@/stores/command-fleet-store";

type CloudStatusRow = {
  status?: CommandCloudStatus | null;
};

export function CommandFleetStatusBridge({ enabled }: { enabled: boolean }) {
  const rows = useConvexSkipQuery(cmdDroneStatusApi.listMyCloudStatuses, { enabled });
  // DeviceIds we wrote on the previous render, so we can diff and
  // remove rows that the Convex query dropped (e.g. an unpair).
  const ownedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!Array.isArray(rows)) return;
    const statuses = (rows as CloudStatusRow[])
      .map((row) => row.status)
      .filter((status): status is CommandCloudStatus => !!status);
    const nextOwned = new Set(statuses.map((s) => s.deviceId));
    const dropped: string[] = [];
    for (const id of ownedRef.current) {
      if (!nextOwned.has(id)) dropped.push(id);
    }
    const store = useCommandFleetStore.getState();
    if (dropped.length > 0) store.removeCloudStatuses(dropped);
    store.upsertCloudStatuses(statuses);
    ownedRef.current = nextOwned;
  }, [rows]);

  // Unmount: clean up the rows we own so a fresh mount doesn't see
  // stale data the user can't unpair.
  useEffect(() => {
    return () => {
      const owned = Array.from(ownedRef.current);
      if (owned.length > 0) {
        useCommandFleetStore.getState().removeCloudStatuses(owned);
      }
      ownedRef.current = new Set();
    };
  }, []);

  return null;
}
