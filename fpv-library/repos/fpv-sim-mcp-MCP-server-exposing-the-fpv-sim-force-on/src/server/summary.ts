/*
 * Plain-language summary for compare_configs. Template-generated from the
 * computed statistics — every sentence is backed by a number in the same
 * response, nothing is editorialized.
 */

import type { SweepSummary, PairedComparison, Side } from "../engine/index.js";

const pct = (v: number): string => (v * 100).toFixed(1) + "%";
const pts = (v: number): string => (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + " points";

function variantSentence(label: string, s: SweepSummary): string {
  return `${label}: BLUFOR ${pct(s.win_rates.BLUFOR)}, OPFOR ${pct(s.win_rates.OPFOR)}, stalemate ${pct(s.win_rates.STALEMATE)}` +
    (s.time_to_kill_s ? ` (mean time-to-kill ${s.time_to_kill_s.mean}s over ${s.time_to_kill_s.n} decisive runs)` : "");
}

export function comparisonSummary(
  labelA: string,
  labelB: string,
  a: SweepSummary,
  b: SweepSummary,
  paired: PairedComparison,
): string {
  const lines: string[] = [];
  lines.push(`Paired comparison over ${a.runs} identical seeds. ${variantSentence(labelA, a)}. ${variantSentence(labelB, b)}.`);
  lines.push(
    `Relative to ${labelA}, ${labelB} shifts the BLUFOR win rate by ${pts(paired.blufor_win_rate_delta)}, ` +
    `the OPFOR win rate by ${pts(paired.opfor_win_rate_delta)}, and the stalemate rate by ` +
    `${pts(paired.stalemate_rate_delta)}. ${paired.flips_total} of ${a.runs} seeds changed outcome.`
  );
  for (const side of ["BLUFOR", "OPFOR"] as Side[]) {
    const d = paired.mean_time_to_fix_delta_s[side];
    if (d !== null && Math.abs(d) >= 1) {
      lines.push(
        `${side}'s mean time-to-fix on the enemy GCS ${d < 0 ? "improves" : "worsens"} by ${Math.abs(d)}s under ${labelB}.`
      );
    }
  }
  const dB = paired.blufor_win_rate_delta, dO = paired.opfor_win_rate_delta;
  if (Math.abs(dB) < 0.02 && Math.abs(dO) < 0.02) {
    lines.push("Verdict: no practically meaningful difference between the variants at this sample size.");
  } else {
    const favored = dB > dO ? "BLUFOR" : "OPFOR";
    lines.push(
      `Verdict: ${labelB} favors ${favored} relative to ${labelA}. The mechanism to check in the numbers: the ` +
      `side whose emissions are easier to collect gets fixed sooner (compare each side's time-to-fix and the ` +
      `enemy's LOB accumulation), and the side that is fixed first is usually the one whose GCS dies.`
    );
  }
  return lines.join(" ");
}
