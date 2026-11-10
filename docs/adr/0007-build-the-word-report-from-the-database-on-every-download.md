# 0007. Build the Word report from the database on every download

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) |
| Supersedes | - |

## Context

The `.docx` was written to disk at generation time and served from there, with a rebuild only
when interview notes existed. Files on a container disk disappear on deploy, so older guides
would have lost their download.

## Decision

`/download/<name>` rebuilds the report from the stored guide and everyone's interview notes on
every request. Nothing is written to disk.

## Consequences

- A deploy cannot break a download, and layout improvements apply to old guides.
- Each download costs a small amount of CPU. It takes milliseconds for a guide of this size.
- Guides created before this change had files on disk; the rebuilt report is equivalent.
