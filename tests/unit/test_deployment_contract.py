"""Guards for the deployment contract that unit tests would otherwise not exercise."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _requirement_names(text: str) -> set[str]:
    names = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        names.add(re.split(r"[<>=!;\[ ]", line, maxsplit=1)[0].casefold().replace("_", "-"))
    return names


def _declared_runtime_dependencies() -> set[str]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    return _requirement_names("\n".join(project["dependencies"]))


def test_requirements_txt_exists_for_streamlit_community_cloud() -> None:
    """Streamlit Cloud reads requirements.txt; without it, it installs its own guess."""

    assert (PROJECT_ROOT / "requirements.txt").is_file()


def test_requirements_txt_covers_every_declared_runtime_dependency() -> None:
    listed = _requirement_names((PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8"))

    assert _declared_runtime_dependencies() <= listed


def test_requirements_txt_excludes_development_only_tools() -> None:
    """The deployment does not run the linter, type checker, or test runner."""

    listed = _requirement_names((PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8"))

    assert not listed & {"mypy", "pytest", "ruff"}


def test_locked_requirements_pin_the_same_runtime_versions() -> None:
    """requirements.txt and requirements.lock must not drift apart."""

    def _pins(text: str) -> dict[str, str]:
        pins = {}
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].split(";", 1)[0].strip()
            if "==" not in line:
                continue
            name, version = line.split("==", 1)
            pins[name.strip().casefold().replace("_", "-")] = version.strip()
        return pins

    deployed = _pins((PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8"))
    locked = _pins((PROJECT_ROOT / "requirements.lock").read_text(encoding="utf-8"))

    assert deployed
    for name, version in deployed.items():
        assert locked.get(name) == version, name


def test_ensure_source_path_puts_the_checkout_ahead_of_a_cached_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces the deployed ImportError: a stale installed package shadowing src/."""

    import app

    monkeypatch.setattr(sys, "path", ["/cached/site-packages", *sys.path])

    app.ensure_source_path()

    assert sys.path[0] == str(PROJECT_ROOT / "src")
    assert sys.path[1] == "/cached/site-packages"


def test_ensure_source_path_is_idempotent_and_adds_no_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    import app

    app.ensure_source_path()
    app.ensure_source_path()
    app.ensure_source_path()

    source_root = str(PROJECT_ROOT / "src")
    assert sys.path.count(source_root) == 1
    assert sys.path[0] == source_root


def test_ensure_source_path_ignores_a_layout_without_a_source_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    before = list(sys.path)
    import app

    app.ensure_source_path(tmp_path)

    assert sys.path == before
