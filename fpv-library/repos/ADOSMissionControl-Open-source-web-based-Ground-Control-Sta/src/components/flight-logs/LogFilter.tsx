"use client";

import { useState, useMemo, useCallback, useDeferredValue } from "react";
import { HistoryToolbar, type DatePreset } from "@/components/history/HistoryToolbar";
import { type SortKey, type SortDir } from "@/components/history/HistoryTable";
import { useHistoryStore } from "@/stores/history-store";
import type { FlightRecord } from "@/lib/types";

const DAY_MS = 86_400_000;

function presetToRange(preset: DatePreset): { fromMs?: number; toMs?: number } {
  if (preset === "all") return {};
  const now = Date.now();
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  if (preset === "today") return { fromMs: start.getTime(), toMs: now };
  if (preset === "7d") return { fromMs: now - 7 * DAY_MS, toMs: now };
  if (preset === "30d") return { fromMs: now - 30 * DAY_MS, toMs: now };
  if (preset === "month") {
    const monthStart = new Date();
    monthStart.setDate(1);
    monthStart.setHours(0, 0, 0, 0);
    return { fromMs: monthStart.getTime(), toMs: now };
  }
  return {};
}

export interface LogFilterState {
  search: string;
  datePreset: DatePreset;
  dateFrom: string;
  dateTo: string;
  status: string;
  droneFilter: string;
  favoritesOnly: boolean;
  showTrash: boolean;
  sort: string;
  sortKey: SortKey;
  sortDir: SortDir;
}

export interface UseLogFilterResult extends LogFilterState {
  filteredRecords: FlightRecord[];
  droneNames: { value: string; label: string }[];
  setSearch: (v: string) => void;
  setStatus: (v: string) => void;
  setDroneFilter: (v: string) => void;
  setFavoritesOnly: (v: boolean) => void;
  setShowTrash: React.Dispatch<React.SetStateAction<boolean>>;
  setSort: (v: string) => void;
  handleSetDateFrom: (v: string) => void;
  handleSetDateTo: (v: string) => void;
  handleSetDatePreset: (p: DatePreset) => void;
  handleSortChange: (key: SortKey) => void;
  handleReset: () => void;
}

export function useLogFilter(allRecords: FlightRecord[]): UseLogFilterResult {
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [datePreset, setDatePreset] = useState<DatePreset>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [status, setStatus] = useState("all");
  const [droneFilter, setDroneFilter] = useState("all");
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [showTrash, setShowTrash] = useState(false);
  const [sort, setSort] = useState("date-desc");
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSetDateFrom = useCallback((v: string) => {
    setDateFrom(v);
    if (v) setDatePreset("all");
  }, []);
  const handleSetDateTo = useCallback((v: string) => {
    setDateTo(v);
    if (v) setDatePreset("all");
  }, []);
  const handleSetDatePreset = useCallback((p: DatePreset) => {
    setDatePreset(p);
    if (p !== "all") {
      setDateFrom("");
      setDateTo("");
    }
  }, []);

  const handleReset = useCallback(() => {
    setSearch("");
    setDatePreset("all");
    setDateFrom("");
    setDateTo("");
    setStatus("all");
    setDroneFilter("all");
    setFavoritesOnly(false);
    setSort("date-desc");
    setSortKey("date");
    setSortDir("desc");
  }, []);

  const handleSortChange = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev !== key) {
        setSortDir("desc");
        return key;
      }
      setSortDir((d) => {
        if (d === "desc") return "asc";
        return "desc";
      });
      return key;
    });
  }, []);

  const droneNames = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of allRecords) {
      if (!seen.has(r.droneId)) seen.set(r.droneId, r.droneName);
    }
    return Array.from(seen.entries()).map(([value, label]) => ({ value, label }));
  }, [allRecords]);

  const filteredRecords = useMemo(() => {
    let records = showTrash
      ? allRecords.filter((r) => r.deleted === true)
      : allRecords.filter((r) => !r.deleted);

    const q = deferredSearch.trim().toLowerCase();
    if (q) {
      records = records.filter((r) => {
        const hay = [
          r.customName,
          r.droneName,
          r.notes,
          ...(r.tags ?? []),
          r.id,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return hay.includes(q);
      });
    }

    if (datePreset !== "all") {
      const { fromMs, toMs } = presetToRange(datePreset);
      if (fromMs !== undefined) records = records.filter((r) => (r.startTime ?? r.date) >= fromMs);
      if (toMs !== undefined) records = records.filter((r) => (r.startTime ?? r.date) <= toMs);
    } else {
      if (dateFrom) {
        const from = new Date(dateFrom).getTime();
        records = records.filter((r) => (r.startTime ?? r.date) >= from);
      }
      if (dateTo) {
        const tov = new Date(dateTo).getTime() + DAY_MS;
        records = records.filter((r) => (r.startTime ?? r.date) <= tov);
      }
    }

    if (status !== "all") records = records.filter((r) => r.status === status);
    if (droneFilter !== "all") records = records.filter((r) => r.droneId === droneFilter);
    if (favoritesOnly) records = records.filter((r) => r.favorite === true);

    const dirSign = sortDir === "desc" ? -1 : 1;
    switch (sortKey) {
      case "date":
        records.sort((a, b) => dirSign * ((b.startTime ?? b.date) - (a.startTime ?? a.date)));
        break;
      case "drone":
        records.sort((a, b) => dirSign * b.droneName.localeCompare(a.droneName));
        break;
      case "duration":
        records.sort((a, b) => dirSign * (b.duration - a.duration));
        break;
      case "distance":
        records.sort((a, b) => dirSign * (b.distance - a.distance));
        break;
      case "maxAlt":
        records.sort((a, b) => dirSign * (b.maxAlt - a.maxAlt));
        break;
      case "battery":
        records.sort((a, b) => dirSign * (b.batteryUsed - a.batteryUsed));
        break;
    }

    return records;
  }, [allRecords, deferredSearch, datePreset, dateFrom, dateTo, status, droneFilter, favoritesOnly, showTrash, sortKey, sortDir]);

  return {
    search,
    datePreset,
    dateFrom,
    dateTo,
    status,
    droneFilter,
    favoritesOnly,
    showTrash,
    sort,
    sortKey,
    sortDir,
    filteredRecords,
    droneNames,
    setSearch,
    setStatus,
    setDroneFilter,
    setFavoritesOnly,
    setShowTrash,
    setSort,
    handleSetDateFrom,
    handleSetDateTo,
    handleSetDatePreset,
    handleSortChange,
    handleReset,
  };
}

export interface LogFilterProps {
  filter: UseLogFilterResult;
  allRecords: FlightRecord[];
  filteredRecords: FlightRecord[];
}

export function LogFilter({ filter, allRecords, filteredRecords }: LogFilterProps) {
  return (
    <HistoryToolbar
      search={filter.search}
      dateFrom={filter.dateFrom}
      dateTo={filter.dateTo}
      datePreset={filter.datePreset}
      status={filter.status}
      droneFilter={filter.droneFilter}
      sort={filter.sort}
      favoritesOnly={filter.favoritesOnly}
      droneNames={filter.droneNames}
      records={filteredRecords}
      onSearchChange={filter.setSearch}
      onDateFromChange={filter.handleSetDateFrom}
      onDateToChange={filter.handleSetDateTo}
      onDatePresetChange={filter.handleSetDatePreset}
      onStatusChange={filter.setStatus}
      onDroneFilterChange={filter.setDroneFilter}
      onSortChange={filter.setSort}
      onFavoritesOnlyChange={filter.setFavoritesOnly}
      showTrash={filter.showTrash}
      onShowTrashChange={filter.setShowTrash}
      onEmptyTrash={() => {
        if (typeof window !== "undefined" && !window.confirm("Permanently delete all trashed flights?")) return;
        const store = useHistoryStore.getState();
        store.emptyTrash();
        void store.persistToIDB();
      }}
      trashCount={allRecords.filter((r) => r.deleted === true).length}
      onReset={filter.handleReset}
    />
  );
}
