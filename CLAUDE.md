# Interview Guide App, Claude Instructions

> **Portable rules live in [AGENTS.md](AGENTS.md).** For any agent, `AGENTS.md` plus the rule
> files it routes to are the single source of truth for branching, commits, PRs, testing and the
> project rules. This file keeps Claude Code specifics and deep reference. On any conflict,
> AGENTS.md wins.
>
> Rules live once, as atomic files under `.contract/rules/`. Edit the source and run
> `python .contract/scripts/build_agents.py`. Never hand-edit a generated routing table.

## Structure

```
app.py               Flask app: routes for guides, interview notes, summary, downloads, health
interview_app/       One module per concern (see ARCHITECTURE.md)
templates/, static/  Jinja pages and the single stylesheet
tests/               pytest suite; runs on SQLite, and on PostgreSQL in CI
tools/               Commit message validator, git hook installer and push guard
.contract/           Agent rule sources and the build that compiles them
.claude/             Claude Code skills, sub-agent, permissions
docs/                ONBOARDING, decision log (adr/), runbooks
.github/             CI, PR title check, security scan, Dependabot
```

## The things to internalise

- **Never commit or push to `main`.** Branch first, always. A `pre-push` hook backstops it.
- **The server decides what a browser may see.** Interview scoring is hidden from others while an
  interview is in progress, and the hiding happens in Python, not in the page
  (`data-scoring-visibility`).
- **`FLASK_SECRET_KEY` and `DATABASE_URL` are required.** Never add a default.
- **Prompts live in the database.** A new environment needs them created or copied.

## Dev commands

| Command | Purpose |
|---|---|
| `python app.py` | Run the app on http://127.0.0.1:5001 |
| `pip install -r requirements-dev.txt` | Install the app and the dev tools |
| `python tools/git/install_hooks.py` | Install the git hooks (once per clone) |
| `ruff check .` and `ruff format .` | Lint and format |
| `mypy` | Type check |
| `pytest` | Tests on SQLite |
| `TEST_DATABASE_URL=postgresql://... pytest` | Tests on PostgreSQL (use a scratch database) |
| `python .contract/scripts/build_agents.py` | Regenerate the agent contract after a rule change |
| `python .contract/scripts/build_agents.py --check` | Fail if generated files are stale (what CI runs) |

## Reference docs

Load these with `@` when working in the relevant area.

| File | Contents |
|---|---|
| `docs/ONBOARDING.md` | The new joiner's guide, and the source the `repo-onboarding` skill walks |
| `ARCHITECTURE.md` | Modules, data, the guide and interview flows, principles |
| `README.md` | Quick start, setup, Development section |
| `docs/adr/README.md` | The decision log: index of significant decisions and their status |
| `docs/runbooks/ci.md` | The workflows, what a run costs, how to reproduce a CI failure locally |
| `docs/runbooks/deployment.md` | Required variables, start command, health check, first-deploy checklist |
| `.contract/README.md` | How the agent contract is authored, built and enforced |

## Claude Code harness

Skills live in `.claude/skills/<name>/SKILL.md` and activate from conversation context, no
`/command` needed. Sub-agents live in `.claude/agents/`.

| Skill | Fires when |
|---|---|
| `repo-onboarding` | A new joiner asks to be onboarded or walked through setup. Reads `docs/ONBOARDING.md` and runs the environment checks a command can settle. |
| `repo-commit` | The user asks to commit, stage changes, or plan commits. Guards the branch, runs the checks, writes the message, and commits. Stops instead when a check fails or a split needs approval. Never pushes. |
| `repo-decision` | The user asks to record a decision, add an ADR, supersede one, or asks why something was decided. Maintains the decision log. |
| `repo-pr-review` | The user asks to review a PR. Multi-agent review with a verification pass; posts inline comments only with `--comment`. |
| `repo-skill-audit` | The user asks to audit skills. The `skill-auditor` sub-agent runs it after any skill file changes. |

| Sub-agent | Invoke when |
|---|---|
| `skill-auditor` | **Any** file under `.claude/skills/` or `.claude/agents/` is added, edited or deleted, even incidentally. Scope it to the changed skill. |

> **Hard rule.** After writing, editing or deleting anything under `.claude/skills/` or
> `.claude/agents/`, invoke `skill-auditor` before the conversation ends. No exceptions,
> including when the change was incidental to a larger task.

`.claude/settings.json` carries permissions. Read-only git and the project's own check commands
are pre-allowed; `.env` files and force-pushes are denied outright. `.claude/launch.json` defines
the dev server for the in-app preview. This repo configures no MCP servers of its own.

On conflict between a skill and a rule under `.contract/rules/`, the rule wins.
