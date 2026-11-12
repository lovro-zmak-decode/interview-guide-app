# 0011. Keep prompts in the database and choose the model from the environment

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-06 |
| PR | [#3](https://github.com/lovro-zmak-decode/interview-guide-app/pull/3) |
| Supersedes | - |

## Context

The instructions sent to the model need frequent tuning by non-developers, for example the
wording that makes questions flow naturally through an interview, and a second prompt was
needed for the end-of-interview summary.

## Decision

Prompts are rows in `system_prompt`, edited on the System Prompts page, with a type: `technical`
for the guide and `summary` for the summary. Generation fails clearly when no suitable prompt
exists; there is no built-in fallback. User input that a prompt does not reference (the
additional notes) is appended so it is never silently dropped. The provider and model come from
the environment (`LLM_PROVIDER`, `OPENAI_MODEL`, `ANTHROPIC_MODEL`), never from code.

## Consequences

- Prompt changes need no deploy.
- Prompts are data: a new environment starts without any and they must be created or copied,
  which is what the local-only transfer script is for.
- New prompt variables must be registered in `interview_app/prompts.py` so the admin page lists
  them.
