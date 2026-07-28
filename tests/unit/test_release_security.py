from __future__ import annotations

from pathlib import Path

from safe_text_to_sql.release import (
    find_forbidden_paths,
    scan_candidate_files,
)


def test_secret_scan_never_reads_local_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "GEMINI_API_KEY=AIza" + "A" * 35,
        encoding="utf-8",
    )
    (tmp_path / "safe.py").write_text("VALUE = 'public'\n", encoding="utf-8")

    findings = scan_candidate_files(tmp_path)

    assert findings == ()


def test_secret_scan_detects_key_shape_without_returning_value(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.py"
    path.write_text("TOKEN = 'AIza" + "B" * 35 + "'\n", encoding="utf-8")

    findings = scan_candidate_files(tmp_path)

    assert len(findings) == 1
    assert findings[0].relative_path == "unsafe.py"
    assert findings[0].category == "google_api_key"
    assert "AIza" not in repr(findings[0])


def test_secret_scan_allows_documented_placeholders(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text(
        "GEMINI_API_KEY=your_gemini_api_key_here\n",
        encoding="utf-8",
    )

    assert scan_candidate_files(tmp_path) == ()


def test_forbidden_tracked_paths_are_reported() -> None:
    findings = find_forbidden_paths(
        [
            "src/app.py",
            ".env",
            ".venv/Scripts/python.exe",
            "data/demo/demo.sqlite",
            "legacy_reference/app.py",
        ]
    )

    assert findings == (
        ".env",
        ".venv/Scripts/python.exe",
        "data/demo/demo.sqlite",
        "legacy_reference/app.py",
    )
