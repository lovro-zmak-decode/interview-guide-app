# Decision log

Architecture Decision Records for the Interview Guide App. One file per decision, numbered,
append-only. Think of it as a migrations system for decisions: a decision, once Accepted, is
never rewritten. When it stops being true, a new decision supersedes it and both stay in the
log. The history of what we believed and when is the point.

Agents and humans alike: **check this index before proposing to change something it covers.**
If a decision here already settles the question, either follow it or write a superseding
record; do not quietly diverge.

## Index

| ID | Decision | Status | PR | Date |
|---|---|---|---|---|
| [0001](0001-record-decisions-in-this-log.md) | Record significant decisions in this log | Accepted | - | 2026-11-10 |
| [0002](0002-use-one-conventional-format-for-commits-and-pr-titles.md) | Use one Conventional format for commits and PR titles, and enforce it | Accepted | - | 2026-11-10 |
| [0003](0003-keep-interview-notes-per-person-and-let-owners-and-admins-take-part.md) | Keep interview notes per person, and let owners and admins take part | Accepted | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) | 2026-11-05 |
| [0004](0004-hide-scores-only-while-an-interview-is-in-progress.md) | Hide scores only while an interview is in progress | Accepted | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) | 2026-11-10 |
| [0005](0005-the-second-round-recommendation-is-set-only-by-the-interviewer.md) | The second-round recommendation is set only by the interviewer | Accepted | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) | 2026-11-06 |
| [0006](0006-store-uploaded-files-in-the-database-behind-a-file-storage-interface.md) | Store uploaded files in the database behind a FileStorage interface | Accepted | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) | 2026-11-10 |
| [0007](0007-build-the-word-report-from-the-database-on-every-download.md) | Build the Word report from the database on every download | Accepted | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) | 2026-11-10 |
| [0008](0008-require-the-secret-key-and-the-database-url-with-no-defaults.md) | Require FLASK_SECRET_KEY and DATABASE_URL, with no defaults | Accepted | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) | 2026-11-10 |
| [0009](0009-name-the-psycopg2-driver-and-pin-python-3-13.md) | Name the psycopg2 driver and pin Python 3.13 | Accepted | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) | 2026-11-10 |
| [0010](0010-save-interview-notes-automatically-after-30-seconds.md) | Save interview notes automatically, 30 seconds after the first change | Accepted | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) | 2026-11-06 |
| [0011](0011-keep-prompts-in-the-database-and-choose-the-model-from-the-environment.md) | Keep prompts in the database and choose the model from the environment | Accepted | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) | 2026-11-06 |
| [0012](0012-keep-transfer-scripts-local-and-copy-content-only.md) | Keep transfer scripts local and copy content only | Accepted | [#5](https://github.com/lovro-zmak-decode/interview-guide-app/pull/5) | 2026-11-10 |
| [0013](0013-run-ci-as-two-jobs-on-sqlite-and-postgresql-with-pinned-actions.md) | Run CI as two jobs, on SQLite and PostgreSQL, with pinned actions | Accepted | [#6](https://github.com/lovro-zmak-decode/interview-guide-app/pull/6) | 2026-11-10 |
| [0014](0014-never-commit-to-main-and-enforce-it-with-a-pre-push-hook.md) | Never commit to main, and enforce it with a native pre-push hook | Accepted | - | 2026-11-10 |
| [0015](0015-leave-deployment-automation-for-later.md) | Leave deployment automation for later | Accepted | - | 2026-11-10 |

## What belongs here

A decision belongs in the log when reversing it later would be expensive, or when the next
person (or agent) would otherwise have to reverse-engineer the *why* from code:

- Technology and library choices, and their pinned-version exceptions
- Data rules: who can see what, what is stored where, what is never stored
- Integration and deployment boundaries
- Process rules the team has agreed to enforce

Not every change is a decision. A bug fix, a refactor or a copy change does not belong here.

## Format

Copy [_template.md](_template.md) to `NNNN-short-slug.md`, using the next four-digit number.
Fill every section. Write for a reader two years from now. No em dashes.

| Status | Meaning |
|---|---|
| Proposed | Under discussion. May be resolved to Accepted or Rejected by editing its status and its index row, nothing else. |
| Accepted | In force. Never edited again, except to mark it superseded. |
| Rejected | Considered and turned down. Stays in the log. |
| Superseded by NNNN | Replaced. Stays in the log; the new record names it in its `Supersedes` field. |

## Rules

1. **Append-only.** Never rewrite an Accepted record. Corrections and reversals are new records.
2. **Never renumber.** Rejected and superseded records keep their number. A gap is left alone.
3. **Link the change.** The PR column names the pull request that made the decision real, or
   `-` when there is none. Never invent one.
4. **Update the index** in the same change that adds or changes a record.

The `repo-decision` skill (`.claude/skills/repo-decision/SKILL.md`) automates this for Claude
Code.
