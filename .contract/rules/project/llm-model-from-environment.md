---
id: llm-model-from-environment
title: Choose the provider and model from the environment, never hardcode a model id
scope: [global]
impact: MEDIUM
triggers: [model, OPENAI_MODEL, ANTHROPIC_MODEL, LLM_PROVIDER, gpt, claude, provider, anthropic, openai]
appliesTo:
  - interview_app/llm_providers.py
---

`LLM_PROVIDER` picks the default provider (OpenAI when unset), `OPENAI_MODEL` and
`ANTHROPIC_MODEL` pick each provider's model. Guide generation and the summary use the model of
the provider stored on the guide. Never hardcode a model id anywhere else, and never put a
model id in the UI or in a test.

Source: [ADR 0011](../../../docs/adr/0011-keep-prompts-in-the-database-and-choose-the-model-from-the-environment.md)
