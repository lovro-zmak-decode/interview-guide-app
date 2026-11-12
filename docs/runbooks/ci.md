# CI runbook

What runs, what it costs, and how to reproduce a failure on your machine.

## Workflows

| Workflow | Runs on | Does |
|---|---|---|
| `ci.yml`, job `checks` | every pull request, push to `main` | `ruff check`, `ruff format --check`, `mypy`, the agent contract check, `pytest` on SQLite, the gitleaks secret scan |
| `ci.yml`, job `tests-postgres` | same | `pytest` against a PostgreSQL 17 service |
| `pr-title.yml` | PR opened, title edited, reopened | the PR title follows the Conventional format (ADR 0002) |
| `security.yml` | Mondays 06:00 UTC, manual | `pip-audit` on `requirements.txt`, gitleaks over the whole history |
| `dependabot.yml` | weekly | pull requests for Python dependencies and GitHub Actions, grouped, held 7 days after release |

GitHub bills each job as a whole minute, so the cheap checks share one job (ADR 0013). Superseded
pull request runs are cancelled; runs on `main` never are.

## Reproduce a failure locally

```bash
source venv/bin/activate
ruff check .                      # lint (ruff check --fix . applies the safe fixes)
ruff format --check .             # formatting (ruff format . fixes it)
mypy
python .contract/scripts/build_agents.py --check   # then without --check to regenerate
pytest
```

To reproduce the PostgreSQL job, use a scratch database (the suite empties and recreates tables
for every test):

```bash
# with Docker
docker run --rm -d --name pgtest -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tests -p 5433:5432 postgres:17
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/tests pytest
docker stop pgtest
```

Without Docker, a Homebrew `postgresql@17` started on a spare port works the same way.

## Reading a failure

- **A test fails only on PostgreSQL:** usually a query or type that SQLite tolerates. Run the
  PostgreSQL command above and read the first failing test.
- **`mypy` fails on a Flask-SQLAlchemy model:** the models module is exempted from `name-defined`
  in `pyproject.toml` because mypy cannot see `db.Model`; other errors are real.
- **The contract check fails:** a rule, template or `AGENTS.md` changed without regenerating.
  Run `python .contract/scripts/build_agents.py` and commit the generated files.
- **The PR title check fails:** edit the title with `gh pr edit <number> --title "..."`.
- **gitleaks reports a finding:** treat it as a real leak first. Revoke the key, then remove it. Add
  an allowlist entry to `.gitleaks.toml` only for a verified false positive, scoped to one path.

## Maintaining the workflows

- Actions are pinned to commit SHAs with the tag in a comment. Dependabot bumps them; when you
  add an action, pin it the same way (`gh api repos/<owner>/<repo>/git/ref/tags/<tag>`).
- The gitleaks version and its SHA-256 appear in `ci.yml` and `security.yml`. Update both
  together, and take the checksum from the release's `checksums.txt`.
- Pull request titles and branch names are untrusted: pass them through `env:`, never inline in
  `run:`.

## Branch protection (not set up yet)

Nothing server-side stops a push to `main` yet; the `pre-push` hook is a local backstop. In GitHub,
Settings, Branches, add a rule for `main` that requires a pull request and the checks `checks`,
`tests-postgres` and `title`. On a private repository this needs a plan that supports required
checks; until then the checks report but do not block the merge button.
