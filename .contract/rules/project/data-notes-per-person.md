---
id: data-notes-per-person
title: Interview notes belong to one person, and only that person edits them
scope: [global]
impact: HIGH
triggers: [interview log, notes, interview_log, participant, owner, admin, edit, permission, access, guide access]
appliesTo:
  - app.py
  - interview_app/models.py
  - interview_app/interview_log.py
---

Notes live in `interview_log`, one row per guide and user (`InterviewLog`, unique on
`guide_id` and `user_id`). A guide's participants are its owner and admins; everyone else gets a
redirect or a 403. Every write endpoint edits the **current user's own row** and nothing else.

- The `started` flag is that person's own "interview started" mode.
- Every save goes through `interview_log.merge_update`, which validates keys, grades, choices
  and sizes. Do not write to `data_json` directly.
- The summary is written from the current user's notes only.

Source: [ADR 0003](../../../docs/adr/0003-keep-interview-notes-per-person-and-let-owners-and-admins-take-part.md)
