# fpv-inventory

An inventory app for FPV quads and parts bins — track parts, builds, and
gear, nest components into assemblies, and keep a history of what's moved
where. Part of the FPVibe federation of tools.

## What is This?

- **Development guidelines** in [`CLAUDE.md`](./CLAUDE.md) for best practices

## Quick Start

1. **Open in a dev container**
   - GitHub Codespaces: Click "Code" → "Create codespace"
   - VS Code: "Reopen in Container"
   - Claude Code on web: Will automatically use the devcontainer

2. **Run it**
   - `deno task dev` — starts the server with `--watch`
   - `deno task test` — run the test suite
   - `deno task check` — type-check the repo

### Development Guide (`CLAUDE.md`)

Comprehensive guide covering:

- Deno essentials for this repo (no Node, no npm, no build step)
- Development methodology (TDD, commits, documentation)
- Technology choices (no React, mobile-responsive)
- FPVibe federation guardrails and Copilot review loop
- Testing strategy

## Development Philosophy

### ✅ Red-Green-Refactor (TDD)

1. Write failing test → commit
2. Implement feature → commit
3. Refactor → commit

### ✅ Commit Early and Often

- Separate commits for tests and implementation
- Show your work through git history
- Meaningful commit messages

### ✅ Keep Documentation Updated

- README stays current
- API docs reflect actual endpoints
- Architecture notes match reality

### ❌ No React

fpv-inventory is server-rendered HTML from `main.ts`. Use:

- Vanilla JS/TS
- Web standards
- HTML templates
- Lightweight libraries (htmx, Alpine.js) if needed

### ✅ Mobile-Responsive

Every interface must work on mobile devices.

## FPVibe Implementation Plan

This repo is one of four (`fpv-inventory`, `flowchart`, `fpv-tools`, `docs`)
being built out under FPVibe's federation architecture. The phase-ordered
blueprint, dependency graph, and architectural decisions live in
[`FPVibe/docs` IMPLEMENTATION-PLAN.md](https://github.com/FPVibe/docs/blob/main/IMPLEMENTATION-PLAN.md) —
that document is authoritative; issues in this repo link back to the
section they implement.

---

**Remember**: Test first. Commit often. No React. Document everything.
