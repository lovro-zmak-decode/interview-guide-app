#!/usr/bin/env python3
"""Build script for the agent contract.

Project-specific values live in .contract/project.config.json. General rules are authored as
templates in .contract/templates/general/ with {{placeholders}}; project rules are authored
directly in .contract/rules/project/. The build interpolates the config and regenerates every
derived artifact so nothing can drift:

  1. Resolved general rule files (.contract/rules/general/*.md) from templates and config.
  2. The routing tables inside AGENTS.md and any per-area AGENTS.md listed in config.apps
     (between the `<!-- BEGIN/END GENERATED -->` markers).
  3. .contract/index.json, a machine index for on-demand retrieval.
  4. .contract/reference/AGENTS.full.md, the compiled whole-set document.

Usage:
  python .contract/scripts/build_agents.py          # write the artifacts
  python .contract/scripts/build_agents.py --check  # exit 1 if the artifacts are stale
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = ROOT / ".contract"
RULES_DIR = CONTRACT_DIR / "rules"
TEMPLATES_GENERAL = CONTRACT_DIR / "templates" / "general"
INDEX_PATH = CONTRACT_DIR / "index.json"
REFERENCE_PATH = CONTRACT_DIR / "reference" / "AGENTS.full.md"
ROOT_AGENTS = ROOT / "AGENTS.md"

CLASSES = [("general", "Ways of working (general)"), ("project", "Project rules")]
REQUIRED_FIELDS = ("id", "title", "scope", "impact", "triggers")


class BuildError(Exception):
    pass


@dataclass
class Rule:
    id: str
    title: str
    cls: str
    scope: list[str]
    impact: str
    triggers: list[str]
    applies_to: list[str]
    file: str
    body: str


def load_config(root: Path = ROOT) -> dict:
    return json.loads((root / ".contract" / "project.config.json").read_text(encoding="utf-8"))


def interpolate(text: str, config: dict) -> str:
    """Replace {{key}} with config[key] (lists joined by ", "). Unknown keys fail the build."""

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in config:
            raise BuildError(f"unknown placeholder {{{{{key}}}}} (not in .contract/project.config.json)")
        value = config[key]
        return ", ".join(value) if isinstance(value, list) else str(value)

    return re.sub(r"\{\{(\w+)\}\}", replace, text)


def _strip_quotes(value: str) -> str:
    return re.sub(r"""^["']|["']$""", "", value)


def parse_rule(raw: str, file: str, cls: str) -> Rule:
    """Parse a rule file: frontmatter with `key: scalar`, inline `[a, b]` or block `- item` lists."""
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
    if not match:
        raise BuildError(f"{file}: missing frontmatter")
    frontmatter, body = match.groups()

    fields: dict[str, str | list[str]] = {}
    block_key: str | None = None
    for line in frontmatter.split("\n"):
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and block_key:
            fields[block_key].append(_strip_quotes(item.group(1).strip()))  # type: ignore[union-attr]
            continue
        pair = re.match(r"^([a-zA-Z]+):\s*(.*)$", line)
        if not pair:
            continue
        key, value = pair.group(1), pair.group(2).strip()
        if value == "":
            fields[key] = []
            block_key = key
        elif value.startswith("[") and value.endswith("]"):
            fields[key] = [_strip_quotes(part.strip()) for part in value[1:-1].split(",") if part.strip()]
            block_key = None
        else:
            fields[key] = _strip_quotes(value)
            block_key = None

    for key in REQUIRED_FIELDS:
        if key not in fields:
            raise BuildError(f'{file}: missing required frontmatter field "{key}"')

    def as_list(value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    return Rule(
        id=str(fields["id"]),
        title=str(fields["title"]),
        cls=cls,
        scope=as_list(fields["scope"]),
        impact=str(fields["impact"]),
        triggers=as_list(fields["triggers"]),
        applies_to=as_list(fields.get("appliesTo")),
        file=file,
        body=body.strip(),
    )


def resolve_general(config: dict) -> dict[str, str]:
    if not TEMPLATES_GENERAL.exists():
        return {}
    return {
        path.name: interpolate(path.read_text(encoding="utf-8"), config)
        for path in sorted(TEMPLATES_GENERAL.glob("*.md"))
        if not path.name.startswith("_")
    }


def read_rules(resolved_general: dict[str, str]) -> list[Rule]:
    rules = [parse_rule(content, name, "general") for name, content in sorted(resolved_general.items())]
    project_dir = RULES_DIR / "project"
    if project_dir.exists():
        for path in sorted(project_dir.glob("*.md")):
            if not path.name.startswith("_"):
                rules.append(parse_rule(path.read_text(encoding="utf-8"), path.name, "project"))

    seen: set[str] = set()
    for rule in rules:
        if rule.id in seen:
            raise BuildError(f"duplicate rule id: {rule.id}")
        seen.add(rule.id)
        if Path(rule.file).stem != rule.id:
            raise BuildError(f'{rule.file}: filename must match id "{rule.id}"')
    return rules


def routing_table(rules: list[Rule], prefix: str) -> str:
    rows = ["| If the task involves... | Read |", "|---|---|"]
    rows += [f"| {', '.join(r.triggers)} | [{r.title}]({prefix}{r.cls}/{r.file}) |" for r in rules]
    return "\n".join(rows)


def inject_generated(content: str, key: str, replacement: str, file: str) -> str:
    pattern = re.compile(
        rf"(<!-- BEGIN GENERATED: {re.escape(key)}[^\n]*-->\n).*?(<!-- END GENERATED: {re.escape(key)} -->)",
        re.DOTALL,
    )
    if not pattern.search(content):
        raise BuildError(f'{file}: missing generated markers for "{key}"')
    return pattern.sub(lambda m: f"{m.group(1)}{replacement}\n{m.group(2)}", content, count=1)


def build_index(rules: list[Rule]) -> str:
    entries = [
        {
            "id": r.id,
            "title": r.title,
            "class": r.cls,
            "file": f".contract/rules/{r.cls}/{r.file}",
            "scope": r.scope,
            "impact": r.impact,
            "triggers": r.triggers,
            "appliesTo": r.applies_to,
        }
        for r in rules
    ]
    counts = {key: sum(1 for e in entries if e["class"] == key) for key, _ in CLASSES}
    return json.dumps({"generated": True, "count": len(entries), "counts": counts, "rules": entries}, indent=2) + "\n"


def build_reference(rules: list[Rule], metadata: dict, config: dict) -> str:
    doc = f"# {metadata['organization']} Agent Contract (compiled reference)\n\n"
    doc += f"**Version {metadata['version']}** ({metadata['date']})\n\n"
    doc += "> Generated from .contract/rules/*.md by build_agents.py. Do not edit by hand.\n"
    doc += "> This is the whole-set reference. Agents should normally read the routing table in\n"
    doc += "> AGENTS.md and load individual rule files, not this file.\n\n---\n\n"
    doc += f"## Abstract\n\n{metadata['abstract']}\n\n---\n\n"
    for cls_key, cls_name in CLASSES:
        cls_rules = [r for r in rules if r.cls == cls_key]
        if not cls_rules:
            continue
        doc += f"## {cls_name}\n\n"
        for category in config["categories"]:
            category_rules = [r for r in cls_rules if r.file.startswith(category["prefix"])]
            if not category_rules:
                continue
            doc += f"### {category['name']}\n\n"
            for r in category_rules:
                doc += f"#### {r.title}\n\n"
                doc += f"**Impact: {r.impact}** | scope: {', '.join(r.scope)} | id: `{r.id}`\n\n"
                body = r.body.replace("](../../../", "](../../")  # rule files are one level deeper than this file
                doc += f"{body}\n\n---\n\n"
    return doc.rstrip() + "\n"


def build_artifacts(root: Path = ROOT) -> dict[Path, str]:
    config = load_config(root)
    metadata = json.loads((root / ".contract" / "metadata.json").read_text(encoding="utf-8"))
    resolved = resolve_general(config)
    rules = read_rules(resolved)

    artifacts: dict[Path, str] = {}
    for name, content in resolved.items():
        artifacts[RULES_DIR / "general" / name] = content

    root_agents = ROOT_AGENTS.read_text(encoding="utf-8")
    artifacts[ROOT_AGENTS] = inject_generated(
        root_agents, "routing", routing_table(rules, ".contract/rules/"), "AGENTS.md"
    )

    for app in config.get("apps", []):
        target = root / app["path"]
        if not target.exists():
            continue
        relative = Path(*([".."] * len(Path(app["path"]).parent.parts)), ".contract", "rules").as_posix() + "/"
        scoped = [r for r in rules if app["scope"] in r.scope]
        content = inject_generated(
            target.read_text(encoding="utf-8"), f"routing:{app['scope']}", routing_table(scoped, relative), app["path"]
        )
        artifacts[target] = content

    artifacts[INDEX_PATH] = build_index(rules)
    artifacts[REFERENCE_PATH] = build_reference(rules, metadata, config)
    return artifacts


def main(argv: list[str]) -> int:
    check = "--check" in argv
    try:
        artifacts = build_artifacts()
    except BuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if check:
        stale = [p for p, content in artifacts.items() if not p.exists() or p.read_text(encoding="utf-8") != content]
        if stale:
            print("Agent contract artifacts are stale. Run: python .contract/scripts/build_agents.py", file=sys.stderr)
            for path in stale:
                print(f"  - {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print("Agent contract artifacts are up to date.")
        return 0

    for path, content in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
