# ADK Battle Labs — Drone Operations Week

## Project Context

This project contains materials for a multi-day drone operations event hosted by ADK Battle Labs. The primary deliverable is a professional one-pager/event document (`adk_battle_labs_drone_ops_week.docx`) that serves as the master reference for participants, vendors, and partners. The document was generated using `docx-js` via a Node.js script.

## Event Overview

- **Event Name:** ADK Battle Labs Drone Operations Week
- **Dates:** June 1–5, 2026 (Monday–Friday)
- **Location:** ADK Battle Labs, Lewis, NY (Adirondack region, northern New York)
- **Audience:** FPV racing teams, defense/tactical UAS operators, counter-UAS (C-UAS) detect-only vendors, commercial drone vendors, military and defense technology companies

## The Four Events

### Event 1: Open-Class Drone Racing
- Traditional FPV drone racing, open-class (all airframe configs allowed)
- **Monday:** Setup, equipment check-in, course configuration, open practice
- **Tuesday–Wednesday:** Open qualifying heats
- **Thursday AM:** Warmups and practice
- **Thursday PM/Evening:** Finals and championship race
- **Friday:** Teardown and closeout

### Event 2: Aerial Point Defense
- Tactical intercept scenario: BLUEFOR FPV team defends a fixed point
- REDFOR fixed-wing asset launches from 3 km out, flies inbound on a disclosed azimuth
- BLUEFOR must intercept before REDFOR penetrates a 500m defensive perimeter
- Successful intercept = cutting the streamer on the tail of the REDFOR aircraft
- **Schedule:** 30-minute sign-up time slots, available all day Tuesday and Wednesday

### Event 3: Moving Vehicle Intercept
- Dynamic targeting against a ground convoy (expected APC-class vehicles)
- Convoy travels a known route within a defined AO (area of operations)
- One vehicle designated as the high-value target (HVT)
- BLUEFOR must positively ID the HVT and execute a simulated kinetic strike before the convoy exits the AO
- ISR drones strongly recommended; loaner ISR platforms available for teams without organic ISR
- **Schedule:** 30-minute sign-up time slots, available all day Tuesday and Wednesday

### Event 4: Fixed Infrastructure Long-Range Engagement
- Precision strike against a static target at ~2 km within VLOS
- Target: satellite dish, designated vehicle, or structure
- Scoring based on strike precision and post-strike battle damage assessment (BDA)
- Combined ISR + strike drone operations encouraged
- **Schedule:** 30-minute sign-up time slots, available all day Tuesday and Wednesday

## Scoring Criteria (as documented)

- **Event 1:** Fastest cumulative lap times through qualifying → finals seeding → championship by finals results
- **Event 2:** Pass/fail intercept + bonus for time-to-intercept and intercept distance from defended point
- **Event 3:** HVT ID accuracy, time to strike, strike proximity to target vehicle
- **Event 4:** Strike precision (distance from target center) + quality of BDA evidence

## Vendor & C-UAS Participation

- Vendor booth slots available on-site throughout the event week
- Demo time slots available on the main race course for live product demonstrations
- Counter-UAS detect-only vendors invited to deploy and test equipment during all flight sorties (all four events)
- C-UAS vendors restricted to passive detection and tracking only — no active countermeasures (jamming, spoofing, kinetic defeat)
- Non-military/commercial vendors encouraged to field teams for racing and tactical events

## Participant Requirements (as documented)

- FAA Part 107 Remote Pilot Certificate (or equivalent authorization)
- Teams responsible for own UAS platforms, batteries, chargers, support equipment (ISR loaners available for Event 3)
- All aircraft must pass pre-flight safety inspection during Monday check-in
- Liability waiver and assumption-of-risk acknowledgment required
- Frequency coordination mandatory — all VTX and control link frequencies registered at check-in
- Compliance with Range Safety Officer (RSO) directives at all times
- Tactical event teams (Events 2, 3, 4) should be prepared to brief their CONOPS before their engagement window

## Safety & Airspace

- Operations under ADK Battle Labs authority with FAA coordination
- Designated RSO on-site for all flight operations
- Monday safety orientation mandatory (emergency procedures, no-fly boundaries, altitude restrictions)
- Weather-dependent operations; RSO may delay, reschedule, or cancel windows

## Logistics & Accommodations

- Nearby lodging: Elizabethtown and Westport (~15–25 min from venue)
- On-site camping/overnight parking TBD — confirm with organizers
- Early June Adirondack weather is variable; participants should plan accordingly

## Document Status & TBD Items

The following items are marked TBD in the current document and need to be filled in:

- [ ] Registration deadline
- [ ] Entry fee / pricing structure
- [ ] Contact email
- [ ] Contact phone number
- [ ] Website URL
- [ ] Recommended lodging list
- [ ] On-site camping/overnight parking policy
- [ ] Tactical event sign-up sheet / process
- [ ] Detailed rules of engagement for each tactical event
- [ ] Equipment class restrictions or specifications (if any)
- [ ] Prize structure / awards
- [ ] Spectator policy
- [ ] Media / photography policy
- [ ] Insurance requirements beyond liability waiver
- [ ] Specific FAA waiver or COA details
- [ ] Parking and site access directions
- [ ] Emergency medical plan / nearest hospital info
- [ ] Alcohol / food vendor policy
- [ ] Comms plan (radios, frequencies, net control)

## File Structure

- `adk_battle_labs_drone_ops_week.docx` — The current one-pager document (generated via docx-js)
- `CLAUDE.md` — This file (project context for Claude Code sessions)

## Style & Tone

The document should maintain a professional, defense-industry-adjacent tone — clear, direct, operationally precise. Use military/aviation terminology where appropriate (AO, BLUEFOR/REDFOR, CONOPS, BDA, ISR, HVT, VLOS, kinetic strike) but keep it accessible to commercial drone racing teams and non-military vendors. The visual style uses navy/red accent colors with clean table layouts.

## Working Notes

- The docx was built with `docx-js` (npm package `docx@9.5.3`) and validated with the Anthropic docx skill toolchain
- If regenerating, use US Letter page size (12240 × 15840 DXA), 0.625" margins (900 DXA sides, 720 DXA top/bottom)
- Numbering config uses `LevelFormat.BULLET` — never unicode bullet characters
- Tables use `WidthType.DXA` exclusively (not percentage — breaks in Google Docs)
- Full content width at current margins: 10440 DXA
