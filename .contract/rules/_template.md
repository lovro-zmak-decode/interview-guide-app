<!-- Place this file in .contract/rules/project/ (project rules) or author a template in .contract/templates/general/ (portable rules). The folder sets the rule's class. -->
---
id: prefix-short-slug
title: Imperative rule title (Always X / Never Y)
scope: [global]
impact: MEDIUM
triggers: [keyword, another keyword]
appliesTo: []
---

One or two sentences on what the rule is and why it exists. Keep it high-signal:
capture the non-obvious constraint an agent cannot infer from reading the code.

**Do:**

```python
# the correct pattern
```

**Never:**

```python
# the pattern that produces a bug or a rejected PR
```

Source: [docs/adr/NNNN-short-slug.md](../../../docs/adr/NNNN-short-slug.md)
