# 0006. Store uploaded files in the database behind a FileStorage interface

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#4](https://github.com/lovro-zmak-decode/interview-guide-app/pull/4) |
| Supersedes | - |

## Context

The app saved uploaded CVs and LinkedIn exports to a folder on disk. On Railway the container
disk is wiped on every deploy, so the files, and the ability to regenerate a guide from them,
would be lost. Buying object storage is a setup cost the project did not want yet.

## Decision

Uploads are kept through a small `FileStorage` interface (`save`, `load`, `delete`) in
`interview_app/storage.py`. The default backend stores the bytes in a database table, chosen by
`FILE_STORAGE=database`. A guide references its files by storage key in `guide_document`.
Moving to S3 or similar later means adding one class and setting the variable.

## Alternatives considered

- **A Railway volume.** Works, but ties the app to one host and one machine.
- **S3 from day one.** Needs an account, credentials and a bucket before it is needed.

## Consequences

- No external storage to set up, and a regenerated guide gets its own copies of the files.
- Large files add to the database size. Uploads are capped at 20 MB each.
- The database backend does not commit; callers commit together with their own changes.
- Everything touching files must go through `get_storage()`, never the table or the disk.
