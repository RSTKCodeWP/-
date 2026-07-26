/*
 * describe_model payload: the modeling assumptions an agent needs in order
 * to reason about what conclusions the simulation can and cannot support.
 * Content is drawn from the original sim's DESIGN_NOTES.md and the inline
 * modeling comments preserved in the engine source.
 */

export const MODEL_DESCRIPTION = {
  overview:
    "Force-on-force engagement between two symmetric teams on a 4000 m x 4000 m notional jungle/coastal box " +
    "(AO KATANA). Each team fields one ground control station (GCS, the target), two passive counter-UAS RF " +
    "direction-finding nodes, and one armed FPV sUAS. Teams hunt each other's GCS by its RF emissions: LOBs " +
    "accumulate into a geolocation fix, the drone dashes to the fix and strikes. Destroying the enemy GCS severs " +
    "their drone's C2 link (it crashes shortly after), which is why the GCS is the win condition. The one " +
    "asymmetry in the default configuration is EMCON posture: BLUFOR keys intermittently, OPFOR nearly " +
    "continuously. All data is notional and unclassified.",

  determinism:
    "All randomness draws from a single seeded mulberry32 stream (terrain uses separate streams derived from the " +
    "same seed). Fixed 0.1 s physics ticks; DF scans every 1.5 s. Identical (seed, config_overrides) inputs " +
    "reproduce the identical engagement, tick for tick — verified against the original browser implementation by " +
    "golden-master tests (see DESIGN_NOTES.md of this project).",

  terrain:
    "Seeded value-noise elevation (three octaves shaped into low jungle hills with a ridge spine, an eastern " +
    "coastline and a northeast bay) plus a separate canopy-density field cut by six clearings and one east-west " +
    "trail. Both are bilinearly sampled 200x200 grids. Terrain affects the engagement only through RF propagation " +
    "and emplacement (units nudge west out of water); drones do not collide with terrain.",

  rf_propagation:
    "pathAtten() samples 14 points along the sensor-to-emitter sight line. Terrain above the line of sight adds " +
    "heavy but not absolute blocking (diffraction is the stated reason blocking saturates rather than going " +
    "binary); segments where the ray is within canopy height (18 m) of the ground accumulate soft vegetation loss " +
    "proportional to canopy density. The result (0 = clean line of sight, capped at 6) multiplies detection " +
    "probability via exp(-att) and inflates bearing error. Frequency references in the event log (915 MHz, " +
    "5.8 GHz) are cosmetic flavor, not a link budget.",

  df_collection: {
    scan_model:
      "Every SCAN_S seconds each side's two nodes roll independent per-scan detection against every active enemy " +
      "emitter within MAX_RANGE_M. Base probabilities: P_DETECT_UL (0.40) against the C2 uplink, P_DETECT_DL " +
      "(0.65) against the FPV video downlink, both scaled down by range and by exp(-attenuation).",
    bearing_error_model:
      "A successful uplink intercept appends a line of bearing with gaussian noise: sigma = BRG_SIGMA_DEG " +
      "(4.0 deg, 1-sigma) inflated by path attenuation as sigma * (1 + 0.5 * att). LOBs are capped at MAX_MEAS " +
      "(140) FIFO per collection effort.",
    downlink_tracks:
      "Video downlink intercepts do NOT feed the GCS fix; they produce a noisy position track of the enemy air " +
      "vehicle (55 m gaussian noise per axis) — situational awareness that the enemy bird is airborne.",
  },

  fix_estimation: {
    solver:
      "Weighted least squares over all held LOBs. Measurement model: perpendicular offset from each bearing line, " +
      "noise sigma_perp = sigma_bearing * range, weight 1/sigma_perp^2. Two iterations (weights depend on range to " +
      "the answer). Covariance = residual-inflated inverse normal matrix: scaled by max(1, chi2/(n-2)) so a " +
      "small-sample geometry cannot report an optimistic ellipse. CEP ~= 0.59*(sigma1+sigma2), floored at " +
      "CEP_FLOOR_M (35 m).",
    quality_gates: [
      "Participation gate: no solve until MIN_LOBS_SOLVE (6) LOBs exist AND the second-strongest collector holds " +
      "MIN_LOBS_2ND (3) of them. Defends against single-sensor solutions whose along-range position slides freely.",
      "Geometry penalty: the crossing angle between the two strongest collectors' mean bearings and the balance " +
      "of their LOB counts divide into the CEP — a shallow-cut or lopsided fix reports a proportionally worse CEP.",
      "Jitter penalty: the last 6 solutions are kept; if the estimate is still wandering (RMS scatter), the " +
      "effective CEP cannot be small yet. Effective CEP = max(formal, geometry-penalized, jitter).",
    ],
    thresholds:
      "FIX ESTABLISHED at >= MIN_LOBS_FIX (10) LOBs and CEP < FIX_CEP_M (240 m). Attack commit at >= " +
      "MIN_LOBS_COMMIT (12) LOBs and CEP < COMMIT_CEP_M (120 m), or a bingo-fuel final push at <= PUSH_BATT_PCT " +
      "(45%) battery accepting CEP < PUSH_CEP_M (260 m).",
  },

  drone_behavior:
    "Finite-state machine: STANDBY -> TRANSIT -> HOLD -> COMMIT -> TERMINAL -> IMPACT, with LINK LOST -> DOWN " +
    "when the team's own GCS dies and DOWN on battery exhaustion. Launch at launchT; fly to a holding point " +
    "HOLD_STANDOFF_M forward of own GCS toward the named area of interest; orbit at LOITER_MPS with a 0.62x " +
    "battery drain while the ground nodes build the fix; dash at DASH_MPS on commit; inside 380 m of the estimate " +
    "descend below canopy at TERMINAL_MPS; visually acquire the real GCS within ACQ_RANGE_M (220 m); if the drone " +
    "reaches the fix point without acquiring, it flies an expanding search growing TERMINAL_SEARCH_GROW m/s — a " +
    "modest fix error is recovered quickly, a gross one burns the battery. Steering is a turn-rate-limited " +
    "heading controller with rate-limited speed and climb; movement is dead reckoning per 0.1 s tick.",

  emcon_model:
    "Each team's C2 uplink and video downlink follow on/off duty cycles with a per-seed random phase offset. A " +
    "team is only collectable while an emitter is keyed. videoOff = 0 means continuous video downlink (the big " +
    "giveaway: P_DETECT_DL 0.65 vs P_DETECT_UL 0.40). Exception: during COMMIT and TERMINAL the attacker needs " +
    "eyes on, so video forces on regardless of posture — even the disciplined side becomes loud in the endgame. " +
    "The teaching point of the default configuration: the side that transmits less is harder to fix.",

  outcomes:
    "BLUFOR or OPFOR win by destroying the enemy GCS (reason gcs_destroyed). Headless runs additionally end in " +
    "STALEMATE when both drones are down (no future state change is possible) or at the sim-time cap (3600 s). " +
    "Roughly 30% of random seeds are genuine stalemates under the honest estimator: disciplined emissions plus " +
    "imperfect DF geometry legitimately deny a fix. That rate is a finding of the original development, not a bug.",

  known_simplifications: [
    "No jamming, spoofing, or kinetic counter-fire against the drones — the cUAS side is sense-only; the counter comes from the friendly FPV strike.",
    "Frequency references (915 MHz, 5.8 GHz) are cosmetic log flavor, not an RF link budget; propagation is the geometric attenuation model above.",
    "One drone per side, one sortie, no reloads or battery swaps.",
    "DF nodes are omniscient about signal identity (no false correlation between the two enemy emitter types, no clutter/ambient emitters).",
    "Flat-earth geometry within the 4 km box; bearings are planar.",
  ],

  validity_notes:
    "Numbers are plausible-magnitude fiction shaped by doctrine, not measured data. The simulation supports " +
    "qualitative conclusions about the detect-fix-commit-strike timeline and the relative effect of EMCON " +
    "posture, collection rate, and fix-gate aggressiveness. It does not support absolute performance claims " +
    "about any real system.",
} as const;
