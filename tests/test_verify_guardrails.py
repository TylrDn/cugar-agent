from pathlib import Path

import pytest

import scripts.verify_guardrails as vg


MINIMAL_ROOT_AGENTS = """# Root
## 1. Scope & Precedence
canonical allowlist denylist escalation budget redaction PlannerAgent WorkerAgent CoordinatorAgent
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


def configure_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vg, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(vg, "ROOT_AGENTS", tmp_path / "AGENTS.md")
    monkeypatch.setattr(vg, "CHANGELOG", tmp_path / "CHANGELOG.md")


def write_allowlisted_dirs(tmp_path: Path) -> None:
    for dirname in vg.CONFIG.allowlisted_dirs:
        target = tmp_path / dirname
        target.mkdir(parents=True, exist_ok=True)
        inherit = target / ".guardrails-inherit"
        inherit.write_text(vg.INHERIT_MARKER, encoding="utf-8")


def write_root_agents(tmp_path: Path, content: str = MINIMAL_ROOT_AGENTS) -> None:
    (tmp_path / "AGENTS.md").write_text(content, encoding="utf-8")


def write_changelog(tmp_path: Path, content: str = MINIMAL_CHANGELOG) -> None:
    (tmp_path / "CHANGELOG.md").write_text(content, encoding="utf-8")


def test_missing_root_agents_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_changelog(tmp_path)

    errors = vg.run_checks(changed_files=[])

    assert any("Root AGENTS.md is missing" in err for err in errors)


def test_missing_inherit_marker_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_root_agents(tmp_path)
    write_changelog(tmp_path)

    for dirname in vg.CONFIG.allowlisted_dirs:
        (tmp_path / dirname).mkdir(parents=True, exist_ok=True)
    # Deliberately omit marker for docs
    for dirname in vg.CONFIG.allowlisted_dirs:
        if dirname == "docs":
            continue
        inherit = tmp_path / dirname / ".guardrails-inherit"
        inherit.write_text(vg.INHERIT_MARKER, encoding="utf-8")

    errors = vg.run_checks(changed_files=[])

    assert any("docs" in err for err in errors)


def test_conflicting_canonical_claim_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path)

    local_agents = tmp_path / "src" / "AGENTS.md"
    local_agents.write_text("This AGENTS is canonical for src", encoding="utf-8")

    errors = vg.run_checks(changed_files=[])

    assert any("canonical" in err.lower() for err in errors)


def test_guardrail_change_requires_vnext_keyword(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- minor update\n## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=["AGENTS.md"])

    assert any("CHANGELOG" in err for err in errors)


def test_happy_path_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- guardrail improvements with CI audit checks\n## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=["scripts/verify_guardrails.py", "docs/guide.md"])

    assert errors == []


def test_missing_guardrail_keywords_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path, content="""# Root
## 1. Scope & Precedence
canonical allowlist
## 2. Profile Isolation
## 3. Registry Hygiene
## 4. Sandbox Expectations
## 5. Audit / Trace Semantics
## 6. Documentation Update Rules
## 7. Verification & No Conflicting Guardrails
""")
    write_changelog(tmp_path)

    errors = vg.run_checks(changed_files=["AGENTS.md"])

    assert any("guardrail keywords" in err for err in errors)


def test_missing_interface_contracts_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path, content="""# Root
## 1. Scope & Precedence
canonical allowlist denylist escalation budget redaction
## 2. Profile Isolation
## 3. Registry Hygiene
## 4. Sandbox Expectations
## 5. Audit / Trace Semantics
## 6. Documentation Update Rules
## 7. Verification & No Conflicting Guardrails
""")
    write_changelog(tmp_path)

    errors = vg.run_checks(changed_files=["AGENTS.md"])

    assert any("planner/worker/coordinator" in err for err in errors)


def test_custom_keyword_env_allows_additional_terms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARDRAILS_VNEXT_KEYWORDS", "compliance")
    monkeypatch.setattr(vg, "CONFIG", vg.GuardrailConfig.from_env())
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- compliance review completed\n## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=["docs/guide.md"])

    assert errors == []


def test_missing_changelog_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)

    errors = vg.run_checks(changed_files=[])

    assert any("CHANGELOG.md is missing" in err for err in errors)


def test_changelog_without_vnext_heading_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=[])

    assert any("must contain a '## vNext' section" in err for err in errors)


def test_changelog_with_empty_vnext_body_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n## v1.0.0\n- baseline\n""")

    errors = vg.run_checks(changed_files=[])

    assert any("Unable to parse '## vNext' section" in err for err in errors)


def test_changelog_with_duplicate_vnext_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_allowlisted_dirs(tmp_path)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- change\n## vNext\n- another\n""")

    errors = vg.run_checks(changed_files=[])

    assert any("Unable to parse '## vNext' section" in err for err in errors)


def test_local_agents_requires_inherit_phrase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    configure_repo(tmp_path, monkeypatch)
    write_root_agents(tmp_path)
    write_changelog(tmp_path)
    write_allowlisted_dirs(tmp_path)

    local_agents = tmp_path / "docs" / "AGENTS.md"
    local_agents.write_text("Custom guardrails", encoding="utf-8")

    errors = vg.run_checks(changed_files=[])

    assert any("inheritance" in err.lower() for err in errors)


def test_main_reports_failures(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(vg, "run_checks", lambda base=None: ["FAIL: missing"])

    exit_code = vg.main([])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Guardrail verification failed" in captured.out
    assert "FAIL" in captured.out


def test_main_reports_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(vg, "run_checks", lambda base=None: [])

    exit_code = vg.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Guardrail verification passed" in captured.out


def test_env_overrides_respected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARDRAILS_ALLOWLISTED_DIRS", "custom")
    monkeypatch.setenv("GUARDRAILS_GUARDED_PREFIXES", "special/")
    monkeypatch.setattr(vg, "CONFIG", vg.GuardrailConfig.from_env())
    configure_repo(tmp_path, monkeypatch)
    write_root_agents(tmp_path)
    write_changelog(tmp_path, content="""## vNext\n- minor update\n## v1.0.0\n- baseline\n""")

    custom_dir = tmp_path / "custom"
    custom_dir.mkdir(parents=True)

    errors = vg.run_checks(changed_files=["special/file.txt"])

    assert any("custom" in err for err in errors)
    assert any("CHANGELOG" in err for err in errors)
