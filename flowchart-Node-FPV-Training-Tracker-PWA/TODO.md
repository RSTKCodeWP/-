# FPV Training Tracker - Todo List

> Semaphore for agent task coordination. Update status as work progresses.

## Active Tasks

| ID | Task | Status | Agent | Issue | Priority | Notes |
|----|------|--------|-------|-------|----------|-------|
| T001 | Create todo list for issues | ✅ Complete | - | #4 | P1 | This file |
| T002 | Verify AGENTS.md accuracy | ✅ Complete | opencode | #9 | P1 | All commands work, structure matches, examples correct |
| T003 | Fix log session dialog | ✅ Complete | opencode | #8 | Modal moved outside page structure |
| T004 | Fix trick selection dropdown | ✅ Complete | opencode | #7 | Lazy-load tricks in showTrickPicker |
| T005 | Enhance trick database | ⚪ Pending | - | #3 | P3 | Add ~20 tricks from PDF across 5 levels |
| T006 | Allow freetext in dropdowns | ⚪ Pending | - | #6 | P3 | Workaround for CRUD ops |
| T007 | CRUD operations for dropdowns | ⚪ Pending | - | #5 | P4 | Nice-to-have for maintenance |
| T008 | Offline-first support | ⚪ Pending | - | #2 | P4 | Queue writes when offline |

## Features from PDF (All Implemented)

| ID | Task | Status | Agent | Priority | Notes |
|----|------|--------|-------|----------|-------|
| T009 | Phase/Gate tracking system | ✅ Exists | - | - | `gate_checks`, `gate_progress` tables + API |
| T010 | Weekly review system | ✅ Exists | - | - | `weekly_reviews`, `mastery_snapshots` + API |
| T011 | Crash taxonomy categorization | ✅ Exists | - | - | `crashes` table with failure_type/root_cause |
| T012 | Drill library with mastery targets | ✅ Exists | - | - | `drills` table with mastery_criteria |
| T013 | Equipment status inventory | ✅ Exists | - | - | `equipment`, `equipment_log` tables + API |
| T014 | Session template enhancement | ✅ Exists | - | - | `packs` table with voltage/focus/crashes |

## Test Coverage Gaps

| ID | Task | Status | Agent | Issue | Priority | Notes |
|----|------|--------|-------|-------|----------|-------|
| T015 | Expand CI test coverage | ✅ Complete | opencode | #10 | Fixed bugs + added pack/crash/review/gate/equip tests |

## Status Legend

- ⚪ Pending - Not started, ready to be claimed
- 🟡 In Progress - Being worked on
- ✅ Complete - Finished and verified
- 🔴 Blocked - Cannot proceed, needs unblocking

## Priority Definitions

- **P1** - Critical for agent coordination / blocks other work
- **P2** - Core feature broken or high-value enhancement
- **P3** - Important but not blocking
- **P4** - Nice-to-have, future work

## Agent Instructions

1. **Claim a task**: Update the "Agent" column with your session/agent identifier
2. **Start work**: Change status to 🟡 In Progress
3. **Complete work**: Change status to ✅ Complete, close associated issue if applicable
4. **Blockers**: If blocked, change status to 🔴 Blocked and note why in Notes column
5. **New tasks**: Add new rows as needed, assign appropriate priority

## Notes

- All P0/P1 issues should be claimed by only ONE agent at a time
- Lower priority tasks (P3/P4) can be worked in parallel by multiple agents
- Update this file atomically to avoid merge conflicts
- Link to GitHub issues using `#<issue-number>` format
