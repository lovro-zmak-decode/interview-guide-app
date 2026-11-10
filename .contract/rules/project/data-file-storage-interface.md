---
id: data-file-storage-interface
title: Uploaded files go through the FileStorage interface, never the table or the disk
scope: [global]
impact: HIGH
triggers: [upload, file, cv, linkedin, storage, stored_file, bytes, s3, disk, uploads, generated]
appliesTo:
  - app.py
  - interview_app/storage.py
---

CV and LinkedIn uploads are kept through `get_storage()` (`interview_app/storage.py`) and
referenced by a storage key in `guide_document`. The default backend stores bytes in the
database, so a deployment needs no external storage and nothing is lost on redeploy. Moving to
S3 later means adding one class with `save`, `load` and `delete` and setting `FILE_STORAGE`.

- Never read or write the `stored_file` table outside the database backend.
- Never keep anything that must survive a deploy on the container's disk.
- The backend does not commit; the caller commits together with its own changes.

Source: [ADR 0006](../../../docs/adr/0006-store-uploaded-files-in-the-database-behind-a-file-storage-interface.md)
