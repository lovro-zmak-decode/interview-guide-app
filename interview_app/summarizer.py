"""
Orchestrates the LLM call: build prompts -> call provider -> parse/validate JSON
into an InterviewSummary. Retries once with a stricter nudge if the model's
first response isn't valid JSON (models occasionally wrap JSON in prose or
markdown fences despite instructions).

The system prompt is not hardcoded here — it's loaded from the DB, editable
from the System Prompts admin page, and rendered with the variables in
PROMPT_VARIABLES. There is no fallback of any kind: the interviewer must pick
a prompt on the generate form (see index.html's "System prompt" field /
app.py's generate() route), and generation fails loudly
(SummaryGenerationError) if none was picked or the chosen one no longer
exists — it never silently substitutes some other prompt.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .llm_providers import LLMProvider
from .models import SystemPrompt
from .prompts import build_user_prompt, format_curated_groups, render_prompt_template
from .schema import InterviewSummary, ensure_baseline_scoring_rows

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class SummaryGenerationError(RuntimeError):
    pass


def _strip_to_json(raw: str) -> str:
    match = _JSON_FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _resolve_variables(
    research_text: str,
    candidate_name: str | None,
    role_title: str | None,
    duration_minutes: int,
    curated_groups: list[tuple[str, list[str]]] | None,
) -> dict:
    # Note: there's no "schema_description" variable here on purpose — the
    # JSON schema lives as plain text directly in the prompt's content (see
    # interview_app.prompts), not as an auto-merged placeholder.
    return {
        "candidate_name": candidate_name or "(not provided)",
        "role_title": role_title or "(not provided)",
        "duration_minutes": duration_minutes,
        "research_text": research_text,
        "curated_questions_block": format_curated_groups(curated_groups or []) or "(none selected)",
    }


def _build_system_prompt(active: SystemPrompt, variables: dict) -> str:
    """`active` must be a real SystemPrompt with non-blank content — callers
    (generate_interview_summary) are responsible for failing loudly before
    this point if no usable prompt exists in the database."""
    return render_prompt_template(active.content, variables)


def _resolve_scoring_row_specs(active: SystemPrompt, variables: dict) -> list[dict]:
    """The active prompt's configured "Quick evaluation" rows (a prop of the
    prompt, editable on the System Prompts page — see
    models.SystemPrompt.scoring_rows), rendered through the same variable
    substitution as the system prompt itself, so e.g. an area of
    "{role_title} (domain knowledge)" becomes "React (domain knowledge)".
    Read only from the prompt's own column — get_scoring_rows() returns an
    empty list (not a hardcoded default) if none are configured."""
    templates = active.get_scoring_rows()
    return [
        {
            "area": render_prompt_template(spec.get("area", ""), variables),
            "ideal_signs": render_prompt_template(spec.get("ideal_signs", ""), variables),
        }
        for spec in templates
    ]


def generate_interview_summary(
    provider: LLMProvider,
    research_text: str,
    candidate_name: str | None,
    role_title: str | None,
    duration_minutes: int = 60,
    curated_groups: list[tuple[str, list[str]]] | None = None,
    prompt_id: int | None = None,
) -> InterviewSummary:
    active = SystemPrompt.query.get(prompt_id) if prompt_id is not None else None

    if active is None or not active.content.strip():
        # No fallback of any kind on purpose: the interviewer must explicitly
        # pick a prompt on the generate form. If none was picked, or the
        # chosen one was deleted since the form loaded, or it exists but has
        # blank content, fail loudly instead of silently substituting some
        # other prompt.
        raise SummaryGenerationError(
            "No system prompt selected. Pick one on the generate form (create one from the "
            "System Prompts admin page first if none exist yet)."
        )

    variables = _resolve_variables(research_text, candidate_name, role_title, duration_minutes, curated_groups)
    system_prompt = _build_system_prompt(active, variables)
    user_prompt = build_user_prompt()

    last_error: Exception | None = None
    for attempt in range(2):
        prompt = user_prompt
        if attempt == 1:
            prompt += (
                "\n\nIMPORTANT: the previous response wasn't valid JSON. Respond with ONLY a "
                "JSON object, no markdown code fences and no text before or after it."
            )
        raw = provider.generate(system_prompt, prompt)
        try:
            data = json.loads(_strip_to_json(raw))
            parsed = InterviewSummary.model_validate(data)
            scoring_specs = _resolve_scoring_row_specs(active, variables)
            parsed.scoring_table = ensure_baseline_scoring_rows(parsed.scoring_table, scoring_specs)
            return parsed
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            continue

    raise SummaryGenerationError(
        f"Model did not return valid JSON after two attempts: {last_error}"
    )
