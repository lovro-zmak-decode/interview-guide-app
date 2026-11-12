---
id: data-word-report-from-database
title: The Word report is built from the database on every download
scope: [global]
impact: MEDIUM
triggers: [docx, word, report, download, build_docx, export, generated]
appliesTo:
  - app.py
  - interview_app/docx_generator.py
---

`/download/<name>` rebuilds the `.docx` from the stored guide and everyone's interview notes
each time (`build_docx`). No generated report is written to disk or stored. A change to the
report layout therefore applies to old guides as well, and a deploy cannot break a download.

Source: [ADR 0007](../../../docs/adr/0007-build-the-word-report-from-the-database-on-every-download.md)
