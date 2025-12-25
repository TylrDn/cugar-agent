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
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
ALLOWLISTED_DIRS = [
    "configurations",
    "docs",
    "src",
    ".github",
    "scripts",
    "examples",
]
INHERIT_MARKER = "Root guardrails apply as-is; no directory-specific overrides."
REQUIRED_SECTIONS = [
    "## 1. Scope & Precedence",
    "## 2. Profile Isolation",
    "## 3. Registry Hygiene",
    "## 4. Sandbox Expectations",
    "## 5. Audit / Trace Semantics",
    "## 6. Documentation Update Rules",
    "## 7. Verification & No Conflicting Guardrails",
]
CANONICAL_INHERIT_PHRASE = "This directory inherits from root `AGENTS.md` (canonical). Conflicts resolve to root."
VNEXT_KEYWORDS = ["guardrail", "audit", "registry", "ci", "safety"]
GUARDED_PATH_PREFIXES = [
    "AGENTS.md",
    "docs/",
    ".github/",
    "scripts/",
    "configurations/",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_root_agents() -> List[str]:
    errors: List[str] = []
    if not ROOT_AGENTS.exists():
        return ["Root AGENTS.md is missing"]
    content = read_text(ROOT_AGENTS)
    for section in REQUIRED_SECTIONS:
        if section not in content:
            errors.append(f"Root AGENTS.md missing required section heading: '{section}'")
    if "canonical" not in content.lower():
        errors.append("Root AGENTS.md must declare itself canonical")
    return errors


def _has_inherit_marker(path: Path) -> bool:
    guard_file = path / ".guardrails-inherit"
    if guard_file.exists():
        try:
            return INHERIT_MARKER.lower() in read_text(guard_file).lower()
        except OSError:
            return False
    readme = path / "README.md"
    if readme.exists():
        try:
            if INHERIT_MARKER.lower() in read_text(readme).lower():
                return True
        except OSError:
            return False
    return False


def ensure_routing_markers() -> List[str]:
    errors: List[str] = []
    for dirname in ALLOWLISTED_DIRS:
        directory = REPO_ROOT / dirname
        if not directory.exists():
            errors.append(f"Allowlisted directory missing: {dirname}")
            continue
        local_agents = directory / "AGENTS.md"
        if local_agents.exists():
            continue
        if not _has_inherit_marker(directory):
            errors.append(
                f"Directory '{dirname}' must contain AGENTS.md or inheritance marker (.guardrails-inherit or README line)"
            )
    return errors


def ensure_no_conflicting_canonical() -> List[str]:
    errors: List[str] = []
    for path in REPO_ROOT.rglob("AGENTS.md"):
        if path.resolve() == ROOT_AGENTS.resolve():
            continue
        content = read_text(path).lower()
        if "canonical" in content and CANONICAL_INHERIT_PHRASE.lower() not in content:
            errors.append(f"{path} claims canonical status; only root AGENTS.md may do that")
    return errors


def _extract_vnext(changelog_text: str) -> Optional[str]:
    match = re.search(r"##\s*vNext\s*(.*?)\n##\s*", changelog_text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"##\s*vNext\s*(.*)", changelog_text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def ensure_changelog(changed_files: Sequence[str]) -> List[str]:
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
        path == "AGENTS.md" or any(path.startswith(prefix) for prefix in GUARDED_PATH_PREFIXES)
        for path in changed_files
    )
    if guarded_changes:
        lower_body = vnext_body.lower()
        if not any(keyword in lower_body for keyword in VNEXT_KEYWORDS):
            errors.append(
                "Guardrail/audit/CI changes detected but CHANGELOG.md vNext lacks guardrail/audit/registry/CI/safety keywords"
            )
    return errors


def _run_git_diff(args: List[str]) -> List[str]:
    try:
        output = subprocess.check_output(args, cwd=REPO_ROOT, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def discover_changed_files(base: Optional[str]) -> List[str]:
    files: Set[str] = set()
    if base:
        files.update(_run_git_diff(["git", "diff", "--name-only", f"{base}...HEAD"]))
    files.update(_run_git_diff(["git", "diff", "--name-only"]))
    files.update(_run_git_diff(["git", "diff", "--name-only", "--cached"]))
    return sorted(files)


def run_checks(base: Optional[str] = None, changed_files: Optional[Sequence[str]] = None) -> List[str]:
    errors: List[str] = []
    errors.extend(ensure_root_agents())
    errors.extend(ensure_routing_markers())
    errors.extend(ensure_no_conflicting_canonical())
    files = list(changed_files) if changed_files is not None else discover_changed_files(base)
    errors.extend(ensure_changelog(files))
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify guardrails and changelog discipline")
    parser.add_argument("--base", help="Git ref to diff against for change detection", default=os.getenv("GUARDRAILS_BASE_REF"))
    args = parser.parse_args(argv)
    errors = run_checks(base=args.base)
    if errors:
        print("Guardrail verification failed:\n - " + "\n - ".join(errors))
        return 1
    print("Guardrail verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
