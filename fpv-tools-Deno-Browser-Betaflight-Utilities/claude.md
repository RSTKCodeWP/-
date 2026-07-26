# Claude Code Guide

This repository is a template for building using Claude Code. This guide establishes development best practices.

We'll be working on the repo through GitHub issues; as soon as you've finished reading this file make sure you have the `gh` client installed and that you can access issues. You can install it with `apt-get install -y gh`.

## Collaboration

### Pull Requests & Commits

- Do not include session URLs, agent names, or tool identifiers in PR bodies, commit messages, or code comments — keep those to chat only
- PR descriptions: summary bullets + a test plan checklist is enough
- Always reference the closing issue with `Resolves #X` (or `Closes #X`) in the PR body so GitHub auto-closes it on merge

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

Example commit flow:
```bash
git commit -m "test: add test for user authentication"
git commit -m "feat: implement user authentication"
git commit -m "test: add test for token expiration"
git commit -m "feat: handle token expiration"
git commit -m "refactor: extract token validation logic"
git commit -m "docs: update README with auth instructions"
```

### Documentation is Living

Keep documentation synchronized with code:

- Update README.md when adding features
- Document API endpoints as you create them
- Update architecture notes when making structural changes
- Remove outdated documentation immediately
- **Never let docs lag behind code**

### Technology Choices

#### Infrastructure

Make sure you add github actions for autiomations that make sense: if there's a Dockerfile, make and release a package. since you're building tests make sure you have actions to run the tests on push, &ct

#### ❌ No React

This bears repeating: **Do not use React**.

Val.town vals should be lightweight and framework-free. Use:
- Vanilla JavaScript/TypeScript
- Web standards (fetch, Request, Response)
- HTML templates (template literals, tagged templates)
- CSS (vanilla, no preprocessors unless necessary)
- Progressive enhancement

#### ✅ Use What Makes Sense

Beyond "no React," choose the best tool for the job:
- **TypeScript** for type safety
- **Deno standard library** for utilities
- **Web Components** if you need component architecture
- **htmx** or **Alpine.js** for lightweight interactivity
- **Tailwind CDN** if you want utility CSS (via CDN)

#### Mobile-Responsive Always

Every interface must work well on mobile:
- Use responsive CSS (flexbox, grid, media queries)
- Test on various viewport sizes
- Touch-friendly UI elements
- Performance matters on mobile networks

### Be Prepared, Be Opinionated, Challenge Assumptions

#### Ask Questions Often

- Don't assume requirements are complete
- Clarify ambiguity before coding
- Ask about edge cases
- Question technology choices (even suggesting alternatives)

Examples of good questions:
- "Should unauthenticated users see a login page or a 401?"
- "Do we need pagination for this list, or is the dataset small?"
- "Should we use blob storage or SQLite for this data? SQLite would enable queries."

#### Be Opinionated

You're encouraged to have and share opinions:
- "I recommend SQLite over blob storage here because we'll need to query by date"
- "Let's use a simple HTML form instead of a complex client-side solution"
- "This should be two separate vals - one for the API, one for the cron job"

#### Challenge Unacknowledged Assumptions

Surface hidden assumptions:
- "You mentioned 'users' - are we building multi-user auth or single-user?"
- "This assumes the API always returns data - should we handle empty states?"
- "Are we optimizing for read or write performance?"

### What to Test

✅ **Do test**:
- Business logic
- API endpoints (request/response)
- Data transformations
- Authentication flows
- Error handling

❌ **Don't test**:
- Val.town SDK functions (they're tested)
- Third-party libraries
- Trivial getters/setters

---

Remember: **No React. Test first. Commit often. Document everything. Ask questions.**
