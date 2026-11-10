---
id: data-scoring-visibility
title: Hide scores from others only while an interview is in progress, and enforce it on the server
scope: [global]
impact: CRITICAL
triggers: [score, scoring, grade, evaluation, recommendation, second round, summary, visibility, shareable, others, participant, hidden]
appliesTo:
  - app.py
  - interview_app/interview_log.py
  - templates/result.html
---

A person's end-of-interview scoring (grades and their notes, the overall recommendation, the
second-round choice, the AI summary) is hidden from other interviewers **only while an
interview is in progress**, theirs or the viewer's, so nobody is influenced mid-interview.
When neither is interviewing, everyone sees everyone's full data. Answers, own questions and
live notes are shared at all times.

The hiding happens on the server, in `_participant_logs` (`app.py`) through
`interview_log.shareable`, so hidden data never reaches the other person's browser. Hiding it
only in the template or the script would leak it through the page source.

- The Word report is the complete record and includes everyone's scoring (`full=True`).
- Never add a new scoring field without adding it to what `shareable` removes.
- Never send data to the page that the viewer is not allowed to see.

**Never:**

```python
others = [InterviewLog.data_json ...]   # raw rows to the page, hiding done in JavaScript
```

Source: [ADR 0004](../../../docs/adr/0004-hide-scores-only-while-an-interview-is-in-progress.md)
