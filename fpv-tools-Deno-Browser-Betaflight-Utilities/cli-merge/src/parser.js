/**
 * Parse a Betaflight CLI dump (diff all / dump all) into labelled sections.
 *
 * Sections are delimited by:
 *   - Lines matching "# word" (e.g. "# feature", "# master")
 *   - "profile N" and "rateprofile N" lines
 *   - "batch start" / "batch end" / "save" (structural)
 *
 * @param {string} text
 * @returns {Array<{id: string, title: string, lines: string[]}>}
 */
export function parseCLI(text) {
  const lines = text.split("\n").map((l) => l.trimEnd());
  /** @type {Array<{id: string, title: string, lines: string[]}>} */
  const sections = [];
  let current = /** @type {{id: string, title: string, lines: string[]}|null} */ (null);
  let pastBatchStart = false;

  // Restore commands ("# restore original profile selection" + "profile N",
  // "# restore original rateprofile selection" + "rateprofile N") need to end
  // up in the footer but must NOT trigger footer early — in Betaflight 4.5+
  // the profile restore appears between the profile sections and the rateprofile
  // sections, so opening footer there would swallow all rateprofile content.
  // Buffer these lines and flush them into footer when we see the real terminal
  // commands (save / batch end / # save configuration).
  /** @type {string[]} */
  const footerBuffer = [];

  function flush() {
    if (!current) return;
    while (current.lines.length && !current.lines[current.lines.length - 1].trim()) {
      current.lines.pop();
    }
    sections.push(current);
    current = null;
  }

  function open(id, title) {
    flush();
    current = { id, title, lines: [] };
  }

  function openFooter() {
    if (current?.id !== "footer") open("footer", "Footer");
    for (const l of footerBuffer) current.lines.push(l);
    footerBuffer.length = 0;
  }

  open("header", "Header");

  for (const line of lines) {
    const t = line.trim();

    // Skip leading blank lines before batch start
    if (!pastBatchStart && !t) continue;

    if (t === "batch start") {
      pastBatchStart = true;
      if (current) current.lines.push(line);
      continue;
    }

    if (!pastBatchStart) {
      if (current) current.lines.push(line);
      continue;
    }

    // profile N
    const profileMatch = /^profile\s+(\d+)$/.exec(t);
    if (profileMatch) {
      if (current?.id === "footer") {
        current.lines.push(line);
      } else {
        const n = profileMatch[1];
        const id = `profile_${n}`;
        const alreadyExists = sections.some((s) => s.id === id) || current?.id === id;
        if (alreadyExists) {
          // Restore command — buffer for footer
          footerBuffer.push(line);
        } else {
          open(id, `Profile ${n}`);
          current.lines.push(line);
        }
      }
      continue;
    }

    // rateprofile N
    const rateMatch = /^rateprofile\s+(\d+)$/.exec(t);
    if (rateMatch) {
      if (current?.id === "footer") {
        current.lines.push(line);
      } else {
        const n = rateMatch[1];
        const id = `rateprofile_${n}`;
        const alreadyExists = sections.some((s) => s.id === id) || current?.id === id;
        if (alreadyExists) {
          // Restore command — buffer for footer
          footerBuffer.push(line);
        } else {
          open(id, `Rate Profile ${n}`);
          current.lines.push(line);
        }
      }
      continue;
    }

    // batch end / save — flush buffer and enter footer
    if (t === "batch end" || t === "save") {
      openFooter();
      current.lines.push(line);
      continue;
    }

    // Section header comment: "# word [word...]" with only safe chars
    // Excludes firmware version lines which contain "/" ":" etc.
    const commentMatch = /^#\s+([a-zA-Z][a-zA-Z0-9_ ]{0,60})$/.exec(t);
    if (commentMatch) {
      const name = commentMatch[1].trim();
      const nameLower = name.toLowerCase();

      // "# profile [N]" / "# rateprofile [N]" are sub-headers, never section openers.
      // Betaflight uses both bare ("# profile") and numbered ("# profile 0") forms.
      // Keep inside the current profile_N / rateprofile_N section when already there;
      // discard otherwise (structural markers in dump-all before the switch command).
      const isProfileSubHdr = /^profile(\s+\d+)?$/.test(nameLower);
      const isRateSubHdr = /^rateprofile(\s+\d+)?$/.test(nameLower);
      if (isProfileSubHdr || isRateSubHdr) {
        if (
          current &&
          ((isProfileSubHdr && current.id.startsWith("profile_")) ||
            (isRateSubHdr && current.id.startsWith("rateprofile_")))
        ) {
          current.lines.push(line);
        }
        continue;
      }

      // "# restore ..." — buffer for footer (do NOT open footer yet; rateprofile
      // sections may still follow in Betaflight 4.5+ format)
      if (nameLower.startsWith("restore")) {
        footerBuffer.push(line);
        continue;
      }

      // "# save configuration" — flush buffer and enter footer
      if (nameLower.startsWith("save config")) {
        openFooter();
        current.lines.push(line);
        continue;
      }

      open(nameLower, name);
      continue;
    }

    if (current) current.lines.push(line);
  }

  flush();

  // Edge case: dump ends without a save command (e.g. truncated or non-standard).
  // Attach any buffered restore lines to an existing footer or create one.
  if (footerBuffer.length > 0) {
    const existingFooter = sections.find((s) => s.id === "footer");
    if (existingFooter) {
      existingFooter.lines.push(...footerBuffer);
    } else {
      sections.push({ id: "footer", title: "Footer", lines: [...footerBuffer] });
    }
  }

  // Extract osd_* settings from master (and any other non-structural section) into
  // a dedicated "osd" section so users can skip or merge OSD layout separately from
  // flight settings. An existing "# osd" section from newer Betaflight dumps is left
  // alone; extracted lines are appended to it if present.
  const osdLines = /** @type {string[]} */ ([]);
  for (const sec of sections) {
    if (sec.id === "header" || sec.id === "footer" || sec.id === "osd") continue;
    const kept = [];
    for (const line of sec.lines) {
      if (/^set\s+osd_/.test(line.trim())) {
        osdLines.push(line);
      } else {
        kept.push(line);
      }
    }
    sec.lines = kept;
  }
  if (osdLines.length > 0) {
    const existing = sections.find((s) => s.id === "osd");
    if (existing) {
      existing.lines.push(...osdLines);
    } else {
      const masterIdx = sections.findIndex((s) => s.id === "master");
      const insertAt = masterIdx !== -1 ? masterIdx + 1 : sections.length;
      sections.splice(insertAt, 0, { id: "osd", title: "OSD", lines: osdLines });
    }
  }

  return sections.filter((s) => s.lines.some((l) => l.trim()));
}

/**
 * Compare two parsed CLI section arrays into a unified diff structure.
 *
 * @param {Array<{id: string, title: string, lines: string[]}>} sectionsA
 * @param {Array<{id: string, title: string, lines: string[]}>} sectionsB
 * @returns {Array<{id: string, title: string, linesA: string[], linesB: string[], status: 'same'|'diff'|'only-a'|'only-b'}>}
 */
export function compareSections(sectionsA, sectionsB) {
  const mapA = new Map(sectionsA.map((s) => [s.id, s]));
  const mapB = new Map(sectionsB.map((s) => [s.id, s]));

  const allIds = [];
  const seen = new Set();

  for (const s of sectionsA) {
    if (!seen.has(s.id)) {
      allIds.push(s.id);
      seen.add(s.id);
    }
  }
  for (const s of sectionsB) {
    if (!seen.has(s.id)) {
      allIds.push(s.id);
      seen.add(s.id);
    }
  }

  // Footer must always render last regardless of which dump introduced extra sections.
  const footerIdx = allIds.indexOf("footer");
  if (footerIdx !== -1 && footerIdx !== allIds.length - 1) {
    allIds.splice(footerIdx, 1);
    allIds.push("footer");
  }

  return allIds.map((id) => {
    const a = mapA.get(id);
    const b = mapB.get(id);
    const source = a ?? b;
    const linesA = a?.lines ?? [];
    const linesB = b?.lines ?? [];

    let status;
    if (!a) status = "only-b";
    else if (!b) status = "only-a";
    else if (linesA.join("\n") === linesB.join("\n")) status = "same";
    else status = "diff";

    return { id, title: source.title, linesA, linesB, status };
  });
}
