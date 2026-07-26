/**
 * @module fc/firmware/firmware-state/use-px4-firmware
 * @description Owns the PX4 slice of the firmware picker: the release
 * catalog, the releases loader, and the derived board list for the
 * selected release.
 * @license GPL-3.0-only
 */

"use client";

import { useState } from "react";
import type { PX4Release } from "@/lib/protocol/firmware/types";
import { px4Manifest } from "./manifests";

export function usePx4Firmware() {
  const [px4Releases, setPx4Releases] = useState<PX4Release[]>([]);
  const [px4Loading, setPx4Loading] = useState(false);
  const [px4Error, setPx4Error] = useState("");
  const [selectedPx4Release, setSelectedPx4Release] = useState("");
  const [selectedPx4Board, setSelectedPx4Board] = useState("");

  async function loadPx4Releases() {
    setPx4Loading(true); setPx4Error("");
    try {
      const releases = await px4Manifest.getReleases();
      setPx4Releases(releases);
      const stable = releases.find((r) => !r.prerelease);
      if (stable) setSelectedPx4Release(stable.tag);
      else if (releases.length > 0) setSelectedPx4Release(releases[0].tag);
    } catch (err) { setPx4Error(err instanceof Error ? err.message : "Failed to load PX4 releases"); }
    finally { setPx4Loading(false); }
  }

  const px4SelectedRelease = px4Releases.find((r) => r.tag === selectedPx4Release);
  const px4Boards = px4SelectedRelease?.boards ?? [];

  return {
    px4Releases, px4Loading, px4Error,
    selectedPx4Release, setSelectedPx4Release,
    selectedPx4Board, setSelectedPx4Board,
    px4Boards,
    loadPx4Releases,
    loadPx4ReleasesRetry: () => { px4Manifest.clearCache(); loadPx4Releases(); },
  };
}
