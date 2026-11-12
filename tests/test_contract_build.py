import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".contract" / "scripts" / "build_agents.py"


@pytest.fixture(scope="module")
def build():
    spec = importlib.util.spec_from_file_location("build_agents", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_agents"] = module  # dataclasses look the module up by name
    spec.loader.exec_module(module)
    return module


def rule_file(**overrides):
    fields = {"id": "a-rule", "title": "A rule", "scope": "[global]", "impact": "LOW", "triggers": "[one, two]"}
    fields.update(overrides)
    lines = [f"{key}: {value}" for key, value in fields.items() if value is not None]
    return "---\n" + "\n".join(lines) + "\n---\n\nBody text.\n"


def test_the_committed_artifacts_are_up_to_date(build, capsys):
    assert build.main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_every_rule_is_in_the_routing_table_and_the_index(build):
    artifacts = build.build_artifacts()
    root_agents = artifacts[build.ROOT_AGENTS]
    rules = build.read_rules(build.resolve_general(build.load_config()))
    assert len(rules) >= 15
    for rule in rules:
        assert f"{rule.cls}/{rule.file}" in root_agents
    assert f'"count": {len(rules)}' in artifacts[build.INDEX_PATH]


def test_a_rule_file_is_parsed_with_inline_and_block_lists(build):
    rule = build.parse_rule(rule_file(appliesTo=""), "a-rule.md", "project")
    assert rule.triggers == ["one", "two"] and rule.scope == ["global"]
    block = (
        "---\nid: x\ntitle: T\nscope: [global]\nimpact: LOW\ntriggers: [t]\nappliesTo:\n  - a/**\n  - b.py\n---\nBody\n"
    )
    assert build.parse_rule(block, "x.md", "project").applies_to == ["a/**", "b.py"]


@pytest.mark.parametrize("missing", ["id", "title", "scope", "impact", "triggers"])
def test_missing_frontmatter_fields_fail_the_build(build, missing):
    with pytest.raises(build.BuildError, match=missing):
        build.parse_rule(rule_file(**{missing: None}), "a-rule.md", "project")


def test_a_file_without_frontmatter_fails_the_build(build):
    with pytest.raises(build.BuildError, match="frontmatter"):
        build.parse_rule("no frontmatter", "x.md", "project")


def test_unknown_placeholders_fail_instead_of_being_emitted(build):
    assert build.interpolate("{{a}} and {{b}}", {"a": "1", "b": ["x", "y"]}) == "1 and x, y"
    with pytest.raises(build.BuildError, match="unknown placeholder"):
        build.interpolate("{{nope}}", {})


def test_the_generated_markers_must_exist(build):
    content = "intro\n<!-- BEGIN GENERATED: routing (x) -->\nold\n<!-- END GENERATED: routing -->\noutro"
    assert "new" in build.inject_generated(content, "routing", "new", "f")
    with pytest.raises(build.BuildError, match="missing generated markers"):
        build.inject_generated("no markers", "routing", "new", "f")


def test_duplicate_ids_and_mismatched_filenames_are_rejected(build, monkeypatch, tmp_path):
    (tmp_path / "project").mkdir()
    (tmp_path / "project" / "a-rule.md").write_text(rule_file(), encoding="utf-8")
    (tmp_path / "project" / "other.md").write_text(rule_file(), encoding="utf-8")
    monkeypatch.setattr(build, "RULES_DIR", tmp_path)
    with pytest.raises(build.BuildError, match="filename must match id|duplicate"):
        build.read_rules({})


def test_stale_artifacts_are_reported(build, monkeypatch, capsys):
    missing = build.ROOT / "does-not-exist.md"
    monkeypatch.setattr(build, "build_artifacts", lambda: {missing: "content"})
    assert build.main(["--check"]) == 1
    assert "stale" in capsys.readouterr().err
