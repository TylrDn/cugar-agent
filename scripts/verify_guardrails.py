from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

INHERIT_MARKER = "inherits: root guardrails"

DEFAULT_ALLOWLISTED_DIRS: tuple[str, ...] = ("docs", "src")
DEFAULT_GUARDED_PREFIXES: tuple[str, ...] = ("AGENTS.md", "config", "configs", "registry", "scripts/verify_guardrails.py")
DEFAULT_VNEXT_KEYWORDS: tuple[str, ...] = ("guardrail", "registry")
REQUIRED_GUARDRAIL_KEYWORDS: tuple[str, ...] = (
    "canonical",
    "allowlist",
    "denylist",
    "escalation",
    "budget",
    "redaction",
)
INTERFACE_CONTRACT_TERMS: tuple[str, ...] = ("PlannerAgent", "WorkerAgent", "CoordinatorAgent")


@dataclass(frozen=True)
class GuardrailConfig:
    allowlisted_dirs: tuple[str, ...]
    guarded_prefixes: tuple[str, ...]
    vnext_keywords: tuple[str, ...]

    @staticmethod
    def _split(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
        if raw is None:
            return default
        tokens: list[str] = []
        normalized = raw.replace(";", ",").replace("|", ",")
        for part in normalized.split(","):
            for token in part.split():
                cleaned = token.strip()
                if cleaned:
                    tokens.append(cleaned)
        return tuple(tokens) if tokens else default

    @classmethod
    def from_env(cls) -> "GuardrailConfig":
        return cls(
            allowlisted_dirs=cls._split(os.getenv("GUARDRAILS_ALLOWLISTED_DIRS"), DEFAULT_ALLOWLISTED_DIRS),
            guarded_prefixes=cls._split(os.getenv("GUARDRAILS_GUARDED_PREFIXES"), DEFAULT_GUARDED_PREFIXES),
            vnext_keywords=cls._split(os.getenv("GUARDRAILS_VNEXT_KEYWORDS"), DEFAULT_VNEXT_KEYWORDS),
        )


CONFIG = GuardrailConfig.from_env()


def _determine_changed_files(base_branch: str | None = None) -> list[str]:
    branch = base_branch or os.getenv("GUARDRAILS_BASE_BRANCH", "origin/main")
    try:
        subprocess.run(
            ["git", "fetch", "origin", branch],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return []

    normalized = branch if "..." not in branch else branch.split("...")[0]
    diff_args = ["git", "diff", "--name-only", f"{normalized}...HEAD"]
    try:
        result = subprocess.run(diff_args, capture_output=True, text=True, check=False, timeout=30)
    except subprocess.TimeoutExpired:
        return []

    if result.returncode != 0 or not result.stdout.strip():
        try:
            fallback = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1...HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return []
        output = fallback.stdout
    else:
        output = result.stdout

    return [line.strip() for line in output.splitlines() if line.strip()]


def _has_guardrail_keywords(content: str) -> bool:
    lowered = content.lower()
    return all(keyword in lowered for keyword in REQUIRED_GUARDRAIL_KEYWORDS)


def _has_interface_terms(content: str) -> bool:
    return all(term in content for term in INTERFACE_CONTRACT_TERMS)


def _load_vnext_body() -> tuple[str | None, str | None]:
    if not CHANGELOG.exists():
        return None, "CHANGELOG.md is missing; update it under '## vNext' for guardrail changes."

    body = CHANGELOG.read_text(encoding="utf-8")
    lines = body.splitlines()
    indices = [idx for idx, line in enumerate(lines) if line.strip().lower() == "## vnext"]
    if not indices:
        return None, "CHANGELOG.md must contain a '## vNext' section."
    if len(indices) > 1:
        return None, "Unable to parse '## vNext' section; multiple headings found."

    start = indices[0] + 1
    end = next((idx for idx, line in enumerate(lines[start:], start=start) if line.startswith("## ")), len(lines))
    section_lines = [line for line in lines[start:end] if line.strip()]
    if not section_lines:
        return None, "Unable to parse '## vNext' section; body is empty."

    return "\n".join(section_lines), None


def _guardrail_change_detected(changed_files: Iterable[str], config: GuardrailConfig) -> bool:
    for path in changed_files:
        normalized = path.lstrip("./")
        if normalized == "AGENTS.md" or normalized.startswith("AGENTS.md/"):
            return True
        if any(normalized.startswith(prefix) for prefix in config.guarded_prefixes):
            return True
    return False


def _check_allowlisted_dirs(config: GuardrailConfig) -> list[str]:
    errors: list[str] = []
    missing_markers: list[str] = []
    for dirname in config.allowlisted_dirs:
        target = REPO_ROOT / dirname
        marker = target / ".guardrails-inherit"
        if not marker.exists() or marker.read_text(encoding="utf-8").strip() != INHERIT_MARKER:
            missing_markers.append(str(dirname))
    if missing_markers:
        errors.append(f"Missing .guardrails-inherit markers for: {', '.join(missing_markers)}")
    return errors


def _check_local_agents(config: GuardrailConfig) -> list[str]:
    errors: list[str] = []
    for dirname in config.allowlisted_dirs:
        agents_path = REPO_ROOT / dirname / "AGENTS.md"
        if not agents_path.exists():
            continue
        content = agents_path.read_text(encoding="utf-8")
        if "canonical" in content.lower():
            errors.append(f"{agents_path.relative_to(REPO_ROOT)} must not declare itself canonical.")
        if "inherit" not in content.lower():
            errors.append(f"{agents_path.relative_to(REPO_ROOT)} must declare inheritance from root guardrails.")
    return errors


def run_checks(changed_files: Sequence[str] | None = None) -> list[str]:
    config = CONFIG
    errors: list[str] = []

    changes = list(changed_files) if changed_files is not None else _determine_changed_files(None)

    if not ROOT_AGENTS.exists():
        errors.append("Root AGENTS.md is missing; guardrail definitions must exist at the repository root.")
    else:
        content = ROOT_AGENTS.read_text(encoding="utf-8")
        if not _has_guardrail_keywords(content):
            errors.append(
                "Root AGENTS.md must include guardrail keywords (canonical, allowlist, denylist, escalation, budget, redaction)."
            )
        if not _has_interface_terms(content):
            errors.append("Root AGENTS.md must document planner/worker/coordinator interface contracts.")

    errors.extend(_check_allowlisted_dirs(config))
    errors.extend(_check_local_agents(config))

    vnext_body, vnext_error = _load_vnext_body()
    if vnext_error:
        errors.append(vnext_error)
    guardrail_change = _guardrail_change_detected(changes, config)
    if guardrail_change and vnext_body:
        if not any(keyword.lower() in vnext_body.lower() for keyword in config.vnext_keywords):
            keywords = ", ".join(config.vnext_keywords)
            allowlisted = ", ".join(config.allowlisted_dirs)
            errors.append(
                f"CHANGELOG '## vNext' must mention guardrail keywords ({keywords}) when guardrail changes affect allowlisted directories ({allowlisted})."
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    errors = run_checks()
    if errors:
        print("Guardrail verification failed:\n" + "\n".join(f"- {err}" for err in errors))
        return 1

    print("Guardrail verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
