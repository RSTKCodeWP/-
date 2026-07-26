/**
 * Minimal parser for ArduPilot versioned parameter-definition XML
 * (`apm.pdef.xml`). The versioned tree is XML-only (no JSON twin), so this
 * targeted string/regex parser converts it to our snapshot shape without an
 * XML dependency.
 *
 * Confirmed structure: `<param name="Vehicle:NAME" humanName="…"
 * documentation="…" user="Standard|Advanced">` with child elements
 * `<field name="Range">MIN MAX</field>`, `<values><value code="N">label</value></values>`,
 * and `<bitmask><bit code="N">label</bit></bitmask>` (note `code=`, not `bit=`).
 *
 * @license GPL-3.0-only
 */

import { trimDescription, compact } from "./_shared.mjs";

const NAMED_ENTITIES = { quot: '"', lt: "<", gt: ">", amp: "&", apos: "'" };
function decodeEntities(s) {
  return s.replace(/&(#x?[0-9a-f]+|\w+);/gi, (m, e) => {
    if (e[0] === "#") {
      const code = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isNaN(code) ? m : String.fromCharCode(code);
    }
    return NAMED_ENTITIES[e] ?? m;
  });
}

function attr(openTag, name) {
  const m = openTag.match(new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`));
  return m ? m[1] : undefined;
}

/** Extract `<tag code="N">label</tag>` pairs (code parsed as float). */
function codeLabels(body, tag) {
  const re = new RegExp(`<${tag}\\s+code="([^"]+)"[^>]*>([\\s\\S]*?)</${tag}>`, "g");
  const out = [];
  let m;
  while ((m = re.exec(body)) !== null) {
    const code = parseFloat(m[1]);
    if (!Number.isNaN(code)) out.push([code, decodeEntities(m[2].trim())]);
  }
  return out.length ? out : undefined;
}

/** Parse the `<field name="Values|Bitmask">code:label,code:label</field>` form. */
function codeLabelField(text, intOnly) {
  const out = [];
  for (const pair of text.split(",")) {
    const idx = pair.indexOf(":");
    if (idx === -1) continue;
    const raw = pair.slice(0, idx).trim();
    const code = intOnly ? parseInt(raw, 10) : parseFloat(raw);
    if (!Number.isNaN(code)) out.push([code, pair.slice(idx + 1).trim()]);
  }
  return out.length ? out : undefined;
}

/** Parse versioned apm.pdef.xml → SerializedMeta[] (our snapshot param shape). */
export function parsePdefXml(xml) {
  const params = [];
  const seen = new Set();
  const paramRe = /<param\b([^>]*)>([\s\S]*?)<\/param>/g;
  let pm;
  while ((pm = paramRe.exec(xml)) !== null) {
    const openTag = pm[1];
    const body = pm[2];
    let name = attr(openTag, "name") ?? "";
    const colon = name.indexOf(":");
    if (colon !== -1) name = name.slice(colon + 1); // strip "Vehicle:" prefix
    if (!name || seen.has(name)) continue;
    seen.add(name);

    const user = attr(openTag, "user");
    let range, units, increment, fieldValues, fieldBitmask;
    const fieldRe = /<field\s+name="([^"]+)"[^>]*>([\s\S]*?)<\/field>/g;
    let fm;
    while ((fm = fieldRe.exec(body)) !== null) {
      const fn = fm[1].toLowerCase();
      const txt = decodeEntities(fm[2].trim());
      if (fn === "range") {
        const [lo, hi] = txt.split(/\s+/).map(parseFloat);
        if (!Number.isNaN(lo) && !Number.isNaN(hi)) range = { min: lo, max: hi };
      } else if (fn === "units") {
        units = txt;
      } else if (fn === "increment") {
        const inc = parseFloat(txt);
        if (!Number.isNaN(inc)) increment = inc;
      } else if (fn === "values") {
        fieldValues = codeLabelField(txt, false);
      } else if (fn === "bitmask") {
        fieldBitmask = codeLabelField(txt, true);
      }
    }

    // Prefer the child-element block form; fall back to the field form.
    const valuesBlock = body.match(/<values>([\s\S]*?)<\/values>/);
    const bitmaskBlock = body.match(/<bitmask>([\s\S]*?)<\/bitmask>/);

    params.push(compact({
      name,
      humanName: decodeEntities(attr(openTag, "humanName") ?? ""),
      description: trimDescription(decodeEntities(attr(openTag, "documentation") ?? "")),
      range,
      units: units || undefined,
      values: (valuesBlock ? codeLabels(valuesBlock[1], "value") : undefined) ?? fieldValues,
      bitmask: (bitmaskBlock ? codeLabels(bitmaskBlock[1], "bit") : undefined) ?? fieldBitmask,
      increment,
      advanced: user === "Advanced" ? true : (user === "Standard" ? false : undefined),
    }));
  }
  return params;
}
