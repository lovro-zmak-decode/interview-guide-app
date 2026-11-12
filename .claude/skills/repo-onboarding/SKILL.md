---
name: repo-onboarding
description: This skill should be used when a new joiner asks to "get onboarded", says they are new to the project, asks to "set up my machine", "walk me through setup", or "how do I get started". Reads docs/ONBOARDING.md as its source of truth, walks it section by section, and runs every environment check a command can settle.
argument-hint: "[optional: a section number to start from]"
---

> **Tools used:** `Bash(python3:*)`, `Bash(git:*)`, `Bash(gh auth status)`, `Bash(pytest:*)`, `Bash(grep:*)`, `Bash(ls:*)`, `Bash(curl:*)`, `Bash(python app.py)`, `Read`.

Walk a new joiner through [docs/ONBOARDING.md](../../../docs/ONBOARDING.md). That file is the source
of truth; this skill is the procedure. Do not restate its content from memory: read it, then walk it.

## Ground rules

- **Never read or print `.env`.** To check a variable is set, use `grep -q '^NAME=.' .env` and look
  only at the exit status. Never ask the user to paste a key into the chat; tell them to put it in
  their own `.env`.
- Run every check a command can settle instead of asking the user. Ask only about things a command
  cannot see (accounts, keys, preferences).
- Go one section at a time, report what passed and what did not, and wait before moving on.
- Never create commits, branches or pull requests during onboarding unless the user asks.

## Step 1, read the guide

Read `docs/ONBOARDING.md` in full. If the user named a section number, start there.

## Step 2, check the environment (sections 3 and 4)

Run in parallel and report a table of pass or fail:

| Check | Command | Pass when |
|---|---|---|
| Python | `python3 --version` | 3.13 or newer |
| Virtual environment | `ls venv/bin/python` | exists |
| Tools installed | `venv/bin/python -m pip list` | Flask, ruff, mypy and pytest listed |
| `.env` exists | `ls .env` | exists |
| Required settings | `grep -q '^FLASK_SECRET_KEY=.' .env`, `grep -q '^DATABASE_URL=.' .env` | both exit 0 |
| A model key | `grep -q '^OPENAI_API_KEY=.' .env`, then the same for `ANTHROPIC_API_KEY` | at least one exits 0 |
| Git hooks | `ls "$(git rev-parse --git-path hooks)/pre-push" "$(git rev-parse --git-path hooks)/commit-msg"` | both exist (this also works in a git worktree) |
| GitHub CLI | `gh auth status` | logged in |

For each failure, show the exact fix from the guide (for example `python tools/git/install_hooks.py`
for the hooks) and offer to run it when it is safe: creating the venv, installing the requirements,
installing the hooks. Never generate or write a secret into `.env` for the user without being asked;
if asked, generate it with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and append
it without printing it.

## Step 3, prove it works

Run `pytest` and report the summary line. Then start the app (`python app.py` in the background) and
`curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5001/healthz`; expect 200. Stop the app
afterwards.

## Step 4, the rest of the guide

Walk sections 5 to 10 in order: the first account and the prompts, the development workflow, the
agent contract, the decision log, where answers live, the first task. For the workflow, show the
`git checkout -b` and commit format examples, and point at `.contract/rules/general/global-branching.md`
and `global-commit.md` instead of restating them.

## Step 5, close

Summarise what is set up, what is still open (for example a missing key), and suggest the first task
from section 10. Do not commit anything.
