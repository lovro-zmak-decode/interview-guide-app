# Interview Guide App Agent Contract (compiled reference)

**Version 0.1.0** (November 2026)

> Generated from .contract/rules/*.md by build_agents.py. Do not edit by hand.
> This is the whole-set reference. Agents should normally read the routing table in
> AGENTS.md and load individual rule files, not this file.

---

## Abstract

Portable, tool-agnostic contract for any coding agent working in the Interview Guide App repo. Carries the way-of-working rules (branching, commits, pull requests, testing) and the project rules that cannot be inferred from the code: who may see which interview scores, how files are stored, how the model and its prompts are configured, and which settings are required. Rules are authored as atomic files under .contract/rules/ and compiled into a reference document plus a machine index for on-demand retrieval.

---

## Ways of working (general)

### Global (always applies)

#### Branch before touching any file, and never commit to main

**Impact: CRITICAL** | scope: global | id: `global-branching`

Never edit, commit or push on `main`. Create and switch to a branch before
the first file change, not at commit time. This holds even when the request is only
"commit" or "commit and push": switch to a new branch first.

**Branch name format:** `{type}/{short-slug}`

- `type` is one of `feat, fix, chore, refactor, test, docs`.
- The slug is short, lowercase and hyphenated: `feat/own-questions`,
  `fix/health-check-redirect`, `chore/dev-harness`.
- The branch must not already exist on the remote. If it does, append an integer:
  `feat/own-questions-2`.

**Do:**

```bash
git branch --show-current            # if this prints main, stop and branch first
git checkout -b fix/health-check-redirect
```

**Never:**

```bash
# editing files while `git branch --show-current` prints `main`
# committing to main, or `git push origin HEAD:main`
```

If you discover you already edited files on `main`, run `git checkout -b <branch>`
immediately (uncommitted changes follow you) before staging anything.

**The `pre-push` hook backstops this** (installed by `python tools/git/install_hooks.py`). It refuses any push whose **remote** ref is
`refs/heads/main`, at any remote, which also catches `git push origin HEAD:main` and
`git push origin my-branch:main`. It is a backstop, not protection: hooks can be skipped
with `--no-verify`, and `main` is not yet protected on GitHub. Emergency bypass, for
repairing `main` after an accident:

```bash
ALLOW_PUSH_TO_MAIN=1 git push ...
```

Source: [ADR 0014](../../docs/adr/0014-never-commit-to-main-and-enforce-it-with-a-pre-push-hook.md)

---

#### Commit only when asked, using the Conventional format

**Impact: HIGH** | scope: global | id: `global-commit`

Commit only when the user asks. Never `git add` or `git commit` while on `main`
(see `global-branching`).

Before committing, run `ruff check .`, `ruff format --check .`, `mypy` and `pytest`
(see `global-testing`), and stage any files the formatter rewrote.

**Message format:** `{type}({scope}): {description}`

- `type`: `feat, fix, chore, refactor, test, docs`
- `scope`: `app, ui, llm, db, ci, docs, tests, repo, deps` (omit the parentheses if the change spans several)
- `description`: imperative, lowercase, no trailing period, under about 70 characters

```
feat(app): add own questions to the interview page
fix(ci): point the health check at /healthz
chore(deps): bump ruff
```

A body is allowed and encouraged when the change needs justification. Explain **why**, not
what the diff already shows. Separate it from the subject with a blank line and wrap at
78 characters.

Never include `Co-Authored-By`, AI attribution, or any reference to the tooling that
produced the change. Never use an em dash (see `style-no-em-dash`).

**The `commit-msg` hook backstops this.** It runs `tools/commit/validate_message.py`, which
reads the type and scope vocabulary from `.contract/project.config.json`, so the hook and
this rule cannot disagree. Merge, revert and autosquash (`fixup!`, `squash!`) subjects are
exempt. It is a backstop, not protection: hooks can be skipped with `--no-verify`. The PR
title follows the same format and is checked in CI (see `global-pr`).

Emergency bypass, for a commit that genuinely cannot take the format:

```bash
SKIP_COMMIT_LINT=1 git commit ...
```

Source: [ADR 0002](../../docs/adr/0002-use-one-conventional-format-for-commits-and-pr-titles.md)

---

#### Open a PR only when asked, with a Conventional title

**Impact: HIGH** | scope: global | id: `global-pr`

Open a pull request only when the user asks, with `gh pr create`, from a branch (never from
`main`). Push the branch only, never `main`.

**Title format:** the same Conventional subject a commit uses (see `global-commit`):

```
feat(app): add own questions to the interview page
```

The title is not cosmetic. On a squash merge GitHub uses the **PR title** as the commit
subject whenever the branch holds more than one commit, so a non-Conventional title lands a
non-Conventional commit on `main`. `.github/workflows/pr-title.yml` checks the title on open
and on every edit, with the same validator as the `commit-msg` hook.

**Description:** what changed, why, and how it was verified (a short test plan). Mention
anything the reviewer must know that the diff does not show. Never add an AI attribution
line or `Co-Authored-By`.

After opening the PR, report its link. Do not merge it unless asked. Do not poll CI in a loop;
read the result once and report it.

Source: [ADR 0002](../../docs/adr/0002-use-one-conventional-format-for-commits-and-pr-titles.md)

---

#### Test, verify, and never weaken tests to pass

**Impact: HIGH** | scope: global | id: `global-testing`

- Add tests for new behaviour and for the bug you fixed. Tests live in `tests/`.
- Before committing run `ruff check .`, `ruff format --check .`, `mypy` and `pytest`.
- A change that touches queries, models or storage must also pass on PostgreSQL, because
  that is the production database: `TEST_DATABASE_URL=postgresql://user:pw@localhost:5432/scratch pytest`.
  The database is emptied for every test, so use a scratch one. CI runs both.
- **Never delete, skip or comment out a test to make a suite pass.** If a test is genuinely
  wrong, explain why instead of silently removing it.
- Tests stub the language model (the `llm` fixture). Never make a test call a real model or
  depend on a real API key.
- Verify against real behaviour, not only green tests: for a UI change start the app and use
  the feature. If a check fails, is missing, or was skipped, say so plainly with the output.
  Never report success you did not verify.

Source: [ADR 0013](../../docs/adr/0013-run-ci-as-two-jobs-on-sqlite-and-postgresql-with-pinned-actions.md)

---

### Code Style

#### Use constants or enums, not scattered string literals

**Impact: MEDIUM** | scope: global | id: `style-constants-over-literals`

For new code and code you touch: when a string value is compared in more than one place
(roles such as `"admin"`, document kinds such as `"cv"`, the second-round choices `"DA"` and
`"NE"`, prompt types), define it once as a constant or `enum` and import it. Do not repeat
the literal across files.

Exception: values that are never compared across files (a route path, a form field name, a
storage key prefix) may stay plain strings.

Source: [CLAUDE.md](../../CLAUDE.md)

---

#### Never use an em dash

**Impact: MEDIUM** | scope: global | id: `style-no-em-dash`

Organization rule: never use an em dash (the U+2014 character) in any output, including code
comments, documentation, commit messages and PR descriptions. Use a colon, a comma,
parentheses, or two sentences instead. The commit-message validator rejects it.

Source: organization instructions

---

#### KISS, DRY, YAGNI, and remove dead code

**Impact: MEDIUM** | scope: global | id: `style-principles`

- **KISS.** Prefer simple, readable code over clever abstractions. One clear purpose per
  module or function.
- **DRY.** Extract repeated logic only when it appears in three or more places and the
  abstraction is clearly stable.
- **YAGNI.** Do not build for hypothetical future requirements. Remove dead code promptly.
- Do only what the task asks. No drive-by refactors of unrelated code.
- Default to no comments. Add one only when the why is non-obvious: a hidden constraint, a
  workaround for a specific bug, behaviour that would surprise a reader. Never narrate what
  the code does, and never write a multi-line docstring.

Source: [CLAUDE.md](../../CLAUDE.md)

---

## Project rules

### Configuration

#### FLASK_SECRET_KEY and DATABASE_URL are required, with no defaults

**Impact: CRITICAL** | scope: global | id: `config-required-settings`

`create_app()` refuses to start unless both `FLASK_SECRET_KEY` and `DATABASE_URL` are set,
and names the missing ones. There is no `"dev"` secret and no fallback database: a forgotten
secret lets anyone forge a login session, and a forgotten URL silently starts on an empty
database. Developers set both in their own `.env` (see `.env.example`).

- A relative SQLite path (`sqlite:///data/app.db`) resolves from the project folder.
- `postgres://` and `postgresql://` URLs are rewritten to `postgresql+psycopg2://`, because the
  newest SQLAlchemy defaults to the `psycopg` driver and we ship `psycopg2-binary`.
- Never read, print or commit `.env`. Never commit a real key.

**Never:**

```python
secret = os.getenv("FLASK_SECRET_KEY", "dev")  # a default is the bug
```

Source: [ADR 0008](../../docs/adr/0008-require-the-secret-key-and-the-database-url-with-no-defaults.md),
[ADR 0009](../../docs/adr/0009-name-the-psycopg2-driver-and-pin-python-3-13.md)

---

### Data and Interviews

#### Uploaded files go through the FileStorage interface, never the table or the disk

**Impact: HIGH** | scope: global | id: `data-file-storage-interface`

CV and LinkedIn uploads are kept through `get_storage()` (`interview_app/storage.py`) and
referenced by a storage key in `guide_document`. The default backend stores bytes in the
database, so a deployment needs no external storage and nothing is lost on redeploy. Moving to
S3 later means adding one class with `save`, `load` and `delete` and setting `FILE_STORAGE`.

- Never read or write the `stored_file` table outside the database backend.
- Never keep anything that must survive a deploy on the container's disk.
- The backend does not commit; the caller commits together with its own changes.

Source: [ADR 0006](../../docs/adr/0006-store-uploaded-files-in-the-database-behind-a-file-storage-interface.md)

---

#### Interview notes belong to one person, and only that person edits them

**Impact: HIGH** | scope: global | id: `data-notes-per-person`

Notes live in `interview_log`, one row per guide and user (`InterviewLog`, unique on
`guide_id` and `user_id`). A guide's participants are its owner and admins; everyone else gets a
redirect or a 403. Every write endpoint edits the **current user's own row** and nothing else.

- The `started` flag is that person's own "interview started" mode.
- Every save goes through `interview_log.merge_update`, which validates keys, grades, choices
  and sizes. Do not write to `data_json` directly.
- The summary is written from the current user's notes only.

Source: [ADR 0003](../../docs/adr/0003-keep-interview-notes-per-person-and-let-owners-and-admins-take-part.md)

---

#### Hide scores from others only while an interview is in progress, and enforce it on the server

**Impact: CRITICAL** | scope: global | id: `data-scoring-visibility`

A person's end-of-interview scoring (grades and their notes, the overall recommendation, the
second-round choice, the AI summary) is hidden from other interviewers **only while an
interview is in progress**, theirs or the viewer's, so nobody is influenced mid-interview.
When neither is interviewing, everyone sees everyone's full data. Answers, own questions and
live notes are shared at all times.

The hiding happens on the server, in `_participant_logs` (`app.py`) through
`interview_log.shareable`, so hidden data never reaches the other person's browser. Hiding it
only in the template or the script would leak it through the page source.

- The Word report is the complete record and includes everyone's scoring (`full=True`).
- Never add a new scoring field without adding it to what `shareable` removes.
- Never send data to the page that the viewer is not allowed to see.

**Never:**

```python
others = [InterviewLog.data_json ...]   # raw rows to the page, hiding done in JavaScript
```

Source: [ADR 0004](../../docs/adr/0004-hide-scores-only-while-an-interview-is-in-progress.md)

---

#### The second-round recommendation is set only by the interviewer

**Impact: HIGH** | scope: global | id: `data-second-round-is-human`

"Preporuka za drugi krug: DA / NE" is a choice the interviewer makes. The model never proposes
it: the summary output (`InterviewDebrief`) has no such field, the summary prompt must not ask
for a verdict, and the choice is never sent to the model.

Source: [ADR 0005](../../docs/adr/0005-the-second-round-recommendation-is-set-only-by-the-interviewer.md)

---

#### The Word report is built from the database on every download

**Impact: MEDIUM** | scope: global | id: `data-word-report-from-database`

`/download/<name>` rebuilds the `.docx` from the stored guide and everyone's interview notes
each time (`build_docx`). No generated report is written to disk or stored. A change to the
report layout therefore applies to old guides as well, and a deploy cannot break a download.

Source: [ADR 0007](../../docs/adr/0007-build-the-word-report-from-the-database-on-every-download.md)

---

### Language Model

#### Choose the provider and model from the environment, never hardcode a model id

**Impact: MEDIUM** | scope: global | id: `llm-model-from-environment`

`LLM_PROVIDER` picks the default provider (OpenAI when unset), `OPENAI_MODEL` and
`ANTHROPIC_MODEL` pick each provider's model. Guide generation and the summary use the model of
the provider stored on the guide. Never hardcode a model id anywhere else, and never put a
model id in the UI or in a test.

Source: [ADR 0011](../../docs/adr/0011-keep-prompts-in-the-database-and-choose-the-model-from-the-environment.md)

---

#### Prompts live in the database, are chosen per use, and have no hardcoded fallback

**Impact: HIGH** | scope: global | id: `llm-prompts-in-database`

The instructions sent to the model are `system_prompt` rows of type `technical` (the guide) or
`summary` (the end-of-interview summary), edited on the System Prompts page. Generation fails
with a clear message when no suitable prompt exists; it never substitutes a built-in one.

- A new `{variable}` must be added to `PROMPT_VARIABLES` or `SUMMARY_PROMPT_VARIABLES` in
  `interview_app/prompts.py` and to the dictionary built where the prompt is rendered.
- A prompt that lacks `{additional_notes}` still gets the notes appended, so user input is not
  silently dropped. Keep that behaviour for any new user-facing input.
- A new environment needs its own prompts created through the admin page (they are data, not code).

Source: [ADR 0011](../../docs/adr/0011-keep-prompts-in-the-database-and-choose-the-model-from-the-environment.md)

---

### Web UI

#### User text is never inserted as HTML

**Impact: HIGH** | scope: global | id: `web-user-text-is-never-html`

Notes, questions, names and model output are untrusted text. In Jinja, rely on autoescaping and
never use `|safe` on user text. In the page scripts, build elements with `createElement` and set
`textContent`; never concatenate user text into `innerHTML`. Data embedded in a script goes
through `|tojson`.

**Never:**

```javascript
element.innerHTML = '<p>' + note + '</p>';   // note is user text
```

Source: [ADR 0003](../../docs/adr/0003-keep-interview-notes-per-person-and-let-owners-and-admins-take-part.md)

---

### Repo and Tooling

#### Significant decisions live in docs/adr, append-only

**Impact: MEDIUM** | scope: global | id: `repo-decision-log`

`docs/adr/` is the project's decision log: one numbered record per significant decision, with
an index and the format spec in [docs/adr/README.md](../../docs/adr/README.md). It exists so
the *why* behind a choice outlives chat threads and the people who made it.

Three obligations:

1. **Check before you contradict.** Before proposing to change a technology choice, a data
   rule, a pinned version or any other recorded decision, read the index. If a record covers it,
   either follow it or write a superseding record; never quietly diverge.
2. **Record, never rewrite.** The log is append-only, like migrations. An Accepted record is
   never edited except to mark it `Superseded by NNNN`. Corrections and reversals are new records.
3. **Link the change.** Every record names the pull request or commit that made the decision
   real, or `-` when there is none. Never invent one.

When a task ends with a decision that is expensive to reverse, or impossible to infer from
code, write the record as part of the task, not as a follow-up.

Source: [docs/adr/README.md](../../docs/adr/README.md)

---

#### Database transfer scripts stay on the developer's machine

**Impact: MEDIUM** | scope: global | id: `repo-local-only-scripts`

Scripts that move data between databases (local to a deployed database, or between
environments) are local-only helpers and do not belong in the repo. They are listed in
`.gitignore` or `.git/info/exclude`. When one is needed it copies **content only** (question
groups and questions, system prompts, interview roles), never users, guides or interview notes,
and refuses to overwrite existing content unless told to.

Source: [ADR 0012](../../docs/adr/0012-keep-transfer-scripts-local-and-copy-content-only.md)

---

#### Pin GitHub Actions to commit SHAs, and never put untrusted text in a shell line

**Impact: HIGH** | scope: global | id: `repo-pinned-actions`

Every `uses:` in `.github/workflows/` is pinned to a full commit SHA with the tag in a comment
(`actions/checkout@<sha> # v7.0.1`); Dependabot bumps them. Pull request titles, branch names
and issue text are untrusted: pass them into a step through `env:`, never inline in a `run:`
line, so they cannot inject commands. Keep `permissions:` as narrow as the job allows.

Source: [ADR 0013](../../docs/adr/0013-run-ci-as-two-jobs-on-sqlite-and-postgresql-with-pinned-actions.md)

---
