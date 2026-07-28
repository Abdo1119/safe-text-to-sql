"""Release checks that never read excluded local secret files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".migration",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "evaluation/results",
        "legacy_reference",
        "logs",
        "venv",
    }
)
_SECRET_PATTERNS = (
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b")),
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
)


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """A finding that records location and category, never the matched value."""

    relative_path: str
    category: str


def scan_candidate_files(root: Path) -> tuple[SecretFinding, ...]:
    """Scan public candidates while explicitly skipping every local dotenv file."""

    findings: list[SecretFinding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if _is_excluded(relative):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for category, pattern in _SECRET_PATTERNS:
            if pattern.search(content):
                findings.append(
                    SecretFinding(
                        relative_path=relative,
                        category=category,
                    )
                )
    return tuple(findings)


def find_forbidden_paths(paths: list[str]) -> tuple[str, ...]:
    """Return paths that must never be tracked or copied into a release."""

    forbidden = []
    for raw_path in paths:
        normalized = PurePosixPath(raw_path.replace("\\", "/")).as_posix()
        if _is_forbidden_release_path(normalized):
            forbidden.append(normalized)
    return tuple(sorted(forbidden))


def _is_excluded(relative: str) -> bool:
    return any(
        relative == directory or relative.startswith(f"{directory}/")
        for directory in _EXCLUDED_DIRECTORIES
    )


def _is_forbidden_release_path(relative: str) -> bool:
    parts = PurePosixPath(relative).parts
    if not parts:
        return False
    if parts[0] in {
        ".migration",
        ".venv",
        "legacy_reference",
        "logs",
        "venv",
    }:
        return True
    cache_names = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    if any(part in cache_names for part in parts):
        return True
    if PurePosixPath(relative).name.startswith(".env") and relative != ".env.example":
        return True
    return relative.startswith("data/demo/") and relative.endswith((".db", ".sqlite"))
