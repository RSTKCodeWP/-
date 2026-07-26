# Claude Code Guide — FPVibe

Development rules for all agents working in FPVibe org repos. Derived from
`cori/claude-code-base` `claude.md` (the canonical template); FPVibe-specific
deltas are marked. When the template's universal guidelines change, propagate
here (the template repo's `/backport-agents` skill handles fan-out).

We work through GitHub issues. Before starting work, find the issue you're
implementing and read it fully — including its Verification section. Use `gh`
where available; in remote/web sessions use the GitHub MCP tools instead.

## Collaboration

### Pull Requests & Commits

- Do not include session URLs, agent names, or tool identifiers in the prose of PR bodies, commit messages, or code comments — keep those to chat only
  - **Exempt:** machine-readable trailers at the end of a commit message (`Co-Authored-By:`, `Claude-Session:`, and the like). They're metadata for tooling, not prose, and some harnesses add them automatically. The rule targets narrative text — a commit body or PR description that reads like a session transcript
- PR descriptions: summary bullets + a test plan checklist is enough
- Always reference the closing issue with `Resolves #X` (or `Closes #X`) in the PR body so GitHub auto-closes it on merge

### Copilot Review Loop

FPVibe delta: every PR gets an automated Copilot review pass before it is
considered done.

1. **On PR creation**, request a review from GitHub Copilot by adding
   Copilot as a reviewer through whatever mechanism the session has: the
   GitHub web UI (Reviewers → Copilot), `gh pr edit <n> --add-reviewer
   Copilot` where the CLI accepts the bot reviewer, or the GitHub MCP
   server's Copilot review-request tool in remote/web sessions. If none of
   these are available, note it in the PR and continue — a missing Copilot
   reviewer must not block the work.
2. **Watch and triage.** Keep watching the PR (subscribe to PR activity in
   remote sessions). For each Copilot comment either fix it, or reply
   briefly why not. Copilot findings are advisory: the issue spec,
   ARCHITECTURE.md, and API-CONTRACT.md always win, and a suggestion is
   never a reason to expand scope or bend the federation guardrails.
3. **Re-request after pushing fixes.** Copilot reviews a snapshot; after
   each push that addresses comments, request a fresh Copilot review so the
   new diff gets a pass.
4. **Exit** when a review round returns no new actionable comments (or only
   restates ones already answered). Cap the loop at three rounds — if
   substantive disagreement remains after that, summarize it in a PR comment
   and leave the call to Cori rather than looping further.

## Development Philosophy and Methodology

### Red-Green-Refactor (TDD)

We follow test-driven development rigorously:

1. **Red**: Write a failing test first
   - Commit the failing test: `git commit -m "test: add failing test for feature X"`

2. **Green**: Write minimal code to make the test pass
   - Commit the implementation: `git commit -m "feat: implement feature X"`

3. **Refactor**: Improve the code while keeping tests green
   - Commit refactoring: `git commit -m "refactor: improve feature X implementation"`

**Coverage Expectations**:

- **Feature Coverage**: Good - Most user-facing features should have tests
- **Function Coverage**: Reasonable - Core business logic should be tested, not every helper

### Commit Early and Often

Show your work through granular commits:

- ✅ Separate commits for failing tests and implementations
- ✅ Meaningful commit messages following conventional commits
- ✅ Commit after each discrete change
- ❌ Don't bundle multiple features in one commit
- ❌ Don't wait until "everything is perfect"

### Documentation is Living

Keep documentation synchronized with code:

- Update README.md when adding features
- Document API endpoints as you create them
- Update architecture notes when making structural changes
- Remove outdated documentation immediately
- **Never let docs lag behind code**

FPVibe delta: cross-tool API shapes are contract-bound. If you change a
response shape listed in `FPVibe/docs` `API-CONTRACT.md`, bump the tool
version, and note the change in `FPVibe/docs` `CHANGELOG.md` in the same
piece of work.

### Technology Choices

#### Infrastructure

Add GitHub Actions for automations that make sense: if there's a Dockerfile,
make and release a package; since you're building tests, make sure actions run
the tests on push, etc.

FPVibe delta: CI is mandatory, not "as makes sense" — **every FPVibe repo
runs its full check suite in GitHub Actions on every push and PR.** If your
change isn't exercised by the repo's existing CI, extend the workflow in the
same PR. A brand-new repo ships its CI workflow in its first PR. "CI green"
is part of Definition of Done everywhere (IMPLEMENTATION-PLAN.md §1.4 in
`FPVibe/docs` tracks per-repo state).

#### ❌ No React

This bears repeating: **Do not use React**.

FPVibe tools are lightweight and framework-free. Use:

- Vanilla JavaScript/TypeScript
- Web standards (fetch, Request, Response)
- HTML templates (template literals, tagged templates)
- CSS (vanilla, no preprocessors unless necessary)
- Progressive enhancement

#### ✅ Use What Makes Sense

Beyond "no React," choose the best tool for the job:

- **TypeScript** for type safety
- **Deno standard library** for utilities (in Deno repos)
- **Web Components** if you need component architecture
- **htmx** or **Alpine.js** for lightweight interactivity
- **Tailwind CDN** if you want utility CSS (via CDN)

FPVibe delta: respect each repo's existing stack — `flowchart` is Node +
Hono + better-sqlite3, `fpv-inventory` is Deno + `deno.land/x/sqlite`,
`fpv-tools` is a static PWA. Don't introduce a second stack into a repo.

#### Mobile-Responsive Always

Every interface must work well on mobile:

- Use responsive CSS (flexbox, grid, media queries)
- Test on various viewport sizes
- Touch-friendly UI elements
- Performance matters on mobile networks

FPVibe delta: dark theme is the default (§9 of ARCHITECTURE.md), with the
Multiboard palette — primary `#9ecae1`, secondary `#9e7bb5`, accent `#f08a3c`.

### Priorities, Checkpoints, and Course Corrections

FPVibe delta — three rules that shape what to work on and when
(full protocol: `FPVibe/docs` IMPLEMENTATION-PLAN.md §1.5–1.7):

- **Broken beats buildout.** Before picking up feature work, check for open
  `bug`-labeled issues in the target repo and `FPVibe/docs`; any open `bug`
  preempts the plan. Bug fixes still follow TDD: failing test reproducing
  the bug first.
- **Human checkpoints gate build streams.** Checkpoint issues in
  `FPVibe/docs` mark where Cori walks through the live install; a gated
  phase doesn't start until its checkpoint closes. Don't route around an
  open checkpoint — repo-internal bootstrap and docs work are the only
  exemptions.
- **Never silently deviate from the architecture.** ARCHITECTURE.md and
  API-CONTRACT.md are canon until amended. If an issue's spec can't work as
  written: stop, comment your evidence, file an `ARCH:` issue in
  `FPVibe/docs` with options and a recommendation, and wait for Cori's
  call. The decision lands as a docs PR (spec amendment + CHANGELOG +
  contract version bump when shapes change) before the blocked work
  resumes.

### FPVibe Federation Guardrails

These come from `FPVibe/docs` `ARCHITECTURE.md` §11 and are non-negotiable:

- No shared database, no shared filesystem between tools
- Cross-tool calls are read-only JSON over HTTP, discovered via env vars
- A cross-tool fetch failure must never prevent a save or crash a page
- No auth, no multi-tenancy — local-only behind Runtipi
- One job per tool; when in doubt, ship a small tool, not a bigger one

### Be Prepared, Be Opinionated, Challenge Assumptions

- Don't assume requirements are complete — clarify ambiguity before coding
- Ask about edge cases
- Share opinions ("I recommend SQLite over blob storage here because…")
- Surface hidden assumptions ("this assumes the API always returns data — should we handle empty states?")

### What to Test

✅ **Do test**:

- Business logic
- API endpoints (request/response)
- Data transformations
- Degradation paths (sibling unreachable, malformed JSON, 404s)
- Error handling

❌ **Don't test**:

- The runtime's standard library
- Third-party libraries
- Trivial getters/setters

---

Remember: **No React. Test first. Commit often. Document everything. Ask questions.**

## fpv-inventory specifics

- Stack: Deno + `deno.land/x/sqlite`. No Node, no npm, no build step.
- `main.ts` is a single server-rendered HTML handler (`makeHandler(db)`) — no client-side framework, no JSON API yet (see INV-2).
- Tests: `deno task test` (see `tests/`). `deno task check` runs `deno check` across the repo.
- Env vars: `DB_PATH` (SQLite file location), `PHOTOS_DIR` (uploaded photo storage).
