FPVibe — Federation Spec & Implementation Brief
Status: v0.3 · SUPERSEDED — retained for historical reference only

> ⚠️ **This spec is superseded by ARCHITECTURE.md v1.0 (and its companion API-CONTRACT.md).**
> The git-substrate model described here (YAML-in-git, commit-on-save, `fpv:` URN scheme,
> resolver service, forward-auth, meta-compose) was replaced by per-tool SQLite databases
> federated via read-only JSON APIs. Do not implement from this document.
> See ARCHITECTURE.md §2 for a summary of what changed and what survived.

Audience: a Claude Code session that has previously worked on flowchart, plus Cori. Purpose: define a small federation of single-purpose FPV tools ("FPVibe"), and brief the implementing agent on how to decompose the existing flowchart work into it.


________________


Read me first (for the implementing agent)
You've worked on flowchart before. This document introduces something you have not seen: FPVibe, an umbrella under which flowchart becomes one of several small, independent tools rather than a single growing app. FPVibe was scoped in a separate planning conversation; everything you need is in this file — do not assume prior knowledge of FPVibe itself.


Your job is not to build a platform. It's to (1) stand up a shared, git-based data substrate, (2) migrate existing flowchart content into it, and (3) scaffold two small tools (fpvibe-fleet, fpvibe-sessions) that conform to the conventions below. Spots and training are deliberately not their own tools yet.


Several modeling calls are reasonable defaults, not settled facts. They are collected in §13 Decisions to confirm. Surface those with Cori before any destructive restructuring of existing flowchart content.


________________


1. TL;DR
* Build a federation, not a monolith: separate single-purpose tools unified by shared conventions, a shared auth boundary, and a meta-compose. Modeled on how DumbWare standardizes its apps.
* flowchart was never one tool — it's a personal KB spanning fleet, flight logs, locations, and training. Decompose it.
* Canonical data lives as text in git (the substrate). Tools are views/editors over it; "the commit is the interface."
* First real tools: fpvibe-fleet (what you own and fly) and fpvibe-sessions (the append-per-flight log, the relational hub). fpvibe-inventory and fpvibe-tune also conform.
* Spots and training start as substrate entities surfaced inside sessions, and get promoted to their own tools only when a concrete trigger fires.
* Integration is "tools agree on IDs, the link scheme, and the auth boundary" — never "they're the same binary."


________________


2. Why a federation (constraints that follow)
DumbWare isn't one app; it's a stack of single-purpose tools (DumbPad, DumbKan, DumbAssets…), each its own repo and container, unified by conventions, a shared auth piece, and a meta-compose. FPVibe is that.


Why it matters for the choices you'll make:


* Contained blast radius — a botched migration in one tool can't take down another.
* Independent shippability — each tool boots, deploys, and fails on its own.
* Native bolt-ons — a new tool joins by conforming, not by being merged into a codebase.


Non-goals (do not do these): no monolith; no plugin framework; no shared "platform" library beyond theme tokens + a tiny link resolver; no tool that can't boot when a sibling is down; don't platformize before three tools conform to this doc.


________________


3. Canonical entities (the nouns)
All nouns live in the substrate regardless of how many tools exist. Authority = the tool allowed to write that noun.


Noun
	What it is
	Authority
	Craft
	A flyable aircraft in the fleet — DIY or commercial. The thing a session is flown with.
	fleet
	Build
	The assembled-from-parts facet of a Craft: its BOM + build log. A facet of Craft, not a separate file (see §13.1). Ties to inventory via the BOM.
	fleet
	Part
	An inventory item, usually a fungible quantity (motors by size/KV, FCs, props, consumables).
	inventory
	Gear
	A discrete, serial/warranty-bearing asset (commercial craft, radios, goggles, printer, CNC). The DumbAssets-shaped slice.
	inventory
	Session
	A flight outing: date, craft, spot, batteries, conditions, drills worked, links to blackbox/DVR.
	sessions
	Spot
	A flying location + airspace/compliance metadata.
	sessions → promote
	Training plan / Drill
	A structured practice progression (e.g. IGOW6 Ch1, power-loop recovery, orbits).
	sessions → promote
	

Key relationships:


* Session is the hub. A session is the join row tying craft + spot + drill + battery + logs together — the relational heart of the flying side, and the reason it's its own tool rather than living inside fleet. It's also where the blackbox workflow plugs in (a session references the .bbl it produced).
* Craft ⊇ Build. A self-built whoop is craft with a bom (a "build"). A commercial DJI Neo 2 is craft with a gear link and no bom.
* Build ⇄ Part is the only tight coupling. A BOM is "this craft consumes these parts × quantities." Inventory reads every craft's BOM to compute allocated-vs-free.


________________


4. The substrate (single source of truth)
Canonical records are text in git. Tools are views and editors; web tools commit-on-save. Derived/runtime/cache state (rendered thumbnails, blackbox parse caches, sessions) is app-local and disposable. Only the gear/warranty view may keep a private JSON store — and even then it exports a git-tracked snapshot that everyone else reads.
Proposed layout
fpvibe-data/                 # substrate repo (or a directory inside cori/me — see §13.4)


  FPVIBE.md                  # this document — the constitution


  fpvibe.config.yaml         # resolver map (URN type -> tool base URL) + palette


  SCHEMA.md                  # entity field reference + templates


  fleet/


    craft/                   # one file per aircraft; BOM + build log embedded when self-built


  inventory/


    parts.md                 # split to parts/<id>.md only if diffs get noisy


    gear.md                  # discrete serial/warranty assets


  sessions/


    2026/                    # year-bucketed flight logs


    spots/                   # promote to top-level fpvibe-spots when trigger fires (§4 / §12)


    training/                # promote to top-level fpvibe-training when trigger fires
Record format
YAML frontmatter + markdown body. Diffable, hand-editable, trivially parseable.


Craft — fleet/craft/lionbee.md (self-built; note embedded bom):


---


id: c-lionbee


type: craft


name: LionBee


class: whoop          # whoop | micro | cinewhoop | 5inch | longrange | commercial


status: flying        # flying | grounded | wip | retired


gear: null            # link to a g-#### record if serial/warranty-tracked


bom:                  # presence of bom == this craft is a "build"


  - { part: p-0007, qty: 4, role: motors }


  - { part: p-0031, qty: 1, role: fc-aio }


tune: DAILYRIP        # optional pointer to a rate/PID profile


acquired: 2025-09


---


Build log, soldering notes, mods, known issues.


Craft — commercial example (no bom, has gear):


---


id: c-neo2


type: craft


name: DJI Neo 2


class: commercial


status: flying


gear: g-0004


bom: null


---


Session — sessions/2026/2026-06-17-01.md:


---


id: s-2026-06-17-01


type: session


date: 2026-06-17


craft: [c-lionbee]


spot: loc-stoughton-field


batteries: 6


conditions: { wind_mph: 8, temp_f: 64 }


drills: [tr-igow6-ch1]


logs:


  - { blackbox: LOG00042.BBL }


  - { dvr: 2026-06-17_lionbee.mp4 }


---


Power loops still mushy on exit. Orbit lines tightening.


Spot — sessions/spots/stoughton-field.md:


---


id: loc-stoughton-field


type: spot


name: Stoughton Soccer Fields


coords: [42.9169, -89.2179]


kind: field          # field | park | bando | indoor


airspace: { class: G, laanc_required: false, notes: "" }


hazards: ["light poles, east edge"]


---


Training — sessions/training/igow6-ch1.md:


---


id: tr-igow6-ch1


type: training


name: "IGOW6 Challenge 1 — Self Orbits"


status: active       # active | parked | done


drills:


  - { id: tr-igow6-ch1-d1, name: "CW orbit, 3 clean rotations", done: false }


  - { id: tr-igow6-ch1-d2, name: "CCW orbit, 3 clean rotations", done: false }


---


Progression notes.


Parts/gear follow the same pattern; keep them terse.


________________


5. Identifiers
Every entity has an opaque, stable ID — assigned once, frozen forever, never reused.


Type
	Form
	Example
	Rationale
	Craft
	c-<slug>
	c-lionbee
	Named, few, referenced constantly → readable slug
	Part
	p-<seq>
	p-0007
	Many, fungible → opaque sequential
	Gear
	g-<seq>
	g-0004
	Same
	Session
	s-<date>-<nn>
	s-2026-06-17-01
	Date-stamped → self-sorting, human-meaningful
	Spot
	loc-<slug>
	loc-stoughton-field
	Named place → slug
	Training
	tr-<slug>
	tr-igow6-ch1
	Named plan → slug; drills nest as tr-…-d1
	

Rules:


* The ID is not the data. Attributes change; the ID doesn't.
* Readability lives in link text, not the ID (see §6) — so opaque part IDs cost nothing in docs.
* Never renumber, never recycle a retired ID.
* "Build" reuses the craft ID — there is no separate build ID (see §13.1).


________________


6. Link scheme (connective tissue)
One URN, URN-style like mailto: (the prefix encodes the type, so the scheme stays flat):


fpv:c-lionbee · fpv:p-0007 · fpv:s-2026-06-17-01 · fpv:loc-stoughton-field


A tiny shared resolver maps a URN to whichever tool currently owns that view — really just type → base_url from fpvibe.config.yaml, plus {base_url}/{id}. Tools register their base URL; the resolver is the only thing that needs to know where a noun lives right now. Move/promote a tool, change one mapping, every link still resolves.


In plain markdown, always write references as links with readable anchor text so they degrade gracefully without a resolver:


Motors: 4× [0702 30000KV (JST)](fpv:p-0007)


fpvibe.config.yaml:


resolver:


  craft:    https://fleet.example.ts.net


  build:    https://fleet.example.ts.net       # build resolves into the fleet craft record


  part:     https://inventory.example.ts.net


  gear:     https://inventory.example.ts.net


  session:  https://sessions.example.ts.net


  spot:     https://sessions.example.ts.net     # until promoted


  training: https://sessions.example.ts.net     # until promoted


palette:                                          # seed from Multiboard scheme (§9)


  primary:   "#9ecae1"   # light blue (placeholder — confirm)


  secondary: "#9e7bb5"   # purple    (placeholder — confirm)


  accent:    "#f08a3c"   # tangerine (placeholder — confirm)


________________


7. Auth boundary
Tools do not roll their own login.


* The tailnet is the perimeter. On Tailscale, per-app PINs are theater — trust tailnet ACLs.
* Anything exposed beyond the tailnet sits behind one shared forward-auth proxy (the DumbAuth equivalent). Tools trust a signed identity header; they implement no sessions.
* A tool must boot and function with auth handled upstream. No bespoke user store.


________________


8. Deploy shape (per citizen)
* single container, non-root (UID 1000);
* configured by FPVIBE_-prefixed env: FPVIBE_PORT, FPVIBE_BASE_URL, FPVIBE_SITE_TITLE, FPVIBE_DATA_PATH (app-local/derived state), FPVIBE_SUBSTRATE_PATH (path/URL to the git substrate, usually mounted read-only or cloned);
* persists only derived/app-local state to /data;
* exposes /healthz (200 = serving);
* ships a Runtipi config entry and a compose fragment;
* is added to fpvibe-compose — one meta-compose that brings the whole suite up (the DumbCompose equivalent).


________________


9. Look
* a single CSS-variables file (fpvibe-theme.css) every tool imports — tokens only, no shared component framework;
* light/dark with persisted preference;
* seed palette from Cori's Multiboard scheme so the tools match the physical bench: light blue primary, purple secondary, tangerine accent. Exact hexes are a confirm item (§13.6).


________________


10. Conformance — what makes a tool an FPVibe citizen
A tool is in the federation iff:


1. One job. Doing two things → it's two tools.
2. Speaks fpv: — resolves the link types it cares about, emits links for entities it references.
3. Substrate, not a fork — reads canonical nouns from the substrate; keeps no private, drifting copy. (Stateless tools: N/A.)
4. FPVIBE_ env; /data for derived state only.
5. Trusts the shared auth boundary — no bespoke login.
6. /healthz, non-root, compose fragment, Runtipi entry.
7. Shared theme tokens + light/dark.
8. Independently deployable and independently failable — boots and degrades gracefully when any sibling is down; no hard runtime dependency on another tool.


New bolt-ons join exactly this way: write the tool, pass the checklist, add it to the meta-compose.


________________


11. The citizens
fpvibe-fleet (the expanded former "flowchart builds")
Authority for Craft (and the Build facet). What you own and fly. Reference-ish; changes on build/buy/mod/retire. Renders a craft's BOM with part names by reading inventory's part records, and links out via fpv:. Computes nothing about stock — that's inventory's job.
fpvibe-sessions (the hub)
Authority for Session. Append-per-flight log. References craft, spot, drills; attaches blackbox/DVR. Also the initial home of Spot and Training records (§12).
fpvibe-inventory (already conceived)
Authority for Part and Gear. Fungible quantities + allocation for parts; discrete serial/warranty assets for gear. Computes free-vs-allocated by reading every fleet/craft/*.md BOM and subtracting on-hand. (Refinement from planning chat: gear sits here as the discrete-asset counterpart to parts, not in fleet — see §13.2.)
fpvibe-tune (stateless)
The da_bits throttle-curve calculator. Owns no entities, reads no substrate — the proof the conventions aren't heavy. Joins purely by adopting naming/theme/deploy/link conventions. Optional nicety: attach a computed curve to a craft by writing a tune pointer that references fpv:c-….


________________


12. Promotion (spots & training)
Both start as substrate entities surfaced inside fpvibe-sessions. Promote to their own citizens only when a concrete trigger fires:


* Spot → fpvibe-spots: when airspace/compliance metadata (Ireland IAA/MySRS registration, LAANC, EU constraints) outgrows notes and wants real structure/validation. This is already close.
* Training → fpvibe-training: when drills need genuine progress tracking/streaks rather than a checklist in a note.


Promotion is cheap by design: move the sessions/spots/ (or training/) substrate directory to the new tool's path, stand up the new container, and change one resolver mapping. All existing fpv: links keep resolving.


________________


13. Decisions to confirm (surface before destructive changes)
1. Craft-as-primary, Build-as-embedded-facet. BOM + build log live in the craft record; there is no separate b- build ID or file. This collapses the earlier "builds" notion into craft. Confirm, or keep Build as its own first-class entity/file. This drives the flowchart migration shape.
2. Inventory owns Gear (discrete assets) alongside Part; fleet only references gear for commercial craft. Confirm vs. fleet owning the gear roster.
3. Spots & training fold into sessions now, promote later. Confirm vs. standing them up as tools immediately.
4. Substrate home: dedicated fpvibe-data repo vs. a directory inside cori/me.
5. Tool code layout: monorepo of citizens vs. repo-per-citizen.
6. Palette hexes for the Multiboard-derived light-blue / purple / tangerine.


________________


14. Implementation brief (phased)
Phase 0 — Substrate + conventions (no tools)
* Create the substrate (repo or cori/me dir) with the §4 tree.
* Add this FPVIBE.md, fpvibe.config.yaml (resolver map + palette, placeholder URLs OK), and SCHEMA.md (field reference + per-entity templates).
* Acceptance: schemas + one valid example record per entity type exist and match the templates.
Phase 1 — Migrate flowchart into the substrate
You know the current flowchart layout; map it onto the model:


* existing build docs → fleet/craft/*.md with embedded bom;
* flight notes / logs → sessions/2026/…;
* locations referenced → sessions/spots/…;
* practice/drill notes → sessions/training/…. Mint stable IDs; never reuse. Confirm §13.1 with Cori before merging/deleting original build docs.
* Acceptance: every existing flowchart artifact maps to a substrate record or is consciously dropped; no data lost; the migration is a reviewable git history.
Phase 2 — Scaffold fpvibe-fleet and fpvibe-sessions
* Each conforms to §8 (container, non-root, FPVIBE_ env, /healthz, reads FPVIBE_SUBSTRATE_PATH, commit-on-save, imports fpvibe-theme.css, compose fragment + Runtipi entry).
* Fleet: view/edit craft+build; render BOM with part names pulled from inventory records; link out via fpv:.
* Sessions: append-per-flight; reference craft/spot/drill; attach blackbox/DVR.
* Acceptance: both boot standalone, pass the §10 checklist, render migrated data, and resolve fpv: links to each other.
Phase 3 — Conform inventory + tune; wire resolver + meta-compose
* inventory: owns parts+gear; computes allocation from all craft BOMs.
* tune: conforms as the stateless citizen.
* Build fpvibe-compose; stand up the tiny resolver (or a static redirect service driven by fpvibe.config.yaml).
* Acceptance: docker compose -f fpvibe-compose … brings the suite up; a part's allocation reflects BOMs; fpv: links resolve suite-wide.
Phase 4 — Promote spots/training on trigger (§12)
* Acceptance: promotion changes exactly one resolver mapping; all existing fpv: links still resolve.


________________


15. Guardrails (anti-patterns)
* No plugin framework; no shared "core" lib beyond theme tokens + the resolver.
* Do not mint spots/training as tools in Phases 2–3 — keep them substrate entities until their trigger fires.
* No tool may hard-depend on a sibling at runtime; each boots and degrades alone.
* No per-tool auth; trust tailnet / forward-auth.
* Prefer commit-on-save to a private DB; only gear/warranty may keep a JSON store, and even then export a git snapshot.
* Keep tools single-job; if one grows a second job, split it.
* Do not destructively restructure existing flowchart content without confirming §13.1.
* When in doubt, ship a fourth small tool — not a bigger third one.