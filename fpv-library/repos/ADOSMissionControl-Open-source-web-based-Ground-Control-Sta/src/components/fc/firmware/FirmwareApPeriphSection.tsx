"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Plug, Power, Send, RotateCcw } from "lucide-react";
import {
  ApPeriphManifest,
  EMBEDDED_BOARD_LIST,
  type BoardManifest,
} from "@/lib/protocol/firmware/ap-periph-manifest";
import { useDroneCanFlashStore } from "@/stores/dronecan/flash-store";
import { useDroneCanNodeStore } from "@/stores/dronecan/node-store";
import { useAgentCapabilitiesStore } from "@/stores/agent-capabilities-store";
import { useDroneManager } from "@/stores/drone-manager";
import { useSlcanModeStore } from "@/stores/slcan-mode-store";
import { isDemoMode } from "@/lib/utils";
import { FirmwareApPeriphNodeTable } from "./FirmwareApPeriphNodeTable";
import { FirmwareApPeriphFirmwareCard } from "./FirmwareApPeriphFirmwareCard";
import { DebugDrawer } from "@/components/config/can/debug/DebugDrawer";

const apPeriphManifest = new ApPeriphManifest();

const DEFAULT_CHANNELS: readonly string[] = ["stable", "beta", "latest"];

interface Props {
  checklistAllChecked: boolean;
  isFlashing: boolean;
  onFlash: (params: {
    targetNodeId: number;
    board: string;
    channel: string;
    transport: "slcan" | "can-forward";
  }) => void | Promise<void>;
}

export function FirmwareApPeriphSection({
  checklistAllChecked,
  isFlashing,
  onFlash,
}: Props) {
  const t = useTranslations("flashTool.apPeriph");
  const demo = isDemoMode();

  // Connection state — in demo mode, treat SLCAN as active so the UI
  // is exerciseable without live agent wiring.
  const [transport, setTransport] = useState<"slcan" | "can-forward">("slcan");

  // SLCAN gating: the radio is only enabled when the selected drone is
  // connected over a WebSerial-capable transport (direct USB). Cloud /
  // MQTT / WebSocket links can't drive SLCAN because they don't own the
  // FC's USB byte stream.
  const selectedDrone = useDroneManager((s) => s.getSelectedDrone());
  const slcanCapable =
    demo || selectedDrone?.transport?.type === "webserial";

  // Live SLCAN state from the arbiter (banner + button glyph).
  const slcanState = useSlcanModeStore((s) => s.state);
  const slcanActive = demo || slcanState === "SLCAN_ACTIVE";

  // CAN_FORWARD reachability: the agent advertises CAN bus presence via
  // `canBuses` once its capability heartbeat has populated. Demo mode
  // enables the option so the production radio path is exerciseable from
  // a synthetic session too.
  const canBuses = useAgentCapabilitiesStore((s) => s.canBuses);
  const canForwardEnabled = demo || (Array.isArray(canBuses) && canBuses.length > 0);

  // Target node selection
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  // Firmware selection
  const [boards, setBoards] = useState<readonly string[]>(EMBEDDED_BOARD_LIST);
  const [channels, setChannels] = useState<readonly string[]>(DEFAULT_CHANNELS);
  const [selectedBoard, setSelectedBoard] = useState<string>("");
  const [selectedChannel, setSelectedChannel] = useState<string>("stable");
  const [manifest, setManifest] = useState<BoardManifest | null>(null);
  const [loadingManifest, setLoadingManifest] = useState(false);
  const [manifestError, setManifestError] = useState("");

  // Flash store mirror for post-flash UI
  const flashState = useDroneCanFlashStore((s) => s.state);

  // Post-flash actions
  const [newNodeIdRaw, setNewNodeIdRaw] = useState("");
  const newNodeIdParsed = useMemo(() => {
    const n = Number.parseInt(newNodeIdRaw, 10);
    if (Number.isFinite(n) && n >= 1 && n <= 127) return n;
    return null;
  }, [newNodeIdRaw]);

  // Look up current node SW version for diff line
  const nodesMap = useDroneCanNodeStore((s) => s.nodes);
  const currentNodeVersion = useMemo(() => {
    if (selectedNodeId == null) return undefined;
    const entry = nodesMap.get(selectedNodeId);
    const sv = entry?.nodeInfo?.software_version;
    if (!sv) return undefined;
    return `${sv.major}.${sv.minor}`;
  }, [nodesMap, selectedNodeId]);

  // Load the channel list once.
  const channelsLoadedRef = useRef(false);
  useEffect(() => {
    if (channelsLoadedRef.current) return;
    channelsLoadedRef.current = true;
    let cancelled = false;
    apPeriphManifest
      .listChannels()
      .then((list) => {
        if (cancelled) return;
        if (list.length > 0) {
          setChannels(list);
          if (!list.includes(selectedChannel)) {
            setSelectedChannel(list[0]);
          }
        }
      })
      .catch(() => {
        // Embedded baseline already seeded.
      });
    return () => {
      cancelled = true;
    };
  }, [selectedChannel]);

  // Load the board list for the selected channel.
  useEffect(() => {
    if (!selectedChannel) return;
    let cancelled = false;
    apPeriphManifest
      .listBoards(selectedChannel)
      .then((list) => {
        if (cancelled) return;
        if (list.length > 0) {
          setBoards(list);
          if (!selectedBoard || !list.includes(selectedBoard)) {
            setSelectedBoard(list[0]);
          }
        }
      })
      .catch(() => {
        setBoards(EMBEDDED_BOARD_LIST);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChannel]);

  // Load the board manifest when both selections are known.
  useEffect(() => {
    if (!selectedChannel || !selectedBoard) return;
    let cancelled = false;
    setLoadingManifest(true);
    setManifestError("");
    apPeriphManifest
      .getBoardManifest(selectedChannel, selectedBoard)
      .then((m) => {
        if (cancelled) return;
        setManifest(m);
      })
      .catch((err) => {
        if (cancelled) return;
        setManifest(null);
        setManifestError(
          err instanceof Error ? err.message : t("firmware.error"),
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingManifest(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedChannel, selectedBoard, t]);

  const retryManifest = () => {
    if (!selectedChannel || !selectedBoard) return;
    apPeriphManifest.clearCache().then(() => {
      setManifest(null);
      setSelectedChannel((c) => c);
    });
  };

  const flashEnabled =
    checklistAllChecked &&
    selectedNodeId != null &&
    !!selectedBoard &&
    !!selectedChannel &&
    manifest?.files.some((f) => f.kind === "app") === true &&
    !isFlashing;

  const handleFlashClick = () => {
    if (!flashEnabled || selectedNodeId == null) return;
    onFlash({
      targetNodeId: selectedNodeId,
      board: selectedBoard,
      channel: selectedChannel,
      transport,
    });
  };
  // Show the debug drawer while a flash is mid-flight. The drawer renders
  // the state-machine ribbon, the byte counter, and the live frame log so
  // operators can diagnose hangs without leaving the page. Once the flow
  // hits a terminal state the post-flash prompts take over and the drawer
  // hides so it doesn't crowd the success / failure summary.
  const flashInFlight =
    flashState !== "IDLE" &&
    flashState !== "DONE" &&
    flashState !== "ABORTED" &&
    flashState !== "FAILED";

  return (
    <>
      {/* Connection card */}
      <div className="bg-bg-secondary border border-border-default p-4 space-y-3">
        <h2 className="text-xs font-semibold text-text-primary flex items-center gap-2">
          <Plug size={14} />
          {t("connection.title")}
        </h2>

        <div
          role="radiogroup"
          aria-label={t("connection.transportAria")}
          className="flex gap-2"
        >
          <button
            role="radio"
            aria-checked={transport === "slcan"}
            disabled={!slcanCapable}
            onClick={() => {
              if (slcanCapable) setTransport("slcan");
            }}
            title={
              slcanCapable
                ? t("connection.transport.slcan")
                : t("connection.transport.slcanRequiresUsb")
            }
            className={`flex-1 px-3 py-2 text-xs font-semibold border cursor-pointer transition-colors ${
              !slcanCapable
                ? "border-border-default text-text-tertiary opacity-40 cursor-not-allowed"
                : transport === "slcan"
                  ? "border-accent-primary text-accent-primary bg-accent-primary/10"
                  : "border-border-default text-text-secondary hover:text-text-primary"
            }`}
          >
            {t("connection.transport.slcan")}
          </button>
          <button
            role="radio"
            aria-checked={transport === "can-forward"}
            disabled={!canForwardEnabled}
            onClick={() => {
              if (canForwardEnabled) setTransport("can-forward");
            }}
            title={
              canForwardEnabled
                ? t("connection.transport.canForwardReady")
                : t("connection.transport.canForwardWaiting")
            }
            className={`flex-1 px-3 py-2 text-xs font-semibold border cursor-pointer transition-colors ${
              !canForwardEnabled
                ? "border-border-default text-text-tertiary opacity-40 cursor-not-allowed"
                : transport === "can-forward"
                  ? "border-accent-primary text-accent-primary bg-accent-primary/10"
                  : "border-border-default text-text-secondary hover:text-text-primary"
            }`}
          >
            {t("connection.transport.canForward")}
          </button>
        </div>

        {transport === "slcan" && !demo && !slcanCapable && (
          <p
            className="text-[10px] text-status-warning"
            data-testid="ap-periph-slcan-requires-usb"
          >
            {t("connection.transport.slcanRequiresUsb")}
          </p>
        )}

        {slcanActive ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] text-status-success">
              {t("connection.slcanActive", {
                port: "CAN1",
                bitrate: "1 Mbps",
                eta: "4:32",
              })}
            </p>
            <button
              disabled
              title={t("connection.configureHint")}
              className="px-3 py-1.5 text-[10px] font-semibold border border-border-default text-text-tertiary opacity-40 cursor-not-allowed"
            >
              <Power size={10} className="inline mr-1.5" />
              {t("connection.resumeMavlink")}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <p className="text-[10px] text-text-tertiary">
              {t("connection.slcanInactive")}
            </p>
            <button
              disabled
              title={t("connection.configureHint")}
              className="px-3 py-1.5 text-[10px] font-semibold border border-border-default text-text-tertiary opacity-40 cursor-not-allowed"
            >
              <Power size={10} className="inline mr-1.5" />
              {t("connection.enterSlcan")}
            </button>
          </div>
        )}
      </div>

      {/* Target node card */}
      <FirmwareApPeriphNodeTable
        selectedNodeId={selectedNodeId}
        onSelect={setSelectedNodeId}
        slcanActive={slcanActive}
      />

      {/* Firmware card */}
      <FirmwareApPeriphFirmwareCard
        boards={boards}
        channels={channels}
        selectedBoard={selectedBoard}
        setSelectedBoard={setSelectedBoard}
        selectedChannel={selectedChannel}
        setSelectedChannel={setSelectedChannel}
        manifest={manifest}
        loading={loadingManifest}
        error={manifestError}
        currentNodeVersion={currentNodeVersion}
        onRetry={retryManifest}
      />

      {/* Flash button */}
      <button
        onClick={handleFlashClick}
        disabled={!flashEnabled}
        className={`w-full px-4 py-2.5 text-sm font-semibold border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 ${
          flashEnabled
            ? "border-accent-primary text-accent-primary bg-accent-primary/10 hover:bg-accent-primary/20"
            : "border-border-default text-text-tertiary"
        }`}
      >
        <Send size={14} />
        {t("flashButton")}
      </button>

      {/* Post-flash prompts */}
      {flashState === "DONE" && selectedNodeId != null && (
        <div
          data-testid="ap-periph-post-flash"
          className="bg-bg-secondary border border-status-success/40 p-4 space-y-3"
        >
          <h2 className="text-xs font-semibold text-status-success">
            {t("postFlash.title")}
          </h2>
          <p className="text-[10px] text-text-tertiary">
            {t("postFlash.subtitle")}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              className="px-3 py-1.5 text-[10px] font-semibold border border-border-default text-text-secondary hover:text-text-primary hover:bg-bg-tertiary cursor-pointer"
            >
              <RotateCcw size={10} className="inline mr-1.5" />
              {t("postFlash.flashBootloader")}
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              max={127}
              value={newNodeIdRaw}
              onChange={(e) => setNewNodeIdRaw(e.target.value)}
              placeholder={t("postFlash.newNodeIdPlaceholder")}
              className="w-24 px-2 py-1 text-[10px] bg-bg-tertiary border border-border-default text-text-primary"
              aria-label={t("postFlash.newNodeIdAria")}
            />
            <button
              disabled={newNodeIdParsed == null}
              className="px-3 py-1.5 text-[10px] font-semibold border border-border-default text-text-secondary hover:text-text-primary hover:bg-bg-tertiary disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            >
              {t("postFlash.changeNodeId")}
            </button>
          </div>
        </div>
      )}

      {/* Debug drawer — only mounted while a flash is mid-flight. */}
      {flashInFlight && <DebugDrawer mode="flash" />}
    </>
  );
}
