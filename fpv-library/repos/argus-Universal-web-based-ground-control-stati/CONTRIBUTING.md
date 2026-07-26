# Contributing to Argus

Thanks for your interest! Here's how to get started.

## Setup

```bash
npm install && pip install -e .
python run.py --sim   # backend + simulator
npm run dev           # frontend dev server at :5173
```

## Before Submitting a PR

All four must pass:

```bash
npx svelte-check --tsconfig ./tsconfig.json   # 0 errors 0 warnings
npx vitest run                                # frontend tests
python -m pytest tests/test_unit_*.py tests/test_contract_*.py  # backend tests
ruff check backend/ scripts/ tests/           # Python lint
```

The pre-commit hook runs lint + type-check; pre-push runs the full test suite.

## Commit Messages

Format: `<type>: <imperative description>`

Types: `feat` / `fix` / `refactor` / `test` / `docs` / `ci` / `chore`

## Protocol Code

Code coupled to ArduPilot behavior (MAVLink commands, ACKs, field offsets, mode IDs, parameter semantics) must cite the upstream source in a code comment. See `CLAUDE.md` for details and examples.

## i18n

All user-visible strings use `t('key')` from `src/lib/i18n.svelte.ts`. Add new keys to `src/lib/locales/zh.ts` and `en.ts`, then run `python scripts/sync_locales.py --write` to propagate to the other 8 locales.

## Reporting Issues

- Bugs and feature requests: [GitHub Issues](https://github.com/L-X-Yao/argus/issues)
- Security vulnerabilities: see `SECURITY.md`
