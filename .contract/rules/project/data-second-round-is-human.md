---
id: data-second-round-is-human
title: The second-round recommendation is set only by the interviewer
scope: [global]
impact: HIGH
triggers: [second round, DA, NE, preporuka, recommendation, summary prompt, debrief, model output]
appliesTo:
  - interview_app/schema.py
  - interview_app/summarizer.py
---

"Preporuka za drugi krug: DA / NE" is a choice the interviewer makes. The model never proposes
it: the summary output (`InterviewDebrief`) has no such field, the summary prompt must not ask
for a verdict, and the choice is never sent to the model.

Source: [ADR 0005](../../../docs/adr/0005-the-second-round-recommendation-is-set-only-by-the-interviewer.md)
