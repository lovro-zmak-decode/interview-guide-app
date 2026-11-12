# 0004. Hide scores only while an interview is in progress

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-10 |
| PR | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) |
| Supersedes | - |

## Context

Interviewers should not be influenced by each other's marks while they are still forming their
own. The first answer was to keep each person's scoring (grades and notes, the overall
recommendation, the second-round choice, the AI summary) private for good. The decision then
changed: once the interviews are finished, everyone should see everyone's data on the report.

## Decision

Another person's scoring is hidden only while an interview is in progress, theirs or the
viewer's. When neither is interviewing, it is visible to everyone. Answers, own questions and
live notes are always shared. The hiding is done on the server (`_participant_logs` with
`interview_log.shareable`), so hidden data never reaches the other person's browser. The Word
report includes everyone's scoring.

## Alternatives considered

- **Private for good.** The first version; replaced because the team wants the full picture
  after the interviews.
- **Hide in the page only.** Leaks the data through the page source.
- **Reveal as soon as the other person finishes.** Lets someone who is still interviewing see a
  colleague's marks, which defeats the purpose.

## Consequences

- Starting an interview again hides everyone's scoring from the person who started it.
- Every new scoring field must be added to what `shareable` removes, or it leaks.
- The Word file reveals everything to anyone who may open the guide, so the privacy applies to
  the page only.
