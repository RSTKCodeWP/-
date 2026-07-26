# AGENTS.md - ADOS Mission Control

Agentic coding instructions for ADOS Mission Control, the open-source browser
and desktop ground control station.

## Purpose

Work in this repository as an engineering agent for the GCS application. Keep
changes practical, typed, demo-compatible, and focused on the operator workflow
being touched.

This file is self-contained for public repository work. Do not rely on
instructions outside this repository when writing code, docs, comments, tests,
examples, logs, or commit messages here.

## Read First

- Check `git status --short` before edits and preserve unrelated changes.
- Inspect the nearest existing component, store, hook, protocol type, or test
  before introducing a new pattern.
- Use `npm run demo` for UI work unless the task needs real hardware behavior.
- Keep demo mode working for new features. Add mock params, mock telemetry, or
  mock protocol stubs when the changed UI needs them.
- Prefer targeted verification over broad checks when a focused command proves
  the change.

## Stack and Commands

- Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4, Zustand 5,
  Convex, Electron.
- Dev server port: `4000`.
- Common commands:

```bash
npm run dev
npm run demo
npm run build
npm run lint
npm test -- --run
npm run desktop:dev
```

- Useful focused commands:

```bash
npm test -- --run path/to/test
npx eslint path/to/file.ts path/to/file.tsx
npm run test:e2e
npm run generate:agent-types
```

Use the focused commands first when they cover the touched surface. Run
`npm run build` for changes that affect routing, dynamic imports, generated
types, Convex usage, or production-only behavior.

## Architecture Map

- App routes: `src/app/`
- Shared UI: `src/components/ui/`
- FC panels: `src/components/fc/*Panel.tsx`
- Indicators: `src/components/indicators/*Indicator.tsx`
- Stores: `src/stores/*-store.ts`, with large stores split into domain slices.
- Agent connection: `src/stores/agent-connection/` and `src/lib/agent/`
- Ground station state: `src/stores/ground-station/`
- Protocol types: `src/lib/protocol/types/`
- MAVLink messages: `src/lib/protocol/messages/`
- Encoders: `src/lib/protocol/encoders/`
- Pattern generators: `src/lib/patterns/*-generator.ts`
- Simulation: `src/components/simulation/`, `src/app/simulate/`,
  `src/lib/terrain/`, and related stores.
- Electron wrapper: `electron/`
- Convex functions: `convex/`

Keep code files near 300 lines when practical. Split files before they become
hard to review, except generated files, fixtures, data tables, and vendored
code.

## Coding Rules

- Keep TypeScript strict. Avoid `any`; use explicit domain types or `unknown`
  with narrowing at boundaries.
- Interactive App Router components need `"use client"` at the top.
- Flight-controller operations go through the `DroneProtocol` interface.
  Components should not call protocol-specific MAVLink or MSP helpers directly.
- FC panels that read or write parameters use `usePanelParams`, shared panel UI,
  armed-state locking, and unsaved-change guards.
- Telemetry time series use bounded ring buffers. Do not store unbounded arrays
  for live telemetry.
- Subscribe to Zustand stores with selectors. Avoid broad `useStore()` calls in
  React components.
- Convex queries must pass `"skip"` when auth, demo mode, or runtime context is
  unavailable.
- Keep generated API types generated. When Drone Agent OpenAPI changes are
  intentionally consumed here, use the project script instead of hand-editing
  generated types.

## UI Rules

- Use the shared `<Select>` component for dropdowns, not native `<select>`.
- Use design tokens and dark-theme variables. Avoid hardcoded colors.
- Keep operator workflows dense, readable, and stable under live telemetry
  updates.
- Guard destructive or flight-affecting actions with clear disabled states,
  armed-state locks, or confirmation flows matching nearby panels.
- Keep loading, empty, disconnected, and demo states explicit.
- Avoid layout shifts from changing telemetry values. Use stable dimensions for
  gauges, counters, maps, video panes, and toolbars.

## Public Boundary

Keep this repository self-contained and technical. Document behavior through
architecture, APIs, commands, schemas, hardware interfaces, deployment steps,
and operator workflows.

Do not include non-public company context, named customers, financial context,
internal planning labels, attribution trails, or source-path hints from outside
this repository. Use neutral placeholders such as `example-oem`,
`cloud.example.com`, and public protocol names.

Comments, examples, fixtures, test names, logs, errors, PR titles, and commit
messages should be bland and technical. Do not write messages that describe a
cleanup of sensitive wording.

## Verification

- UI-only change: run focused ESLint for touched files and focused Vitest when
  behavior changed.
- Store, hook, parser, protocol, terrain, or simulation logic: add or update
  focused Vitest coverage and run it.
- Route, build config, dynamic import, Convex, or Electron change: run
  `npm run build`; add `npm run electron:compile` for Electron-only changes.
- Demo-visible workflow: smoke with `npm run demo` when practical.
- Browser flow with real interactions: use Playwright only for the affected
  route or workflow.

Before finalizing, run `git diff --check` and targeted scans on changed public
files for non-public context, named customers, internal planning labels,
attribution-trail wording, and financial context. Report any skipped checks.

## Review Expectations

When reviewing, list findings first and focus on behavior regressions,
performance leaks, memory leaks, missing demo coverage, unsafe flight-control
flows, state churn, and missing tests. Cite file and line references.

For implementation work, keep changes scoped to the touched workflow and verify
the smallest surface that proves the fix.

## Cross-Repo Impact

- Drone Agent API or telemetry shape changes may require generated API type
  updates and UI state handling here.
- Documentation changes may be needed when setup, API behavior, operator
  workflows, or troubleshooting steps change.
- Extension host changes must preserve declared slots, permissions, and stable
  host contracts for `ADOSExtensions`.

## Related Public Projects

- [ADOS Drone Agent](https://github.com/altnautica/ADOSDroneAgent) - companion
  and ground-node agent that Mission Control can connect to.
- [ADOS Documentation](https://github.com/altnautica/Documentation) - public
  docs for user and developer workflows.
