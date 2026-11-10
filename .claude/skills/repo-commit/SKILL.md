---
name: repo-commit
description: This skill should be used when the user asks to "commit", "commit changes", "stage and commit", "create a git commit", "commit my work", "plan the commits", "what should I commit", or says "/repo-commit". Checks the branch, runs the lint, type and test checks, decides whether the work is one commit or several, and writes a Conventional Commits message following this repo's contract.
argument-hint: "[optional: a hint about what the change is]"
---

> **Tools used:** `Bash(git:*)`, `Bash(ruff:*)`, `Bash(mypy:*)`, `Bash(pytest:*)`, `Bash(python:*)`, `Bash(grep:*)`, `Bash(mktemp:*)`, `Bash(rm:*)`, `Read`.

Prepare a commit that satisfies [.contract/rules/general/global-commit.md](../../../.contract/rules/general/global-commit.md)
and [global-branching.md](../../../.contract/rules/general/global-branching.md). Those rules are the
authority; this skill is the procedure for applying them.

## PRE-CONDITION, branch guard

Run `git branch --show-current` before anything else.

**If the branch is `main`, stop.** Do not stage, do not commit, do not run checks. Tell the user:

> You are on `main`. The contract forbids committing there, and the `pre-push` hook will refuse
> the push anyway. Options:
> 1. Branch now, keeping the current changes: `git checkout -b {type}/{short-slug}`
> 2. Name an existing branch to switch to

Wait for the user to choose. Only continue once the branch is not `main`.

## Step 1, inspect the working tree

Run in parallel: `git status --short`, `git diff --stat`, `git diff --cached --stat`,
`git log --oneline -5`. The log shows the message style actually in use.

## Step 2, decide one commit or several

Look at the changed paths and ask whether they are one logical change. Split when the changes
span **unrelated concerns**. Do **not** split just because paths differ: a route and the
template that renders it are one change. If a split is needed, present a plan listing each
proposed commit and its files, stage nothing, and wait for confirmation.

## Step 3, run the checks for what changed

| Changed path | Commands |
|---|---|
| `app.py`, `interview_app/**`, `tools/**`, `tests/**` | `ruff check .`, `ruff format --check .`, `mypy`, `pytest` |
| `templates/**`, `static/**` | `pytest`, and start the app and use the page (see `global-testing`) |
| `.contract/**`, `AGENTS.md` | `python .contract/scripts/build_agents.py --check` |
| `.github/**` | read the workflow once more; it cannot be run locally |
| `pyproject.toml`, `requirements*.txt` | the four commands above, since a config or version change affects every check |
| docs only | none |

A change to queries, models or storage must also pass on PostgreSQL (`TEST_DATABASE_URL=...`).

On failure:

- **Lint or format errors:** offer to fix with `ruff check --fix .` and `ruff format .`, show what
  changed, continue.
- **Type errors:** show them and ask whether to continue. Default to stopping.
- **Test failures:** stop and report the failure with its output. Never suggest skipping or
  deleting a test (`global-testing`).
- **`--check` on the contract fails:** run `python .contract/scripts/build_agents.py` and stage
  the regenerated files. This one is safe to fix without asking.

## Step 4, stage

Check `git status` for anything sensitive before staging broadly: `.env*`, `*.pem`, keys, local
databases, `uploads/`. If any appear, stage selectively and say what was left out. Otherwise
`git add -A` and confirm with `git diff --cached --stat`.

Sweep the lines this commit adds for obvious secrets, through a file so a failing `git diff`
cannot read as clean:

```bash
d=$(mktemp)
git diff --cached -U0 > "$d" && grep -nE "^\+.*(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA )?PRIVATE KEY)" "$d"
status=$?; rm -f "$d"; echo "sweep exit: $status"
```

Read the exit status, not the output: `1` means nothing matched, so proceed; `0` means a secret is
being added, so stop and report it; anything else means the sweep failed, so stop and report the
error. Never read a failure as clean.

## Step 5, write the message

The format, the type and scope vocabulary, the body guidance and the bans (no `Co-Authored-By`, no
AI attribution, no em dash) are in [global-commit](../../../.contract/rules/general/global-commit.md),
and the vocabulary comes from `.contract/project.config.json`. Follow that rule; do not restate it
here. Pick the scope from the staged files:

| Staged files mostly in | Scope |
|---|---|
| `interview_app/llm_providers.py`, `prompts.py`, `summarizer.py`, `schema.py`, `system_prompts.py` | `llm` |
| `interview_app/models.py`, `storage.py` | `db` |
| `app.py`, `interview_app/**` (the rest) | `app` |
| `templates/**`, `static/**` | `ui` |
| `.github/workflows/**` | `ci` |
| `tests/**` | `tests` |
| `requirements*.txt`, `.github/dependabot.yml` | `deps` |
| `.contract/**`, `.claude/**`, `tools/**`, root config | `repo` |
| `docs/**`, `*.md` | `docs` |
| spread across several | omit the scope |

The `commit-msg` hook rejects a message that misses any of this. To check one without committing:
`python tools/commit/validate_message.py --source=commit <file>`.

## Step 6, present, then commit

Show the staged files, the check results, the proposed message in a fenced block, and the secret
sweep's exit status. The user's request to commit is the confirmation required by `global-commit`,
so run `git commit` with the message once the checks passed and the sweep exited `1`.

Stop without committing, and ask, when a split plan needs approval, when a check failed, or when
the sweep did not exit `1`. Never push; pushing is a separate request.
