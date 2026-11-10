---
id: llm-prompts-in-database
title: Prompts live in the database, are chosen per use, and have no hardcoded fallback
scope: [global]
impact: HIGH
triggers: [prompt, system prompt, system_prompt, template variable, PROMPT_VARIABLES, guide prompt, summary prompt, instructions]
appliesTo:
  - interview_app/prompts.py
  - interview_app/summarizer.py
  - interview_app/system_prompts.py
---

The instructions sent to the model are `system_prompt` rows of type `technical` (the guide) or
`summary` (the end-of-interview summary), edited on the System Prompts page. Generation fails
with a clear message when no suitable prompt exists; it never substitutes a built-in one.

- A new `{variable}` must be added to `PROMPT_VARIABLES` or `SUMMARY_PROMPT_VARIABLES` in
  `interview_app/prompts.py` and to the dictionary built where the prompt is rendered.
- A prompt that lacks `{additional_notes}` still gets the notes appended, so user input is not
  silently dropped. Keep that behaviour for any new user-facing input.
- A new environment needs its own prompts created through the admin page (they are data, not code).

Source: [ADR 0011](../../../docs/adr/0011-keep-prompts-in-the-database-and-choose-the-model-from-the-environment.md)
