---
id: repo-local-only-scripts
title: Database transfer scripts stay on the developer's machine
scope: [global]
impact: MEDIUM
triggers: [migration, migrate, transfer, copy database, script, railway, postgres, local only, export, import, seed]
appliesTo:
  - .gitignore
---

Scripts that move data between databases (local to a deployed database, or between
environments) are local-only helpers and do not belong in the repo. They are listed in
`.gitignore` or `.git/info/exclude`. When one is needed it copies **content only** (question
groups and questions, system prompts, interview roles), never users, guides or interview notes,
and refuses to overwrite existing content unless told to.

Source: [ADR 0012](../../../docs/adr/0012-keep-transfer-scripts-local-and-copy-content-only.md)
