# 0012. Keep transfer scripts local and copy content only

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#5](https://github.com/lovro-zmak-decode/interview-guide-app/pull/5) |
| Supersedes | - |

## Context

The repo contained a script and two guides for copying the whole local database to a hosted
one. It copied every table, including users, generated guides and interview notes, and deleted
the target's existing rows. The move to Railway needs only the questions, system prompts and
interview roles.

## Decision

Database transfer scripts do not live in the repo. They stay on the developer's machine and are
ignored by git. A transfer copies content only (question groups with their questions, system
prompts, interview roles), gives the question groups to the first superadmin on the target,
refuses to run when the target already has content unless told to replace it, and never prints
the database password.

## Consequences

- The repo carries no one-off tooling, and no script that could be run against production data
  by accident.
- The script is not reviewed or tested with the code, so it must be written carefully when
  needed.
