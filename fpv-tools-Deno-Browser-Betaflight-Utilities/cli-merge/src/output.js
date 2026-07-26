/**
 * Parse "set key = value" commands out of CLI lines.
 *
 * @param {string[]} lines
 * @returns {{ sets: Map<string, string>, other: string[] }}
 */
export function parseSetCommands(lines) {
  const sets = new Map();
  const other = [];
  for (const line of lines) {
    const m = /^set\s+(\S+)\s*=\s*(.+)$/.exec(line.trim());
    if (m) {
      sets.set(m[1], m[2].trim());
    } else {
      other.push(line);
    }
  }
  return { sets, other };
}

/**
 * Build the merged CLI output string from section selections.
 *
 * @param {Array<{id: string, title: string, linesA: string[], linesB: string[], status: string}>} sections
 * @param {Record<string, 'a'|'b'|'both'|'skip'>} selections  - keyed by section id
 * @param {Record<string, 'a'|'b'>} setSelections             - keyed by `${sectionId}:${setKey}`
 * @returns {string}
 */
export function buildOutput(sections, selections, setSelections = {}) {
  const outputLines = [];

  for (const sec of sections) {
    const sel = selections[sec.id] ?? defaultSelection(sec);
    if (sel === "skip") continue;

    const sectionLines = getSectionLines(sec, sel, setSelections);
    if (!sectionLines.some((l) => l.trim())) continue;

    const needsCommentHeader = !["header", "footer"].includes(sec.id) &&
      !sec.id.startsWith("profile_") &&
      !sec.id.startsWith("rateprofile_");

    if (needsCommentHeader) {
      outputLines.push(`# ${sec.title}`);
    }

    outputLines.push(...sectionLines);
    outputLines.push("");
  }

  while (outputLines.length && !outputLines[outputLines.length - 1].trim()) {
    outputLines.pop();
  }

  return outputLines.join("\n");
}

/** @param {{status: string}} sec */
function defaultSelection(sec) {
  return sec.status === "only-b" ? "b" : "a";
}

/**
 * @param {{id: string, linesA: string[], linesB: string[]}} sec
 * @param {string} sel
 * @param {Record<string, string>} setSelections
 * @returns {string[]}
 */
function getSectionLines(sec, sel, setSelections) {
  if (sel === "a") return [...sec.linesA];
  if (sel === "b") return [...sec.linesB];

  // "both" mode
  const allLines = [...sec.linesA, ...sec.linesB];
  const hasSetCmds = allLines.some((l) => /^set\s+/.test(l.trim()));

  if (hasSetCmds) {
    return mergeSetSection(sec, setSelections);
  }

  // Union merge for non-set sections: A lines + B lines not already in A
  const setA = new Set(sec.linesA.map((l) => l.trim()).filter(Boolean));
  const merged = [...sec.linesA];
  for (const line of sec.linesB) {
    if (line.trim() && !setA.has(line.trim())) merged.push(line);
  }
  return merged;
}

/**
 * Merge a section that contains "set key = value" commands.
 * Non-set lines are unioned; set commands use per-key selection (defaults to A).
 *
 * @param {{id: string, linesA: string[], linesB: string[]}} sec
 * @param {Record<string, string>} setSelections
 * @returns {string[]}
 */
function mergeSetSection(sec, setSelections) {
  const { sets: setsA, other: otherA } = parseSetCommands(sec.linesA);
  const { sets: setsB, other: otherB } = parseSetCommands(sec.linesB);

  const result = [];

  // Non-set lines: union of A and B
  const otherASet = new Set(otherA.map((l) => l.trim()).filter(Boolean));
  result.push(...otherA.filter((l) => l.trim()));
  for (const line of otherB) {
    if (line.trim() && !otherASet.has(line.trim())) result.push(line);
  }

  // Set commands: per-key selection, defaulting to A
  const allKeys = [...new Set([...setsA.keys(), ...setsB.keys()])];
  for (const key of allKeys) {
    const choice = setSelections[`${sec.id}:${key}`] ?? "a";
    const val = choice === "a"
      ? (setsA.get(key) ?? setsB.get(key))
      : (setsB.get(key) ?? setsA.get(key));
    if (val !== undefined) {
      result.push(`set ${key} = ${val}`);
    }
  }

  return result;
}
