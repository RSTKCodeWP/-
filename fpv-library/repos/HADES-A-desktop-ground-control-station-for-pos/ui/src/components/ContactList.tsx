import { useMemo, useState } from "react";

import { useClearanceStore } from "../store/clearanceStore";
import { buildContactRows, type ContactRow, type SortKey, type SortSpec } from "../store/contactView";
import { useContactStore } from "../store/contacts";
import { useSelectionStore } from "../store/selection";
import { contactStatus } from "../ui/contactStatus";
import { formatAge } from "../ui/format";
import { statusGlyph, statusTextClass } from "../ui/status";
import { ConfidenceBar } from "./ConfidenceBar";
import { Placeholder } from "./Placeholder";

/* The prioritized survivor list (impl-plan Task 5.4). One row per contact with the
 * NON-NEGOTIABLE columns: track id, class, detection AND localization confidence as
 * SEPARATE meters, clearance, age, CONVERGING/STABLE, heading-limited. Rows are bound
 * bidirectionally to the global selection spine (click commits, hover previews). Default
 * sort = actionability (urgent on top); cleared contacts demote, never vanish. Numbers are
 * mono/tabular. The algorithm proposes, the operator disposes (sortable headers). */

const FRAME_RATE = 30; // age_frames → seconds for display

const COLUMNS: { key: SortKey | null; label: string }[] = [
  { key: null, label: "" }, // status glyph
  { key: "track", label: "TRK" },
  { key: null, label: "CLASS" },
  { key: "det", label: "DET" },
  { key: "loc", label: "LOC" },
  { key: null, label: "CLR" },
  { key: "age", label: "AGE" },
  { key: "convergence", label: "CONV" },
  { key: null, label: "HDG" },
];

export function ContactList() {
  const contacts = useContactStore((s) => s.contacts);
  const clearance = useClearanceStore((s) => s.states);
  const [sort, setSort] = useState<SortSpec>({ key: "actionability", dir: "desc" });

  const rows = useMemo(
    () => buildContactRows(contacts, clearance, sort),
    [contacts, clearance, sort],
  );

  if (rows.length === 0) {
    return <Placeholder label="No contacts yet" hint="Survivors plot here as they're detected" />;
  }

  const toggleSort = (key: SortKey | null) => {
    if (!key) return;
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));
  };

  return (
    <table className="w-full border-collapse font-mono text-xs" role="grid" aria-label="Survivor contacts">
      <thead className="sticky top-0 bg-surface-1 text-text-lo">
        <tr>
          {COLUMNS.map((col, i) => (
            <th
              key={i}
              role="columnheader"
              scope="col"
              aria-sort={
                col.key && sort.key === col.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"
              }
              className={`px-1 py-1 text-left font-medium ${col.key ? "cursor-pointer select-none hover:text-text-mid" : ""}`}
              onClick={() => toggleSort(col.key)}
            >
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <ContactRowView key={row.record.track_id} row={row} />
        ))}
      </tbody>
    </table>
  );
}

function ContactRowView({ row }: { row: ContactRow }) {
  const { record } = row;
  const selectedId = useSelectionStore((s) => s.selectedId);
  const select = useSelectionStore((s) => s.select);
  const hover = useSelectionStore((s) => s.hover);
  const clearHover = useSelectionStore((s) => s.clearHover);
  const isSelected = selectedId === record.track_id;
  const status = contactStatus(record);

  return (
    <tr
      role="row"
      data-testid={`row-${record.track_id}`}
      data-contact-row="true"
      data-track-id={record.track_id}
      data-selected={isSelected}
      aria-selected={isSelected}
      tabIndex={0}
      onClick={() => select(record.track_id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          select(record.track_id);
        }
      }}
      onMouseEnter={() => hover(record.track_id)}
      onMouseLeave={() => clearHover()}
      className={`h-[var(--row-h)] cursor-pointer border-l-2 outline-none transition-colors duration-micro ${
        isSelected
          ? "border-blue-bright bg-surface-3"
          : "border-transparent hover:bg-surface-2"
      } ${row.cleared ? "opacity-60" : ""} focus-visible:shadow-focus`}
    >
      <td className={`px-1 ${statusTextClass(status)}`} aria-label={status}>
        {statusGlyph(status)}
      </td>
      <td className="px-1 text-text-hi">{record.track_id}</td>
      <td className="px-1 text-text-mid">{record.actionability_class}</td>
      <td className="px-1">
        <ConfidenceBar value={record.detection_conf} label="detection confidence" />
      </td>
      <td className="px-1">
        <ConfidenceBar
          value={record.lat === null ? null : record.localization_conf}
          label="localization confidence"
        />
      </td>
      <td className="px-1 text-text-mid">{row.clearance.replace("_", " ")}</td>
      <td className="px-1 text-text-mid">{formatAge(record.age_frames / FRAME_RATE)}</td>
      <td className="px-1 text-text-mid">
        {record.convergence_state === "STABLE" ? "STBL" : "CONV"}
      </td>
      <td className="px-1">
        {record.heading_limited ? (
          <span className="text-st-stale" title="heading-limited">
            ⚠ HL
          </span>
        ) : (
          <span className="text-text-lo">—</span>
        )}
      </td>
    </tr>
  );
}
