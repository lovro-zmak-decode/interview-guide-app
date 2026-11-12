# 0003. Keep interview notes per person, and let owners and admins take part

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-05 |
| PR | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) |
| Supersedes | - |

## Context

The report page started as a read-only document. Interviewers wanted to take notes during the
interview, grade the candidate and record a recommendation, and later more than one person
would interview the same candidate. Notes stored on the guide itself would make everyone
overwrite one another.

## Decision

Notes live in their own table, `interview_log`, with one row per guide and user. The guide's
owner and any admin take part; everyone else is refused. Every write edits the current user's
own row, and a person's "interview started" mode is part of that row. All saves are validated by
`interview_log.merge_update`.

## Alternatives considered

- **One notes column on the guide.** Simple, but two people would overwrite each other.
- **Only the owner takes notes.** The first version. It cannot support a second interviewer.

## Consequences

- Several people can write at the same time without conflicts.
- Other people's notes are shown read-only, refreshed every few seconds by polling the
  server, not by a push channel.
- Access is by role (owner or admin). Letting any logged-in user join would be a separate
  decision.
- Notes are user text, so they are only ever inserted into the page as text, never as HTML.
