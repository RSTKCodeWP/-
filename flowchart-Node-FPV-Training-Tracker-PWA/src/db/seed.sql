-- =====================
-- TRICKS (Level 1-5)
-- =====================

-- Level 1: Foundation (Month 1)
INSERT OR IGNORE INTO tricks (id, name, level, category, description, indoor_notes, reference_links, prerequisites, phase_introduced) VALUES
(1, 'Clean Roll (Left)', 1, 'roll', 'Right stick full deflection left, return to center at exactly 360°. Practice until 10 consecutive rolls with <5° deviation.', 'Practice at 4-5ft altitude for margin.', '[{"label":"Headmazta: Rolls","url":"https://www.youtube.com/@headmazta"}]', '[]', 1),
(2, 'Clean Roll (Right)', 1, 'roll', 'Right stick full deflection right, return to center at exactly 360°. Same mastery standard as left rolls.', 'Practice at 4-5ft altitude for margin.', '[{"label":"Headmazta: Rolls","url":"https://www.youtube.com/@headmazta"}]', '[]', 1),
(3, 'Clean Flip (Forward)', 1, 'flip-loop', 'Right stick full forward for a 360° pitch rotation.', 'Practice at 4-5ft altitude. Watch for exit drift from contaminated inputs.', '[{"label":"Headmazta: Rolls","url":"https://www.youtube.com/@headmazta"}]', '[]', 1),
(4, 'Clean Flip (Back)', 1, 'flip-loop', 'Right stick full back for a 360° pitch rotation.', 'Practice at 4-5ft altitude.', '[{"label":"Headmazta: Rolls","url":"https://www.youtube.com/@headmazta"}]', '[]', 1),
(5, 'Yaw Spin', 1, 'yaw-spin', 'Left stick full yaw while maintaining altitude and position. Complete 360° ending within 10° of original heading.', '', '[]', '[]', 1),
(6, 'Gap Threading', 1, 'combo', 'Fly through doorways and openings at controlled speed, progressing to knife-edge (90° roll) through narrow gaps.', 'Use your doorways as natural training gates.', '[]', '[]', 1),
(7, 'Coordinated Turn', 1, 'combo', 'Turn using roll, pitch, and yaw simultaneously to maintain altitude and forward velocity without drifting sideways. Mode 2: roll + yaw same direction + slight pitch back.', '', '[]', '[]', 1),
(8, 'Inverted Hang', 1, 'combo', 'Flip inverted at 5-6ft, hold with reduced throttle. Progress from 2s to 5s to 10s. Master: 10s hover with <1ft drift.', 'Center of room. Half-roll to inverted at 4-5ft, hold 1-2s, roll back. Gradually extend.', '[{"label":"Headmazta: Inverted","url":"https://www.youtube.com/@headmazta"}]', '[]', 1),
(9, 'Ceiling Scrape', 1, 'combo', 'Maintain controlled hover <6 inches from ceiling for 10+ seconds. Tests fine throttle control.', 'Bernoulli effect pulls drone upward. If stuck, disarm immediately. Requires 60-80% throttle.', '[]', '[]', 1),
(10, 'Orbit', 1, 'combo', 'Object in room center, orbit at 4-5ft radius at 3ft height. Mode 2: simultaneous roll + opposite yaw + forward pitch.', 'Master 5 clean orbits each direction with object staying center-frame.', '[{"label":"Headmazta: Orbit","url":"https://www.youtube.com/@headmazta"}]', '[]', 1);

-- Level 2: Acro Vocabulary (Months 2-3)
INSERT OR IGNORE INTO tricks (id, name, level, category, description, indoor_notes, reference_links, prerequisites, phase_introduced) VALUES
(11, 'Split-S', 2, 'flip-loop', 'Fly forward at 5-6ft, quick roll to inverted, cut throttle to 0-10%, pull pitch back to arc under into direction change, gradually increase throttle to level out.', 'Indoor: 60-70% throttle blip for ~0.2s before rolling inverted gives upward momentum without ceiling contact. Start at 5ft. Common failure: rolling too slowly.', '[{"label":"Infinity Loops: Split-S","url":"https://www.youtube.com/@infinityloops"},{"label":"Pro Whooper: Split-S","url":"https://prowhooper.com"}]', '[1,2,8]', 1),
(12, 'Power Loop (Indoor)', 2, 'flip-loop', 'Start at 3-4ft altitude. Sharp throttle blip (80-90%, ~0.3s) simultaneous with full pitch-back. Throttle catch at 50-60% on exit.', 'Loop diameter compresses to 3-4ft in standard rooms. Blip and pitch-back must happen at exact same instant. Bi-blade props help with off-throttle momentum.', '[{"label":"Infinity Loops: Power Loop","url":"https://www.youtube.com/@infinityloops"},{"label":"Headmazta: Power Loop","url":"https://www.youtube.com/@headmazta"}]', '[3,4,9]', 1),
(13, 'Power Loop (Outdoor)', 2, 'flip-loop', 'Sustained throttle through a wide arc around objects. Start high (50+ ft) and work down.', 'N/A - outdoor only. Loop must be round, not egg-shaped. Loop a specific object without bailing out.', '[{"label":"Infinity Loops: Power Loop","url":"https://www.youtube.com/@infinityloops"}]', '[12]', 2),
(14, 'Matty Flip', 2, 'flip-loop', 'Fly forward over object, push pitch forward to front flip, cut throttle during flip, hold pitch forward to arc backward under the object.', 'Prerequisite drill: punch-out-and-catch. Start with just the initial flick without completing rotation. Throttle pulse timing is critical at stall point.', '[{"label":"Astrorocketz: Matty Flip","url":"https://www.youtube.com/@astrorocketz"},{"label":"Pro Whooper: Matty Flip","url":"https://prowhooper.com"}]', '[3,8]', 1),
(15, 'Immelmann Turn', 2, 'flip-loop', 'Half loop upward + 180° roll at top to level out. Gains altitude while reversing direction.', 'Pitch back to initiate half-loop, blip throttle through climb, roll 180° at apex.', '[]', '[3,4,1,2]', 2);

-- Level 2-3: Rewinds
INSERT OR IGNORE INTO tricks (id, name, level, category, description, indoor_notes, reference_links, prerequisites, phase_introduced) VALUES
(16, 'Stall Flip Rewind', 2, 'recovery', 'Punch up, half-flip to inverted, stall, then reverse the flip to return upright. The undo button of freestyle.', '', '[{"label":"Pro Whooper: Rewind","url":"https://prowhooper.com"}]', '[3,4]', 2),
(17, 'Side Rewind', 3, 'recovery', 'Roll left ~180°, snap to full right roll, add opposite yaw during reversal, blip throttle to maintain altitude.', '', '[{"label":"Pro Whooper: Rewind","url":"https://prowhooper.com"}]', '[1,2,5]', 3),
(18, 'Stall Rewind with Yaw', 3, 'recovery', 'Fly up, stall, 360° yaw spin at apex (zero throttle), fall back through entry path.', '', '[]', '[5,16]', 3);

-- Level 3: Multi-axis (Months 4-5)
INSERT OR IGNORE INTO tricks (id, name, level, category, description, indoor_notes, reference_links, prerequisites, phase_introduced) VALUES
(19, 'Trippy Spin', 3, 'combo', 'Simultaneous pitch-back and roll input (right stick to bottom-left or bottom-right corner) while modulating throttle 30-70%. Corkscrew path.', 'Easier to learn on 3-inch. Start at high altitude with 50% pitch-back and 50% roll for one rotation.', '[{"label":"Headmazta: Trippy Spin","url":"https://www.youtube.com/@headmazta"},{"label":"Pro Whooper: Trippy Spin","url":"https://prowhooper.com"}]', '[1,2,3,4]', 2),
(20, 'Inverted Yaw Spin', 3, 'yaw-spin', 'Roll inverted, full yaw input while managing inverted throttle, roll back upright. Combination of yaw and roll to spin on a line.', '', '[]', '[8,5]', 3),
(21, 'Rubik''s Cube', 3, 'combo', 'Pitch forward 180° → full roll 360° → pitch forward 180°. Cube-like tumbling pattern.', '', '[]', '[1,2,3,4]', 3),
(22, 'Juicy Flick', 3, 'combo', 'Fast pitch forward to flip inverted → brief inverted hang → continue flip back upright. Like Matty Flip but faster and snappier.', '', '[]', '[14,8]', 3);

-- Level 4: Technical freestyle (Months 5-6)
INSERT OR IGNORE INTO tricks (id, name, level, category, description, indoor_notes, reference_links, prerequisites, phase_introduced) VALUES
(23, 'Stall Rewind (Advanced)', 4, 'recovery', 'Fly under object, punch up, 180° spin, fall back through gap. Precise throttle timing to stall at exactly right height.', '', '[]', '[16,18]', 3),
(24, 'Powerloop-Dive Combo', 4, 'combo', 'Powerloop around an object then immediately dive through a gap below it without pause. Where flow and tricks merge.', '', '[]', '[13,6]', 3);

-- Level 5: Aspirational (IGOW competition)
INSERT OR IGNORE INTO tricks (id, name, level, category, description, indoor_notes, reference_links, prerequisites, phase_introduced) VALUES
(25, 'Hamhook', 5, 'combo', '½ front flip to inverted → 180° inverted yaw spin → pitch back to sweep under obstacle.', '', '[]', '[20,14]', 4),
(26, 'Rodeo 7', 5, 'combo', 'Backflip + 360° yaw spin blended for 720° total rotation. Typically off a jump or over an object.', '', '[]', '[4,5]', 4),
(27, 'McTwist', 5, 'combo', 'Corked rotation combining diagonal flip and yaw.', '', '[]', '[19,5]', 4),
(28, 'Sbang Sequence', 5, 'combo', 'Multiple wall-taps chained together. Requires blind flying.', '', '[]', '[23]', 4),
(29, 'Kururi', 5, 'combo', 'Complex multi-axis spin requiring blind flying and muscle memory.', '', '[]', '[21,20]', 4);

-- =====================
-- DRILLS
-- =====================
INSERT OR IGNORE INTO drills (id, name, description, mastery_criteria, related_tricks, space_required) VALUES
(1, 'Double-Door Figure-8 Flow', 'Two reference objects 8ft apart or use doorways as natural gates. Fly figure-8s at 3-4ft height in both directions with height variations at 2, 4, and 6ft.', 'Variance of <2 seconds across 10 consecutive laps. This is your primary indoor progress metric.', '[7,6]', 'indoor-large'),
(2, 'Orbit Drill', 'Object in room center, orbit at 4-5ft radius at 3ft height. Mode 2: simultaneous roll + opposite yaw + forward pitch.', '5 clean orbits each direction with object staying center-frame, then inverted orbits.', '[10]', 'indoor-large'),
(3, 'Punch-Out and Catch', 'From 2ft, punch to ~6ft (within ceiling margin), cut throttle, catch before dropping below 3ft.', 'Consistent catch within 1ft of target altitude with no oscillation on recovery.', '[12,14]', 'indoor-small'),
(4, 'Ceiling Scrape', 'Maintain controlled hover <6 inches from ceiling for 10+ seconds.', 'Hold position for 10 seconds without touching ceiling.', '[9,12]', 'indoor-small'),
(5, 'Inverted Hang Practice', 'Center of room, flip inverted at 5-6ft, hold with reduced throttle. Progress from 2s to 5s to 10s.', '10-second inverted hover with <1ft drift in any direction.', '[8,11,14]', 'indoor-small'),
(6, 'Doorway Gap Threading', 'Practice entering and exiting doorways at different angles and speeds, progressing to knife-edge passes.', '20 consecutive passes without touching the frame.', '[6]', 'indoor-large'),
(7, 'Wall Proximity Flying', 'Fly along 20ft wall at 3ft height, starting at 3ft distance. Decrease to 2ft, 1ft, 6 inches. Both directions.', 'Consistent passes at 6-inch distance without wall contact.', '[7]', 'indoor-large'),
(8, 'IGOW Line Pressure', 'Plan a continuous line of 4 specific tricks. If you miss any element, land and restart.', 'Complete the planned 4-trick line 2 out of 5 attempts.', '[11,12,14]', 'outdoor-open');

-- =====================
-- GATE CHECKS
-- =====================

-- Phase 1 -> 2
INSERT OR IGNORE INTO gate_checks (id, phase, item_text, is_hard_gate, sort_order) VALUES
(1,  1, 'Clean rolls and flips both directions with 70%+ consistent exit planes', 1, 1),
(2,  1, 'Hold inverted hover for 5+ seconds with <1ft drift', 1, 2),
(3,  1, 'Land a split-S indoors 3 out of 5 attempts', 1, 3),
(4,  1, 'Land a power loop indoors 3 out of 5 attempts', 1, 4),
(5,  1, 'Figure-8 10-lap variance <2 seconds', 1, 5),
(6,  1, 'Thread gaps <3ft wide consistently', 0, 6),
(7,  1, 'Ceiling scrape hold 10 seconds', 0, 7),
(8,  1, '15+ hours combined sim and real acro time', 0, 8);

-- Phase 2 -> 3
INSERT OR IGNORE INTO gate_checks (id, phase, item_text, is_hard_gate, sort_order) VALUES
(9,  2, '5+ outdoor packs on 5-inch without uncontrolled crashes', 1, 1),
(10, 2, 'Clean rolls, flips, and split-S at safe altitude', 1, 2),
(11, 2, 'Maintain orientation after tricks (no post-trick lost in space)', 1, 3),
(12, 2, 'Fly in 8-10 mph wind with confidence', 1, 4),
(13, 2, 'Comfortably fly within 10ft of a large object', 1, 5),
(14, 2, 'Land smoothly and consistently', 0, 6),
(15, 2, 'Complete at least one power loop (even wide and high)', 0, 7);

-- Phase 3 -> 4
INSERT OR IGNORE INTO gate_checks (id, phase, item_text, is_hard_gate, sort_order) VALUES
(16, 3, '3-trick combo with smooth transitions, no obvious pause 3/5 attempts', 1, 1),
(17, 3, 'Adapt flight lines to new location within 2-3 packs', 0, 2),
(18, 3, '5+ trick repertoire executed reliably at 70%+', 1, 3),
(19, 3, 'DVR reviewed every session', 1, 4),
(20, 3, 'Fly comfortably in 10-15 mph wind on 5-inch', 0, 5),
(21, 3, 'Flown at 3+ different locations', 0, 6);

-- Phase 4 (Final Exam)
INSERT OR IGNORE INTO gate_checks (id, phase, item_text, is_hard_gate, sort_order) VALUES
(22, 4, '45-sec continuous line with flow + vertical + technical + recovery element', 1, 1),
(23, 4, 'No ground touches during final line', 1, 2),
(24, 4, 'Smooth throttle management (no audible pumping)', 1, 3),
(25, 4, 'Denver flying locations scouted', 1, 4),
(26, 4, 'Spares packed for travel', 0, 5);

-- Initialize gate_progress for all gates
INSERT OR IGNORE INTO gate_progress (gate_check_id, met, date_met)
SELECT id, 0, NULL FROM gate_checks;

-- =====================
-- DENVER PREP CHECKLIST
-- =====================
INSERT OR IGNORE INTO denver_items (id, category, text, sort_order) VALUES
(1,  'locations', 'Scout Chatfield State Park model airfield (south of Denver)', 1),
(2,  'locations', 'Find private property options outside city park jurisdiction', 2),
(3,  'locations', 'Check areas outside Denver city limits', 3),
(4,  'locations', 'Identify hotel room for whoop flying', 4),
(5,  'legal', 'TRUST test completion proof printed/saved', 1),
(6,  'legal', 'FAA registration for >250g quads', 2),
(7,  'legal', 'B4UFLY app installed and tested', 3),
(8,  'legal', 'Check LAANC authorization for DEN Class B airspace', 4),
(9,  'legal', 'Check Centennial Airport (APA) Class D airspace', 5),
(10, 'equipment', 'Pack spare frames (4-8)', 1),
(11, 'equipment', 'Pack spare props (20+, mixed 2 and 3-blade)', 2),
(12, 'equipment', 'Pack spare batteries (6-10 x 1S 300mAh BT2.0)', 3),
(13, 'equipment', 'Pack spare motors (2+)', 4),
(14, 'equipment', 'BT2.0 pigtails packed', 5),
(15, 'equipment', 'Test ELRS link in urban RF environment', 6),
(16, 'equipment', 'Verify DJI O4 video in RF-noisy area', 7),
(17, 'logistics', 'Spotter arranged for outdoor flights', 1),
(18, 'logistics', 'Battery charging solution for travel', 2),
(19, 'logistics', 'Toolkit packed (soldering iron, hex keys, spare screws)', 3);

-- =====================
-- RESOURCES
-- =====================
INSERT OR IGNORE INTO resources (id, name, type, url, description) VALUES
(1,  'Headmazta', 'youtube', 'https://www.youtube.com/@headmazta', 'No Talking Trick Tutorials (NTTT) - rolls, inverted, orbits, power loops with stick input visualization'),
(2,  'Infinity Loops', 'youtube', 'https://www.youtube.com/@infinityloops', 'Whooptorial Wednesday - split-S, power loops, trippy spins, wall taps with stick overlays'),
(3,  'Pro Whooper', 'website', 'https://prowhooper.com', '90+ trick tricktionary, 10-week Freestyle Boot Camp, IGOW competition framework'),
(4,  'Joshua Bardwell', 'youtube', 'https://www.youtube.com/@joshuabardwell', 'Betaflight configuration, build tutorials, troubleshooting, rate tuning'),
(5,  'Oscar Liang', 'website', 'https://oscarliang.com', 'PID tuning, Blackbox analysis, stick overlay tutorials, whoop-specific settings'),
(6,  'Mr. Steele', 'youtube', 'https://www.youtube.com/@mrsteele', 'Consistency philosophy and proximity flying principles'),
(7,  'Skitzo', 'youtube', 'https://www.youtube.com/@skitzo', 'Understanding flow at the highest level'),
(8,  'Le Drib', 'youtube', 'https://www.youtube.com/@ledrib', 'Creative freestyle and competition-style flow'),
(9,  'GAPiT FPV', 'youtube', 'https://www.youtube.com/@gapitfpv', 'Dramatic pauses and backtracking technique'),
(10, 'Astrorocketz', 'youtube', 'https://www.youtube.com/@astrorocketz', 'Matty flip progression tutorials'),
(11, 'FPVFrenzy', 'website', 'https://fpvfrenzy.com', 'Lessons in Flow article - must-read on flow theory'),
(12, 'GetFPV Learn', 'website', 'https://www.getfpv.com/learn', 'Psychology at events, general FPV education'),
(13, 'FPV Mastery', 'website', 'https://fpvmastery.com', '10+ hours step-by-step video, mindful training approach, live coaching'),
(14, 'FPV Unlocked', 'website', 'https://fpvunlocked.com', '30-day structured curriculum'),
(15, 'B4UFLY', 'app', 'https://www.faa.gov/uas/getting_started/b4ufly', 'FAA airspace restriction checking'),
(16, 'AirMap', 'app', 'https://www.airmap.com', 'Airspace and LAANC authorization'),
(17, 'UAV Forecast', 'app', 'https://www.uavforecast.com', 'Weather and flying conditions forecast'),
(18, 'Blackbox Explorer', 'tool', 'https://github.com/betaflight/blackbox-log-viewer', 'Web-based Blackbox log viewing'),
(19, 'PIDtoolbox', 'tool', 'https://github.com/bw1129/PIDtoolbox', 'Deep Blackbox analysis - spectral noise and step response'),
(20, 'VelociDrone', 'sim', 'https://www.velocidrone.com', 'Primary sim ($20) - integrates Betaflight directly for 1:1 rate/PID matching'),
(21, 'Liftoff: Micro Drones', 'sim', 'https://store.steampowered.com/app/1344460/Liftoff_Micro_Drones/', 'Whoop-class physics with indoor environments ($6)'),
(22, 'TRYP FPV', 'sim', 'https://store.steampowered.com/app/1534870/TRYP_FPV/', 'Best freestyle-specific environments with photorealistic locations ($15)'),
(23, 'IntoFPV Forum', 'community', 'https://intofpv.com', 'Active trick discussions and DVR review threads'),
(24, 'r/fpv', 'community', 'https://www.reddit.com/r/fpv', 'Reddit FPV community for feedback'),
(25, 'r/TinyWhoop', 'community', 'https://www.reddit.com/r/TinyWhoop', 'Reddit whoop-specific community'),
(26, 'MultiGP', 'community', 'https://www.multigp.com', 'Local racing/freestyle groups and events near Denver');

-- =====================
-- WEEK SCHEDULE (20 weeks)
-- =====================

-- Phase 1: Indoor acro tricks (Weeks 1-6)
INSERT OR IGNORE INTO week_schedule (id, week_number, phase, primary_drills, target, sim_focus, go_nogo) VALUES
(1, 1, 1, 'Pure-axis rolls (L and R), pure-axis flips (fwd and back), figure-8 flow drill, ceiling scrape', '5-6 sessions, 3 packs each', 'Rolls and flips at altitude with stick overlay on. Inverted hover attempts.', '50%+ clean roll exits both directions. 10-lap figure-8 time recorded as baseline.'),
(2, 2, 1, 'Pure-axis rolls/flips (consistency push), inverted hang (2→5 sec), orbit drill, gap threading', '5-6 sessions, 3 packs each', 'Inverted hover hold target: 10 sec. Slow-rate flips (300-400°/s) tracking horizon.', '70%+ clean roll/flip exits. Inverted hang 3+ sec real, 10+ sec sim. 5 clean orbits each direction.'),
(3, 3, 1, 'Split-S technique (start at 5ft), punch-out-and-catch, inverted hang (extend to 5+ sec)', '5-6 sessions, 3 packs each', 'Split-S at safe altitude—land 5 in a row before attempting real. Inverted yaw turns.', 'First real split-S attempts. Punch-out catch within 1ft of target. Inverted hang 5 sec real.'),
(4, 4, 1, 'Split-S (consistency), power loop technique (start in sim, transfer to real), ceiling scrape refinement', '5-6 sessions, 3 packs each', 'Power loops—sim until you land 5 consecutive. Focus on simultaneous blip + pitch-back timing.', 'Split-S 2/5 success rate real. First real power loop attempts. Ceiling scrape 10 sec hold.'),
(5, 5, 1, 'Power loop (consistency push), split-S + cruise combos, matty flip intro (initial flick only), punch-out-and-catch', '5-6 sessions, 3 packs each', 'Full matty flips at altitude. Power loops around sim objects. 2-trick lines: split-S → cruise → power loop.', 'Split-S 3/5. Power loop 2/5. Matty flip: can execute initial flick and recover.'),
(6, 6, 1, 'Power loop + split-S consistency, matty flip full attempts, 2-trick linking, wall proximity', '5-6 sessions, 3 packs each', 'Matty flips around objects. 3-trick sim lines. Rewind introduction.', 'PHASE 1 GATE: Split-S 3/5. Power loop 3/5. Inverted hang 5 sec. Figure-8 variance <2s. Rolls/flips 70%+ clean.');

-- Phase 2: Outdoor transition (Weeks 7-14)
INSERT OR IGNORE INTO week_schedule (id, week_number, phase, primary_drills, target, sim_focus, go_nogo) VALUES
(7, 7, 2, 'First outdoor flights: 75mm whoop, open field, no obstacles. Forward flight, banking turns, figure-8s around single object.', '4-5 sessions, 6-8 packs each', '5-inch sim profile: hover practice, forward flight, gentle turns. Get comfortable with momentum.', 'Completed 3+ outdoor sessions. Can maintain orientation at 10-20ft altitude. No panicked disarms.'),
(8, 8, 2, 'Outdoor whoop: rolls/flips at 30+ ft altitude, split-S in open air, begin orbiting objects. Continue indoor whoop for trick maintenance.', '5-6 sessions mixed indoor/outdoor', '5-inch sim: rolls and flips at altitude. Split-S with forward exit momentum.', 'Outdoor rolls/flips 50%+ clean. Outdoor split-S attempted. Indoor tricks maintained.'),
(9, 9, 2, 'Introduce 3-inch (Rekon3 Nano): hover, forward flight, banking. Note inertia difference. Outdoor whoop: power loops at 40+ ft.', '5-6 sessions, split whoop and 3-inch', '5-inch sim: power loops at altitude. Matty flips. Propwash recovery (fly forward through descents).', '3-inch: comfortable hover and forward flight. Outdoor whoop power loop attempted.'),
(10, 10, 2, '3-inch: rolls, flips, split-S at 50+ ft. Begin gentle wind days (5-8 mph). Outdoor whoop: matty flip attempts at safe altitude.', '5-6 sessions', '5-inch sim: wind enabled. Practice maintaining lines in turbulence. Trippy spin introduction.', '3-inch: rolls and flips 50%+ clean. Flown in 5+ mph wind.'),
(11, 11, 2, 'Maiden 5-inch build. Hover test, throttle limit 70%. Gentle forward flight. Rolls at 80+ ft altitude. Continue 3-inch for trick practice.', '4-5 sessions, prioritize 5-inch maiden + 3-inch', '5-inch sim: match your real build rates/PIDs. Practice exact maneuvers you will attempt real.', '5-inch: successful maiden. Comfortable hover. Forward flight with banking turns.'),
(12, 12, 2, '5-inch: rolls, flips, split-S at 60+ ft. Start 15-20° camera angle. 3-inch: power loops around objects, proximity introduction.', '5-6 sessions, split 5-inch and 3-inch', 'Trippy spin practice. Rewind technique. 5-inch flow lines in sim.', '5-inch: clean rolls/flips. Split-S attempted. 3-inch: power loop around an object.'),
(13, 13, 2, '5-inch: power loops (wide, high), proximity within 10-20ft of objects. Fly all three sizes in one session. Wind up to 10-12 mph on 5-inch.', '5-6 sessions', 'Matty flip and rewind combos. 2-3 trick lines around sim objects.', '5-inch: power loop attempted. Comfortable in 8-10 mph wind. Flies all three sizes.'),
(14, 14, 2, '5-inch: split-S, power loops, basic proximity. Begin 2-trick sequences. 3-inch: matty flip, trippy spin attempts.', '5-6 sessions', '3-4 trick flow lines. Inverted yaw spin. Juicy flick.', 'PHASE 2 GATE: 5-inch 5+ packs no crashes. Clean rolls/flips/split-S at altitude. Power loop landed. 8-10 mph wind. Proximity within 10ft.');

-- Phase 3: Flow and lines (Weeks 15-18)
INSERT OR IGNORE INTO week_schedule (id, week_number, phase, primary_drills, target, sim_focus, go_nogo) VALUES
(15, 15, 3, '5-inch: 2-trick combos (power loop → split-S, split-S → matty flip). Fly a new location. Eliminate pauses between tricks.', '5-6 sessions, minimum 2 locations', '4-5 trick flow lines. Practice exit of trick A = entry of trick B transitions.', '2-trick combos with smooth transitions. Flown at 2+ locations.'),
(16, 16, 3, '3-trick lines. Throttle-controlled hang time practice. Trippy spin on 3-inch/5-inch. Rewinds as flow recovery. Explore a third location.', '5-6 sessions, minimum 3 locations total', '5-trick lines. Rubik''s cube. Inverted yaw spin.', '3-trick combo landed on video. Trippy spin 30%+ success.'),
(17, 17, 3, 'Extend to 4-trick lines. Vary tempo (fast → slow → fast). IGOW line drill: plan 4 tricks, restart if you miss one. Fly in 10-15 mph wind.', '5-6 sessions', 'Long flow lines (60+ seconds). Practice reading new sim environments quickly.', '4-trick line on video. IGOW line completed 2/5 attempts. Comfortable 10-15 mph.'),
(18, 18, 3, 'Polish and consolidate. DVR review every session. Film best line attempts. Build go-to 3-trick combo at 80%+. Fly 4th location.', '5-6 sessions, 4+ total locations', 'Refine weakest trick. Practice pressure: one take lines with restart penalty.', 'PHASE 3 GATE: 3-trick combo smooth 3/5. 5+ trick repertoire at 70%+. DVR reviewed. 3+ locations. 10-15 mph wind comfortable.');

-- Phase 4: Denver confidence (Weeks 19-20)
INSERT OR IGNORE INTO week_schedule (id, week_number, phase, primary_drills, target, sim_focus, go_nogo) VALUES
(19, 19, 4, 'Polish go-to combos. Practice warm-up → show cycle: 1-2 easy packs then attempt best line. Film everything. Fly for an audience. Indoor whoop to stay sharp.', '5-6 sessions', 'Final exam line practice: flow → vertical → technical → recovery, 45 sec continuous.', 'Go-to combo lands 4/5 attempts. Flown for at least one spectator.'),
(20, 20, 4, 'Scout Denver locations (Chatfield, private property). Test ELRS in urban RF. Hotel whoop sessions. Pack spares. Final exam line attempts.', 'Travel-dependent', 'Final polish. Visualize Denver lines.', 'PHASE 4 GATE: 45-sec continuous line with flow + vertical + technical + recovery. No ground touches, smooth throttle. Locations scouted. Spares packed.');
