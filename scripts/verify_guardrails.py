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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
DEFAULT_ALLOWLISTED_DIRS = [
    "configurations",
    "config",
    "docs",
    "src",
    ".github",
    "scripts",
    "examples",
]
DEFAULT_GUARDED_PATH_PREFIXES = [
    "AGENTS.md",
    "docs/",
    ".github/",
    "scripts/",
    "configurations/",
    "config/",
]
DEFAULT_VNEXT_KEYWORDS = ["guardrail", "audit", "registry", "ci", "safety", "policy", "verification"]
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
REQUIRED_GUARDRAIL_KEYWORDS = ["allowlist", "denylist", "escalation", "redaction", "budget"]
REQUIRED_INTERFACES = ["PlannerAgent", "WorkerAgent", "CoordinatorAgent"]
SAFE_GIT_REF_PATTERN = re.compile(r"^(?!-)[A-Za-z0-9._/\-]+$")


def _csv_env(var: str, default: List[str]) -> List[str]:
    raw = os.getenv(var)
    if not raw:
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass
class GuardrailConfig:
    allowlisted_dirs: List[str]
    guarded_path_prefixes: List[str]
    vnext_keywords: List[str]

    @classmethod
    def from_env(cls) -> "GuardrailConfig":
        return cls(
            allowlisted_dirs=_csv_env("GUARDRAILS_ALLOWLISTED_DIRS", DEFAULT_ALLOWLISTED_DIRS),
            guarded_path_prefixes=_csv_env(
                "GUARDRAILS_GUARDED_PREFIXES", DEFAULT_GUARDED_PATH_PREFIXES
            ),
            vnext_keywords=_csv_env("GUARDRAILS_VNEXT_KEYWORDS", DEFAULT_VNEXT_KEYWORDS),
        )


CONFIG = GuardrailConfig.from_env()


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


def ensure_guardrail_keywords() -> List[str]:
    if not ROOT_AGENTS.exists():
        return []
    content = read_text(ROOT_AGENTS).lower()
    missing = [kw for kw in REQUIRED_GUARDRAIL_KEYWORDS if kw.lower() not in content]
    if not missing:
        return []
    return [
        "Root AGENTS.md missing required guardrail keywords: "
        + ", ".join(sorted(missing))
    ]


def ensure_interface_contracts() -> List[str]:
    if not ROOT_AGENTS.exists():
        return []
    content = read_text(ROOT_AGENTS)
    missing = [iface for iface in REQUIRED_INTERFACES if iface not in content]
    if not missing:
        return []
    return [
        "Root AGENTS.md must describe planner/worker/coordinator interfaces; missing: "
        + ", ".join(sorted(missing))
    ]


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
    for dirname in CONFIG.allowlisted_dirs:
        directory = REPO_ROOT / dirname
        if not directory.exists():
            errors.append(f"Allowlisted directory missing: {dirname}")
            continue
        local_agents = directory / "AGENTS.md"
        if local_agents.exists():
            content = read_text(local_agents)
            if CANONICAL_INHERIT_PHRASE.lower() not in content.lower():
                errors.append(
                    f"{local_agents} must declare inheritance from root AGENTS.md"
                )
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
    matches = list(re.finditer(r"##\s*vNext\b", changelog_text, flags=re.IGNORECASE))
    if not matches or len(matches) > 1:
        return None
    match = matches[0]
    start = match.end()
    remainder = changelog_text[start:]
    next_heading = re.search(r"\n##\s+", remainder)
    body = remainder[: next_heading.start()] if next_heading else remainder
    body = body.strip()
    return body or None


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
        path == "AGENTS.md" or any(path.startswith(prefix) for prefix in CONFIG.guarded_path_prefixes)
        for path in changed_files
    )
    if guarded_changes:
        lower_body = vnext_body.lower()
        if not any(keyword in lower_body for keyword in CONFIG.vnext_keywords):
            errors.append(
                "Guardrail/audit/CI changes detected but CHANGELOG.md vNext lacks guardrail/audit/registry/CI/safety keywords"
            )
    return errors


def discover_changed_files(base: Optional[str]) -> List[str]:
    files: Set[str] = set()

    def _git_diff_name_only(extra_args: Sequence[str]) -> List[str]:
        cmd = ["git", "diff", "--name-only", *extra_args]
        try:
            completed = subprocess.run(
                cmd,
                cwd=REPO_ROOT,
                text=True,
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    if base:
        sanitized_base = base if SAFE_GIT_REF_PATTERN.match(base) else None
        if sanitized_base:
            files.update(_git_diff_name_only([f"{sanitized_base}...HEAD"]))
    files.update(_git_diff_name_only([]))
    files.update(_git_diff_name_only(["--cached"]))
    return sorted(files)


def run_checks(base: Optional[str] = None, changed_files: Optional[Sequence[str]] = None) -> List[str]:
    errors: List[str] = []
    errors.extend(ensure_root_agents())
    errors.extend(ensure_guardrail_keywords())
    errors.extend(ensure_interface_contracts())
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
