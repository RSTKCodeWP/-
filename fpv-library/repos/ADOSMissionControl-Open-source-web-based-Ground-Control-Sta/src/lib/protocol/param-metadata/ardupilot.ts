/**
 * ArduPilot parameter-definition XML parser.
 *
 * Parses the ArduPilot parameter-definition XML into the metadata superset.
 * Used by the regression suite and available for any XML-source path; runtime
 * freshness comes from the hosted registry (no upstream fetch at runtime).
 *
 * @module protocol/param-metadata/ardupilot
 * @license GPL-3.0-only
 */

import type { ParamMetadata } from "./types";

/** Parse ArduPilot parameter-definition XML into the metadata map. */
export function parseParamXml(xml: string): Map<string, ParamMetadata> {
  const map = new Map<string, ParamMetadata>();
  const parser = new DOMParser();
  const doc = parser.parseFromString(xml, "text/xml");

  for (const pf of doc.querySelectorAll("paramfile")) {
    for (const p of pf.querySelectorAll("param")) parseParamElement(p, map);
  }
  // Flat-structure XMLs carry top-level <param> outside <paramfile>/<vehicles>.
  for (const p of doc.querySelectorAll("param")) {
    const parent = p.parentElement?.tagName;
    if (parent === "paramfile" || parent === "vehicles") continue;
    parseParamElement(p, map);
  }
  return map;
}

/** Parse "code:label,code:label" using parseFloat so non-integer enum codes
 *  (e.g. ArduPilot `0.1:Very Low`) are not collapsed by parseInt. */
function parseCodeLabelPairs(raw: string): Map<number, string> {
  const out = new Map<number, string>();
  for (const pair of raw.split(",")) {
    const idx = pair.indexOf(":");
    if (idx === -1) continue;
    const code = parseFloat(pair.slice(0, idx).trim());
    if (!Number.isNaN(code)) out.set(code, pair.slice(idx + 1).trim());
  }
  return out;
}

function parseParamElement(el: Element, map: Map<string, ParamMetadata>): void {
  let name = el.getAttribute("name") ?? "";
  const colonIdx = name.indexOf(":"); // strip "Vehicle:" prefix
  if (colonIdx !== -1) name = name.slice(colonIdx + 1);
  if (!name) return;

  const meta: ParamMetadata = {
    name,
    humanName: el.getAttribute("humanName") ?? "",
    description: el.getAttribute("documentation") ?? "",
  };

  for (const child of el.children) {
    const tag = child.tagName.toLowerCase();
    const text = child.textContent?.trim() ?? "";
    if (tag === "field") {
      const field = child.getAttribute("name")?.toLowerCase() ?? "";
      if (field === "range") {
        const [min, max] = text.split(/\s+/).map(parseFloat);
        if (!Number.isNaN(min) && !Number.isNaN(max)) meta.range = { min, max };
      } else if (field === "units") {
        meta.units = text;
      } else if (field === "increment") {
        const inc = parseFloat(text);
        if (!Number.isNaN(inc)) meta.increment = inc;
      } else if (field === "rebootrequired") {
        meta.rebootRequired = text.toLowerCase() === "true";
      } else if (field === "readonly") {
        meta.readOnly = text.toLowerCase() === "true";
      } else if (field === "user") {
        meta.advanced = text.toLowerCase() === "advanced";
      } else if (field === "default") {
        const def = parseFloat(text);
        if (!Number.isNaN(def)) meta.defaultValue = def;
      }
    } else if (tag === "values") {
      const values = new Map<number, string>();
      for (const v of child.children) {
        const code = v.getAttribute("code");
        if (code === null) continue;
        const num = parseFloat(code);
        if (!Number.isNaN(num)) values.set(num, v.textContent?.trim() ?? "");
      }
      if (values.size > 0) meta.values = values;
    } else if (tag === "bitmask") {
      const bitmask = new Map<number, string>();
      for (const b of child.children) {
        // ArduPilot uses `code=` on <bit>; tolerate the legacy `bit=` too.
        const bit = b.getAttribute("code") ?? b.getAttribute("bit");
        if (bit === null) continue;
        const num = parseInt(bit, 10);
        if (!Number.isNaN(num)) bitmask.set(num, b.textContent?.trim() ?? "");
      }
      if (bitmask.size > 0) meta.bitmask = bitmask;
    }
  }

  // Attribute-form fields (some XML variants inline these on <param>).
  const rangeAttr = el.getAttribute("Range");
  if (rangeAttr && !meta.range) {
    const [min, max] = rangeAttr.split(/\s+/).map(parseFloat);
    if (!Number.isNaN(min) && !Number.isNaN(max)) meta.range = { min, max };
  }
  const unitsAttr = el.getAttribute("Units");
  if (unitsAttr && !meta.units) meta.units = unitsAttr;
  const incrAttr = el.getAttribute("Increment");
  if (incrAttr && meta.increment === undefined) {
    const inc = parseFloat(incrAttr);
    if (!Number.isNaN(inc)) meta.increment = inc;
  }
  const valuesAttr = el.getAttribute("Values");
  if (valuesAttr && !meta.values) {
    const values = parseCodeLabelPairs(valuesAttr);
    if (values.size > 0) meta.values = values;
  }
  const bitmaskAttr = el.getAttribute("Bitmask");
  if (bitmaskAttr && !meta.bitmask) {
    const bitmask = parseCodeLabelPairs(bitmaskAttr);
    if (bitmask.size > 0) meta.bitmask = bitmask;
  }
  const rebootAttr = el.getAttribute("RebootRequired");
  if (rebootAttr) meta.rebootRequired = rebootAttr.toLowerCase() === "true";
  const readOnlyAttr = el.getAttribute("ReadOnly");
  if (readOnlyAttr) meta.readOnly = readOnlyAttr.toLowerCase() === "true";
  const userAttr = el.getAttribute("User");
  if (userAttr && meta.advanced === undefined) meta.advanced = userAttr.toLowerCase() === "advanced";

  map.set(name, meta);
}
