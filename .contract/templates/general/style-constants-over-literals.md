---
id: style-constants-over-literals
title: Use constants or enums, not scattered string literals
scope: [global]
impact: MEDIUM
triggers: [enum, string literal, constant, status, role, kind, magic string, superadmin]
appliesTo: []
---

For new code and code you touch: when a string value is compared in more than one place
(roles such as `"admin"`, document kinds such as `"cv"`, the second-round choices `"DA"` and
`"NE"`, prompt types), define it once as a constant or `enum` and import it. Do not repeat
the literal across files.

Exception: values that are never compared across files (a route path, a form field name, a
storage key prefix) may stay plain strings.

Source: [CLAUDE.md](../../../CLAUDE.md)
