"""Verify public release candidates without reading local dotenv files."""

from __future__ import annotations

import subprocess
from pathlib import Path

from safe_text_to_sql.release import find_forbidden_paths, scan_candidate_files


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    findings = scan_candidate_files(root)
    tracked_paths = _tracked_paths(root)
    forbidden = find_forbidden_paths(tracked_paths)
    if findings or forbidden:
        for finding in findings:
            print(f"Secret pattern: {finding.relative_path} ({finding.category})")
        for path in forbidden:
            print(f"Forbidden release path: {path}")
        raise SystemExit(1)
    print("Release verification passed: no candidate secret patterns or forbidden tracked paths.")


def _tracked_paths(root: Path) -> list[str]:
    if not (root / ".git").is_dir():
        return []
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


if __name__ == "__main__":
    main()
