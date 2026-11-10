# 0001. Record significant decisions in this log

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | - |
| Supersedes | - |

## Context

The app grew quickly: Google sign-in, interview mode, per-person notes, file storage, a
deployment move. Many choices were made in conversation and are visible only as code. The next
person, or the next coding agent, has to reverse-engineer the reason for each one, and may undo
a deliberate choice because it looks arbitrary.

## Decision

We will keep an append-only decision log in `docs/adr/`: one numbered file per significant
decision and an index table in `README.md`. Accepted decisions are never rewritten; a decision
that stops being true is superseded by a new record, and both remain. The log is wired into the
agent contract as a routed rule, so it is loaded only when a task touches a recorded decision.

## Consequences

- The reasoning behind a choice outlives the conversation that produced it.
- The index, not any single file, is the source of current truth, so readers must check the
  status column.
- It only works if it is fed: a decision that meets the bar in the README is recorded as part
  of the task that makes it, not afterwards.
