---
id: web-user-text-is-never-html
title: User text is never inserted as HTML
scope: [global]
impact: HIGH
triggers: [innerHTML, xss, escape, template, jinja, textContent, user input, notes, script, tojson]
appliesTo:
  - templates/**
  - static/**
---

Notes, questions, names and model output are untrusted text. In Jinja, rely on autoescaping and
never use `|safe` on user text. In the page scripts, build elements with `createElement` and set
`textContent`; never concatenate user text into `innerHTML`. Data embedded in a script goes
through `|tojson`.

**Never:**

```javascript
element.innerHTML = '<p>' + note + '</p>';   // note is user text
```

Source: [ADR 0003](../../../docs/adr/0003-keep-interview-notes-per-person-and-let-owners-and-admins-take-part.md)
