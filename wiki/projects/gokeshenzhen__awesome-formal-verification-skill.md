# Awesome Formal Verification Skill

> Картка виставки. Зал: [Зір і алгоритми](../halls/ai.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [gokeshenzhen/awesome-formal-verification-skill](https://github.com/gokeshenzhen/awesome-formal-verification-skill) |
| Локальна тека | `fpv-library/repos/awesome-formal-verification-skill-AI-Agent-FPV-SVA-TCL-Open-source-formal` |
| У бібліотеці | keep |
| Категорії каталогу | `ai` |
| Зірки (каталог) | 21 |
| Оновлено upstream | 2026-07-27 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

An open-source, AI-agent-agnostic knowledge base for formal verification, designed to supercharge your EDA workflow with any AI coding assistant.

> 🎯 **Current Focus**: JasperGold Formal Property Verification (FPV) > 🗺️ **Roadmap**: CDC/RDC, Superlint, Coverage, VC Formal support

_З README.md, без переказу._

## Для чого

面向 AI 编程 Agent 的开源形式验证技能库，聚焦 FPV、SVA、证明优化、TCL 脚本与可扩展的形式验证工作流。Open-source formal verification skills for AI coding agents, focused on FPV, SVA, proof optimization, TCL scripting, and scalable verification workflows.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: 面向 AI 编程 Agent 的开源形式验证技能库，聚焦 FPV、SVA、证明优化、TCL 脚本与可扩展的形式验证工作流。Open-source formal verification skills for AI coding agents, focused on FPV, SVA, proof optimization, TCL scripting, and scalable verification workflows.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `adapters/`
- `AGENTS.md`
- `benchmarks/`
- `CLAUDE.md`
- `CONTRIBUTING.md`
- `knowledge/`
- `LICENSE`
- `README.md`
- `README.zh.md`
- `scripts/`
- `tool-specific/`

Типи файлів за вибіркою (37 файлів, глибина до 3): Markdown (26), .txt (4), (без суфікса) (3), JSON (2), shell (2).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

Clone the repo, then run the installer once:

```bash
git clone https://github.com/gokeshenzhen/awesome-formal-verification-skill.git
cd awesome-formal-verification-skill
bash scripts/install.sh
```

That's it. The installer auto-detects the AI agents on your machine and registers
the skill for each:

- **Claude Code** and **Codex** — both use global skills directories. The
  installer points them at this repo's canonical skill directory
  (`adapters/claude-code/`) via directory symlinks:
  `~/.claude/skills/`, `~/.agents/skills/` for current Codex, and
  `~/.codex/skills/` for legacy Codex installs.
  Restart the agent and the skill auto-triggers on any FPV task
  (formal / property / assertion / prove / CEX / JasperGold / VC Formal / FPV).
- **Cursor** and **Gemini CLI** — these use *project-level* rule/context files,
  not a global skills directory. If detected, the installer prints exactly how to
  wire them into a project.

Because each agent's skill entry is a directory symlink to this checkout,
updating the repo (`git pull`) updates every agent instantly — no reinstall.
`SKILL.md` itself stays a normal tracked file inside the repo, which avoids
scanner issues with file-level `SKILL.md` symlinks. Re-run the installer after
moving the repo; use `bash scripts/install.sh --uninstall` to remove the links.

> The per-agent wrapper files under `adapters/` are the source-of-truth manifests
> the installer wires up — you normally don't touch them directly.

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../fpv-library/repos/awesome-formal-verification-skill-AI-Agent-FPV-SVA-TCL-Open-source-formal/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/awesome-formal-verification-skill-AI-Agent-FPV-SVA-TCL-Open-source-formal/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/gokeshenzhen__awesome-formal-verification-skill.md`.
