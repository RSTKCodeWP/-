/**
 * @module fc/firmware/firmware-state/use-ados-agent-firmware
 * @description Owns the ADOS-agent slice of the firmware picker: the
 * board catalog (network manifest or demo fallback), the loader, the
 * effect that resets the selected board when the drone/ground stack
 * switches, and the derived install method for the selected board.
 * @license GPL-3.0-only
 */

"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type AdosAgentBoard,
  type AdosAgentStack,
} from "@/lib/protocol/firmware/ados-agent-manifest";
import type { FirmwareStack } from "@/lib/protocol/firmware/types";
import { isDemoMode } from "@/lib/utils";
import { isAdosStack } from "../firmware-constants";
import { adosManifest } from "./manifests";
import { DEMO_ADOS_AGENT_VERSION, DEMO_ADOS_BOARDS } from "./demo-catalog";

export function useAdosAgentFirmware(firmwareStack: FirmwareStack) {
  const [adosBoards, setAdosBoards] = useState<AdosAgentBoard[]>([]);
  const [adosLoading, setAdosLoading] = useState(false);
  const [adosError, setAdosError] = useState("");
  const [adosAgentVersion, setAdosAgentVersion] = useState("");
  const [selectedAdosBoardId, setSelectedAdosBoardId] = useState("");
  // Tracks whether the manifest came from the upstream catalog or the
  // embedded baseline. Drives the "offline catalog" pill in the picker.
  const [adosManifestSource, setAdosManifestSource] = useState<string | undefined>(undefined);

  async function loadAdosManifest() {
    setAdosLoading(true); setAdosError("");
    // In demo mode the proxy at /api/ados-manifest may not be reachable
    // (and adds noise to the demo regardless), so seed the picker with a
    // small built-in catalog and skip the network call entirely.
    if (isDemoMode()) {
      setAdosBoards(DEMO_ADOS_BOARDS);
      setAdosAgentVersion(DEMO_ADOS_AGENT_VERSION);
      setAdosManifestSource("fallback");
      const stackKey = isAdosStack(firmwareStack) ? (firmwareStack as AdosAgentStack) : "ados-drone-agent";
      const first = DEMO_ADOS_BOARDS.find((b) => b.stacks.includes(stackKey));
      if (first) setSelectedAdosBoardId(first.id);
      setAdosLoading(false);
      return;
    }
    try {
      const data = await adosManifest.getManifest();
      setAdosBoards(data.boards);
      setAdosAgentVersion(data.agentVersion);
      setAdosManifestSource(data.source);
      const stackKey = isAdosStack(firmwareStack) ? (firmwareStack as AdosAgentStack) : "ados-drone-agent";
      const first = data.boards.find((b) => b.stacks.includes(stackKey));
      if (first) setSelectedAdosBoardId(first.id);
    } catch (err) {
      setAdosError(err instanceof Error ? err.message : "Failed to load ADOS agent manifest");
    } finally { setAdosLoading(false); }
  }

  // When the ADOS stack switches between drone and ground, the available
  // boards change. Reset the selected board if it no longer supports the
  // active stack so the picker shows a fresh choice.
  useEffect(() => {
    if (!isAdosStack(firmwareStack) || adosBoards.length === 0) return;
    const currentBoard = adosBoards.find((b) => b.id === selectedAdosBoardId);
    const stackKey = firmwareStack as AdosAgentStack;
    if (!currentBoard || !currentBoard.stacks.includes(stackKey)) {
      const next = adosBoards.find((b) => b.stacks.includes(stackKey));
      setSelectedAdosBoardId(next?.id ?? "");
    }
  }, [firmwareStack, adosBoards, selectedAdosBoardId]);

  // Selected ADOS board's install method, if any. Used by FirmwarePanel
  // to gate the WebUSB-required warning to web-flash boards only.
  const adosInstallMethod = useMemo(() => {
    if (!isAdosStack(firmwareStack)) return null;
    const board = adosBoards.find((b) => b.id === selectedAdosBoardId);
    if (!board) return null;
    const stackKey = firmwareStack as AdosAgentStack;
    return board.installs[stackKey]?.method ?? null;
  }, [firmwareStack, adosBoards, selectedAdosBoardId]);

  return {
    adosBoards, adosLoading, adosError, adosAgentVersion,
    adosManifestSource,
    selectedAdosBoardId, setSelectedAdosBoardId, adosInstallMethod,
    loadAdosManifest,
    loadAdosManifestRetry: () => { adosManifest.clearCache(); loadAdosManifest(); },
  };
}
