---
id: repo-decision-log
title: Significant decisions live in docs/adr, append-only
scope: [global]
impact: MEDIUM
triggers: [decision, adr, decision log, architecture decision, why did we choose, why was this chosen, supersede, record a decision, tradeoff]
appliesTo:
  - docs/adr/**
---

`docs/adr/` is the project's decision log: one numbered record per significant decision, with
an index and the format spec in [docs/adr/README.md](../../../docs/adr/README.md). It exists so
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

Source: [docs/adr/README.md](../../../docs/adr/README.md)
