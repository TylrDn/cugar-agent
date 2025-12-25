from pathlib import Path

import pytest

import scripts.verify_guardrails as vg


MINIMAL_ROOT_AGENTS = """# Root
## 1. Scope & Precedence
canonical
## 2. Profile Isolation
## 3. Registry Hygiene
## 4. Sandbox Expectations
## 5. Audit / Trace Semantics
## 6. Documentation Update Rules
## 7. Verification & No Conflicting Guardrails
"""


MINIMAL_CHANGELOG = """## vNext
- guardrail change
## v1.0.0
- baseline
"""


def configure_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> vg.GuardrailConfig:
    monkeypatch.setattr(vg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vg, "ROOT_AGENTS", tmp_path / "AGENTS.md")
    monkeypatch.setattr(vg, "CHANGELOG", tmp_path / "CHANGELOG.md")
    monkeypatch.setattr(vg, "GUARDRAILS_TOML", tmp_path / "guardrails.toml")
    monkeypatch.setattr(vg, "PYPROJECT", tmp_path / "pyproject.toml")
    return vg.load_guardrail_config(tmp_path)


def write_allowlisted_dirs(tmp_path: Path, config: vg.GuardrailConfig) -> None:
    for dirname in config.allowlisted_dirs:
        target = tmp_path / dirname
        target.mkdir(parents=True, exist_ok=True)
        inherit = target / ".guardrails-inherit"
        inherit.write_text(config.inherit_marker, encoding="utf-8")


def write_root_agents(tmp_path: Path, content: str = MINIMAL_ROOT_AGENTS) -> None:
    (tmp_path / "AGENTS.md").write_text(content, encoding="utf-8")


def write_changelog(tmp_path: Path, content: str = MINIMAL_CHANGELOG) -> None:
    (tmp_path / "CHANGELOG.md").write_text(content, encoding="utf-8")


def test_missing_root_agents_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path, config)
    write_changelog(tmp_path)

    errors = vg.run_checks(changed_files=[], config=config)

    assert any("Root AGENTS.md is missing" in err for err in errors)


def test_missing_inherit_marker_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configure_repo(tmp_path, monkeypatch)
    write_root_agents(tmp_path)
    write_changelog(tmp_path)

    for dirname in config.allowlisted_dirs:
        (tmp_path / dirname).mkdir(parents=True, exist_ok=True)
    # Deliberately omit marker for docs
    for dirname in config.allowlisted_dirs:
        if dirname == "docs":
            continue
        inherit = tmp_path / dirname / ".guardrails-inherit"
        inherit.write_text(config.inherit_marker, encoding="utf-8")

    errors = vg.run_checks(changed_files=[], config=config)

    assert any("docs" in err for err in errors)


def test_conflicting_canonical_claim_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path, config)
    write_root_agents(tmp_path)
    write_changelog(tmp_path)

    local_agents = tmp_path / "src" / "AGENTS.md"
    local_agents.write_text("This AGENTS is canonical for src", encoding="utf-8")

    errors = vg.run_checks(changed_files=[], config=config)

    assert any("canonical" in err.lower() for err in errors)


def test_guardrail_change_requires_vnext_keyword(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path, config)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- minor update\n## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=["AGENTS.md"], config=config)

    assert any("CHANGELOG" in err for err in errors)


def test_happy_path_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path, config)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- guardrail improvements with CI audit checks\n## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=["scripts/verify_guardrails.py", "docs/guide.md"], config=config)

    assert errors == []


def test_vnext_parser_handles_terminal_section() -> None:
    body = vg._extract_vnext("""## vNext\n- note\n- another\n""")
    assert body == "- note\n- another"


def test_guardrails_config_from_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "guardrails.toml").write_text(
        """[guardrails]\nallowlisted_dirs=[\"alpha\"]\ninherit_marker=\"custom marker\"\nrequired_sections=[\"## 1. Scope & Precedence\"]\ncanonical_inherit_phrase=\"inherit note\"\nvnext_keywords=[\"custom\"]\nguarded_path_prefixes=[\"alpha/\"]\n""",
        encoding="utf-8",
    )
    config = configure_repo(tmp_path, monkeypatch)

    assert config.allowlisted_dirs == ["alpha"]
    assert config.inherit_marker == "custom marker"
    assert config.required_sections == ["## 1. Scope & Precedence"]
    assert config.canonical_inherit_phrase == "inherit note"
    assert config.vnext_keywords == ["custom"]
    assert config.guarded_path_prefixes == ["alpha/"]


def test_guardrails_config_from_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """[tool.guardrails]\nallowlisted_dirs=[\"beta\"]\n""",
        encoding="utf-8",
    )
    config = configure_repo(tmp_path, monkeypatch)
    assert config.allowlisted_dirs == ["beta"]


def test_invalid_git_ref_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vg, "REPO_ROOT", Path("/tmp/nowhere"))
    with pytest.raises(ValueError):
        vg.discover_changed_files("bad ref with space")
