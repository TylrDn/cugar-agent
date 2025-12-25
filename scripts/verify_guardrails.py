#!/usr/bin/env python3
"""Guardrail and changelog verification script.

Checks:
- Root AGENTS.md exists and contains required sections.
- Allowlisted directories carry routing markers (AGENTS.md or inheritance marker).
- No non-root AGENTS.md claims to be canonical.
- CHANGELOG.md has a vNext section and guardrail-related changes update it.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised via dependency in setup script
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
GUARDRAILS_TOML = REPO_ROOT / "guardrails.toml"
PYPROJECT = REPO_ROOT / "pyproject.toml"


@dataclass
class GuardrailConfig:
    allowlisted_dirs: List[str] = field(default_factory=list)
    inherit_marker: str = "Root guardrails apply as-is; no directory-specific overrides."
    required_sections: List[str] = field(default_factory=list)
    canonical_inherit_phrase: str = "This directory inherits from root `AGENTS.md` (canonical). Conflicts resolve to root."
    vnext_keywords: List[str] = field(default_factory=list)
    guarded_path_prefixes: List[str] = field(default_factory=list)


DEFAULT_CONFIG = GuardrailConfig(
    allowlisted_dirs=["configurations", "docs", "src", ".github", "scripts", "examples"],
    required_sections=[
        "## 1. Scope & Precedence",
        "## 2. Profile Isolation",
        "## 3. Registry Hygiene",
        "## 4. Sandbox Expectations",
        "## 5. Audit / Trace Semantics",
        "## 6. Documentation Update Rules",
        "## 7. Verification & No Conflicting Guardrails",
    ],
    vnext_keywords=["guardrail", "audit", "registry", "ci", "safety"],
    guarded_path_prefixes=["AGENTS.md", "docs/", ".github/", "scripts/", "configurations/"],
)

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_toml(path: Path) -> Dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_guardrail_config(repo_root: Optional[Path] = None) -> GuardrailConfig:
    repo_root = repo_root or REPO_ROOT
    config_path = repo_root / "guardrails.toml"
    pyproject_path = repo_root / "pyproject.toml"
    config: Dict[str, object] = {}
    if config_path.exists():
        config = _load_toml(config_path).get("guardrails", {})
    elif pyproject_path.exists():
        raw = _load_toml(pyproject_path)
        tool = raw.get("tool", {}) if isinstance(raw, dict) else {}
        config = tool.get("guardrails", {}) if isinstance(tool, dict) else {}

    return GuardrailConfig(
        allowlisted_dirs=list(config.get("allowlisted_dirs", DEFAULT_CONFIG.allowlisted_dirs)),
        inherit_marker=str(config.get("inherit_marker", DEFAULT_CONFIG.inherit_marker)),
        required_sections=list(config.get("required_sections", DEFAULT_CONFIG.required_sections)),
        canonical_inherit_phrase=str(
            config.get(
                "canonical_inherit_phrase", DEFAULT_CONFIG.canonical_inherit_phrase
            )
        ),
        vnext_keywords=[kw.lower() for kw in config.get("vnext_keywords", DEFAULT_CONFIG.vnext_keywords)],
        guarded_path_prefixes=list(
            config.get("guarded_path_prefixes", DEFAULT_CONFIG.guarded_path_prefixes)
        ),
    )


def ensure_root_agents(config: GuardrailConfig) -> List[str]:
    errors: List[str] = []
    if not ROOT_AGENTS.exists():
        return ["Root AGENTS.md is missing"]
    content = read_text(ROOT_AGENTS)
    for section in config.required_sections:
        if section not in content:
            errors.append(f"Root AGENTS.md missing required section heading: '{section}'")
    if "canonical" not in content.lower():
        errors.append("Root AGENTS.md must declare itself canonical")
    return errors

def _has_inherit_marker(path: Path, config: GuardrailConfig) -> bool:
    guard_file = path / ".guardrails-inherit"
    if guard_file.exists():
        try:
            return config.inherit_marker.lower() in read_text(guard_file).lower()
        except OSError:
            return False
    readme = path / "README.md"
    if readme.exists():
        try:
            if config.inherit_marker.lower() in read_text(readme).lower():
                return True
        except OSError:
            return False
    return False

def ensure_routing_markers(config: GuardrailConfig) -> List[str]:
    errors: List[str] = []
    for dirname in config.allowlisted_dirs:
        directory = REPO_ROOT / dirname
        if not directory.exists():
            errors.append(f"Allowlisted directory missing: {dirname}")
            continue
        local_agents = directory / "AGENTS.md"
        if local_agents.exists():
            continue
        if not _has_inherit_marker(directory, config):
            errors.append(
                f"Directory '{dirname}' must contain AGENTS.md or inheritance marker (.guardrails-inherit or README line)"
            )
    return errors

def ensure_no_conflicting_canonical(config: GuardrailConfig) -> List[str]:
    errors: List[str] = []
    for path in REPO_ROOT.rglob("AGENTS.md"):
        if path.resolve() == ROOT_AGENTS.resolve():
            continue
        content = read_text(path).lower()
        if "canonical" in content and config.canonical_inherit_phrase.lower() not in content:
            errors.append(f"{path} claims canonical status; only root AGENTS.md may do that")
    return errors

def _extract_vnext(changelog_text: str) -> Optional[str]:
    lines = changelog_text.splitlines()
    section_start = None
    for idx, line in enumerate(lines):
        if re.match(r"##\s*vNext\b", line, flags=re.IGNORECASE):
            section_start = idx + 1
            break
    if section_start is None:
        return None
    body_lines: List[str] = []
    for line in lines[section_start:]:
        if re.match(r"##\s+", line):
            break
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def ensure_changelog(changed_files: Sequence[str], config: GuardrailConfig) -> List[str]:
    errors: List[str] = []
    if not CHANGELOG.exists():
        return ["CHANGELOG.md is missing"]
    changelog_text = read_text(CHANGELOG)
    if "## vnext" not in changelog_text.lower():
        errors.append("CHANGELOG.md must contain a '## vNext' section")
        return errors
    vnext_body = _extract_vnext(changelog_text)
    if vnext_body is None:
        errors.append("Unable to parse '## vNext' section")
        return errors

    guarded_changes = any(
        path == "AGENTS.md" or any(path.startswith(prefix) for prefix in config.guarded_path_prefixes)
        for path in changed_files
    )
    if guarded_changes:
        lower_body = vnext_body.lower()
        if not any(keyword in lower_body for keyword in config.vnext_keywords):
            errors.append(
                "Guardrail/audit/CI changes detected but CHANGELOG.md vNext lacks guardrail/audit/registry/CI/safety keywords"
            )
    return errors

def _validate_git_ref(git_ref: str) -> str:
    if not git_ref:
        raise ValueError("git ref must be non-empty")
    if not re.fullmatch(r"[A-Za-z0-9._/@\-]+", git_ref):
        raise ValueError(f"Invalid git ref: {git_ref}")
    return git_ref


def _run_git_diff(args: List[str]) -> List[str]:
    result = subprocess.run(args, cwd=REPO_ROOT, text=True, capture_output=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def discover_changed_files(base: Optional[str]) -> List[str]:
    files: Set[str] = set()
    if base:
        files.update(_run_git_diff(["git", "diff", "--name-only", f"{_validate_git_ref(base)}...HEAD"]))
    files.update(_run_git_diff(["git", "diff", "--name-only"]))
    files.update(_run_git_diff(["git", "diff", "--name-only", "--cached"]))
    return sorted(files)

def run_checks(
    base: Optional[str] = None,
    changed_files: Optional[Sequence[str]] = None,
    config: Optional[GuardrailConfig] = None,
) -> List[str]:
    config = config or load_guardrail_config()
    errors: List[str] = []
    errors.extend(ensure_root_agents(config))
    errors.extend(ensure_routing_markers(config))
    errors.extend(ensure_no_conflicting_canonical(config))
    files = list(changed_files) if changed_files is not None else discover_changed_files(base)
    errors.extend(ensure_changelog(files, config))
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify guardrails and changelog discipline")
    parser.add_argument("--base", help="Git ref to diff against for change detection", default=os.getenv("GUARDRAILS_BASE_REF"))
    args = parser.parse_args(argv)
    try:
        errors = run_checks(base=args.base)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
        print(f"Guardrail verification aborted: {exc}")
        return 1
    if errors:
        print("Guardrail verification failed:\n - " + "\n - ".join(errors))
        return 1
    print("Guardrail verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
