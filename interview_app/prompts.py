"""
Prompt construction for the interview-summary LLM call.

The system prompt encodes the structure and tone of the reference document
(an English-language interview prep guide), AND carries the actual
per-request context (candidate name, role, duration, research text, curated
questions) via the variables in PROMPT_VARIABLES below. It's stored in the DB
(see interview_app.models.SystemPrompt) so all of this — instructions and
variable placement alike — can be edited from the System Prompts admin page.

Because the research text and other request-specific details are now filled
in via variables inside the (editable) system prompt, the user message is
deliberately just a short, fixed trigger — see build_user_prompt(). Careful:
if a prompt is edited to remove one of these variables (e.g. {research_text}),
the model simply won't see that piece of information anymore.

There is no hardcoded fallback prompt in this file — a SystemPrompt's
`content` is read only from the database (see interview_app.models.SystemPrompt
and interview_app.summarizer._build_system_prompt). If no prompt exists yet,
create one from the System Prompts admin page; interview_app.schema.SCHEMA_DESCRIPTION
is available there for reference if you want to paste the JSON schema into a
new prompt's content as plain text.
"""

from __future__ import annotations

import re

# Variables that can be referenced as {name} inside a SystemPrompt's content.
# Shown on the System Prompts edit page so admins know what's available and
# what each one means. Keep this in sync with the `variables` dict built in
# interview_app.summarizer._build_system_prompt.
PROMPT_VARIABLES = [
    {
        "name": "candidate_name",
        "description": "The candidate's name, if the interviewer typed one in.",
    },
    {
        "name": "role_title",
        "description": "The interview role being generated for, if one was picked or typed.",
    },
    {
        "name": "duration_minutes",
        "description": "Planned interview duration, in minutes.",
    },
    {
        "name": "research_text",
        "description": "Everything gathered from the CV, LinkedIn text, and any linked pages (GitHub, portfolio).",
    },
    {
        "name": "curated_questions_block",
        "description": (
            "Optional pool of questions the interviewer curated from the Questions DB, grouped "
            "by group name — pick which ones (if any) fit this candidate and the interview "
            "duration; not all of them need to be used."
        ),
    },
]

_VARIABLE_RE = re.compile(r"\{(\w+)\}")


def render_prompt_template(template: str, variables: dict) -> str:
    """Fills in {variable} placeholders from `variables`. Anything not in the
    dict — including stray curly braces from pasted JSON examples — is left
    untouched instead of raising, unlike str.format()."""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return str(variables[key]) if key in variables else match.group(0)

    return _VARIABLE_RE.sub(_replace, template)


def format_curated_groups(curated_groups: list[tuple[str, list[str]]]) -> str:
    if not curated_groups:
        return ""
    lines = [
        "Optional pool of questions from the Questions DB, curated ahead of time by the "
        "interviewer (grouped below). Select whichever fit this candidate and the available "
        "interview time and weave them into the guide sections — you do not need to use all "
        "of them:"
    ]
    for group_name, questions in curated_groups:
        lines.append(f"\nGroup: {group_name}")
        for q in questions:
            lines.append(f"- {q}")
    return "\n".join(lines)


def build_user_prompt() -> str:
    """All the actual request context (candidate name, role, duration,
    research text, curated questions) is now filled into the system prompt
    via its {variables} — see _build_system_prompt in interview_app.summarizer.
    The user message is just the trigger to generate."""
    return "Generate the first-interview guide now, in the requested JSON format."
