"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { HistoryStatsBar } from "@/components/history/HistoryStatsBar";
import { HistoryBulkActions } from "@/components/history/HistoryBulkActions";
import { EmptyState } from "@/components/history/EmptyState";
import { CloudSyncBridge } from "@/components/history/CloudSyncBridge";
import { LogFilter, useLogFilter } from "@/components/flight-logs/LogFilter";
import { LogTable, useListLayout } from "@/components/flight-logs/LogTable";
import { LogDetail, LogReplayView, useReplay } from "@/components/flight-logs/LogDetail";
import { useHistoryStore } from "@/stores/history-store";
import { useOperatorProfileStore } from "@/stores/operator-profile-store";
import { useAircraftRegistryStore } from "@/stores/aircraft-registry-store";
import { useBatteryRegistryStore } from "@/stores/battery-registry-store";
import { useEquipmentRegistryStore } from "@/stores/equipment-registry-store";
import { useLoadoutStore } from "@/stores/loadout-store";
import { isDemoMode } from "@/lib/utils";
import type { FlightRecord } from "@/lib/types";

export default function FlightHistoryPage() {
  // Load any persisted history + operator profile + aircraft registry from
  // IndexedDB on first mount. All three are idempotent.
  const loadFromIDB = useHistoryStore((s) => s.loadFromIDB);
  const loadOperator = useOperatorProfileStore((s) => s.loadFromIDB);
  const loadAircraft = useAircraftRegistryStore((s) => s.loadFromIDB);
  const loadBatteries = useBatteryRegistryStore((s) => s.loadFromIDB);
  const loadEquipment = useEquipmentRegistryStore((s) => s.loadFromIDB);
  const loadLoadouts = useLoadoutStore((s) => s.loadFromIDB);
  const initWithSeedData = useHistoryStore((s) => s.initWithSeedData);
  const resetDemoData = useHistoryStore((s) => s.resetDemoData);

  useEffect(() => {
    void loadOperator();
    void loadAircraft();
    void loadBatteries();
    void loadEquipment();
    void loadLoadouts();

    // In demo mode: always wipe persisted history and re-seed from the
    // curated dataset. Demo records are filtered out of persistToIDB so
    // a clean reset never destroys real imports or live-hardware flights.
    if (!isDemoMode()) {
      void loadFromIDB();
      return;
    }

    let cancelled = false;
    void (async () => {
      const mod = await import("@/mock/history");
      const { seedDemoHistory, seedDemoTelemetryRecordings } = mod;

      await resetDemoData();
      if (cancelled) return;

      const records = seedDemoHistory();
      await seedDemoTelemetryRecordings(records);
      if (cancelled) return;
      initWithSeedData(records);
    })();

    return () => {
      cancelled = true;
    };
  }, [loadFromIDB, loadOperator, loadAircraft, loadBatteries, loadEquipment, loadLoadouts, initWithSeedData, resetDemoData]);

  const allRecords = useHistoryStore((s) => s.records);
  const filter = useLogFilter(allRecords);
  const layout = useListLayout();

  // Selection state (multi-select)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const lastClickedRef = useRef<string | null>(null);

  // Detail panel selection
  const [selectedRecord, setSelectedRecord] = useState<FlightRecord | null>(null);

  const replay = useReplay(selectedRecord);

  // keyboard shortcuts for the history page
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't capture when typing in an input/textarea
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      if (e.key === "/" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        const searchInput = document.querySelector<HTMLInputElement>('[data-history-search]');
        searchInput?.focus();
      }
      if (e.key === "Escape") {
        if (selectedRecord) setSelectedRecord(null);
        else if (selectedIds.size > 0) setSelectedIds(new Set());
      }
      if (e.key === "t" && !e.metaKey && !e.ctrlKey) {
        filter.setShowTrash((v) => !v);
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedIds.size > 0 && !e.metaKey) {
          const store = useHistoryStore.getState();
          for (const id of selectedIds) store.removeRecord(id);
          void store.persistToIDB();
          setSelectedIds(new Set());
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selectedRecord, selectedIds, filter]);

  const handleToggleSelect = useCallback((id: string, range: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (range && lastClickedRef.current) {
        // Range select between lastClickedRef.current and id within current visible page order.
        // Simplification: just toggle the single item; full range select needs page records.
        // (a future pass can add multi-page range selection.)
        if (next.has(id)) next.delete(id);
        else next.add(id);
      } else {
        if (next.has(id)) next.delete(id);
        else next.add(id);
      }
      lastClickedRef.current = id;
      return next;
    });
  }, []);

  const handleSelectAllPage = useCallback((ids: string[], allSelected: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        for (const id of ids) next.delete(id);
      } else {
        for (const id of ids) next.add(id);
      }
      return next;
    });
  }, []);

  const handleResetAll = useCallback(() => {
    filter.handleReset();
    setSelectedIds(new Set());
  }, [filter]);

  // Replay mode: full-screen replay replaces table
  if (replay.replayState) {
    return (
      <LogReplayView
        recording={replay.replayState.recording}
        record={replay.replayState.record}
        onExit={replay.handleExitReplay}
      />
    );
  }

  return (
    <div className="relative flex-1 flex flex-col h-full overflow-hidden">
      <CloudSyncBridge />
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-default shrink-0">
        <h1 className="text-sm font-display font-semibold text-text-primary">Flight History</h1>
      </div>

      {/* Toolbar */}
      <LogFilter
        filter={{ ...filter, handleReset: handleResetAll }}
        allRecords={allRecords}
        filteredRecords={filter.filteredRecords}
      />

      {/* Stats bar */}
      {allRecords.length > 0 && <HistoryStatsBar records={filter.filteredRecords} />}

      {/* Table + Detail */}
      <div className="flex flex-1 overflow-hidden">
        {allRecords.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <LogTable
              records={filter.filteredRecords}
              selectedRecord={selectedRecord}
              onSelectRecord={setSelectedRecord}
              selectedIds={selectedIds}
              onToggleSelect={handleToggleSelect}
              onSelectAllPage={handleSelectAllPage}
              sortKey={filter.sortKey}
              sortDir={filter.sortDir}
              onSortChange={filter.handleSortChange}
              listWidth={layout.listWidth}
              listCollapsed={layout.listCollapsed}
              onResizeStart={layout.handleResizeStart}
              onResizeMove={layout.handleResizeMove}
              onResizeEnd={layout.handleResizeEnd}
            />

            {selectedRecord && (
              <LogDetail
                record={selectedRecord}
                onClose={() => setSelectedRecord(null)}
                onReplay={replay.handleReplay}
                listCollapsed={layout.listCollapsed}
                onToggleListCollapsed={layout.toggleListCollapsed}
              />
            )}
          </>
        )}
      </div>

      <HistoryBulkActions
        records={filter.filteredRecords}
        selectedIds={selectedIds}
        onClearSelection={() => setSelectedIds(new Set())}
      />
    </div>
  );
}
