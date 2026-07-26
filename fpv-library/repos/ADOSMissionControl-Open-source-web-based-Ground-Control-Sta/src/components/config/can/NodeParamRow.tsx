"use client";

/**
 * @module NodeParamRow
 * @description Renders a single editable row of the per-node parameter
 * table. Handles the three concrete value tags (Integer, Real, Boolean,
 * String) and respects optional min/max bounds when present. Empty-tagged
 * values are skipped by the caller before this component is mounted.
 *
 * @license GPL-3.0-only
 */

import { useMemo } from "react";
import {
  ValueTag,
  type Value as ParamValueRaw,
} from "@/lib/dronecan/dsdl/param-getset";
import type { ParamEntry } from "@/hooks/use-dronecan-node-params";

export type ParamValue = ParamValueRaw;

interface NodeParamRowProps {
  entry: ParamEntry;
  onChange: (value: ParamValue) => void;
}

function valueTypeLabel(v: ParamValue): string {
  switch (v.tag) {
    case ValueTag.Integer:
      return "int";
    case ValueTag.Real:
      return "real";
    case ValueTag.Boolean:
      return "bool";
    case ValueTag.String:
      return "str";
    case ValueTag.Empty:
    default:
      return "—";
  }
}

function asNumeric(v: ParamValue | undefined): number | undefined {
  if (!v) return undefined;
  if (v.tag === ValueTag.Integer) return Number(v.value);
  if (v.tag === ValueTag.Real) return v.value;
  return undefined;
}

export function NodeParamRow({ entry, onChange }: NodeParamRowProps) {
  const v = entry.value;
  const minNum = useMemo(() => asNumeric(entry.min), [entry.min]);
  const maxNum = useMemo(() => asNumeric(entry.max), [entry.max]);

  let input: React.ReactNode;
  switch (v.tag) {
    case ValueTag.Integer: {
      input = (
        <input
          type="number"
          step={1}
          min={minNum}
          max={maxNum}
          value={Number(v.value)}
          onChange={(e) => {
            const n = Math.trunc(Number(e.target.value));
            if (Number.isFinite(n)) {
              onChange({ tag: ValueTag.Integer, value: BigInt(n) });
            }
          }}
          className="w-full px-1.5 py-0.5 text-[11px] font-mono bg-bg-tertiary border border-border-default rounded text-text-primary"
          aria-label={`${entry.name} value`}
        />
      );
      break;
    }
    case ValueTag.Real: {
      input = (
        <input
          type="number"
          step="any"
          min={minNum}
          max={maxNum}
          value={v.value}
          onChange={(e) => {
            const n = Number(e.target.value);
            if (Number.isFinite(n)) {
              onChange({ tag: ValueTag.Real, value: n });
            }
          }}
          className="w-full px-1.5 py-0.5 text-[11px] font-mono bg-bg-tertiary border border-border-default rounded text-text-primary"
          aria-label={`${entry.name} value`}
        />
      );
      break;
    }
    case ValueTag.Boolean: {
      input = (
        <label className="flex items-center gap-1.5 text-[11px] text-text-primary">
          <input
            type="checkbox"
            checked={v.value}
            onChange={(e) =>
              onChange({ tag: ValueTag.Boolean, value: e.target.checked })
            }
            aria-label={`${entry.name} value`}
          />
          <span className="font-mono">{v.value ? "true" : "false"}</span>
        </label>
      );
      break;
    }
    case ValueTag.String: {
      input = (
        <input
          type="text"
          value={v.value}
          onChange={(e) =>
            onChange({ tag: ValueTag.String, value: e.target.value })
          }
          className="w-full px-1.5 py-0.5 text-[11px] font-mono bg-bg-tertiary border border-border-default rounded text-text-primary"
          aria-label={`${entry.name} value`}
        />
      );
      break;
    }
    case ValueTag.Empty:
    default:
      input = (
        <span className="text-[11px] font-mono text-text-tertiary">—</span>
      );
      break;
  }

  return (
    <tr
      data-dirty={entry.dirty ? "true" : "false"}
      className={
        entry.dirty
          ? "bg-status-warning/10 border-b border-border-default"
          : "border-b border-border-default"
      }
    >
      <td className="py-1 px-2 font-mono text-[11px] text-text-primary whitespace-nowrap">
        {entry.name}
      </td>
      <td className="py-1 px-2 align-middle">{input}</td>
      <td className="py-1 px-2 font-mono text-[10px] text-text-tertiary">
        {valueTypeLabel(v)}
      </td>
      <td className="py-1 px-2 text-[10px] text-text-tertiary">
        {minNum !== undefined || maxNum !== undefined
          ? `${minNum ?? "—"} … ${maxNum ?? "—"}`
          : ""}
      </td>
    </tr>
  );
}
