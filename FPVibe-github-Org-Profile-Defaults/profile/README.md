# FPVibe

A federation of single-purpose FPV tools — not a monolith, not a platform. Independent tools unified by shared conventions, a common data model, and a consistent identity. Each tool owns its own repo, deploy, and release lifecycle.

## Core principles

- **Git is the single source of truth.** Tools are views/editors over a shared git substrate. "The commit is the interface."
- **FOSS, self-hosted, composable.** No subscriptions, no lock-in. Runtipi + Tailscale is the deployment substrate.
- **Federation over platform.** Tools stay separate. The entity schema federates them, not a shared runtime.
- **Promote, don't pre-build.** Start with fewer tools than entities. Promote to a standalone tool only when it earns one.

## Canonical entities

| Entity | What | ID pattern |
|--------|------|------------|
| Craft | Any flyable aircraft (DIY or commercial) | `c-<slug>` |
| Build | Assembly + BOM for a craft (facet of Craft) | part of craft record |
| Part | Inventory item (motor, FC, frame, etc.) | `p-<seq>` |
| Gear | Serial/warranty asset (radios, goggles, etc.) | `g-<seq>` |
| Session | A flight outing — date, craft, spot, drills, logs | `s-<date>-<nn>` |
| Spot | Flying location + airspace/compliance metadata | `loc-<slug>` |
| Training | Structured practice progression (IGOW, drills) | `tr-<slug>` |

Session is the relational hub — the join row tying craft + spot + drill + logs together.

## Citizens

| Tool | Scope | Hosting |
|------|-------|---------|
| fpvibe-fleet | Craft + builds ("what you own and fly") | Container / Tipi |
| fpvibe-sessions | Append-per-flight log, the hub | Container / Tipi |
| fpvibe-inventory | Parts stock, BOM consumption tracking | Container / Tipi |
| fpvibe-tune | Betaflight tune profiles, rate presets | Static or container |

## Architecture

Modeled on DumbWare: single-purpose tools, shared conventions, meta-compose. FPVibe adds a shared data model (entities + `fpv:` link scheme) on top. Tools agree on IDs, links, and auth — never on being the same binary.

## Docs

- [FPVIBE.md — Federation Spec & Implementation Brief](https://github.com/FPVibe/docs/blob/main/FPVIBE.md) (v0.3, living document)
- [Context Document — tooling landscape and migration map](https://github.com/FPVibe/docs/blob/main/fpvibe-context.md)