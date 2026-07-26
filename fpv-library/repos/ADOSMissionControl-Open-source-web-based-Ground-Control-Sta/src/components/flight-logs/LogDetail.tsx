"use client";

import { useState, useCallback } from "react";
import { HistoryDetailPanel } from "@/components/history/detail/HistoryDetailPanel";
import { ReplayView } from "@/components/history/ReplayView";
import type { FlightRecord } from "@/lib/types";
import type { TelemetryRecording } from "@/lib/telemetry-recorder";

export interface UseReplayResult {
  replayState: { recording: TelemetryRecording; record: FlightRecord } | null;
  handleReplay: (recording: TelemetryRecording) => void;
  handleExitReplay: () => void;
}

export function useReplay(selectedRecord: FlightRecord | null): UseReplayResult {
  const [replayState, setReplayState] = useState<{ recording: TelemetryRecording; record: FlightRecord } | null>(null);

  const handleReplay = useCallback((recording: TelemetryRecording) => {
    if (selectedRecord) {
      setReplayState({ recording, record: selectedRecord });
    }
  }, [selectedRecord]);

  const handleExitReplay = useCallback(() => {
    setReplayState(null);
  }, []);

  return { replayState, handleReplay, handleExitReplay };
}

export interface LogReplayViewProps {
  recording: TelemetryRecording;
  record: FlightRecord;
  onExit: () => void;
}

export function LogReplayView({ recording, record, onExit }: LogReplayViewProps) {
  return <ReplayView recording={recording} flightRecord={record} onExit={onExit} />;
}

export interface LogDetailProps {
  record: FlightRecord;
  onClose: () => void;
  onReplay: (recording: TelemetryRecording) => void;
  listCollapsed: boolean;
  onToggleListCollapsed: () => void;
}

export function LogDetail({ record, onClose, onReplay, listCollapsed, onToggleListCollapsed }: LogDetailProps) {
  return (
    <HistoryDetailPanel
      record={record}
      onClose={onClose}
      onReplay={onReplay}
      listCollapsed={listCollapsed}
      onToggleListCollapsed={onToggleListCollapsed}
    />
  );
}
