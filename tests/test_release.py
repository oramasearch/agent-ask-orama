# SPDX-License-Identifier: MIT

"""The release this tree is: its version, read from the code, has notes in docs/releases/."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

from agent_ask_orama import service
from agent_ask_orama.agent import PROMPT_VERSION

ROOT = Path(__file__).resolve().parent.parent
RELEASES = ROOT / "docs" / "releases"


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def test_the_installed_package_is_the_pyproject_version() -> None:
    assert version("agent-ask-orama") == project_version()


def test_release_notes_exist_for_the_project_version() -> None:
    current = project_version()
    notes = RELEASES / f"v{current}.md"
    assert notes.is_file(), f"no release notes at {notes.relative_to(ROOT)}"
    heading = next(line for line in notes.read_text().splitlines() if line.startswith("# "))
    assert f"v{current}" in heading
    index = (RELEASES / "README.md").read_text()
    assert f"[v{current}](v{current}.md)" in index


def test_healthz_reports_the_release_and_prompt_version() -> None:
    body = service.health(service.State())
    assert body["ok"] is True
    assert body["agent"] == "agent-ask-orama"
    assert body["version"] == project_version()
    assert body["prompt_version"] == PROMPT_VERSION
