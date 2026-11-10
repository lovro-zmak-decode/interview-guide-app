# Onboarding

Welcome. This page gets you from a fresh clone to a running app, a green test suite and your first
pull request. The `repo-onboarding` skill walks it with you in Claude Code and runs the checks a
command can settle.

## 1. What this project is

A Flask app that turns a candidate's CV and LinkedIn profile into a timed, tailored interview
guide with a language model, then supports running the interview: notes, grades, recommendations
and a summary, for one or several interviewers. Read [ARCHITECTURE.md](../ARCHITECTURE.md) once;
it is short.

## 2. The things to internalise

- **Never commit or push to `main`.** Work on a branch and open a pull request. A git hook
  backstops this, but the habit is the real protection.
- **The server decides what a browser may see.** One interviewer's scores are hidden from the
  others while an interview is in progress, and the hiding happens in Python, not in the page.
- **`FLASK_SECRET_KEY` and `DATABASE_URL` are required.** The app will not start without them.
- **Prompts live in the database.** A fresh database has none; see section 5.

## 3. Access checklist

- [ ] GitHub access to `lovro-zmak-decode/interview-guide-app`
- [ ] An OpenAI API key (or an Anthropic key) for generating guides. Ask the team lead; never paste
      a key into chat, commits or files other than your own `.env`
- [ ] `gh` installed and logged in (`gh auth login`)

## 4. Prerequisites and first run

You need Python 3.13 or newer (3.14 works locally) and git.

```bash
git clone git@github.com:lovro-zmak-decode/interview-guide-app.git
cd interview-guide-app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
python tools/git/install_hooks.py        # git hooks: ruff, commit message format, no push to main
cp .env.example .env
```

Edit `.env` and set, at least:

- `FLASK_SECRET_KEY`: any long random string. Generate one with
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `DATABASE_URL`: `sqlite:///data/app.db` for local development
- `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY`)

Then run the app and the tests:

```bash
python app.py        # http://127.0.0.1:5001
pytest
```

The first visit to the app opens a one-time `/setup` page that creates the first account, with
full (superadmin) access. Further accounts are created from Admin, Users.

## 5. A fresh database has no prompts

Guide generation needs a **system prompt** of type `technical`, and the end-of-interview summary
needs one of type `summary`. Create them on the System Prompts page, or ask a teammate for the
text. The page lists the `{variables}` each type can use. Without a prompt, generation fails with a
message saying so.

Question groups can be imported from a Word file on the My questions page.

## 6. Development workflow

```bash
git checkout -b feat/short-slug     # types: feat, fix, chore, refactor, test, docs
# ... work ...
ruff check . && ruff format --check . && mypy && pytest
git commit -m "feat(app): describe the change"     # the hook checks the format
git push -u origin HEAD
gh pr create                                        # the title uses the same format
```

CI runs the same checks on SQLite and the tests again on PostgreSQL. Changes that touch queries,
models or storage should also pass on PostgreSQL locally; see [docs/runbooks/ci.md](runbooks/ci.md).

## 7. The agent contract

The rules coding agents follow live once, as files under `.contract/rules/`, and are compiled
into the routing table in [AGENTS.md](../AGENTS.md). Humans benefit from reading it too: it is the
short list of what is non-obvious about this project. Change a rule by editing its source and
running `python .contract/scripts/build_agents.py`; see [.contract/README.md](../.contract/README.md).

## 8. The decision log

[docs/adr/](adr/README.md) records why significant choices were made. Check it before changing
something it covers, and add a record when you make a decision that would be expensive to reverse.

## 9. Where the answers live

| Question | Look at |
|---|---|
| How does the code fit together? | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| Why was X decided? | [docs/adr/](adr/README.md) |
| What must I not do? | [AGENTS.md](../AGENTS.md) and the rule it routes to |
| How do I reproduce a CI failure? | [docs/runbooks/ci.md](runbooks/ci.md) |
| What does a deployment need? | [docs/runbooks/deployment.md](runbooks/deployment.md) |
| Google sign-in setup | `GOOGLE_OAUTH_TEST.md` (local) and `GOOGLE_OAUTH_SETUP.md` (production) |

## 10. Your first task

Pick something small: a copy fix, a missing test, a typo in a doc. Take it through the whole loop
in section 6, including the pull request, so the workflow is familiar before the real work starts.
