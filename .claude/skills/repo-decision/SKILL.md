---
name: repo-decision
description: This skill should be used when the user asks to "record a decision", "add an ADR", "log this decision", "write a decision record", "supersede a decision", asks "why did we choose X", asks to "write up this decision", or says "/repo-decision". Reads the decision log in docs/adr/, assigns the next ID, drafts the record, and updates the index. Also answers "why" questions from existing records.
argument-hint: "[the decision to record, or the question to answer]"
---

> **Tools used:** `Read`, `Write`, `Edit`, `Grep`, `Bash(git:*)`.

Maintain the decision log in [docs/adr/](../../../docs/adr/). The format spec and the append-only
rule live in [docs/adr/README.md](../../../docs/adr/README.md) and
[.contract/rules/project/repo-decision-log.md](../../../.contract/rules/project/repo-decision-log.md);
those are the authority, this skill is the procedure.

## Mode 1, answer a "why" question

When the user asks why something was decided, grep `docs/adr/` for the topic before searching
anywhere else. Quote the record by ID and check its status: a `Superseded by` record answers what
we *used to* think, so follow the chain to the current one. If no record covers it, say so
plainly; do not reconstruct a rationale and present it as recorded.

## Mode 2, record a decision

1. **Read the index** in `docs/adr/README.md`. Determine the next four-digit ID, and whether this
   decision **supersedes** an existing record (same topic, new answer). If unsure, ask.
2. **Gather what the record needs.**
   - **PR.** Take the pull request from the conversation or the current branch. If there is none
     yet, use `-`. Never invent one.
   - **Status.** `Accepted` when the user states the decision as made; `Proposed` when it is still
     being floated. When ambiguous, ask. Resolving a `Proposed` record to `Accepted` or `Rejected`
     later is a permitted edit: change the status in its file and its index row, nothing else.
   - **Context and consequences.** Pull the real constraints from the conversation. If the user
     gave only the conclusion, ask one focused question for the why; a record without context is
     worthless in two years.
3. **Write the record.** Copy `docs/adr/_template.md` to `docs/adr/NNNN-short-slug.md` and fill
   every section (delete "Alternatives considered" only when there was no real alternative). Add
   the index row in `README.md`, in ID order.
4. **If superseding:** confirm with the user before touching the old record, then set its status to
   `Superseded by NNNN` in its file and its index row, and name it in the new record's
   `Supersedes` field. That status flip is the only permitted edit to an Accepted record.

Fill the template's `Date` with today's date. The append-only, no-renumbering and no-rename
rules are in [repo-decision-log](../../../.contract/rules/project/repo-decision-log.md) and the ADR
README; follow them, and offer a superseding record instead of editing an Accepted one.

Show the drafted record and the index diff, then stop. Committing goes through `repo-commit`.
