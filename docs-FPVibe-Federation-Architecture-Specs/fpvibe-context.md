FPVibe — Context Document
Purpose: Reference for any Claude Code session, planning conversation, or future-Cori who needs the full picture of the FPV tooling landscape, what exists, where it lives, and how it maps to the FPVibe federation.


Last compiled: 2026-07-04

> ⚠️ **Historical snapshot — partially out of date.** This document describes the landscape
> *before* the FPVibe org existed and before the architecture pivoted from a git substrate to
> API federation (ARCHITECTURE.md v1.0). Known-stale items: repos now live under `FPVibe/*`
> (not `cori/*`); fpv-tools is public on Pages; the planned `fpvibe-fleet` / `fpvibe-sessions` /
> `fpvibe-inventory` / `fpvibe-tune` citizens were replaced by the actual tools `flowchart`
> (sessions) and `fpv-inventory` (parts/builds/gear); FPVIBE.md v0.3 — cited throughout this
> document as the canonical living spec — is itself superseded by ARCHITECTURE.md +
> API-CONTRACT.md; the `fpv:` URN/ID scheme and the six v0.3
> open decisions are superseded by ARCHITECTURE.md §12. Kept for provenance: the body below is
> the unedited 2026-07-04 snapshot and keeps its original framing (e.g. calling FPVIBE.md a
> "living spec"); the "what exists / next steps" tables in §5 no longer reflect current state.


________________


1. What is FPVibe
FPVibe is a federation of single-purpose FPV tools — not a monolith, not a platform, not a SaaS product. The design philosophy mirrors DumbWare: independent containers (or static sites, or skills) unified by shared conventions, a common data model, and a consistent identity. Each tool owns its own repo, deploy, and release lifecycle. Integration is "they agree on IDs and auth," never "they're the same binary."


The architecture was formalized in a living spec, FPVIBE.md (currently at v0.3), produced during a June 2026 planning session. The spec started as a DumbWare-style conventions reference and was expanded into a full implementation brief for handoff to Claude Code.
Core principles
* Git is the single source of truth. Tools are views/editors over a shared git substrate. "The commit is the interface."
* FOSS, self-hosted, composable. No subscriptions, no lock-in, no vendor-hosted dependencies. Runtipi + Tailscale is the deployment substrate.
* Federation over platform. Tools stay separate. The entity schema federates them, not a shared runtime. A botched inventory migration shouldn't take down the throttle calculator.
* Promote, don't pre-build. Start with fewer tools than entities. Promote an entity to its own citizen only when it earns a standalone lifecycle.
The seven canonical entities
These are the load-bearing contract — the thing that actually federates tools:


Entity
	What it represents
	ID pattern
	Craft
	Any flyable aircraft, DIY or commercial
	c-meteor75pro
	Build
	The assembly + BOM for a craft you built (facet of Craft)
	Part of craft record
	Part
	Inventory item (motor, FC, frame, etc.)
	Opaque sequential
	Gear
	Serial/warranty view of commercial equipment (radios, goggles, printers)
	Opaque sequential
	Session
	A flight outing: date, craft, spot, batteries, conditions, drills, BBL/DVR links
	s-2026-07-04-01
	Spot
	A flying location + airspace/compliance metadata
	loc-stoughton-field
	Training
	Structured progression: plans, drills, IGOW challenges
	tr-igow6-ch3
	

Session is the hub — the join row tying craft + spot + drill + battery + logs together. It's the relational heart of the flying side, and where the blackbox workflow plugs in (a session references the .bbl it produced).
Planned initial citizens (from FPVIBE.md v0.3)
Tool name
	Scope
	Hosting
	fpvibe-fleet
	Craft + builds + gear roster ("what you own and fly")
	Container / Tipi
	fpvibe-sessions
	Append-per-flight log, the hub
	Container / Tipi
	fpvibe-inventory
	Parts stock, BOM consumption tracking
	Container / Tipi
	fpvibe-tune
	Betaflight tune profiles, rate presets, filter configs
	Static or container
	

________________


2. Pre-existing repos and tools (the "before" state)
These are the repos and projects that predate the FPVibe name. Most are private under github.com/cori. The FPVibe migration involves either absorbing, renaming, or referencing these — not starting from scratch.
cori/flowchart
* Status: Active, private repo, has had Claude Code sessions working on it.
* What it is: The primary in-progress FPV service. Originally referred to as "flowstate" in planning conversations; renamed to flowchart in FPVIBE.md v0.3 to match the actual repo name.
* Scope: Started as a personal KB spanning fleet management, sessions, builds, and gear. The June 2026 planning sessions concluded that flowchart was never really one tool — it's a personal KB covering several concerns that should be decomposed into the fpvibe-* citizens.
* FPVibe relationship: flowchart's content is the source material for the federation. The FPVIBE.md handoff document instructs the Claude Code session with local repo access to map flowchart's existing layout into the four initial citizens. Phase 1 of the spec is literally "inventory what's in flowchart and migrate it."
* Key content areas: Craft definitions, build logs/BOMs, session logs, gear registry, Betaflight CLI profiles (DAILYRIP, MID, FLAT), battery tracking.
cori/fpv-tools (GitHub Pages)
* Status: Live, likely private or unlisted, hosted on GitHub Pages.
* What it is: A collection of static client-side calculators and reference tools for FPV.
* Known tools: Prop pitch calculator, throttle calculator, and other reference utilities.
* FPVibe relationship: These stay together as a single hub — renaming to fpvibe/web or an org Pages site was recommended. The DumbWare per-repo split doesn't earn its keep here because static calculators have no independent lifecycle. Fragmenting them into N repos is pure ceremony. They join the federation by speaking the entity schema (a prop-pitch calculator references Part and Craft entities), not by becoming separate services.
* Hosting decision: GitHub Pages for free public reach; optionally also deployable as an nginx container in Tipi for private-behind-Tailscale access. Same artifact can do both.
Betaflight blackbox skill (betaflight-blackbox)
* Status: Active Claude Code skill, stored locally. The skill is also installed in this Claude.ai environment.
* What it is: A reusable skill for decoding and analyzing Betaflight blackbox logs. Components include decode.sh, analyze.py, turtle-mode classifier, cell count auto-detection, and per-session triage logic for multi-session dataflash dumps.
* Key capabilities: Tune health checks, motor balance analysis, voltage sag profiling, RPM/desync investigation, gyro noise and filter analysis, loop timing, crash forensics, flight comparison. Handles multi-session dumps by splitting into individual arm/disarm sessions and triaging real flights from bench/idle sessions.
* FPVibe relationship: The blackbox analyzer belongs in the federation as a skill or MCP server, not as a standalone web app. The diagnostic analysis is LLM-powered, meaning a standalone deployment either loses the analysis or requires hosting an LLM endpoint — which is a non-starter. The skill stays where the model already is (Claude Code, or Hermes Agent with a local model via Ollama).
* Distribution options explored:
   * Public GitHub repo with SKILL.md (immediate practical path, community-familiar)
   * PyPI package for reusable compute components (betaflight-blackbox-core)
   * MCP server exposing decode/analyze/compare as callable tools
   * Claude Code plugin marketplace (cori/fpv as a single marketplace for all FPV skills)
   * Cross-agent compatibility: skills work across Claude Code, Hermes, Cursor, Codex, and others — "Claude Code skill" is increasingly just "skill"
* Hermes Agent angle: NousResearch Hermes reads Claude-style marketplace manifests directly. A marketplace built for Claude Code installs into Hermes as-is. Hermes is model-agnostic, so the skill can run with a local model via Ollama — converting the "I won't host an LLM" blocker into a quality question. Still gated on whether a local model is sharp enough for tune analysis.
* Competitive landscape note: Betaflight's native Chirp Signal Generator (BF 2025.12+) and upcoming autotune analysis page narrow the differentiation window. Related projects: bvandevliet/betaflight-mcp (MCP server for live FC access), SebGalina/betaflight-claude-skill (Apache 2.0 skill with chirp analysis and Bode plots), raylanlin/smarttune-cli (MIT CLI with pure-Python decoder).
Gear packing lists (in flowchart)
* Status: Planned, architecture designed, handoff document produced.
* What it is: Composable session-type-based packing checklists for FPV bags. Two bags defined: a whoop bag (1S analog, indoor/micro) and an acro/long-range bag (5" freestyle, 3", LR). Each item carries a justification field and a tier (core, conditional, bench).
* Architecture: A gear/ directory of component files, a sessions/ directory of profiles that compose lists from components, and an optional bin/pack generator that flattens a session profile into a tickbox checklist at pack time. The bench tier documents deliberate exclusions (essentialist philosophy: every item "defends its position").
* FPVibe relationship: Lives inside fpvibe-fleet or fpvibe-inventory, depending on final decomposition. Uses Gear and Session entities.
IGOW challenge archive
* Status: Compiled, output file produced in a June 2026 session.
* What it is: A comprehensive reference of all IGOW challenge descriptions across seasons 1–6, compiled from YouTube video descriptions (via yt-dlp batch scraping) and the official IGOW challenges page. 144 total entries covering regular season and preseason challenges.
* Data pipeline: yt-dlp with custom delimiter format (%(id)s|||%(title)s|||%(description)s|||END_OF_RECORD), batch processing with --batch-file, sponsor/affiliate boilerplate stripping via regex. YouTube bot detection required fallback to the IGOW Google Sites page for IGOW6 data.
* Analysis produced: Lomb-Scargle-inspired periodicity analysis of trick sequencing across seasons, sponsor rotation patterns, and predictions for upcoming challenges.
* FPVibe relationship: Maps to the Training entity. Would live in a training/drills section of the federation, referenced by Session entries when competing. Currently a standalone reference file, not yet integrated into any tool.
drone-mesh-mapper (Colonel Panic ecosystem)
* Status: Built hardware, documented, firmware tested.
* What it is: A portable drone Remote ID detection field unit. Detects FAA Remote ID broadcasts over WiFi (and BLE on the S3) and forwards them over LoRa mesh via Meshtastic.
* Hardware: XIAO ESP32-S3 (scanner) + Heltec WiFi LoRa V3 (mesh radio), connected via 4-wire UART. SD card logging extension explored for standalone recording without a Pi.
* Software: colonelpanichacks/drone-mesh-mapper firmware on the scanner, stock Meshtastic on the Heltec, Flask-based mesh-mapper.py for visualization (runs on Pi Zero 2W or any Python host).
* FPVibe relationship: Tangential — it's an FPV-adjacent field tool, not a fleet/session/tune tool. Could map to the Spot entity (airspace awareness at a flying location) but doesn't need to be an fpvibe citizen. It's in the federation by speaking the same entity language if/when it references spots, but it has its own independent lifecycle.


________________


3. The "brand change" — what it actually means
The move to FPVibe is not a rebrand of a single product. It's the recognition that several independent tools, repos, and skills already exist and should be federated under a shared identity rather than continuing as disconnected projects under cori/*.
What changes
* GitHub: Create an fpvibe org. Move or fork relevant repos into it. fpv-tools becomes fpvibe/web (or the org's Pages site). flowchart content gets decomposed into fpvibe-fleet, fpvibe-sessions, fpvibe-inventory, fpvibe-tune.
* Naming: All federation citizens use the fpvibe-* prefix. The calculators/static tools live under the hub, not fragmented.
* Spec: FPVIBE.md (or fpvibe/spec) is the canonical entity definition and conventions reference. It's the one genuinely load-bearing artifact.
* Hosting: Per-tool decision. Static-capable tools → GitHub Pages (public reach) and/or Tipi (private). Stateful services → Tipi containers behind Tailscale. Skills → Claude Code plugin marketplace under fpvibe/ or cori/fpv.
* Distribution: The Claude Code plugin marketplace format doubles as Hermes-compatible, so one marketplace repo (fpvibe/skills or cori/fpv) serves both Claude Code and self-hosted agent installs.
What doesn't change
* Git as source of truth. No database-first tools.
* FOSS/self-hosted philosophy. Nothing metered, nothing vendor-hosted.
* The tools themselves. A prop-pitch calculator is still a prop-pitch calculator. The blackbox skill is still a skill. Federation is organizational, not functional.
* Audience: Primarily personal. Tipi-everything is the correct and simplest answer. GitHub Pages is optional sugar for public reach.
Open architectural decisions (from FPVIBE.md v0.3)
Six decisions flagged as requiring confirmation before destructive changes:


1. Craft-as-superset with Build-as-facet (vs. Build as top-level noun) — affects whether fleet stays one tool
2. Gear entity scope — commercial-only or also DIY accessories
3. Session ID format — date-stamped vs. sequential
4. Training entity promotion threshold — when does it earn its own citizen
5. Spot entity promotion threshold — same question
6. Inventory ↔ fleet data interlock — the one pair where data genuinely interlocks (a BOM is "this build consumes these parts"); these two might share a substrate or merge


________________


4. Analogies and reference architectures
These came up during planning as models for how FPVibe should (and shouldn't) work:


* DumbWare — the direct model. Single-purpose tools, shared conventions, meta-compose. FPVibe adds a shared data model (entities) on top.
* Plan 9 — "every tool exposes itself as a file over 9P, so the filesystem is the integration layer." Swap "filesystem" for "git repo" and that's FPVibe.
* Gridfinity / Multiboard — the physical-world version. A shared interface spec (the grid) plus unlimited independent modules that all just fit. Cori already trusts conformance-to-a-shared-spec every time he prints a bin.
* HashiCorp — single-purpose tools unified by a shared config language (HCL). HCL is their "convention."
* Charm (Glow, Gum, VHS) — shared libraries (Lipgloss/Bubble Tea) for consistent look. Theme tokens as code.
* suckless (dwm/dmenu/st) — same ethos, dmenu as shared component.
* systemd — the cautionary tale. Began as init, absorbed everything into one coupled project. The federation that became a platform. The exact drift FPVibe's non-goals exist to prevent.
* Nextcloud — the milder warning. A platform with plugins, which is the model deliberately walked away from.


________________


5. Current state and next steps
What exists today
Artifact
	Location
	Status
	FPVIBE.md v0.3
	Produced in Claude.ai, handed to Claude Code
	Living spec, needs entity schema finalization
	flowchart repo
	cori/flowchart (private)
	Active, content to be decomposed
	fpv-tools (Pages)
	cori/fpv-tools (private/unlisted)
	Live, static calculators
	betaflight-blackbox skill
	Local Claude Code skill dir
	Active, daily use
	IGOW archive
	Output file from Claude.ai session
	Complete through IGOW6 RS#2
	drone-mesh-mapper
	Hardware built, firmware from colonelpanichacks
	Functional, SD logging extension planned
	Gear packing architecture
	Handoff doc from Claude.ai session
	Design complete, not yet implemented
	What needs to happen
1. Create fpvibe GitHub org — cosmetic but establishes the namespace.
2. Finalize the six open architectural decisions — these gate Phase 1 of FPVIBE.md.
3. Run the flowchart content inventory — the Claude Code session with local access maps flowchart's layout to the four initial citizens.
4. Move fpv-tools into the org — rename or fork to fpvibe/web.
5. Decide audience — personal (Tipi everything, Pages optional) vs. public (Pages for static, Tipi for services). This is the single decision that resolves most remaining hosting questions.
6. Set up the plugin marketplace repo — fpvibe/skills with the blackbox skill as the first entry, formatted as a Claude Code plugin marketplace (.claude-plugin/marketplace.json), which Hermes also reads natively.