# 0005. The second-round recommendation is set only by the interviewer

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-06 |
| PR | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) |
| Supersedes | - |

## Context

The end-of-interview summary includes "Preporuka za drugi krug: DA / NE". The first plan had
the model propose DA or NE for the interviewer to confirm. The interviewer asked for the
opposite: the choice is theirs alone.

## Decision

The model never proposes the second-round choice. The summary the model returns has only the
summary text and the suggestions for second-round questions. The DA/NE choice has no default,
is set by the interviewer at any time, and is never sent to the model.

## Consequences

- No risk of a model verdict anchoring the interviewer.
- The choice is saved at once outside an interview, because it is a single click and a 30
  second delay made no sense there.
