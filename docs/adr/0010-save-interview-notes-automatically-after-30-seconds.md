# 0010. Save interview notes automatically, 30 seconds after the first change

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-06 |
| PR | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) |
| Supersedes | - |

## Context

During an interview the notes must not be lost, but saving on every keystroke would hammer the
database. The interviewer asked for a delay and for it to be configurable in code.

## Decision

The first unsaved change starts a timer of `INTERVIEW_AUTOSAVE_SECONDS` (30, in `app.py`); when
it fires, everything changed since the last save is sent in one request. Typing continuously
does not postpone the save. Saves also happen on "End interview", on "Save now" and when the
page is hidden or closed. If a save fails the page keeps retrying and keeps a copy of the text
in the browser, which is offered back on the next visit.

## Alternatives considered

- **Save after the user stops typing (debounce).** A long burst of typing would never save.
- **Save on every change.** Too many requests.

## Consequences

- At most about 30 seconds of text is at risk if the browser crashes, which the browser copy
  covers.
- The "Restored unsaved text" message can appear even when the text was already saved, because
  a page that unloads cannot wait for the server's confirmation. This was judged acceptable.
- The DA/NE choice outside an interview is saved at once instead.
